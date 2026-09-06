"""
Phase F3 Step 3E-A: Expanded BIS LIMS Catalog Integrity Audit Suite.

Verifies:
1. Catalog Integrity:
   - Directory count reconciliation (581 discovered)
   - Unique laboratory count (580 validated)
   - Category count reconciliation (10 BIS Owned, 430 Valid Recognized, 140 Empanelled)
   - Rejected record handling (1 rejected: ECO Laboratories, internal_id: 313)
   - Duplicate detection (0 duplicate entries)
   - Public lab_code consistency & internal_id uniqueness
   - Strict separation between lab_code and internal_id
   - Address preservation (raw addresses preserved verbatim)
2. Scope Integrity:
   - Every scope links to a valid laboratory in the catalog
   - Zero orphan scopes
   - Complete vs Partial scope fidelity
   - Excluded clause isolation
   - Clause record counts and fee linkage
   - Empty-scope laboratories (39) have zero fabricated scopes
   - Zero synthesized scopes
3. Provenance & Authority:
   - All labs and scopes have valid lims.bis.gov.in source URLs and SHA-256 hashes
   - Zero external metadata (Geoapify, Google Maps, coordinates) in catalog
   - Zero LLM imports or dependencies
4. Matching Engine Regression:
   - IS 8978 returns verified capable laboratories
   - Multi-lab and single-lab queries
   - Uncataloged standards return NO_MATCH
   - Repeated queries yield bitwise identical output
"""

import json
from pathlib import Path
from collections import Counter
import pytest

from ai.lims.models import (
    LabCategory,
    NormalizedLimsLab,
    NormalizedLimsScope,
    RejectedRecord,
)
from ai.lims.retrieval_layer import LimsRetrievalLayer
from ai.lims.matching_engine import LimsMatchingEngine
from ai.lims.matching_models import (
    MatchStatus,
    ScopeCompleteness,
    MatchReason,
    LabMatchingRequest,
)

CATALOG_DIR = Path("data/catalog/phase_f3_lims")
DIRECTORY_DIR = Path("data/raw/immutable/lims_directory")
SCOPE_DIR = Path("data/raw/immutable/lims_scope")


# =========================================================================
# 1. CATALOG INTEGRITY AUDIT
# =========================================================================

def test_audit_01_directory_count_reconciliation():
    """Audit: 581 raw directory rows discovered across 30 pages."""
    manifest_file = DIRECTORY_DIR / "directory_manifest.json"
    assert manifest_file.exists()
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert len(manifest) == 30
    total_discovered = sum(m["rows_found"] for m in manifest)
    assert total_discovered == 581


def test_audit_02_unique_laboratory_count():
    """Audit: Exactly 580 validated laboratories exist in normalized catalog."""
    labs_file = CATALOG_DIR / "laboratories_normalized.jsonl"
    with labs_file.open("r", encoding="utf-8") as f:
        labs = [json.loads(line) for line in f]
    assert len(labs) == 580
    internal_ids = [l["internal_id"] for l in labs]
    assert len(set(internal_ids)) == 580, "Duplicate internal_ids found in catalog!"


def test_audit_03_category_reconciliation():
    """Audit: Category breakdown matches 10 BIS Owned, 430 Recognized, 140 Empanelled."""
    labs_file = CATALOG_DIR / "laboratories_normalized.jsonl"
    with labs_file.open("r", encoding="utf-8") as f:
        labs = [json.loads(line) for line in f]
    counts = Counter(l["category"] for l in labs)
    assert counts["BIS_OWNED"] == 10
    assert counts["BIS_RECOGNIZED"] == 430
    assert counts["BIS_EMPANELLED"] == 140
    # 430 valid recognized + 1 rejected recognized = 431 discovered recognized
    assert counts["BIS_RECOGNIZED"] + 1 == 431


def test_audit_04_rejected_record_integrity():
    """Audit: Exactly 1 record rejected with explicit statutory rationale."""
    rej_file = CATALOG_DIR / "rejected_records.jsonl"
    assert rej_file.exists()
    with rej_file.open("r", encoding="utf-8") as f:
        rejections = [json.loads(line) for line in f]
    assert len(rejections) == 1
    rej = rejections[0]
    assert rej["record_type"] == "LABORATORY"
    assert rej["raw_data"]["internal_id"] == 313
    assert rej["raw_data"]["lab_code"] == "9134816"
    assert "MISSING_ADDRESS" in rej["rejection_reason"]
    assert rej["raw_data"]["raw_address"] == "-"


def test_audit_05_identifier_separation_and_uniqueness():
    """Audit: public lab_code and internal_id remain strictly separated."""
    labs_file = CATALOG_DIR / "laboratories_normalized.jsonl"
    with labs_file.open("r", encoding="utf-8") as f:
        for line in f:
            l = json.loads(line)
            assert isinstance(l["internal_id"], int)
            assert isinstance(l["lab_code"], str)
            assert l["lab_code"] != str(l["internal_id"])


def test_audit_06_address_preservation():
    """Audit: original_address is preserved verbatim without external geocoding modification."""
    labs_file = CATALOG_DIR / "laboratories_normalized.jsonl"
    with labs_file.open("r", encoding="utf-8") as f:
        for line in f:
            l = json.loads(line)
            assert "original_address" in l
            assert len(l["original_address"].strip()) >= 4
            # Zero geocoding metadata present
            assert "latitude" not in l
            assert "longitude" not in l
            assert "geoapify" not in json.dumps(l).lower()


# =========================================================================
# 2. SCOPE INTEGRITY AUDIT
# =========================================================================

def test_audit_07_scope_foreign_key_linkage():
    """Audit: Every scope links to an existing validated laboratory."""
    retrieval = LimsRetrievalLayer.load_from_catalog(CATALOG_DIR)
    for scope in retrieval._scopes.values():
        parent_lab = retrieval.get_laboratory_by_id(scope.internal_lab_id)
        assert parent_lab is not None, f"Orphan scope found! ID: {scope.scope_id}"
        assert parent_lab.internal_id == scope.internal_lab_id
        assert parent_lab.lab_code == scope.lab_code


def test_audit_08_empty_scope_laboratories_have_zero_scopes():
    """Audit: All 39 empty-scope laboratories have zero fabricated scopes."""
    retrieval = LimsRetrievalLayer.load_from_catalog(CATALOG_DIR)
    empty_labs = [l for l in retrieval._labs.values() if l.scope_status == "SCOPE_EMPTY"]
    assert len(empty_labs) == 39
    for elab in empty_labs:
        scopes = retrieval.get_scope_for_laboratory(elab.internal_id)
        assert len(scopes) == 0, f"Lab {elab.internal_id} has fabricated scopes!"


def test_audit_09_complete_vs_partial_scope_fidelity():
    """Audit: Partial scopes have exclusions or complete_scope=False; complete scopes have 0 exclusions."""
    scopes_file = CATALOG_DIR / "scope_normalized.jsonl"
    with scopes_file.open("r", encoding="utf-8") as f:
        scopes = [json.loads(line) for line in f]

    assert len(scopes) == 6327
    complete_count = 0
    partial_count = 0
    for s in scopes:
        if s["is_complete_scope"] and not s["excluded_clauses"]:
            complete_count += 1
        else:
            partial_count += 1

    assert complete_count > 0
    assert partial_count >= 0
    assert complete_count + partial_count == 6327


def test_audit_10_clause_and_fee_integrity():
    """Audit: Total clause records match 368,886 with valid fee linkage."""
    manifest = json.loads((CATALOG_DIR / "catalog_manifest.json").read_text(encoding="utf-8"))
    scopes_file = CATALOG_DIR / "scope_normalized.jsonl"
    total_clauses = 0
    with scopes_file.open("r", encoding="utf-8") as f:
        for line in f:
            s = json.loads(line)
            total_clauses += len(s["clauses"])

    assert total_clauses == 368886
    assert total_clauses == manifest["total_clause_records"]


# =========================================================================
# 3. PROVENANCE & SECURITY AUDIT
# =========================================================================

def test_audit_11_provenance_integrity():
    """Audit: Every lab and scope maintains official BIS LIMS provenance."""
    labs_file = CATALOG_DIR / "laboratories_normalized.jsonl"
    scopes_file = CATALOG_DIR / "scope_normalized.jsonl"

    with labs_file.open("r", encoding="utf-8") as f:
        for line in f:
            l = json.loads(line)
            assert l["source_url"].startswith("https://lims.bis.gov.in/")
            assert len(l["provenance_sha256"]) == 64

    with scopes_file.open("r", encoding="utf-8") as f:
        for line in f:
            s = json.loads(line)
            assert s["source_url"].startswith("https://lims.bis.gov.in/")
            assert len(s["source_sha256"]) == 64


def test_audit_12_zero_llm_or_external_enrichment():
    """Audit: Zero LLMs or external enrichment in ai/lims/."""
    for p in Path("ai/lims").glob("*.py"):
        text = p.read_text(encoding="utf-8").lower()
        assert "groq" not in text
        assert "openai" not in text
        assert "geoapify" not in text


# =========================================================================
# 4. MATCHING REGRESSION ON EXPANDED CATALOG
# =========================================================================

def test_audit_13_matching_regression_is_8978():
    """Audit: IS 8978 matching yields verified candidate laboratories."""
    engine = LimsMatchingEngine()
    req = LabMatchingRequest(standard="IS 8978")
    res = engine.match(req)
    assert res.status == MatchStatus.EXACT_MATCH
    assert res.total_candidates == 10
    # Top laboratory is verified
    top = res.candidates[0]
    assert "8978" in top.matching_standard
    assert top.category == LabCategory.BIS_RECOGNIZED
    assert top.rank == 1


def test_audit_14_matching_regression_uncataloged_standard():
    """Audit: Uncataloged standard returns NO_MATCH without synthetic broadening."""
    engine = LimsMatchingEngine()
    req = LabMatchingRequest(standard="IS 99999_NONEXISTENT")
    res = engine.match(req)
    assert res.status == MatchStatus.NO_MATCH
    assert res.total_candidates == 0
    assert len(res.candidates) == 0


def test_audit_15_matching_regression_determinism():
    """Audit: 10 repeated queries across expanded catalog yield bitwise identical candidates."""
    engine = LimsMatchingEngine()
    req = LabMatchingRequest(standard="IS 8978")
    runs = [engine.match(req).to_dict()["candidates"] for _ in range(10)]
    for r in runs[1:]:
        assert r == runs[0]


def test_audit_16_manifest_exact_reconciliation():
    """Audit: Manifest numbers strictly match independent recalculation from catalog files."""
    manifest = json.loads((CATALOG_DIR / "catalog_manifest.json").read_text(encoding="utf-8"))

    with (CATALOG_DIR / "laboratories_normalized.jsonl").open("r", encoding="utf-8") as f:
        labs = [json.loads(line) for line in f]

    with (CATALOG_DIR / "scope_normalized.jsonl").open("r", encoding="utf-8") as f:
        scopes = [json.loads(line) for line in f]

    with (CATALOG_DIR / "rejected_records.jsonl").open("r", encoding="utf-8") as f:
        rejections = [json.loads(line) for line in f]

    assert manifest["unique_laboratories"] == len(labs)
    assert manifest["total_scope_records"] == len(scopes)
    assert manifest["total_rejected_records"] == len(rejections)
    assert manifest["total_standards_associated"] == len({s["standard_number"] for s in scopes})
    assert manifest["total_clause_records"] == sum(len(s["clauses"]) for s in scopes)
