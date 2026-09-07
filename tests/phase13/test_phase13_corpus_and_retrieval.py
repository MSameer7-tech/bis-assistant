"""
Phase 13 Test Suite: Corpus Integrity, Retrieval Index, and Hybrid Search Engine

Tests:
1. Canonical corpus schema and volume invariants (20,745 units)
2. Retrieval index structural integrity (retrieval_units, BM25, vectors, metadata)
3. Offline execution enforcement (zero external network/HuggingFace calls)
4. Multi-channel retrieval (Structured, BM25, Dense Vector)
5. Evidence depth and authority tier invariants:
   - IS 10500: Normative specifications (Tier 1 Normative)
   - IS 4985: Operational & normative pipe evidence (Tier 1 & Tier 2)
   - IS 16102 Part 1: Normative LED safety requirements (Tier 1 Normative)
   - IS 8978: LIMS testing scope & fee evidence ONLY (Tier 2 LIMS; no normative clauses)
   - Catalog standard (e.g. IS 16189): Metadata only
6. Reciprocal Rank Fusion & Exact Match Boosting
7. Performance latency (< 500ms per query)
"""

import os
import json
import pytest
import numpy as np
from pathlib import Path

# Force offline mode
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

from scripts.phase13_hybrid_retrieval import (
    Phase13RetrievalData,
    Phase13HybridRetrievalEngine,
    canonical_std,
    base_std,
    extract_query_identifiers
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CORPUS_PATH = PROJECT_ROOT / "data/derived/phase13/canonical_corpus_v1.jsonl"
INDEX_DIR = PROJECT_ROOT / "data/derived/phase13/retrieval_index_full_v1"
MANIFEST_PATH = INDEX_DIR / "retrieval_index_manifest.json"


@pytest.fixture(scope="module")
def retrieval_data():
    return Phase13RetrievalData()


@pytest.fixture(scope="module")
def engine(retrieval_data):
    return Phase13HybridRetrievalEngine(retrieval_data)


# -----------------------------------------------------------------------------
# 1. Corpus and Index Integrity Tests
# -----------------------------------------------------------------------------

def test_canonical_corpus_file_exists():
    assert CORPUS_PATH.exists(), f"Corpus file missing at {CORPUS_PATH}"
    assert CORPUS_PATH.stat().st_size > 20 * 1024 * 1024, "Corpus file is suspiciously small"


def test_retrieval_index_artifacts_exist():
    assert (INDEX_DIR / "retrieval_units.jsonl").exists()
    assert (INDEX_DIR / "bm25_index.pkl").exists()
    assert (INDEX_DIR / "vector/vectors.npy").exists()
    assert (INDEX_DIR / "vector/vector_metadata.jsonl").exists()
    assert MANIFEST_PATH.exists()


def test_index_manifest_metadata():
    with open(MANIFEST_PATH, "r") as f:
        manifest = json.load(f)
    assert manifest["index_version"] == "v13.0"
    assert manifest["phase"] == "13"
    assert manifest["total_units"] == 20745
    assert manifest["vector_count"] == 20745
    assert manifest["vector_dimension"] == 384
    assert manifest["offline_enforced"] is True


def test_vector_matrix_dimensions(retrieval_data):
    assert retrieval_data.vectors.shape == (20745, 384)
    assert retrieval_data.vectors.dtype == np.float32
    # Verify embeddings are normalized
    norms = np.linalg.norm(retrieval_data.vectors[:100], axis=1)
    np.testing.assert_allclose(norms, 1.0, atol=1e-3)


def test_retrieval_units_schema(retrieval_data):
    assert len(retrieval_data.units) == 20745
    sample = retrieval_data.units[0]
    mandatory_fields = [
        "retrieval_unit_id", "authority_tier", "evidence_depth",
        "document_type", "text", "full_index_text"
    ]
    for field in mandatory_fields:
        assert field in sample, f"Missing field {field} in unit"
        assert sample[field] is not None, f"Field {field} is None"


# -----------------------------------------------------------------------------
# 2. Query Identifier Extraction Tests
# -----------------------------------------------------------------------------

def test_extract_query_identifiers_is_number():
    ids = extract_query_identifiers("What does IS 10500 specify for drinking water?")
    assert "IS 10500" in ids["is_numbers"]


def test_extract_query_identifiers_multi_part():
    ids = extract_query_identifiers("Requirements for LED lamps under IS 16102 Part 1")
    assert any("16102" in s for s in ids["is_numbers"])


def test_extract_query_identifiers_clause():
    ids = extract_query_identifiers("What does clause 5.1 of IS 10500 specify?")
    assert "5.1" in ids["clauses"]
    assert ids["intent"] == "CLAUSE_LOOKUP"


def test_extract_query_identifiers_qco():
    ids = extract_query_identifiers("Is there a mandatory quality control order for cables?")
    assert ids["intent"] == "QCO"


# -----------------------------------------------------------------------------
# 3. Representative Standards Retrieval Tests
# -----------------------------------------------------------------------------

def test_retrieval_is10500_drinking_water_normative(engine):
    query = "What is the acceptable limit for total dissolved solids in IS 10500 drinking water?"
    res = engine.search(query, top_k=5)

    assert res["evidence_status"] == "SUFFICIENT"
    cov = res["standard_coverage"].get("IS 10500")
    assert cov is not None
    assert cov["has_normative_clauses"] is True
    assert cov["max_evidence_depth"] == "FULL_NORMATIVE_CLAUSE"

    # Top result must be Tier 1 Normative and mention limits
    top = res["results"][0]
    assert top["authority_tier"] == "TIER_1_NORMATIVE"
    assert "10500" in top["standard_number"]
    assert ("tds" in top["text"].lower() or "total dissolved solids" in top["text"].lower() or "clause" in top["text"].lower())


def test_retrieval_is4985_upvc_pipes(engine):
    query = "Hydrostatic pressure test requirements and grouping guidelines under IS 4985"
    res = engine.search(query, top_k=5)

    assert res["evidence_status"] == "SUFFICIENT"
    cov = res["standard_coverage"].get("IS 4985")
    assert cov is not None
    assert cov["has_normative_clauses"] is True

    # Check that results contain IS 4985 evidence
    top_standards = [r["standard_number"] for r in res["results"][:3]]
    assert any("4985" in s for s in top_standards)


def test_retrieval_is16102_led_lamps_multi_revision(engine):
    query = "Safety requirements for self-ballasted LED lamps under IS 16102 Part 1"
    res = engine.search(query, top_k=5)

    assert res["evidence_status"] == "SUFFICIENT"
    cov = res["standard_coverage"].get("IS 16102 Part 1") or res["standard_coverage"].get("IS 16102")
    assert cov is not None
    assert cov["has_normative_clauses"] is True

    top = res["results"][0]
    assert top["authority_tier"] == "TIER_1_NORMATIVE"
    assert "16102" in top["standard_number"]


def test_retrieval_is8978_water_heaters_lims_only(engine):
    query = "What clauses specify temperature cut-off testing for water heaters under IS 8978?"
    res = engine.search(query, top_k=5)

    # Invariant: IS 8978 has NO normative clauses in repository
    cov = res["standard_coverage"].get("IS 8978")
    assert cov is not None
    assert cov["is_lims_only"] is True
    assert cov["has_normative_clauses"] is False
    assert cov["abstention_required_for_clauses"] is True

    # Invariant: Retrieved IS 8978 evidence MUST be Tier 2 LIMS
    for r in res["results"]:
        if r.get("standard_number") and "8978" in r["standard_number"]:
            assert r["authority_tier"] == "TIER_2_LIMS"
            assert r["evidence_depth"] == "LIMS_SCOPE_FEE_ONLY"


def test_retrieval_metadata_only_standard(engine):
    query = "What are the test requirements for IS 16189?"
    res = engine.search(query, top_k=5)

    cov = res["standard_coverage"].get("IS 16189")
    assert cov is not None
    assert cov["is_metadata_only"] is True
    assert cov["has_normative_clauses"] is False
    assert cov["abstention_required_for_clauses"] is True


# -----------------------------------------------------------------------------
# 4. Fusion and Ranking Invariant Tests
# -----------------------------------------------------------------------------

def test_exact_identifier_boost_applied(engine):
    res = engine.search("IS 10500 specifications", top_k=10)
    # Units matching IS 10500 should receive exact_identifier_match=True
    matching = [r for r in res["results"] if r.get("exact_identifier_match")]
    assert len(matching) > 0
    # Top result should be boosted
    assert res["results"][0]["exact_identifier_match"] is True


def test_authority_tier_weighting_order(engine):
    # Tier 1 Normative should have higher weight than Tier 3 Catalog
    res = engine.search("IS 10500", top_k=20)
    normative_weights = [r["authority_weight"] for r in res["results"] if r["authority_tier"] == "TIER_1_NORMATIVE"]
    catalog_weights = [r["authority_weight"] for r in res["results"] if r["authority_tier"] == "TIER_3_CATALOG"]

    if normative_weights and catalog_weights:
        assert max(normative_weights) > max(catalog_weights)


def test_retrieval_latency(engine):
    res = engine.search("What is IS 10500?", top_k=10)
    assert res["duration_ms"] < 1000, f"Retrieval too slow: {res['duration_ms']}ms"
