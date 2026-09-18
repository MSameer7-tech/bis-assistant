"""
Phase PC-4: Testing + Certification Process Engine Test Suite.

Automated verification suite testing all required areas:
1. Standard with verified testing requirements (CONFIRMED)
2. Standard with partial testing evidence (PARTIAL)
3. Standard with no testing evidence (UNKNOWN)
4. Test method with clause provenance (explicit numerical clauses)
5. Product Manual supplying test requirements / references
6. Product Manual with unresolved version conflict
7. Missing test method remains unknown (zero clause invention)
8. Missing sampling requirement remains unknown (zero sample size invention)
9. Testing evidence does NOT imply mandatory certification
10. Generic BIS process does NOT imply product-specific process
11. Scheme definition does NOT imply scheme applicability
12. QCO conflict remains preserved (37 records)
13. QCO unknown remains preserved (8 records)
14. No laboratory qualification performed by PC-4 (zero lab ranking/selection)
15. Provenance completeness (100% coverage, zero orphan records)
16. Duplicate relationship prevention (strictly unique keys)
17. Deterministic rebuild (identical SHA-256 hashes)
18. Frozen PC-3 and earlier subsystems immutability
"""

import json
import os
import hashlib
from pathlib import Path
import pytest

from ai.compliance.testing_models import (
    TestingRequirementStatus,
    InspectionRequirementStatus,
    SamplingRequirementStatus,
    TestingRequirementRelationshipRecord,
    InspectionRequirementRelationshipRecord,
    SamplingRequirementRelationshipRecord,
)
from ai.compliance.process_models import (
    CertificationProcessStatus,
    CertificationProcedureRecord,
    TestingProcessRelationshipRecord,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PC3_DIR = PROJECT_ROOT / "data" / "compliance" / "relationships"
PC2_DIR = PROJECT_ROOT / "data" / "compliance" / "normalized"
PC4_DIR = PROJECT_ROOT / "data" / "compliance" / "testing_process"
METADATA_DIR = PC4_DIR / "metadata"


def load_jsonl(filepath: Path):
    records = []
    assert filepath.exists(), f"File does not exist: {filepath}"
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def compute_sha256(filepath: Path) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


# ---------------------------------------------------------------------------
# Test 1: Standard with Verified Testing Requirements (CONFIRMED)
# ---------------------------------------------------------------------------
def test_01_standard_with_verified_testing_requirements():
    """Standard with verified SIT requirements has CONFIRMED testing/inspection/sampling status."""
    tp_rels = load_jsonl(PC4_DIR / "testing_process_relationships.jsonl")
    cement = [r for r in tp_rels if r["standard_normalized"] == "IS 269"]
    assert len(cement) > 0
    for rec in cement:
        assert rec["testing_status"] == TestingRequirementStatus.TESTING_REQUIREMENTS_CONFIRMED
        assert rec["inspection_status"] == InspectionRequirementStatus.INSPECTION_REQUIREMENTS_CONFIRMED
        assert rec["sampling_status"] == SamplingRequirementStatus.SAMPLING_REQUIREMENTS_CONFIRMED
        assert len(rec["associated_testing_ids"]) > 0
        assert len(rec["associated_inspection_ids"]) > 0
        assert len(rec["associated_sampling_ids"]) > 0


# ---------------------------------------------------------------------------
# Test 2: Standard with Partial Testing Evidence (PARTIAL)
# ---------------------------------------------------------------------------
def test_02_standard_with_partial_testing_evidence():
    """Standard with Product Manual but no complete SIT record has PARTIAL testing status."""
    tp_rels = load_jsonl(PC4_DIR / "testing_process_relationships.jsonl")
    # IS 1653 has a Product Manual in PC-2 but no SIT in testing_requirements.jsonl
    partial_recs = [r for r in tp_rels if r["standard_normalized"] == "IS 1653"]
    assert len(partial_recs) > 0
    for rec in partial_recs:
        assert rec["testing_status"] == TestingRequirementStatus.TESTING_REQUIREMENTS_PARTIAL
        assert rec["inspection_status"] == InspectionRequirementStatus.INSPECTION_REQUIREMENTS_PARTIAL
        assert rec["sampling_status"] == SamplingRequirementStatus.SAMPLING_REQUIREMENTS_PARTIAL
        assert rec["product_manual_count"] > 0


# ---------------------------------------------------------------------------
# Test 3: Standard with No Testing Evidence (UNKNOWN)
# ---------------------------------------------------------------------------
def test_03_standard_with_no_testing_evidence():
    """Standard with neither SIT nor PM has UNKNOWN testing/inspection/sampling/process status (never 'NO')."""
    tp_rels = load_jsonl(PC4_DIR / "testing_process_relationships.jsonl")
    unknown_recs = [r for r in tp_rels if r["testing_status"] == TestingRequirementStatus.TESTING_REQUIREMENTS_UNKNOWN]
    assert len(unknown_recs) == 306
    for rec in unknown_recs:
        assert rec["inspection_status"] == InspectionRequirementStatus.INSPECTION_REQUIREMENTS_UNKNOWN
        assert rec["sampling_status"] == SamplingRequirementStatus.SAMPLING_REQUIREMENTS_UNKNOWN
        assert rec["certification_process_status"] == CertificationProcessStatus.CERTIFICATION_PROCESS_UNKNOWN
        assert len(rec["associated_testing_ids"]) == 0
        assert rec["product_manual_count"] == 0


# ---------------------------------------------------------------------------
# Test 4: Test Method with Clause Provenance
# ---------------------------------------------------------------------------
def test_04_test_method_with_clause_provenance():
    """Where SIT specifies a clause, clause is preserved for laboratory capability matching."""
    tr_rels = load_jsonl(PC4_DIR / "testing_requirement_relationships.jsonl")
    # IS 374 specifies Clause 10.4 and Clause 10.5
    fan_tests = [r for r in tr_rels if r["standard_normalized"] == "IS 374"]
    assert len(fan_tests) == 1
    fan = fan_tests[0]
    assert "Clause 10.4" in fan["test_clause"]
    assert "Clause 10.5" in fan["test_clause"]
    assert fan["test_name"] == "Air Delivery and Service Value"
    assert fan["source_record_id"] == "NORM-TEST-SIT-IS-374-2019-0001"
    assert fan["evidence_hash"] is not None

    # IS 1786 specifies Clause 9.2
    tmt_tests = [r for r in tr_rels if r["standard_normalized"] == "IS 1786"]
    assert len(tmt_tests) == 1
    assert "Clause 9.2" in tmt_tests[0]["test_clause"]

    # IS 16046 (PART 2) specifies Clause 7.3.2 and Clause 7.3.6
    battery_tests = [r for r in tr_rels if r["standard_normalized"] == "IS 16046 (PART 2)"]
    assert len(battery_tests) == 1
    assert "Clause 7.3.2" in battery_tests[0]["test_clause"]
    assert "Clause 7.3.6" in battery_tests[0]["test_clause"]


# ---------------------------------------------------------------------------
# Test 5: Product Manual Supplying Test Requirements
# ---------------------------------------------------------------------------
def test_05_product_manual_supplying_test_requirements():
    """Product manual reference is attached to testing relationships when available."""
    tr_rels = load_jsonl(PC4_DIR / "testing_requirement_relationships.jsonl")
    rich_pm_stds = ["IS 1293", "IS 2062", "IS 694", "IS 4985"]
    for s in rich_pm_stds:
        matches = [r for r in tr_rels if r["standard_normalized"] == s]
        assert len(matches) == 1
        assert matches[0]["product_manual_reference"] is not None


# ---------------------------------------------------------------------------
# Test 6: Product Manual with Unresolved Version Conflict
# ---------------------------------------------------------------------------
def test_06_product_manual_with_unresolved_version_conflict():
    """Standards with multiple PM versions preserve conflict state without picking an arbitrary version."""
    tp_rels = load_jsonl(PC4_DIR / "testing_process_relationships.jsonl")
    pm_conflicts = [r for r in tp_rels if r["product_manual_status"] == "PRODUCT_MANUAL_CONFLICT"]
    assert len(pm_conflicts) == 187
    for rec in pm_conflicts:
        assert len(rec["conflict_ids"]) > 0
        assert rec["product_manual_count"] > 1


# ---------------------------------------------------------------------------
# Test 7: Missing Test Method Remains Unknown (Zero Clause Invention)
# ---------------------------------------------------------------------------
def test_07_missing_test_method_remains_unknown():
    """Where source SIT does not provide an explicit numerical clause, test_clause is None (never synthetic)."""
    tr_rels = load_jsonl(PC4_DIR / "testing_requirement_relationships.jsonl")
    # IS 269 cites IS 4031 (Part 6) without specific numerical clause
    cement_tr = [r for r in tr_rels if r["standard_normalized"] == "IS 269"][0]
    assert cement_tr["test_clause"] is None

    # IS 14543 cites IS 15185 / IS 15186 without specific numerical clause
    water_tr = [r for r in tr_rels if r["standard_normalized"] == "IS 14543"][0]
    assert water_tr["test_clause"] is None

    no_clause_count = sum(1 for r in tr_rels if r["test_clause"] is None)
    assert no_clause_count == 102


# ---------------------------------------------------------------------------
# Test 8: Missing Sampling Requirement Remains Unknown
# ---------------------------------------------------------------------------
def test_08_missing_sampling_requirement_remains_unknown():
    """Where sampling evidence is absent, status is SAMPLING_REQUIREMENTS_UNKNOWN with no synthetic defaults."""
    tp_rels = load_jsonl(PC4_DIR / "testing_process_relationships.jsonl")
    unknown_sampling = [r for r in tp_rels if r["sampling_status"] == SamplingRequirementStatus.SAMPLING_REQUIREMENTS_UNKNOWN]
    assert len(unknown_sampling) == 306
    for rec in unknown_sampling:
        assert len(rec["associated_sampling_ids"]) == 0


# ---------------------------------------------------------------------------
# Test 9: Testing Evidence Does NOT Imply Mandatory Certification
# ---------------------------------------------------------------------------
def test_09_testing_evidence_does_not_imply_mandatory_certification():
    """Testing requirements confirmed does NOT upgrade or alter PC-3 mandatory certification status."""
    tp_rels = load_jsonl(PC4_DIR / "testing_process_relationships.jsonl")
    # Ceiling fans (IS 374) and Plugs (IS 1293) have confirmed SIT testing, but QCO_CONFLICT in PC-3
    conflicted_with_sit = [
        r for r in tp_rels
        if r["testing_status"] == TestingRequirementStatus.TESTING_REQUIREMENTS_CONFIRMED
        and r["mandatory_certification_status"] == "QCO_CONFLICT"
    ]
    assert len(conflicted_with_sit) > 0
    for rec in conflicted_with_sit:
        assert rec["qco_status"] == "QCO_CONFLICT"
        assert rec["mandatory_certification_status"] == "QCO_CONFLICT"


# ---------------------------------------------------------------------------
# Test 10: Generic BIS Process Does NOT Imply Product-Specific Process
# ---------------------------------------------------------------------------
def test_10_generic_bis_process_does_not_imply_product_specific_process():
    """Generic Scheme I procedures from PC-2 are NOT stamped as confirmed product processes."""
    tp_rels = load_jsonl(PC4_DIR / "testing_process_relationships.jsonl")
    confirmed_process = [r for r in tp_rels if r["certification_process_status"] == CertificationProcessStatus.CERTIFICATION_PROCESS_CONFIRMED]
    assert len(confirmed_process) == 0, "Zero products should have CONFIRMED certification process because scheme is unestablished"

    for r in tp_rels:
        assert len(r["associated_procedure_ids"]) == 0


# ---------------------------------------------------------------------------
# Test 11: Scheme Definition Does NOT Imply Scheme Applicability
# ---------------------------------------------------------------------------
def test_11_scheme_definition_does_not_imply_scheme_applicability():
    """100% of composite records retain CERTIFICATION_SCHEME_UNKNOWN from PC-3."""
    tp_rels = load_jsonl(PC4_DIR / "testing_process_relationships.jsonl")
    assert len(tp_rels) == 665
    for r in tp_rels:
        assert r["scheme_applicability_status"] == "CERTIFICATION_SCHEME_UNKNOWN"


# ---------------------------------------------------------------------------
# Test 12: QCO Conflict Remains Preserved
# ---------------------------------------------------------------------------
def test_12_qco_conflict_remains_preserved():
    """All 37 QCO conflict states from PC-3 remain preserved in PC-4."""
    tp_rels = load_jsonl(PC4_DIR / "testing_process_relationships.jsonl")
    qco_conflicts = [r for r in tp_rels if r["qco_status"] == "QCO_CONFLICT"]
    assert len(qco_conflicts) == 37
    for r in qco_conflicts:
        assert r["mandatory_certification_status"] == "QCO_CONFLICT"


# ---------------------------------------------------------------------------
# Test 13: QCO Unknown Remains Preserved
# ---------------------------------------------------------------------------
def test_13_qco_unknown_remains_preserved():
    """All 8 QCO status unknown states from PC-3 remain preserved in PC-4."""
    tp_rels = load_jsonl(PC4_DIR / "testing_process_relationships.jsonl")
    qco_unknowns = [r for r in tp_rels if r["qco_status"] == "QCO_STATUS_UNKNOWN"]
    assert len(qco_unknowns) == 8
    for r in qco_unknowns:
        assert r["mandatory_certification_status"] == "QCO_STATUS_UNKNOWN"


# ---------------------------------------------------------------------------
# Test 14: No Laboratory Qualification Performed by PC-4
# ---------------------------------------------------------------------------
def test_14_no_laboratory_qualification_performed_by_pc4():
    """PC-4 creates test requirements only; zero laboratory qualification, ranking, or selection."""
    files = [
        "testing_requirement_relationships.jsonl",
        "inspection_requirement_relationships.jsonl",
        "sampling_requirement_relationships.jsonl",
        "testing_process_relationships.jsonl",
    ]
    for fname in files:
        records = load_jsonl(PC4_DIR / fname)
        for rec in records:
            assert "laboratory_id" not in rec
            assert "qualified_laboratories" not in rec
            assert "laboratory_ranking" not in rec
            assert "nearest_laboratory" not in rec


# ---------------------------------------------------------------------------
# Test 15: Provenance Completeness
# ---------------------------------------------------------------------------
def test_15_provenance_completeness():
    """Every record across all 4 PC-4 relationship files has non-empty provenance and zero orphans."""
    files = [
        "testing_requirement_relationships.jsonl",
        "inspection_requirement_relationships.jsonl",
        "sampling_requirement_relationships.jsonl",
        "testing_process_relationships.jsonl",
    ]
    for fname in files:
        records = load_jsonl(PC4_DIR / fname)
        assert len(records) > 0, f"File {fname} is empty"
        for rec in records:
            prov = rec.get("provenance")
            assert prov is not None, f"Missing provenance in {fname}: {rec}"
            assert len(prov.get("source_record_ids", [])) > 0, f"Missing source_record_ids in {fname}"
            assert prov.get("source_verification_state") in ("SOURCE_VERIFIED", "SOURCE_UNVERIFIED")


# ---------------------------------------------------------------------------
# Test 16: Duplicate Relationship Prevention
# ---------------------------------------------------------------------------
def test_16_duplicate_relationship_prevention():
    """All primary keys and composite tuples are strictly unique across PC-4 files."""
    # 1. Testing requirement relationships
    tr_rels = load_jsonl(PC4_DIR / "testing_requirement_relationships.jsonl")
    assert len(tr_rels) == 120
    tr_keys = {r["relationship_id"] for r in tr_rels}
    assert len(tr_keys) == 120
    tr_stds = {r["standard_normalized"] for r in tr_rels}
    assert len(tr_stds) == 120

    # 2. Inspection requirement relationships
    ir_rels = load_jsonl(PC4_DIR / "inspection_requirement_relationships.jsonl")
    assert len(ir_rels) == 120
    ir_keys = {r["relationship_id"] for r in ir_rels}
    assert len(ir_keys) == 120

    # 3. Sampling requirement relationships
    sr_rels = load_jsonl(PC4_DIR / "sampling_requirement_relationships.jsonl")
    assert len(sr_rels) == 120
    sr_keys = {r["relationship_id"] for r in sr_rels}
    assert len(sr_keys) == 120

    # 4. Composite testing process relationships
    tp_rels = load_jsonl(PC4_DIR / "testing_process_relationships.jsonl")
    assert len(tp_rels) == 665
    tp_keys = {r["relationship_id"] for r in tp_rels}
    assert len(tp_keys) == 665
    tp_pairs = {(r["product_name"], r["standard_normalized"]) for r in tp_rels}
    assert len(tp_pairs) == 665


# ---------------------------------------------------------------------------
# Test 17: Deterministic Rebuild
# ---------------------------------------------------------------------------
def test_17_deterministic_rebuild():
    """Rebuilding produces byte-identical files with matching SHA-256 hashes."""
    from scripts.compliance.build_pc4_testing_process import build_pc4_testing_process

    manifest_path = METADATA_DIR / "testing_process_manifest.json"
    assert manifest_path.exists()
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    expected_hashes = manifest["artifact_hashes"]

    # Trigger rebuild
    build_pc4_testing_process()

    # Re-verify hashes
    files = [
        "testing_requirement_relationships.jsonl",
        "inspection_requirement_relationships.jsonl",
        "sampling_requirement_relationships.jsonl",
        "testing_process_relationships.jsonl",
    ]
    for fname in files:
        fpath = PC4_DIR / fname
        current_hash = compute_sha256(fpath)
        assert current_hash == expected_hashes[fname], f"Hash mismatch for {fname}: expected {expected_hashes[fname]}, got {current_hash}"


# ---------------------------------------------------------------------------
# Test 18: Frozen PC-3 and Earlier Subsystems Immutability
# ---------------------------------------------------------------------------
def test_18_frozen_pc3_immutability():
    """All frozen PC-3 relationship files match their manifest SHA-256 hashes bitwise."""
    pc3_manifest_path = PC3_DIR / "metadata" / "relationship_manifest.json"
    assert pc3_manifest_path.exists()
    with open(pc3_manifest_path, "r", encoding="utf-8") as f:
        pc3_manifest = json.load(f)

    for fname, exp_hash in pc3_manifest["artifact_hashes"].items():
        assert compute_sha256(PC3_DIR / fname) == exp_hash, f"PC-3 file {fname} was modified!"

    # Check frozen application files exist
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
        assert (PROJECT_ROOT / rel_path).exists(), f"Frozen file missing: {rel_path}"
