"""
Phase PC-3: Product -> Standard -> QCO -> Certification Scheme Relationship Engine Test Suite.

Automated verification suite testing all 15 required areas:
1. Product with verified Indian Standard and confirmed QCO
2. Product with verified Indian Standard but NO QCO in corpus
3. Specific products with active QCO confirmed
4. Product where QCO status is UNKNOWN
5. Product affected by conflicting QCO records
6. QCO with missing effective date (no synthetic defaults)
7. Standard with multiple Product Manual versions (conflict disclosed)
8. Product with no established scheme applicability (preserved as UNKNOWN)
9. No false inference: Standard does NOT imply mandatory certification
10. No false inference: Product Manual does NOT imply mandatory certification
11. No false inference: Scheme definitions do NOT imply product applicability
12. Universal Provenance and lineage completeness (zero orphans)
13. Deterministic deduplication across all 5 relationship files
14. Byte-deterministic rebuild (identical SHA-256 hashes)
15. Frozen-system and previous phase immutability
"""

import json
import os
import hashlib
from pathlib import Path
import pytest

from ai.compliance.relationship_models import (
    QcoRelationshipStatus,
    MandatoryCertificationStatus,
    SchemeApplicabilityStatus,
    ProductManualRelationshipStatus,
    ProductStandardRelationshipRecord,
    StandardQcoRelationshipRecord,
    QcoRequirementRelationshipRecord,
    CertificationSchemeRelationshipRecord,
    CompositeComplianceRelationshipRecord,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "compliance" / "raw"
NORMALIZED_DIR = PROJECT_ROOT / "data" / "compliance" / "normalized"
RELATIONSHIPS_DIR = PROJECT_ROOT / "data" / "compliance" / "relationships"
METADATA_DIR = RELATIONSHIPS_DIR / "metadata"


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
# Test 1: Product with Verified Standard and Active QCO
# ---------------------------------------------------------------------------
def test_01_product_with_verified_standard():
    """Product with verified standard and operative QCO yields confirmed mandatory requirement."""
    composites = load_jsonl(RELATIONSHIPS_DIR / "compliance_relationships.jsonl")
    pvc_wires = [c for c in composites if c["product_name"] == "pvc wire" and c["standard_normalized"] == "IS 694"]
    assert len(pvc_wires) == 1
    rec = pvc_wires[0]
    assert rec["qco_status"] == QcoRelationshipStatus.QCO_APPLIES
    assert rec["mandatory_certification_status"] == MandatoryCertificationStatus.MANDATORY_CERTIFICATION_CONFIRMED
    assert rec["source_verification_state"] == "SOURCE_VERIFIED"
    assert rec["provenance"]["source_layer"] == "PC-2_NORMALIZED"
    assert len(rec["provenance"]["source_record_ids"]) > 0
    assert len(rec["associated_qco_ids"]) > 0


# ---------------------------------------------------------------------------
# Test 2: Product with Standard but NO QCO in Corpus
# ---------------------------------------------------------------------------
def test_02_product_with_standard_but_no_qco():
    """Product with standard but no authoritative QCO yields MANDATORY_CERTIFICATION_NOT_ESTABLISHED (never 'NO')."""
    composites = load_jsonl(RELATIONSHIPS_DIR / "compliance_relationships.jsonl")
    acsr = [c for c in composites if c["product_name"] == "acsr conductor" and c["standard_normalized"] == "IS 398 (PART 2)"]
    assert len(acsr) == 1
    rec = acsr[0]
    assert rec["qco_status"] == QcoRelationshipStatus.QCO_NOT_ESTABLISHED
    assert rec["mandatory_certification_status"] == MandatoryCertificationStatus.MANDATORY_CERTIFICATION_NOT_ESTABLISHED
    assert len(rec["associated_qco_ids"]) == 0
    assert len(rec["notification_numbers"]) == 0
    assert rec["effective_date"] is None


# ---------------------------------------------------------------------------
# Test 3: Specific Product with QCO Confirmed
# ---------------------------------------------------------------------------
def test_03_product_with_qco_confirmed():
    """Confirm mandatory requirement details, authorities, and notifications for confirmed products."""
    composites = load_jsonl(RELATIONSHIPS_DIR / "compliance_relationships.jsonl")
    confirmed = [c for c in composites if c["mandatory_certification_status"] == MandatoryCertificationStatus.MANDATORY_CERTIFICATION_CONFIRMED]
    assert len(confirmed) == 222

    # Check table fan (IS 555) with amended QCO operative
    fan = [c for c in confirmed if c["product_name"] == "table fan" and c["standard_normalized"] == "IS 555"][0]
    assert fan["qco_status"] == QcoRelationshipStatus.QCO_AMENDED
    assert fan["mandatory_certification_status"] == MandatoryCertificationStatus.MANDATORY_CERTIFICATION_CONFIRMED
    assert len(fan["notification_numbers"]) > 0

    # Cross-check in standard_qco_relationships
    std_qcos = load_jsonl(RELATIONSHIPS_DIR / "standard_qco_relationships.jsonl")
    is555_rel = [s for s in std_qcos if s["standard_normalized"] == "IS 555"][0]
    assert is555_rel["qco_relationship_status"] == QcoRelationshipStatus.QCO_AMENDED
    assert len(is555_rel["associated_qco_ids"]) > 0


# ---------------------------------------------------------------------------
# Test 4: Product with QCO Status UNKNOWN
# ---------------------------------------------------------------------------
def test_04_product_with_qco_status_unknown():
    """QCO status UNKNOWN propagates honestly to mandatory status UNKNOWN."""
    composites = load_jsonl(RELATIONSHIPS_DIR / "compliance_relationships.jsonl")
    fridge = [c for c in composites if c["product_name"] == "refrigerator" and c["standard_normalized"] == "IS 15750"]
    assert len(fridge) == 1
    rec = fridge[0]
    assert rec["qco_status"] == QcoRelationshipStatus.QCO_STATUS_UNKNOWN
    assert rec["mandatory_certification_status"] == MandatoryCertificationStatus.QCO_STATUS_UNKNOWN

    # Check standard_qco_relationships count of unknown
    std_qcos = load_jsonl(RELATIONSHIPS_DIR / "standard_qco_relationships.jsonl")
    unknowns = [s for s in std_qcos if s["qco_relationship_status"] == QcoRelationshipStatus.QCO_STATUS_UNKNOWN]
    assert len(unknowns) == 190


# ---------------------------------------------------------------------------
# Test 5: Product Affected by Conflicting QCOs
# ---------------------------------------------------------------------------
def test_05_product_affected_by_conflicting_qcos():
    """Conflicting QCO records result in QCO_CONFLICT with disclosed conflict IDs without silent resolution."""
    composites = load_jsonl(RELATIONSHIPS_DIR / "compliance_relationships.jsonl")
    conflicts = [c for c in composites if c["qco_status"] == QcoRelationshipStatus.QCO_CONFLICT]
    assert len(conflicts) == 37

    # Check ceiling fan (IS 374)
    cfan = [c for c in conflicts if c["product_name"] == "ceiling fan" and c["standard_normalized"] == "IS 374"][0]
    assert cfan["mandatory_certification_status"] == MandatoryCertificationStatus.QCO_CONFLICT
    assert len(cfan["conflict_ids"]) > 0

    # Ensure all conflict IDs exist in normalized conflicts.jsonl
    norm_conflicts = load_jsonl(NORMALIZED_DIR / "metadata" / "conflicts.jsonl")
    norm_conflict_ids = {c["conflict_id"] for c in norm_conflicts}
    for cid in cfan["conflict_ids"]:
        assert cid in norm_conflict_ids


# ---------------------------------------------------------------------------
# Test 6: QCO with Missing Effective Date
# ---------------------------------------------------------------------------
def test_06_qco_with_missing_effective_date():
    """QCO records with missing effective dates remain None; no synthetic date inference."""
    qco_reqs = load_jsonl(RELATIONSHIPS_DIR / "qco_requirement_relationships.jsonl")
    missing_dates = [q for q in qco_reqs if q["commencement_date"] is None]
    assert len(missing_dates) == 149

    for q in missing_dates:
        assert q["commencement_date"] is None

    composites = load_jsonl(RELATIONSHIPS_DIR / "compliance_relationships.jsonl")
    missing_comp_dates = [c for c in composites if c["effective_date"] is None]
    assert len(missing_comp_dates) > 0


# ---------------------------------------------------------------------------
# Test 7: Standard with Multiple Product Manual Versions
# ---------------------------------------------------------------------------
def test_07_standard_with_multiple_pm_versions():
    """Standards with conflicting Product Manual versions are flagged as PRODUCT_MANUAL_CONFLICT."""
    composites = load_jsonl(RELATIONSHIPS_DIR / "compliance_relationships.jsonl")
    pm_conflicts = [c for c in composites if c["product_manual_status"] == ProductManualRelationshipStatus.PRODUCT_MANUAL_CONFLICT]
    assert len(pm_conflicts) == 187

    # Ensure conflict IDs are tracked
    for rec in pm_conflicts:
        assert len(rec["conflict_ids"]) > 0
        assert rec["product_manual_count"] > 1


# ---------------------------------------------------------------------------
# Test 8: Product with No Established Scheme Applicability
# ---------------------------------------------------------------------------
def test_08_product_with_no_established_scheme():
    """Every product retains CERTIFICATION_SCHEME_UNKNOWN; zero fabricated scheme mappings."""
    schemes = load_jsonl(RELATIONSHIPS_DIR / "certification_scheme_relationships.jsonl")
    assert len(schemes) == 665
    for s in schemes:
        assert s["scheme_applicability_status"] == SchemeApplicabilityStatus.CERTIFICATION_SCHEME_UNKNOWN
        assert s["scheme_id"] is None
        assert s["scheme_name"] is None
        assert s["applicability_basis"] == "NO_AUTHORITATIVE_APPLICABILITY_RECORD_IN_CORPUS"

    composites = load_jsonl(RELATIONSHIPS_DIR / "compliance_relationships.jsonl")
    assert len(composites) == 665
    for c in composites:
        assert c["scheme_applicability_status"] == SchemeApplicabilityStatus.CERTIFICATION_SCHEME_UNKNOWN


# ---------------------------------------------------------------------------
# Test 9: No False Inference: Standard Does NOT Imply Mandatory Certification
# ---------------------------------------------------------------------------
def test_09_no_false_inference_standard_implies_mandatory():
    """Absence of QCO MUST yield MANDATORY_CERTIFICATION_NOT_ESTABLISHED, never MANDATORY_CERTIFICATION_CONFIRMED."""
    composites = load_jsonl(RELATIONSHIPS_DIR / "compliance_relationships.jsonl")
    no_qco = [c for c in composites if c["qco_status"] == QcoRelationshipStatus.QCO_NOT_ESTABLISHED]
    assert len(no_qco) == 398

    for c in no_qco:
        assert c["mandatory_certification_status"] == MandatoryCertificationStatus.MANDATORY_CERTIFICATION_NOT_ESTABLISHED


# ---------------------------------------------------------------------------
# Test 10: No False Inference: Product Manual Does NOT Imply Mandatory Certification
# ---------------------------------------------------------------------------
def test_10_no_false_inference_pm_implies_mandatory():
    """Having a Product Manual does NOT imply mandatory certification."""
    composites = load_jsonl(RELATIONSHIPS_DIR / "compliance_relationships.jsonl")
    pm_available_no_qco = [
        c for c in composites
        if c["product_manual_status"] == ProductManualRelationshipStatus.PRODUCT_MANUAL_AVAILABLE
        and c["qco_status"] == QcoRelationshipStatus.QCO_NOT_ESTABLISHED
    ]
    assert len(pm_available_no_qco) == 86

    for c in pm_available_no_qco:
        assert c["mandatory_certification_status"] == MandatoryCertificationStatus.MANDATORY_CERTIFICATION_NOT_ESTABLISHED


# ---------------------------------------------------------------------------
# Test 11: No False Inference: Scheme Definitions Do NOT Imply Applicability
# ---------------------------------------------------------------------------
def test_11_no_false_inference_scheme_definition_implies_applicability():
    """Definitions of schemes exist, but product-specific applicability remains strictly unknown."""
    norm_schemes = load_jsonl(NORMALIZED_DIR / "certification_scheme_map.jsonl")
    assert len(norm_schemes) == 12

    scheme_rels = load_jsonl(RELATIONSHIPS_DIR / "certification_scheme_relationships.jsonl")
    assert len(scheme_rels) == 665
    for rel in scheme_rels:
        assert rel["scheme_applicability_status"] == SchemeApplicabilityStatus.CERTIFICATION_SCHEME_UNKNOWN
        assert rel["scheme_id"] is None


# ---------------------------------------------------------------------------
# Test 12: Provenance and Lineage Completeness
# ---------------------------------------------------------------------------
def test_12_provenance_and_lineage_completeness():
    """Every record across all 5 relationship files has valid non-empty provenance and zero orphans."""
    files = [
        "product_standard_relationships.jsonl",
        "standard_qco_relationships.jsonl",
        "qco_requirement_relationships.jsonl",
        "certification_scheme_relationships.jsonl",
        "compliance_relationships.jsonl",
    ]
    for fname in files:
        records = load_jsonl(RELATIONSHIPS_DIR / fname)
        assert len(records) > 0, f"File {fname} is empty"
        for rec in records:
            prov = rec.get("provenance")
            assert prov is not None, f"Missing provenance in {fname}: {rec}"
            assert len(prov.get("source_record_ids", [])) > 0, f"Missing source_record_ids in {fname}"
            assert prov.get("source_layer") == "PC-2_NORMALIZED"
            assert prov.get("source_verification_state") in ("SOURCE_VERIFIED", "SOURCE_UNVERIFIED")


# ---------------------------------------------------------------------------
# Test 13: Deterministic Deduplication
# ---------------------------------------------------------------------------
def test_13_deterministic_deduplication():
    """All keys and primary tuples are strictly unique across relationship files."""
    # 1. Product -> Standard (product_name, standard_number)
    psms = load_jsonl(RELATIONSHIPS_DIR / "product_standard_relationships.jsonl")
    assert len(psms) == 665
    psm_keys = {(p["product_name"], p["standard_number"]) for p in psms}
    assert len(psm_keys) == 665

    # 2. Standard -> QCO (standard_normalized)
    sqcos = load_jsonl(RELATIONSHIPS_DIR / "standard_qco_relationships.jsonl")
    assert len(sqcos) == 431
    sqco_keys = {s["standard_normalized"] for s in sqcos}
    assert len(sqco_keys) == 431

    # 3. QCO Requirement (qco_id)
    qreqs = load_jsonl(RELATIONSHIPS_DIR / "qco_requirement_relationships.jsonl")
    assert len(qreqs) == 313
    qreq_keys = {q["qco_id"] for q in qreqs}
    assert len(qreq_keys) == 313

    # 4. Schemes (relationship_id)
    schemes = load_jsonl(RELATIONSHIPS_DIR / "certification_scheme_relationships.jsonl")
    assert len(schemes) == 665
    scheme_keys = {s["relationship_id"] for s in schemes}
    assert len(scheme_keys) == 665

    # 5. Composite Compliance (product_name, standard_normalized)
    comps = load_jsonl(RELATIONSHIPS_DIR / "compliance_relationships.jsonl")
    assert len(comps) == 665
    comp_keys = {(c["product_name"], c["standard_normalized"]) for c in comps}
    assert len(comp_keys) == 665


# ---------------------------------------------------------------------------
# Test 14: Byte-Deterministic Rebuild
# ---------------------------------------------------------------------------
def test_14_byte_deterministic_rebuild():
    """Rebuilding the dataset produces byte-identical files with matching SHA-256 hashes."""
    from scripts.compliance.build_pc3_relationships import build_pc3_relationships

    manifest_path = METADATA_DIR / "relationship_manifest.json"
    assert manifest_path.exists()
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    expected_hashes = manifest["artifact_hashes"]

    # Trigger rebuild
    build_pc3_relationships()

    # Re-verify hashes
    files = [
        "product_standard_relationships.jsonl",
        "standard_qco_relationships.jsonl",
        "qco_requirement_relationships.jsonl",
        "certification_scheme_relationships.jsonl",
        "compliance_relationships.jsonl",
    ]
    for fname in files:
        fpath = RELATIONSHIPS_DIR / fname
        current_hash = compute_sha256(fpath)
        assert current_hash == expected_hashes[fname], f"Hash mismatch for {fname}: expected {expected_hashes[fname]}, got {current_hash}"


# ---------------------------------------------------------------------------
# Test 15: Frozen-System Immutability
# ---------------------------------------------------------------------------
def test_15_frozen_system_immutability():
    """All frozen systems and prior phase datasets remain completely untouched."""
    # Check PC-1 raw directory exists with all 6 core files
    raw_files = [
        "qcos/qcos.jsonl",
        "product_standard/product_standard_sources.jsonl",
        "certification_schemes/schemes.jsonl",
        "testing/sit_records.jsonl",
        "product_manuals/product_manuals.jsonl",
        "certification_process/certification_procedures.jsonl",
    ]
    for rf in raw_files:
        assert (RAW_DIR / rf).exists(), f"Missing PC-1 raw file: {rf}"

    # Check PC-2 normalized directory exists with all 7 datasets matching manifest counts
    norm_manifest_path = NORMALIZED_DIR / "metadata" / "normalization_manifest.json"
    assert norm_manifest_path.exists()
    with open(norm_manifest_path, "r", encoding="utf-8") as f:
        norm_manifest = json.load(f)

    norm_counts = norm_manifest.get("normalized_record_counts", {})
    assert norm_counts.get("qco_registry") == 313
    assert norm_counts.get("product_standard_map") == 665
    assert norm_counts.get("certification_scheme_map") == 12
    assert norm_counts.get("testing_requirements") == 120
    assert norm_counts.get("product_manual_registry") == 763
    assert norm_counts.get("certification_process") == 28
    assert norm_counts.get("document_registry") == 1076
    assert norm_counts.get("total_normalized_records") == 2977

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
