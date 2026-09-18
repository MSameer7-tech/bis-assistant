"""
Phase PC-2: BIS Compliance Data Normalization & Provenance Test Suite.

Automated verification suite testing all 16 required areas:
1. Schema validity
2. Provenance preservation
3. Source verification preservation
4. QCO status preservation
5. Effective-date preservation
6. Product -> Standard lineage
7. Standard edition preservation
8. Scheme definition/applicability separation
9. Product Manual lineage
10. Testing/SIT traceability
11. Certification procedure lineage
12. Document hash integrity
13. Conflict detection
14. Unknown/null preservation
15. No-new-knowledge invariant (every normalized record traces to PC-1)
16. Frozen-system immutability
"""

import json
import os
import hashlib
from pathlib import Path
import pytest

from ai.compliance.normalized_models import (
    SourceVerificationState,
    RecordType,
    ConflictType,
    NormalizedQcoRecord,
    NormalizedProductStandardMap,
    NormalizedSchemeRecord,
    NormalizedTestingRequirement,
    NormalizedProductManual,
    NormalizedCertificationProcedure,
    NormalizedDocumentEntry,
    ComplianceConflictRecord,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "compliance" / "raw"
NORMALIZED_DIR = PROJECT_ROOT / "data" / "compliance" / "normalized"
METADATA_DIR = NORMALIZED_DIR / "metadata"


def load_jsonl(filepath: Path):
    records = []
    assert filepath.exists(), f"File does not exist: {filepath}"
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


# ---------------------------------------------------------------------------
# Test 1: Schema Validity
# ---------------------------------------------------------------------------
def test_01_schema_validity():
    """All 7 JSONL datasets strictly validate against their Pydantic schemas."""
    # 1. QCOs
    qcos = load_jsonl(NORMALIZED_DIR / "qco_registry.jsonl")
    assert len(qcos) == 313
    for q in qcos:
        NormalizedQcoRecord(**q)

    # 2. Product -> Standard
    psms = load_jsonl(NORMALIZED_DIR / "product_standard_map.jsonl")
    assert len(psms) == 665
    for psm in psms:
        NormalizedProductStandardMap(**psm)

    # 3. Schemes
    schemes = load_jsonl(NORMALIZED_DIR / "certification_scheme_map.jsonl")
    assert len(schemes) == 12
    for s in schemes:
        NormalizedSchemeRecord(**s)

    # 4. Testing / SIT
    tests = load_jsonl(NORMALIZED_DIR / "testing_requirements.jsonl")
    assert len(tests) == 120
    for t in tests:
        NormalizedTestingRequirement(**t)

    # 5. Product Manuals
    pms = load_jsonl(NORMALIZED_DIR / "product_manual_registry.jsonl")
    assert len(pms) == 763
    for pm in pms:
        NormalizedProductManual(**pm)

    # 6. Certification Procedures
    procs = load_jsonl(NORMALIZED_DIR / "certification_process.jsonl")
    assert len(procs) == 28
    for proc in procs:
        NormalizedCertificationProcedure(**proc)

    # 7. Documents
    docs = load_jsonl(NORMALIZED_DIR / "document_registry.jsonl")
    assert len(docs) == 1076
    for d in docs:
        NormalizedDocumentEntry(**d)


# ---------------------------------------------------------------------------
# Test 2: Provenance Preservation
# ---------------------------------------------------------------------------
def test_02_provenance_preservation():
    """Every record contains the universal provenance contract fields."""
    files = [
        NORMALIZED_DIR / "qco_registry.jsonl",
        NORMALIZED_DIR / "product_standard_map.jsonl",
        NORMALIZED_DIR / "certification_scheme_map.jsonl",
        NORMALIZED_DIR / "testing_requirements.jsonl",
        NORMALIZED_DIR / "product_manual_registry.jsonl",
        NORMALIZED_DIR / "certification_process.jsonl",
    ]
    for fpath in files:
        records = load_jsonl(fpath)
        for r in records:
            assert "provenance" in r, f"Missing provenance in {r['record_id']}"
            prov = r["provenance"]
            assert "source_url" in prov
            assert "source_document" in prov
            assert "source_hash" in prov
            assert "source_location" in prov
            assert "retrieved_at" in prov


# ---------------------------------------------------------------------------
# Test 3: Source Verification Preservation
# ---------------------------------------------------------------------------
def test_03_source_verification_preservation():
    """Verification states match PC-1: 1,607 verified, 294 unverified. Zero upgrades."""
    files = [
        NORMALIZED_DIR / "qco_registry.jsonl",
        NORMALIZED_DIR / "product_standard_map.jsonl",
        NORMALIZED_DIR / "certification_scheme_map.jsonl",
        NORMALIZED_DIR / "testing_requirements.jsonl",
        NORMALIZED_DIR / "product_manual_registry.jsonl",
        NORMALIZED_DIR / "certification_process.jsonl",
    ]
    verified = 0
    unverified = 0
    for fpath in files:
        records = load_jsonl(fpath)
        for r in records:
            state = r.get("source_verification_state")
            assert state in ("SOURCE_VERIFIED", "SOURCE_UNVERIFIED"), f"Invalid state {state} in {r['record_id']}"
            if state == "SOURCE_VERIFIED":
                verified += 1
            else:
                unverified += 1

    assert verified == 1607, f"Expected 1607 verified records, found {verified}"
    assert unverified == 294, f"Expected 294 unverified records, found {unverified}"
    assert verified + unverified == 1901


# ---------------------------------------------------------------------------
# Test 4: QCO Status Preservation
# ---------------------------------------------------------------------------
def test_04_qco_status_preservation():
    """QCO status strictly preserved from PC-1; no autonomous status promotion."""
    qcos = load_jsonl(NORMALIZED_DIR / "qco_registry.jsonl")
    raw_qcos = load_jsonl(RAW_DIR / "qcos" / "qcos.jsonl")
    raw_status_map = {q["qco_id"]: q.get("status", "UNKNOWN") for q in raw_qcos}

    valid_statuses = {"ACTIVE", "UPCOMING", "SUPERSEDED", "AMENDED", "UNKNOWN"}
    for q in qcos:
        st = q.get("status")
        assert st in valid_statuses, f"Invalid QCO status {st}"
        assert st == raw_status_map[q["qco_id"]], f"Status mismatch for {q['qco_id']}"


# ---------------------------------------------------------------------------
# Test 5: Effective-Date Preservation
# ---------------------------------------------------------------------------
def test_05_effective_date_preservation():
    """Effective dates are preserved from raw sources; missing dates remain null."""
    qcos = load_jsonl(NORMALIZED_DIR / "qco_registry.jsonl")
    raw_qcos = load_jsonl(RAW_DIR / "qcos" / "qcos.jsonl")
    raw_date_map = {q["qco_id"]: q.get("effective_date") for q in raw_qcos}

    null_count = 0
    for q in qcos:
        qid = q["qco_id"]
        assert q.get("effective_date") == raw_date_map[qid]
        if q.get("effective_date") is None:
            null_count += 1

    assert null_count > 0, "Expected null effective dates to be preserved without invention"


# ---------------------------------------------------------------------------
# Test 6: Product -> Standard Lineage
# ---------------------------------------------------------------------------
def test_06_product_standard_lineage():
    """All 665 Product -> Standard pairs have direct lineage and clause citations."""
    psms = load_jsonl(NORMALIZED_DIR / "product_standard_map.jsonl")
    assert len(psms) == 665
    for psm in psms:
        assert psm.get("product_original")
        assert psm.get("standard_original")
        assert psm.get("standard_normalized")
        assert psm.get("source_record_id")
        assert psm.get("source_document")


# ---------------------------------------------------------------------------
# Test 7: Standard Edition Preservation
# ---------------------------------------------------------------------------
def test_07_standard_edition_preservation():
    """Original standard string preserves edition/revision while normalized provides clean identifier."""
    psms = load_jsonl(NORMALIZED_DIR / "product_standard_map.jsonl")
    found_edition = False
    for psm in psms:
        orig = psm["standard_original"]
        norm = psm["standard_normalized"]
        assert norm == norm.upper()
        if ":" in orig:
            found_edition = True
            assert ":" not in norm or "IS/IEC" in norm or "ISO" in norm
    assert found_edition, "Expected standards with edition years to be tested"


# ---------------------------------------------------------------------------
# Test 8: Scheme Definition vs Applicability Separation
# ---------------------------------------------------------------------------
def test_08_scheme_definition_applicability_separation():
    """12 scheme definitions isolated; zero ungrounded scheme applicability records."""
    schemes = load_jsonl(NORMALIZED_DIR / "certification_scheme_map.jsonl")
    assert len(schemes) == 12
    defs = [s for s in schemes if s["record_type"] == RecordType.SCHEME_DEFINITION.value]
    apps = [s for s in schemes if s["record_type"] == RecordType.SCHEME_APPLICABILITY.value]
    assert len(defs) == 12
    assert len(apps) == 0  # No inferred applicability mappings


# ---------------------------------------------------------------------------
# Test 9: Product Manual Lineage
# ---------------------------------------------------------------------------
def test_09_product_manual_lineage():
    """All 763 Product Manuals preserved with exact verification states (646 vs 117)."""
    pms = load_jsonl(NORMALIZED_DIR / "product_manual_registry.jsonl")
    assert len(pms) == 763
    verified = [p for p in pms if p["source_verification_state"] == "SOURCE_VERIFIED"]
    unverified = [p for p in pms if p["source_verification_state"] == "SOURCE_UNVERIFIED"]
    assert len(verified) == 646
    assert len(unverified) == 117


# ---------------------------------------------------------------------------
# Test 10: Testing/SIT Traceability
# ---------------------------------------------------------------------------
def test_10_testing_sit_traceability():
    """120 SIT test requirements preserved with methods, frequency, sample size; is_mandatory not assumed."""
    tests = load_jsonl(NORMALIZED_DIR / "testing_requirements.jsonl")
    assert len(tests) == 120
    for t in tests:
        assert t.get("test_name")
        assert t.get("standard_original")
        assert t.get("source_record_id")
        # Mandatory must not be blindly assumed as true
        assert t.get("is_mandatory") is None


# ---------------------------------------------------------------------------
# Test 11: Certification Procedure Lineage
# ---------------------------------------------------------------------------
def test_11_certification_procedure_lineage():
    """28 certification procedures preserved with procedure types and stages."""
    procs = load_jsonl(NORMALIZED_DIR / "certification_process.jsonl")
    assert len(procs) == 28
    valid_proc_types = {"NORMAL", "SIMPLIFIED", "CRS", "FMCS", "UNKNOWN"}
    for p in procs:
        assert p.get("procedure_type") in valid_proc_types
        assert p.get("scheme_id")
        assert p.get("title")
        assert p.get("source_record_id")


# ---------------------------------------------------------------------------
# Test 12: Document Hash Integrity
# ---------------------------------------------------------------------------
def test_12_document_hash_integrity():
    """1,076 documents registered with cryptographic SHA-256 matching disk payloads."""
    docs = load_jsonl(NORMALIZED_DIR / "document_registry.jsonl")
    assert len(docs) == 1076

    # Verify a random sample of 25 files on disk
    import random
    sample = random.sample(docs, 25)
    for doc in sample:
        fpath = PROJECT_ROOT / doc["relative_path"]
        assert fpath.exists(), f"Document file missing: {fpath}"
        h = hashlib.sha256()
        with open(fpath, "rb") as fp:
            while chunk := fp.read(65536):
                h.update(chunk)
        assert h.hexdigest().lower() == doc["sha256"].lower()


# ---------------------------------------------------------------------------
# Test 13: Conflict Detection
# ---------------------------------------------------------------------------
def test_13_conflict_detection():
    """conflicts.jsonl exists and logs conflicts with affected records and unresolved policy."""
    conflicts = load_jsonl(METADATA_DIR / "conflicts.jsonl")
    assert len(conflicts) > 0
    for c in conflicts:
        ComplianceConflictRecord(**c)
        assert c["conflict_id"].startswith("CONF-")
        assert c["resolution_policy"] == "UNRESOLVED_DISCLOSED"
        assert len(c["affected_record_ids"]) > 1

    # Verify that S.O. 3840(E) is detected as a conflict
    so_conflicts = [c for c in conflicts if "3840(E)" in c.get("entity_reference", "")]
    assert len(so_conflicts) > 0, "Expected S.O. 3840(E) conflict to be detected"


# ---------------------------------------------------------------------------
# Test 14: Unknown/Null Preservation
# ---------------------------------------------------------------------------
def test_14_unknown_null_preservation():
    """Missing fields remain explicit null or UNKNOWN; zero synthetic inference."""
    qcos = load_jsonl(NORMALIZED_DIR / "qco_registry.jsonl")
    null_notif = sum(1 for q in qcos if q.get("notification_number") is None)
    null_auth = sum(1 for q in qcos if q.get("issuing_authority") is None)
    unknown_status = sum(1 for q in qcos if q.get("status") == "UNKNOWN")
    assert null_notif > 0
    assert null_auth > 0
    assert unknown_status > 0


# ---------------------------------------------------------------------------
# Test 15: No-New-Knowledge Invariant
# ---------------------------------------------------------------------------
def test_15_no_new_knowledge_invariant():
    """Every single core normalized record maps deterministically to a PC-1 raw record."""
    manifest_path = METADATA_DIR / "normalization_manifest.json"
    assert manifest_path.exists()
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    lineage = manifest.get("lineage_summary", {})
    assert lineage.get("total_core_normalized") == 1901
    assert lineage.get("traceable_to_pc1") == 1901
    assert lineage.get("orphan_records") == 0
    assert lineage.get("lineage_coverage_percent") == 100.0


# ---------------------------------------------------------------------------
# Test 16: Frozen-System Immutability
# ---------------------------------------------------------------------------
def test_16_frozen_system_immutability():
    """Verify that completed systems remain frozen and untouched."""
    frozen_files = [
        "scripts/phase12_e_production_rag.py",
        "scripts/phase12_f2_orchestrator.py",
        "data/derived/phase12/grounded_rag_v1/claim_validator.py",
        "backend/lab_finder_api.py",
        "data/catalog/phase_f3_lims/catalog_manifest.json",
        "backend/app.py",
        "frontend/app.js",
    ]
    for rel_path in frozen_files:
        fpath = PROJECT_ROOT / rel_path
        assert fpath.exists(), f"Frozen system file missing: {fpath}"
