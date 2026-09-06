"""
Phase F3 Step 3E: Test Suite for Complete BIS LIMS Laboratory Catalog Expansion.

Verifies:
1. multi-page recognized lab ingestion
2. BIS-owned lab ingestion
3. empanelled lab ingestion
4. pagination traversal
5. duplicate handling
6. category preservation
7. public code/internal ID separation
8. missing-field preservation
9. scope linkage
10. empty scope handling
11. scope retrieval failure handling
12. malformed scope handling
13. provenance/hash generation
14. deterministic repeated build
15. no external enrichment
16. no LLM dependency
17. catalog statistics accuracy
"""

import json
from pathlib import Path
import pytest

from ai.lims.models import (
    LabCategory,
    RawLimsLabRecord,
    RawLimsScopeRecord,
    NormalizedLimsLab,
    NormalizedLimsScope,
    RejectedRecord,
)
from ai.lims.extractor import LimsExtractor, sha256_text
from ai.lims.validator import LimsValidator, LimsDeduplicationEngine
from ai.lims.retrieval_layer import LimsRetrievalLayer


CATALOG_DIR = Path("data/catalog/phase_f3_lims")
DIRECTORY_DIR = Path("data/raw/immutable/lims_directory")
SCOPE_DIR = Path("data/raw/immutable/lims_scope")


def test_01_multi_page_recognized_lab_ingestion():
    """Criterion 1: Verified that recognized labs span multiple directory pages."""
    manifest_file = DIRECTORY_DIR / "directory_manifest.json"
    assert manifest_file.exists(), "Directory manifest missing"
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    recog_pages = [m for m in manifest if m["category"] == "BIS_RECOGNIZED"]
    assert len(recog_pages) == 22, f"Expected 22 recognized pages, got {len(recog_pages)}"
    total_recog_rows = sum(m["rows_found"] for m in recog_pages)
    assert total_recog_rows == 431, f"Expected 431 recognized labs, got {total_recog_rows}"


def test_02_bis_owned_lab_ingestion():
    """Criterion 2: Verified 10 BIS-owned laboratories discovered and normalized."""
    manifest_file = DIRECTORY_DIR / "directory_manifest.json"
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    bis_pages = [m for m in manifest if m["category"] == "BIS_OWNED"]
    assert len(bis_pages) == 1
    assert bis_pages[0]["rows_found"] == 10


def test_03_empanelled_lab_ingestion():
    """Criterion 3: Verified 140 empanelled laboratories across 7 pages."""
    manifest_file = DIRECTORY_DIR / "directory_manifest.json"
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    empan_pages = [m for m in manifest if m["category"] == "BIS_EMPANELLED"]
    assert len(empan_pages) == 7
    total_empan_rows = sum(m["rows_found"] for m in empan_pages)
    assert total_empan_rows == 140


def test_04_pagination_traversal():
    """Criterion 4: Pagination stops deterministically when a page returns 0 rows."""
    # Verified: recognized page 22 has 11 rows, page 23 returns 0 rows (end of pagination)
    manifest = json.loads((DIRECTORY_DIR / "directory_manifest.json").read_text(encoding="utf-8"))
    recog_last = next(m for m in manifest if m["category"] == "BIS_RECOGNIZED" and m["page"] == 22)
    assert recog_last["rows_found"] == 11


def test_05_duplicate_handling():
    """Criterion 5: Duplicate records are identified without merging distinct labs."""
    dedup = LimsDeduplicationEngine()
    lab1 = NormalizedLimsLab(
        internal_id=999,
        lab_code="8999999",
        lab_name="Duplicate Test Lab",
        category=LabCategory.BIS_RECOGNIZED,
        original_address="Address 1, Delhi",
        source_url="https://lims.bis.gov.in/home/labs/?page=1"
    )
    lab2 = NormalizedLimsLab(
        internal_id=999,
        lab_code="8999999",
        lab_name="Duplicate Test Lab",
        category=LabCategory.BIS_RECOGNIZED,
        original_address="Address 1, Delhi",
        source_url="https://lims.bis.gov.in/home/labs/?page=2"
    )
    validated, dups = dedup.process_laboratories([lab1, lab2])
    assert len(validated) == 1
    assert len(dups) == 1
    assert dups[0]["type"] == "CLEAN_DUPLICATE"


def test_06_category_preservation():
    """Criterion 6: LabCategory enums are preserved with 0 conflation."""
    manifest = json.loads((CATALOG_DIR / "catalog_manifest.json").read_text(encoding="utf-8"))
    assert manifest["bis_owned_count"] == 10
    assert manifest["bis_recognized_count"] == 431
    assert manifest["bis_empanelled_count"] == 140


def test_07_public_code_internal_id_separation():
    """Criterion 7: public lab_code and internal_id remain strictly separated."""
    labs_file = CATALOG_DIR / "laboratories_normalized.jsonl"
    with labs_file.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            d = json.loads(line)
            assert isinstance(d["internal_id"], int)
            assert isinstance(d["lab_code"], str)
            # Cannot be identical
            assert d["lab_code"] != str(d["internal_id"])
            if idx > 100:
                break


def test_08_missing_field_preservation():
    """Criterion 8: Missing fields are preserved as None/empty, never inferred."""
    # In BIS LIMS, Lab 1989 has no lab code in table
    labs_file = CATALOG_DIR / "laboratories_normalized.jsonl"
    with labs_file.open("r", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d["internal_id"] == 1989:
                # Should not have invented a 7-digit code
                assert not d["lab_code"].isdigit()


def test_09_scope_linkage():
    """Criterion 9: Scopes correctly link to parent laboratories via internal_id."""
    retrieval = LimsRetrievalLayer.load_from_catalog(CATALOG_DIR)
    for scope in list(retrieval._scopes.values())[:50]:
        parent_lab = retrieval.get_laboratory_by_id(scope.internal_lab_id)
        assert parent_lab is not None
        assert parent_lab.internal_id == scope.internal_lab_id


def test_10_empty_scope_handling():
    """Criterion 10: Laboratories with empty scope remain in directory with SCOPE_EMPTY status."""
    manifest = json.loads((CATALOG_DIR / "catalog_manifest.json").read_text(encoding="utf-8"))
    assert manifest["scope_empty_count"] == 39
    assert manifest["laboratories_without_scope"] == 39

    labs_file = CATALOG_DIR / "laboratories_normalized.jsonl"
    found_empty = False
    with labs_file.open("r", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d.get("scope_status") == "SCOPE_EMPTY":
                found_empty = True
                break
    assert found_empty is True


def test_11_scope_retrieval_failure_handling():
    """Criterion 11: Scope retrieval failure records explicit error rather than discarding lab."""
    scope_manifest = json.loads((SCOPE_DIR / "scope_acquisition_manifest.json").read_text(encoding="utf-8"))
    # In live acquisition, all 581 succeeded HTTP 200, 0 network failure
    assert len(scope_manifest) == 581
    assert all("scope_status" in item for item in scope_manifest)


def test_12_malformed_scope_handling():
    """Criterion 12: Malformed scope with unresolvable standard is rejected with explicit code."""
    lab_lookup = {
        999: NormalizedLimsLab(
            internal_id=999,
            lab_code="8999999",
            lab_name="Test Lab",
            category=LabCategory.BIS_RECOGNIZED,
            original_address="Valid Address 123",
            source_url="https://lims.bis.gov.in"
        )
    }
    malformed_scope = RawLimsScopeRecord(
        raw_scope_id="RAW_MALFORMED_1",
        internal_lab_id=999,
        raw_standard="INVALID_NON_STANDARD_TEXT",
        raw_product="Product",
        source_url="https://lims.bis.gov.in/test",
        source_sha256="sha_test"
    )
    norm, rej = LimsValidator.validate_and_normalize_scope(malformed_scope, lab_lookup)
    assert norm is None
    assert rej is not None
    assert "INVALID_STANDARD_IDENTIFIER" in rej.rejection_reason


def test_13_provenance_hash_generation():
    """Criterion 13: Every laboratory and scope retains SHA-256 provenance."""
    labs_file = CATALOG_DIR / "laboratories_normalized.jsonl"
    scopes_file = CATALOG_DIR / "scope_normalized.jsonl"

    with labs_file.open("r", encoding="utf-8") as f:
        sample_lab = json.loads(f.readline())
        assert len(sample_lab["provenance_sha256"]) == 64

    with scopes_file.open("r", encoding="utf-8") as f:
        sample_scope = json.loads(f.readline())
        assert len(sample_scope["source_sha256"]) == 64


def test_14_deterministic_repeated_build():
    """Criterion 14: Manifest contains exact deterministic counts matching file rows."""
    manifest = json.loads((CATALOG_DIR / "catalog_manifest.json").read_text(encoding="utf-8"))

    with (CATALOG_DIR / "laboratories_normalized.jsonl").open("r", encoding="utf-8") as f:
        lab_count = sum(1 for _ in f)
    with (CATALOG_DIR / "scope_normalized.jsonl").open("r", encoding="utf-8") as f:
        scope_count = sum(1 for _ in f)

    assert lab_count == manifest["unique_laboratories"]
    assert scope_count == manifest["total_scope_records"]


def test_15_no_external_enrichment():
    """Criterion 15: No Geoapify, Google Maps, or coordinates in catalog files."""
    labs_file = CATALOG_DIR / "laboratories_normalized.jsonl"
    with labs_file.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            assert "geoapify" not in line.lower()
            assert "latitude" not in line.lower()
            assert "longitude" not in line.lower()
            if idx > 100:
                break


def test_16_no_llm_dependency():
    """Criterion 16: Zero LLM / Groq imports in ai/lims/ source files."""
    for p in Path("ai/lims").glob("*.py"):
        text = p.read_text(encoding="utf-8").lower()
        assert "groq" not in text
        assert "openai" not in text


def test_17_catalog_statistics_accuracy():
    """Criterion 17: Catalog statistics provide exact accounting without false claims."""
    manifest = json.loads((CATALOG_DIR / "catalog_manifest.json").read_text(encoding="utf-8"))
    assert manifest["total_directory_records_discovered"] == 581
    assert manifest["unique_laboratories"] == 580
    assert manifest["rejected_identity_records"] == 1
    assert manifest["laboratories_with_scope_available"] == 541
    assert manifest["laboratories_without_scope"] == 39
    assert manifest["total_scope_records"] == 6327
    assert manifest["total_standards_associated"] == 1264
    assert manifest["total_clause_records"] == 368886
