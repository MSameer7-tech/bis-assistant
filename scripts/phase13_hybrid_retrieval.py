#!/usr/bin/env python3
"""
Phase 13: Full BIS Authoritative Hybrid Retrieval Engine

Combines:
1. Structured exact identifier retrieval (IS numbers, clauses, lab codes)
2. BM25Okapi lexical retrieval over 20,745 units
3. Dense semantic vector retrieval (all-MiniLM-L6-v2)
4. Reciprocal Rank Fusion (RRF) with configurable rrf_k and boost_factor
5. Authority-Tier weighting (Tier 1 Normative > Tier 1 Regulatory > Tier 2 > Tier 3 Catalog)
6. Evidence-depth tracking and strict honest abstention boundaries
"""

import os
import sys
import re
import json
import pickle
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np

# Force offline mode for sentence-transformers / huggingface
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sentence_transformers import SentenceTransformer
from scripts.phase13_bm25 import BM25Okapi, tokenize_bm25

INDEX_DIR = PROJECT_ROOT / "data/derived/phase13/retrieval_index_full_v1"
RU_PATH = INDEX_DIR / "retrieval_units.jsonl"
BM25_PATH = INDEX_DIR / "bm25_index.pkl"
VECTORS_PATH = INDEX_DIR / "vector/vectors.npy"
VECTOR_META_PATH = INDEX_DIR / "vector/vector_metadata.jsonl"
MANIFEST_PATH = INDEX_DIR / "retrieval_index_manifest.json"
MODEL_PATH = PROJECT_ROOT / "data/models/embeddings/all-MiniLM-L6-v2"
COVERAGE_DOC = PROJECT_ROOT / "docs/phase13/phase13_standard_coverage.md"

# ── Regex Patterns ──
IS_PATTERN = re.compile(r'\b(?:IS|is)\s*(\d+(?:[-/]\d+)*(?:\s*(?:Part|Pt\.?)\s*\d+)?)\b', re.IGNORECASE)
CLAUSE_PATTERN = re.compile(r'\b(?:clause|cl\.?|sec\.?|section)\s*([0-9]+(?:\.[0-9]+)*)\b', re.IGNORECASE)
LAB_CODE_PATTERN = re.compile(r'\b(?:lab(?:oratory)?)\s*(\d{2,6})\b', re.IGNORECASE)

# ── Authority Tier Weights ──
AUTHORITY_TIER_WEIGHTS = {
    "TIER_1_NORMATIVE": 1.25,
    "TIER_1_REGULATORY": 1.15,
    "TIER_2_TESTING": 1.05,
    "TIER_2_OPERATIONAL": 1.00,
    "TIER_2_LIMS": 0.85,
    "TIER_3_CATALOG": 0.60
}

DEPTH_PRIORITY = {
    "FULL_NORMATIVE_CLAUSE": 10,
    "REGULATORY_MANDATE": 9,
    "TESTING_SCHEDULE": 8,
    "PRODUCT_MANUAL_OPERATIONAL": 7,
    "OPERATIONAL_RECORD": 6,
    "PROCEDURE_GUIDE": 5,
    "LIMS_SCOPE_FEE_ONLY": 4,
    "PRODUCT_RELATIONSHIP_METADATA": 2,
    "METADATA_ONLY": 1
}


def canonical_std(raw: Any) -> str:
    """Canonicalizes standard string, e.g. 'IS 16102 (Part 1)' -> 'IS 16102 Part 1'."""
    if not raw:
        return ""
    c = str(raw).strip()
    if c.upper().startswith("IS"):
        c = c[2:].strip()
    c = re.sub(r"[():]", " ", c)
    c = re.sub(r"\s+", " ", c).strip()
    c = re.sub(r"\bpart\s*(\d+)\b", r"Part \1", c, flags=re.IGNORECASE)
    c = re.sub(r"\bpt\.?\s*(\d+)\b", r"Part \1", c, flags=re.IGNORECASE)
    return f"IS {c}".strip()


def base_std(canon: str) -> str:
    """Extracts base standard, e.g. 'IS 16102 Part 1' -> 'IS 16102'."""
    m = re.match(r"(IS\s*\d+)", canon)
    return m.group(1) if m else canon


def extract_clause_str(clause_val: Any) -> Optional[str]:
    """Extracts normalized clause string from dict or string representation."""
    if not clause_val:
        return None
    if isinstance(clause_val, dict):
        return str(clause_val.get("number", "")).strip() or None
    c_str = str(clause_val).strip()
    if c_str.lower().startswith("table"):
        return c_str
    m = re.search(r"\b(?:clause|cl\.?|sec\.?|section)\s*([0-9]+(?:\.[0-9]+)*)\b", c_str, re.IGNORECASE)
    if m:
        return m.group(1)
    if re.match(r"^[0-9]+(?:\.[0-9]+)*$", c_str):
        return c_str
    return c_str


def extract_query_identifiers(query: str) -> Dict[str, Any]:
    """Extracts structured entities, standard numbers, clauses, and query intent."""
    is_numbers = []
    for m in IS_PATTERN.finditer(query):
        is_numbers.append(canonical_std(m.group(0)))

    clauses = []
    for m in CLAUSE_PATTERN.finditer(query):
        clauses.append(m.group(1))

    lab_codes = []
    for m in LAB_CODE_PATTERN.finditer(query):
        lab_codes.append(m.group(1))

    q_lower = query.lower()
    intent = "GENERAL"
    if "clause" in q_lower or "section" in q_lower or clauses:
        intent = "CLAUSE_LOOKUP"
    elif "qco" in q_lower or "order" in q_lower or "gazette" in q_lower or "mandatory" in q_lower:
        intent = "QCO"
    elif "lab" in q_lower or "testing facility" in q_lower or "laboratory" in q_lower:
        intent = "LABORATORY"
    elif "fee" in q_lower or "cost" in q_lower or "charges" in q_lower:
        intent = "TESTING_FEES"
    elif any(w in q_lower for w in ["requirement", "requirements", "require", "test", "method", "sampling", "grouping"]):
        intent = "REQUIREMENTS"
    elif "act" in q_lower or "statutory" in q_lower:
        intent = "STATUTE"
    elif is_numbers:
        intent = "STANDARD_LOOKUP"

    return {
        "is_numbers": list(dict.fromkeys(is_numbers)),
        "clauses": list(dict.fromkeys(clauses)),
        "lab_codes": list(dict.fromkeys(lab_codes)),
        "intent": intent
    }


class Phase13RetrievalData:
    """In-memory cache and indexes for Phase 13 Authoritative Retrieval."""

    def __init__(self):
        start = time.time()
        print(f"[Phase13RetrievalData] Loading units from {RU_PATH}...")
        self.units = []
        self.unit_by_id = {}
        self.is_number_index = {}        # 'IS 10500' -> [unit_idx]
        self.clause_index = {}           # ('IS 10500', '4.1') -> [unit_idx]
        self.tier_index = {}             # tier -> [unit_idx]
        self.depth_by_standard = {}      # standard -> max evidence depth

        with open(RU_PATH, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                if not line.strip():
                    continue
                u = json.loads(line)
                u["_idx"] = idx
                self.units.append(u)
                self.unit_by_id[u["retrieval_unit_id"]] = u

                std = u.get("standard_number")
                if std:
                    cs = canonical_std(std)
                    bs = base_std(cs)

                    for s_key in set([cs, bs]):
                        if s_key not in self.is_number_index:
                            self.is_number_index[s_key] = []
                        self.is_number_index[s_key].append(idx)

                        depth = u.get("evidence_depth", "METADATA_ONLY")
                        curr_depth = self.depth_by_standard.get(s_key)
                        if not curr_depth or DEPTH_PRIORITY.get(depth, 0) > DEPTH_PRIORITY.get(curr_depth, 0):
                            self.depth_by_standard[s_key] = depth

                raw_clause = u.get("clause")
                c_str = extract_clause_str(raw_clause)
                if std and c_str:
                    cs = canonical_std(std)
                    bs = base_std(cs)
                    for s_key in set([cs, bs]):
                        ckey = (s_key, c_str)
                        if ckey not in self.clause_index:
                            self.clause_index[ckey] = []
                        self.clause_index[ckey].append(idx)

                tier = u.get("authority_tier", "TIER_3_CATALOG")
                if tier not in self.tier_index:
                    self.tier_index[tier] = []
                self.tier_index[tier].append(idx)

        print(f"[Phase13RetrievalData] Loaded {len(self.units):,} units in {time.time() - start:.2f}s.")

        print(f"[Phase13RetrievalData] Loading BM25 index from {BM25_PATH}...")
        with open(BM25_PATH, "rb") as f:
            self.bm25 = pickle.load(f)

        print(f"[Phase13RetrievalData] Loading vector matrix from {VECTORS_PATH}...")
        self.vectors = np.load(str(VECTORS_PATH))

        print(f"[Phase13RetrievalData] Loading vector metadata from {VECTOR_META_PATH}...")
        self.vector_metadata = []
        with open(VECTOR_META_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    self.vector_metadata.append(json.loads(line))

        print(f"[Phase13RetrievalData] Ready. Standards indexed: {len(self.is_number_index):,}")


class Phase13HybridRetrievalEngine:
    """
    Phase 13 Hybrid Retrieval Engine executing:
    Structured + BM25 + Dense Semantic -> RRF -> Boost -> Authority Weighting
    """

    def __init__(self, data: Phase13RetrievalData, model: Optional[SentenceTransformer] = None):
        self.data = data
        if model is None:
            print(f"[Phase13HybridRetrievalEngine] Initializing SentenceTransformer from {MODEL_PATH}...")
            self.model = SentenceTransformer(str(MODEL_PATH), device="cpu")
        else:
            self.model = model

    def search(
        self,
        query: str,
        top_k: int = 10,
        rrf_k: int = 20,
        boost_factor: float = 2.5,
        channel_weights: Optional[Dict[str, float]] = None,
        filter_standard: Optional[str] = None,
        filter_tier: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes hybrid retrieval for query.
        Returns detailed results including evidence depth, authority tiers, and scoring traces.
        """
        start_time = time.time()
        norm_query = " ".join(query.strip().split())
        weights = channel_weights or {
            "structured": 1.0,
            "bm25": 1.0,
            "vector": 1.0
        }

        if not norm_query:
            return {
                "query": query,
                "normalized_query": "",
                "extracted_identifiers": {
                    "is_numbers": [],
                    "clauses": [],
                    "lab_codes": [],
                    "intent": "UNKNOWN"
                },
                "total_candidates_found": 0,
                "evidence_status": "INSUFFICIENT",
                "standard_coverage": {},
                "results": [],
                "duration_ms": round((time.time() - start_time) * 1000, 2),
                "provenance": {
                    "engine": "Phase 13 Authoritative Hybrid Retrieval Engine",
                    "index_version": "v13.0",
                    "total_units_in_index": len(self.data.units),
                    "parameters": {
                        "top_k": top_k,
                        "rrf_k": rrf_k,
                        "boost_factor": boost_factor,
                        "channel_weights": weights
                    }
                }
            }

        extracted = extract_query_identifiers(norm_query)

        # Merge explicit filter with extracted standard if provided
        target_standards = extracted["is_numbers"]
        if filter_standard:
            target_standards = [canonical_std(filter_standard)]

        # Expand target standards with base standards
        expanded_target_standards = set()
        for s in target_standards:
            expanded_target_standards.add(s)
            expanded_target_standards.add(base_std(s))

        # Check standard presence in corpus
        target_stds_in_corpus = any(
            (s in self.data.is_number_index) for s in expanded_target_standards
        )

        if target_standards and not target_stds_in_corpus:
            # Explicit target standard is completely unknown in corpus
            standard_coverage_info = {}
            for std in target_standards:
                standard_coverage_info[std] = {
                    "max_evidence_depth": "NOT_IN_CORPUS",
                    "has_normative_clauses": False,
                    "has_operational_manuals": False,
                    "is_lims_only": False,
                    "is_metadata_only": False,
                    "abstention_required_for_clauses": True,
                    "abstention_reason": f"Standard {std} is not present in the authoritative BIS corpus."
                }

            return {
                "query": query,
                "normalized_query": norm_query,
                "extracted_identifiers": extracted,
                "total_candidates_found": 0,
                "evidence_status": "INSUFFICIENT",
                "standard_coverage": standard_coverage_info,
                "results": [],
                "duration_ms": round((time.time() - start_time) * 1000, 2),
                "provenance": {
                    "engine": "Phase 13 Authoritative Hybrid Retrieval Engine",
                    "index_version": "v13.0",
                    "total_units_in_index": len(self.data.units),
                    "parameters": {
                        "top_k": top_k,
                        "rrf_k": rrf_k,
                        "boost_factor": boost_factor,
                        "channel_weights": weights
                    }
                }
            }

        # ---------------------------------------------------------------------
        # Channel 1: Structured Identifier Search
        # ---------------------------------------------------------------------
        structured_results = []
        structured_unit_scores = {}
        for std in expanded_target_standards:
            unit_indices = self.data.is_number_index.get(std, [])
            for u_idx in unit_indices:
                u = self.data.units[u_idx]
                score = 1.0
                # Clause match bonus in structured channel
                u_clause = extract_clause_str(u.get("clause"))
                if extracted["clauses"] and u_clause and u_clause in extracted["clauses"]:
                    score += 2.5
                rid = u["retrieval_unit_id"]
                structured_unit_scores[rid] = max(structured_unit_scores.get(rid, 0.0), score)

        # Sort structured candidates
        ranked_structured = sorted(structured_unit_scores.items(), key=lambda x: -x[1])[:50]
        for rank, (rid, sc) in enumerate(ranked_structured, 1):
            structured_results.append({"retrieval_unit_id": rid, "rank": rank, "score": sc})

        # ---------------------------------------------------------------------
        # Channel 2: BM25 Lexical Search
        # ---------------------------------------------------------------------
        tokens = tokenize_bm25(norm_query)
        bm25_scores = self.data.bm25.get_scores(tokens)
        top_bm25_indices = np.argsort(bm25_scores)[::-1][:50]
        bm25_results = []
        for rank, idx in enumerate(top_bm25_indices, 1):
            idx = int(idx)
            if bm25_scores[idx] <= 0:
                break
            rid = self.data.units[idx]["retrieval_unit_id"]
            bm25_results.append({"retrieval_unit_id": rid, "rank": rank, "score": float(bm25_scores[idx])})

        # ---------------------------------------------------------------------
        # Channel 3: Vector Semantic Search
        # ---------------------------------------------------------------------
        q_emb = self.model.encode([norm_query], normalize_embeddings=True, convert_to_numpy=True).astype(np.float32)
        vec_scores = (self.data.vectors @ q_emb.T).flatten()
        top_vec_indices = np.argsort(vec_scores)[::-1][:50]
        vector_results = []
        for rank, idx in enumerate(top_vec_indices, 1):
            idx = int(idx)
            rid = self.data.vector_metadata[idx]["retrieval_unit_id"]
            vector_results.append({"retrieval_unit_id": rid, "rank": rank, "score": float(vec_scores[idx])})

        # ---------------------------------------------------------------------
        # Candidate Union & Reciprocal Rank Fusion
        # ---------------------------------------------------------------------
        candidates = {}
        for ch_name, ch_res in [("structured", structured_results), ("bm25", bm25_results), ("vector", vector_results)]:
            for item in ch_res:
                rid = item["retrieval_unit_id"]
                if rid not in candidates:
                    candidates[rid] = {
                        "retrieval_unit_id": rid,
                        "channel_ranks": {},
                        "channel_scores": {},
                        "exact_identifier_match": False
                    }
                candidates[rid]["channel_ranks"][ch_name] = item["rank"]
                candidates[rid]["channel_scores"][ch_name] = item["score"]

        # ---------------------------------------------------------------------
        # RRF Scoring + Exact Match Boost + Authority Weighting
        # ---------------------------------------------------------------------
        scored_candidates = []
        for rid, cand in candidates.items():
            unit = self.data.unit_by_id[rid]

            # Filter check
            if filter_tier and unit.get("authority_tier") != filter_tier:
                continue

            # Standard match check
            unit_std = canonical_std(unit.get("standard_number")) if unit.get("standard_number") else ""
            unit_base = base_std(unit_std)
            is_exact_std = False
            if expanded_target_standards and (unit_std in expanded_target_standards or unit_base in expanded_target_standards):
                is_exact_std = True
                cand["exact_identifier_match"] = True

            # If user explicitly specified target standard(s), isolate retrieval to those standards
            if expanded_target_standards and not is_exact_std:
                continue

            # Calculate base RRF
            rrf_score = 0.0
            for ch_name, rk in cand["channel_ranks"].items():
                w = weights.get(ch_name, 1.0)
                rrf_score += w * (1.0 / (rrf_k + rk))

            # Apply Exact Match Boost
            if is_exact_std:
                rrf_score *= boost_factor

            # Additional boost if exact clause matches
            u_clause = extract_clause_str(unit.get("clause"))
            if extracted["clauses"] and u_clause and u_clause in extracted["clauses"]:
                rrf_score *= 1.5

            # Apply Authority Tier Weight
            tier = unit.get("authority_tier", "TIER_3_CATALOG")
            tier_weight = AUTHORITY_TIER_WEIGHTS.get(tier, 0.60)
            final_score = rrf_score * tier_weight

            scored_candidates.append({
                "retrieval_unit_id": rid,
                "score": final_score,
                "base_rrf": rrf_score,
                "authority_tier": tier,
                "authority_weight": tier_weight,
                "evidence_depth": unit.get("evidence_depth"),
                "document_type": unit.get("document_type"),
                "standard_number": unit.get("standard_number"),
                "standard_part": unit.get("standard_part"),
                "edition_year": unit.get("edition_year"),
                "clause": u_clause,
                "raw_clause": unit.get("clause"),
                "heading": unit.get("heading"),
                "page": unit.get("page"),
                "text": unit.get("text"),
                "channel_ranks": cand["channel_ranks"],
                "exact_identifier_match": cand["exact_identifier_match"]
            })

        # Sort descending by score, deterministic secondary sort on ID
        scored_candidates.sort(key=lambda x: (-x["score"], x["retrieval_unit_id"]))
        top_results = scored_candidates[:top_k]

        # ---------------------------------------------------------------------
        # Assess Evidence Coverage & Depth Status
        # ---------------------------------------------------------------------
        standard_coverage_info = {}
        for std in target_standards:
            max_depth = self.data.depth_by_standard.get(std) or self.data.depth_by_standard.get(base_std(std)) or "NOT_IN_CORPUS"
            has_norm = max_depth in ("FULL_NORMATIVE_CLAUSE", "REGULATORY_MANDATE")
            is_op = max_depth in ("PRODUCT_MANUAL_OPERATIONAL", "OPERATIONAL_RECORD", "TESTING_SCHEDULE", "PROCEDURE_GUIDE")
            is_lims = max_depth == "LIMS_SCOPE_FEE_ONLY"
            is_meta = max_depth in ("METADATA_ONLY", "PRODUCT_RELATIONSHIP_METADATA")

            standard_coverage_info[std] = {
                "max_evidence_depth": max_depth,
                "has_normative_clauses": has_norm,
                "has_operational_manuals": is_op,
                "is_lims_only": is_lims,
                "is_metadata_only": is_meta,
                "abstention_required_for_clauses": not has_norm,
                "abstention_reason": (
                    "Only laboratory scope & fee evidence is available in official BIS records. Normative clause text is not in corpus."
                    if is_lims else (
                        "Only catalog metadata (title/year/status) is available in official BIS records. Normative text is not in corpus."
                        if is_meta else None
                    )
                )
            }

        # Global evidence status
        if not top_results:
            evidence_status = "INSUFFICIENT"
        else:
            # Check if any target standard is restricted to LIMS or metadata only
            is_any_target_lims_or_meta = False
            if target_standards:
                for std in target_standards:
                    cov = standard_coverage_info.get(std, {})
                    if (
                        cov.get("is_lims_only")
                        or cov.get("is_metadata_only")
                        or cov.get("max_evidence_depth") in ("LIMS_SCOPE_FEE_ONLY", "METADATA_ONLY", "PRODUCT_RELATIONSHIP_METADATA")
                    ):
                        is_any_target_lims_or_meta = True
                        break

            if is_any_target_lims_or_meta:
                evidence_status = "PARTIAL"
            else:
                has_normative = any(r["authority_tier"] in ("TIER_1_NORMATIVE", "TIER_1_REGULATORY") for r in top_results)
                has_operational = any(r["authority_tier"] in ("TIER_2_OPERATIONAL", "TIER_2_TESTING") for r in top_results)
                if has_normative or has_operational:
                    evidence_status = "SUFFICIENT"
                else:
                    evidence_status = "PARTIAL"

        return {
            "query": query,
            "normalized_query": norm_query,
            "extracted_identifiers": extracted,
            "total_candidates_found": len(candidates),
            "evidence_status": evidence_status,
            "standard_coverage": standard_coverage_info,
            "results": top_results,
            "duration_ms": round((time.time() - start_time) * 1000, 2),
            "provenance": {
                "engine": "Phase 13 Authoritative Hybrid Retrieval Engine",
                "index_version": "v13.0",
                "total_units_in_index": len(self.data.units),
                "parameters": {
                    "top_k": top_k,
                    "rrf_k": rrf_k,
                    "boost_factor": boost_factor,
                    "channel_weights": weights
                }
            }
        }


if __name__ == "__main__":
    data = Phase13RetrievalData()
    engine = Phase13HybridRetrievalEngine(data)

    test_queries = [
        "What is the required limit for total dissolved solids in IS 10500 drinking water?",
        "What are the operational grouping guidelines for UPVC pipes under IS 4985?",
        "What are the normative safety requirements for LED lamps in IS 16102 Part 1?",
        "What clauses specify temperature cut-off testing for water heaters under IS 8978?",
        "What is IS 1234?"
    ]

    print("\n" + "="*80)
    print("RUNNING DIAGNOSTIC QUERIES OVER PHASE 13 FULL INDEX")
    print("="*80)

    for q in test_queries:
        res = engine.search(q, top_k=3)
        print(f"\nQUERY: {q}")
        print(f"IDENTIFIERS: {res['extracted_identifiers']}")
        print(f"COVERAGE: {json.dumps(res['standard_coverage'], indent=2)}")
        print(f"EVIDENCE STATUS: {res['evidence_status']} (in {res['duration_ms']} ms)")
        for idx, r in enumerate(res["results"], 1):
            print(f"  [{idx}] Score: {r['score']:.4f} | Tier: {r['authority_tier']} | Depth: {r['evidence_depth']} | Std: {r['standard_number']} | Clause: {r['clause']}")
            print(f"      Heading: {r['heading']}")
            snippet = r['text'][:140].replace('\n', ' ')
            print(f"      Snippet: {snippet}...")
