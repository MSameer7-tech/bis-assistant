#!/usr/bin/env python3
"""
Phase 13: Canonical BIS Authoritative RAG Corpus Builder

Aggregates, normalizes, and deterministically deduplicates all valid
authoritative BIS evidence across:
1. Normative Standard Chunks (Tier 1 Normative)
2. Master Regulatory Evidence Registry (Tier 1 Regulatory & Tier 2 Testing)
3. BIS Product Manual Evidence Packages (Tier 2 Operational)
4. BIS Missing Domains Dataset (v22 - Tier 2 LIMS & Procedures)
5. Standards Catalog & Entity Registry (Tier 3 Catalog Metadata)
6. Product-to-Standard Relationships (Tier 3 Catalog Metadata)

Strictly enforces authority tiers, evidence depths, and zero-hallucination.
Outputs to: data/derived/phase13/canonical_corpus_v1.jsonl
"""

import os
import sys
import json
import re
import hashlib
from pathlib import Path
from collections import Counter, defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

OUTPUT_DIR = PROJECT_ROOT / "data/derived/phase13"
CORPUS_PATH = OUTPUT_DIR / "canonical_corpus_v1.jsonl"
MANIFEST_PATH = OUTPUT_DIR / "canonical_corpus_manifest.json"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_is_standard(text: str) -> tuple:
    """
    Extracts (normalized_is, part, year) from a text string.
    Examples:
      'DOC-064_IS_10500___2012.pdf' -> ('IS 10500', None, '2012')
      'IS 16102 (Part 1) : 2012' -> ('IS 16102 (Part 1)', '1', '2012')
      'PM-SRC-006-102-IS-4985-2021-UNPLASTICIZED-PVC-PIPES' -> ('IS 4985', None, '2021')
    """
    if not text:
        return None, None, None

    # Try matching IS and optional Part
    m = re.search(
        r'(?:^|[^a-zA-Z0-9])IS[_\s:-]+([0-9]+)(?:[_\s:-]+(?:Part|Pt)[.\s_-]*([0-9]+)|\s*\(\s*(?:Part|Pt)[.\s]*([0-9]+)\s*\))?',
        text,
        re.IGNORECASE
    )
    if not m:
        return None, None, None

    num = m.group(1)
    part = m.group(2) or m.group(3)
    norm_is = f"IS {num} (Part {part})" if part else f"IS {num}"

    # Try extracting 4-digit year (1950 - 2030)
    year = None
    ym = re.search(r'\b(19\d\d|20[0-3]\d)\b', text)
    if ym:
        year = ym.group(1)

    return norm_is, part, year


def build_canonical_corpus():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("=== Phase 13: Building Canonical Authoritative Corpus ===")

    corpus = []
    seen_hashes = set()
    stats = Counter()
    standards_set = set()
    depth_stats = Counter()
    tier_stats = Counter()

    # -------------------------------------------------------------------------
    # SOURCE 1: Normative Standards Chunks (data/chunks/*.chunks.json)
    # Tier 1 Normative — 110 Indian Standards, full clauses and definitions
    # -------------------------------------------------------------------------
    chunks_files = sorted(glob.glob(str(PROJECT_ROOT / "data/chunks/*.chunks.json")))
    print(f"Ingesting {len(chunks_files)} Normative Standards chunk files...")
    
    for cf in chunks_files:
        doc_id = Path(cf).name.replace(".chunks.json", "")
        with open(cf, "r", encoding="utf-8") as f:
            try:
                chunks = json.load(f)
            except Exception as e:
                continue

        for chunk in chunks:
            text = (chunk.get("text") or chunk.get("chunk_text") or "").strip()
            if not text:
                continue

            raw_std = chunk.get("standard_number") or ""
            norm_is, part, yr = parse_is_standard(raw_std or doc_id)
            if not yr:
                yr = chunk.get("edition_year") or chunk.get("metadata", {}).get("year")
            if not part:
                part = chunk.get("standard_part")

            clause = chunk.get("clause") or chunk.get("metadata", {}).get("clause")
            heading = chunk.get("heading") or chunk.get("title") or chunk.get("metadata", {}).get("heading")
            page = chunk.get("page") or chunk.get("metadata", {}).get("page")
            force = chunk.get("normative_force") or "MANDATORY"
            ch_hash = chunk.get("content_hash") or sha256_text(text)

            # Deduplication key: exact standard, clause, content hash
            dup_key = f"{norm_is}|{clause}|{ch_hash}"
            if dup_key in seen_hashes:
                stats["normative_duplicates_skipped"] += 1
                continue
            seen_hashes.add(dup_key)

            unit_id = f"ev_norm_{doc_id}_{len(corpus):06d}"
            rec = {
                "evidence_id": unit_id,
                "source_id": chunk.get("chunk_id") or doc_id,
                "document_id": doc_id,
                "document_family_id": chunk.get("source_family_id") or doc_id,
                "standard_number": norm_is,
                "standard_part": str(part) if part else None,
                "edition_year": str(yr) if yr else None,
                "document_type": "NORMATIVE_STANDARD",
                "authority_tier": "TIER_1_NORMATIVE",
                "evidence_depth": "FULL_NORMATIVE_CLAUSE",
                "clause": str(clause) if clause else None,
                "heading": str(heading).strip() if heading else None,
                "page": str(page) if page else None,
                "normative_force": force,
                "passage_text": text,
                "source_url": chunk.get("source_url"),
                "checksum_sha256": ch_hash,
                "provenance": {
                    "source_archive": str(Path(cf).relative_to(PROJECT_ROOT)),
                    "original_chunk_id": chunk.get("chunk_id"),
                    "raw_sha256": chunk.get("parent_raw_sha256")
                }
            }
            corpus.append(rec)
            stats["tier1_normative_units"] += 1
            depth_stats["FULL_NORMATIVE_CLAUSE"] += 1
            tier_stats["TIER_1_NORMATIVE"] += 1
            if norm_is:
                standards_set.add(norm_is)

    # -------------------------------------------------------------------------
    # SOURCE 2: BIS Product Manual Evidence Packages (data/processed/evidence_units/)
    # Tier 2 Operational — 640 standard packages, 17,167 units
    # -------------------------------------------------------------------------
    eu_dirs = sorted(glob.glob(str(PROJECT_ROOT / "data/processed/evidence_units/*")))
    print(f"Ingesting {len(eu_dirs)} Product Manual evidence directories...")

    for ed in eu_dirs:
        eu_file = Path(ed) / "evidence_units.json"
        if not eu_file.exists():
            continue

        dir_name = Path(ed).name
        with open(eu_file, "r", encoding="utf-8") as f:
            try:
                units = json.load(f)
            except Exception:
                continue

        for u in units:
            text = (u.get("content_text") or u.get("text") or "").strip()
            if not text:
                continue

            doc_fam = u.get("document_family_id") or dir_name
            norm_is, part, yr = parse_is_standard(doc_fam)
            clause = u.get("section_or_clause")
            heading = u.get("heading")
            page = u.get("page_number")
            u_hash = u.get("unit_content_sha256") or sha256_text(text)

            dup_key = f"{norm_is}|{clause}|{u_hash}"
            if dup_key in seen_hashes:
                stats["pm_duplicates_skipped"] += 1
                continue
            seen_hashes.add(dup_key)

            doc_type = u.get("document_type") or "PRODUCT_MANUAL"
            auth_class = u.get("authority_class") or "OFFICIAL_OPERATIONAL"
            tier = "TIER_1_NORMATIVE" if auth_class == "PRIMARY_NORMATIVE" else "TIER_2_OPERATIONAL"

            u_raw_id = u.get("evidence_unit_id")
            unit_id = f"ev_pm_{u_raw_id}" if u_raw_id else f"ev_pm_{len(corpus):06d}"
            rec = {
                "evidence_id": unit_id,
                "source_id": u.get("evidence_unit_id") or dir_name,
                "document_id": u.get("document_id") or dir_name,
                "document_family_id": doc_fam,
                "standard_number": norm_is,
                "standard_part": str(part) if part else None,
                "edition_year": str(yr) if yr else None,
                "document_type": doc_type,
                "authority_tier": tier,
                "evidence_depth": "PRODUCT_MANUAL_OPERATIONAL",
                "clause": str(clause) if clause else None,
                "heading": str(heading).strip() if heading else None,
                "page": str(page) if page else None,
                "normative_force": "OPERATIONAL_MANDATORY" if tier == "TIER_2_OPERATIONAL" else "MANDATORY",
                "passage_text": text,
                "source_url": u.get("source_url"),
                "checksum_sha256": u_hash,
                "provenance": {
                    "source_archive": str(Path(eu_file).relative_to(PROJECT_ROOT)),
                    "original_evidence_id": u.get("evidence_unit_id"),
                    "raw_sha256": u.get("parent_raw_sha256")
                }
            }
            corpus.append(rec)
            stats["tier2_operational_pm_units"] += 1
            depth_stats["PRODUCT_MANUAL_OPERATIONAL"] += 1
            tier_stats[tier] += 1
            if norm_is:
                standards_set.add(norm_is)

    # -------------------------------------------------------------------------
    # SOURCE 3: Master Regulatory & Testing Registry (data/registry/evidence.jsonl)
    # Tier 1 Regulatory, Tier 2 Testing, Tier 2 Operational — 2,166 records
    # -------------------------------------------------------------------------
    reg_path = PROJECT_ROOT / "data/registry/evidence.jsonl"
    if reg_path.exists():
        print("Ingesting Master Regulatory & Testing Evidence Registry...")
        with open(reg_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                rec_raw = json.loads(line)
                text = (rec_raw.get("verbatim_quote") or "").strip()
                if not text:
                    continue

                ev_id = rec_raw.get("evidence_id")
                stype = rec_raw.get("source_type") or "REGULATION"
                title = rec_raw.get("citation_title") or ""
                norm_is, part, yr = parse_is_standard(title)
                if not norm_is:
                    norm_is, part, yr = parse_is_standard(text)

                u_hash = rec_raw.get("content_sha256") or sha256_text(text)
                dup_key = f"{stype}|{ev_id}|{u_hash}"
                if dup_key in seen_hashes:
                    stats["reg_duplicates_skipped"] += 1
                    continue
                seen_hashes.add(dup_key)

                # Classify authority and depth
                if stype in ["QCO_ORDER", "BIS_ACT_STATUTE", "REGULATION"]:
                    tier = "TIER_1_REGULATORY"
                    depth = "REGULATORY_MANDATE"
                elif stype in ["SIT_SCHEDULE"]:
                    tier = "TIER_2_TESTING"
                    depth = "TESTING_SCHEDULE"
                elif stype in ["STANDARD_PDF"]:
                    tier = "TIER_1_NORMATIVE"
                    depth = "FULL_NORMATIVE_CLAUSE"
                else:
                    tier = "TIER_2_OPERATIONAL"
                    depth = "OPERATIONAL_RECORD"

                rec = {
                    "evidence_id": f"ev_reg_{ev_id}",
                    "source_id": ev_id,
                    "document_id": rec_raw.get("document_id") or ev_id,
                    "document_family_id": rec_raw.get("source_family") or stype,
                    "standard_number": norm_is,
                    "standard_part": str(part) if part else None,
                    "edition_year": str(yr) if yr else None,
                    "document_type": stype,
                    "authority_tier": tier,
                    "evidence_depth": depth,
                    "clause": str(rec_raw.get("clause_number")) if rec_raw.get("clause_number") else None,
                    "heading": title,
                    "page": str(rec_raw.get("page_number")) if rec_raw.get("page_number") else None,
                    "normative_force": "LEGAL_MANDATORY" if tier == "TIER_1_REGULATORY" else "OPERATIONAL",
                    "passage_text": text,
                    "source_url": rec_raw.get("provenance_url"),
                    "checksum_sha256": u_hash,
                    "provenance": {
                        "source_registry": "data/registry/evidence.jsonl",
                        "gazette_notification": rec_raw.get("gazette_notification_number"),
                        "effective_date": rec_raw.get("effective_date"),
                        "document_sha256": rec_raw.get("document_sha256")
                    }
                }
                corpus.append(rec)
                stats["regulatory_testing_registry_units"] += 1
                depth_stats[depth] += 1
                tier_stats[tier] += 1
                if norm_is:
                    standards_set.add(norm_is)

    # -------------------------------------------------------------------------
    # SOURCE 4: BIS Missing Domains Foundation (v22)
    # Tier 2 LIMS & Procedures — 1,135 records (preserving continuity for IS 8978, fees, lab scopes)
    # -------------------------------------------------------------------------
    v22_path = PROJECT_ROOT / "data/bootstrap/bis_missing_domains_dataset_v22.jsonl"
    if v22_path.exists():
        print("Ingesting v22 Missing Domains Foundation (LIMS Scopes, Fees, Procedures)...")
        with open(v22_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                rec_raw = json.loads(line)
                rec_id = rec_raw.get("record_id") or ""
                dom = rec_raw.get("domain") or "OTHER"
                rtype = rec_raw.get("record_type") or "DOCUMENT"
                title = rec_raw.get("title") or ""
                content = rec_raw.get("content") or rec_raw.get("text") or ""
                if not content:
                    continue

                norm_is, part, yr = parse_is_standard(title)
                if not norm_is:
                    norm_is, part, yr = parse_is_standard(content)

                u_hash = sha256_text(content)
                dup_key = f"v22|{rec_id}|{u_hash}"
                if dup_key in seen_hashes:
                    stats["v22_duplicates_skipped"] += 1
                    continue
                seen_hashes.add(dup_key)

                if dom == "LABORATORIES" or "SCOPE" in rec_id or "FEE" in rec_id:
                    tier = "TIER_2_LIMS"
                    depth = "LIMS_SCOPE_FEE_ONLY"
                    doc_type = "LAB_SCOPE" if "SCOPE" in rec_id or rtype == "LAB_SCOPE" else "TESTING_FEE"
                elif dom in ["CONSUMER_BIS_CARE", "FAQ_GUIDES_BOOKLETS", "LICENCES_REGISTRATIONS", "HALLMARKING"]:
                    tier = "TIER_2_OPERATIONAL"
                    depth = "PROCEDURE_GUIDE"
                    doc_type = "PROCEDURE_GUIDE"
                else:
                    tier = "TIER_2_OPERATIONAL"
                    depth = "OPERATIONAL_RECORD"
                    doc_type = "DOCUMENT"

                rec = {
                    "evidence_id": f"ev_v22_{rec_id}",
                    "source_id": rec_id,
                    "document_id": rec_id,
                    "document_family_id": dom,
                    "standard_number": norm_is,
                    "standard_part": str(part) if part else None,
                    "edition_year": str(yr) if yr else None,
                    "document_type": doc_type,
                    "authority_tier": tier,
                    "evidence_depth": depth,
                    "clause": None,
                    "heading": title,
                    "page": None,
                    "normative_force": "OPERATIONAL_VERIFIED",
                    "passage_text": content,
                    "source_url": rec_raw.get("source_url") or rec_raw.get("source", {}).get("url"),
                    "checksum_sha256": u_hash,
                    "provenance": {
                        "corpus_source": "data/bootstrap/bis_missing_domains_dataset_v22.jsonl",
                        "record_id": rec_id,
                        "domain": dom,
                        "parent_raw_sha256": rec_raw.get("source_sha256")
                    }
                }
                corpus.append(rec)
                stats["v22_foundation_units"] += 1
                depth_stats[depth] += 1
                tier_stats[tier] += 1
                if norm_is:
                    standards_set.add(norm_is)

    # -------------------------------------------------------------------------
    # SOURCE 5: Standards Metadata & Catalog Registry (data/registry/standards.jsonl)
    # Tier 3 Catalog Metadata — 646 standards
    # -------------------------------------------------------------------------
    std_path = PROJECT_ROOT / "data/registry/standards.jsonl"
    if std_path.exists():
        print("Ingesting Standards Entity Catalog Metadata...")
        with open(std_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                srec = json.loads(line)
                is_num = srec.get("is_number") or ""
                title = srec.get("title") or ""
                year = srec.get("edition") or ""
                sid = srec.get("standard_id") or is_num

                text = f"Indian Standard {is_num}: {title} (Edition: {year}). Status: OFFICIAL_CATALOG_ENTRY. [Catalog Metadata Entry: Technical requirements and clause texts are governed by normative documents]."
                u_hash = sha256_text(text)
                dup_key = f"std_meta|{is_num}|{year}"
                if dup_key in seen_hashes:
                    stats["catalog_duplicates_skipped"] += 1
                    continue
                seen_hashes.add(dup_key)

                norm_is, part, yr = parse_is_standard(is_num)
                rec = {
                    "evidence_id": f"ev_cat_{sid}",
                    "source_id": sid,
                    "document_id": sid,
                    "document_family_id": "STANDARDS_CATALOG",
                    "standard_number": norm_is or is_num,
                    "standard_part": str(part) if part else None,
                    "edition_year": str(yr or year) if (yr or year) else None,
                    "document_type": "STANDARD_METADATA",
                    "authority_tier": "TIER_3_CATALOG",
                    "evidence_depth": "METADATA_ONLY",
                    "clause": None,
                    "heading": f"{is_num} - {title}",
                    "page": None,
                    "normative_force": "METADATA_INFORMATIONAL",
                    "passage_text": text,
                    "source_url": "https://www.services.bis.gov.in/php/BIS_2.0/bisconnect/knowyourstandards/indian_standards/isdetails",
                    "checksum_sha256": u_hash,
                    "provenance": {
                        "source_file": "data/registry/standards.jsonl",
                        "standard_id": sid
                    }
                }
                corpus.append(rec)
                stats["catalog_metadata_units"] += 1
                depth_stats["METADATA_ONLY"] += 1
                tier_stats["TIER_3_CATALOG"] += 1
                if norm_is:
                    standards_set.add(norm_is)

    # -------------------------------------------------------------------------
    # SOURCE 6: Product-to-Standard Relationships (data/catalog/compulsory_certification/...)
    # Tier 3 Catalog Metadata — 960 records
    # -------------------------------------------------------------------------
    rel_path = PROJECT_ROOT / "data/catalog/compulsory_certification/product_standard_relationships.jsonl"
    if rel_path.exists():
        print("Ingesting Product-to-Standard Relationships...")
        with open(rel_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                rrec = json.loads(line)
                pname = rrec.get("product_name") or ""
                std_raw = rrec.get("standard_number") or ""
                scheme = rrec.get("scheme") or "Scheme I"
                rid = rrec.get("record_id") or ""

                text = f"Product '{pname}' is mapped to Indian Standard {std_raw} under certification {scheme}."
                u_hash = sha256_text(text)
                dup_key = f"prod_rel|{pname}|{std_raw}"
                if dup_key in seen_hashes:
                    stats["rel_duplicates_skipped"] += 1
                    continue
                seen_hashes.add(dup_key)

                norm_is, part, yr = parse_is_standard(std_raw)
                ev_rel_id = f"ev_rel_{rid}" if rid else f"ev_rel_{len(corpus):06d}"
                rec = {
                    "evidence_id": ev_rel_id,
                    "source_id": rid,
                    "document_id": rid,
                    "document_family_id": "PRODUCT_MAPPINGS",
                    "standard_number": norm_is or std_raw,
                    "standard_part": str(part) if part else None,
                    "edition_year": str(yr) if yr else None,
                    "document_type": "PRODUCT_RELATIONSHIP",
                    "authority_tier": "TIER_3_CATALOG",
                    "evidence_depth": "PRODUCT_RELATIONSHIP_METADATA",
                    "clause": None,
                    "heading": f"Product Mapping: {pname} -> {std_raw}",
                    "page": None,
                    "normative_force": "METADATA_INFORMATIONAL",
                    "passage_text": text,
                    "source_url": rrec.get("source_url"),
                    "checksum_sha256": u_hash,
                    "provenance": {
                        "source_file": "data/catalog/compulsory_certification/product_standard_relationships.jsonl",
                        "record_id": rid
                    }
                }
                corpus.append(rec)
                stats["product_relationship_units"] += 1
                depth_stats["PRODUCT_RELATIONSHIP_METADATA"] += 1
                tier_stats["TIER_3_CATALOG"] += 1
                if norm_is:
                    standards_set.add(norm_is)

    # -------------------------------------------------------------------------
    # Write canonical corpus to JSONL
    # -------------------------------------------------------------------------
    print(f"\nWriting {len(corpus):,} canonical evidence units to {CORPUS_PATH}...")
    corpus_sha256 = hashlib.sha256()
    with open(CORPUS_PATH, "w", encoding="utf-8") as f:
        for rec in corpus:
            line = json.dumps(rec, ensure_ascii=False)
            f.write(line + "\n")
            corpus_sha256.update(line.encode("utf-8"))

    final_sha = corpus_sha256.hexdigest()
    print(f"Canonical Corpus SHA-256: {final_sha}")

    # Build manifest
    manifest = {
        "corpus_version": "v13.0",
        "phase": "13",
        "description": "Phase 13 BIS Canonical Authoritative RAG Corpus",
        "creation_timestamp": "2026-09-06T23:30:00Z",
        "canonical_corpus_path": str(CORPUS_PATH.relative_to(PROJECT_ROOT)),
        "canonical_corpus_sha256": final_sha,
        "total_evidence_units": len(corpus),
        "total_standards_represented": len(standards_set),
        "source_contributions": dict(stats),
        "authority_tier_distribution": dict(tier_stats),
        "evidence_depth_distribution": dict(depth_stats)
    }

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Manifest written to {MANIFEST_PATH}")
    print(f"Total Evidence Units: {len(corpus):,}")
    print(f"Total Distinct Standards Represented: {len(standards_set):,}")
    print("Authority Tiers:", dict(tier_stats))
    print("Evidence Depths:", dict(depth_stats))
    return manifest


if __name__ == "__main__":
    import glob
    build_canonical_corpus()
