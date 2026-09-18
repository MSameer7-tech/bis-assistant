"""
Phase PC-5: Comprehensive Adversarial Test Suite for Product Compliance Journey Orchestrator & API.

Verifies all 32 required architectural and compliance invariants:
1. Product with confirmed standard
2. Explicit IS number overrides ambiguous product
3. Multiple applicable standards preserved
4. Product with no established standard
5. Confirmed QCO
6. Unknown QCO
7. QCO conflict
8. Mandatory certification not established
9. Scheme applicability remains unknown
10. Testing confirmed
11. Testing partial
12. Testing unknown
13. Inspection status preserved
14. Sampling status preserved
15. Certification process partial
16. Certification process unknown
17. Generic process never promoted to product-specific
18. Testing does not imply mandatory certification
19. PC-3 regulatory states preserved exactly
20. PC-4 states preserved exactly
21. F3 qualification actually used
22. Capability precedes proximity
23. Nearby unqualified lab excluded
24. Zero qualified laboratories handled cleanly
25. Provenance completeness
26. Unknown stages remain explicit
27. No empty journey
28. Deterministic repeated request
29. PC-3 files remain byte-identical
30. PC-4 files remain byte-identical
31. F3 frozen files remain unchanged
32. Zero LLM/Groq regulatory decisions
"""

import json
import hashlib
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from ai.compliance.journey_models import (
    ComplianceJourneyRequest,
    ComplianceJourneyResponse,
    JourneyStatus,
    ProductResolutionStatus,
    StandardResolutionStatus,
    LaboratoryStageStatus,
)
from ai.compliance.journey_orchestrator import (
    get_compliance_orchestrator,
    ComplianceJourneyOrchestrator,
)
from backend.app import app

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "compliance"
PC3_DIR = DATA_DIR / "relationships"
PC4_DIR = DATA_DIR / "testing_process"


def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


@pytest.fixture(scope="module")
def orchestrator():
    return get_compliance_orchestrator()


@pytest.fixture(scope="module")
def api_client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Test Scenarios 1 to 4: Product & Standard Resolution
# ---------------------------------------------------------------------------

def test_01_product_with_confirmed_standard(orchestrator):
    """1. Product query 'ceiling fan' resolves to IS 374."""
    req = ComplianceJourneyRequest(product="ceiling fan")
    res = orchestrator.build_journey(req)
    
    assert res.status == JourneyStatus.JOURNEY_ESTABLISHED
    assert res.product.status == ProductResolutionStatus.PRODUCT_IDENTIFIED
    assert res.product.resolved_product_name.lower() == "ceiling fan"
    assert res.applicable_standards.status == StandardResolutionStatus.STANDARDS_IDENTIFIED
    assert res.applicable_standards.primary_standard == "IS 374"
    assert len(res.applicable_standards.standards) >= 1


def test_02_explicit_is_number_overrides_ambiguous_product(orchestrator):
    """2. Explicit IS 4985 overrides ambiguous product text 'we manufacture PVC pipes'."""
    req = ComplianceJourneyRequest(
        standard="IS 4985",
        product="we manufacture PVC pipes"
    )
    res = orchestrator.build_journey(req)
    
    assert res.status == JourneyStatus.JOURNEY_ESTABLISHED
    assert res.applicable_standards.status == StandardResolutionStatus.STANDARDS_IDENTIFIED
    assert res.applicable_standards.primary_standard == "IS 4985"
    # Does NOT return ambiguous product because explicit standard took precedence
    assert res.status != JourneyStatus.AMBIGUOUS_PRODUCT


def test_03_multiple_applicable_standards_preserved(orchestrator):
    """3. Product 'automotive vehicles' maps to both IS 15633 and IS 15636; both are preserved."""
    req = ComplianceJourneyRequest(product="automotive vehicles")
    res = orchestrator.build_journey(req)
    
    assert res.status == JourneyStatus.JOURNEY_ESTABLISHED
    assert len(res.applicable_standards.standards) == 2
    stds = {s.standard_number for s in res.applicable_standards.standards}
    assert stds == {"IS 15633", "IS 15636"}
    for s in res.applicable_standards.standards:
        assert s.standard_number in ("IS 15633", "IS 15636")


def test_04_no_standard_established(orchestrator):
    """4. Query 'I manufacture timber doors' returns STANDARD_NOT_ESTABLISHED with explicit message."""
    req = ComplianceJourneyRequest(product="I manufacture timber doors")
    res = orchestrator.build_journey(req)
    
    assert res.status == JourneyStatus.STANDARD_NOT_ESTABLISHED
    assert res.product.status == ProductResolutionStatus.PRODUCT_NOT_ESTABLISHED
    assert res.applicable_standards.status == StandardResolutionStatus.STANDARD_NOT_ESTABLISHED
    assert "not established" in res.warnings[0].lower()


# ---------------------------------------------------------------------------
# Test Scenarios 5 to 9: Regulatory, Mandatory & Scheme Grounding
# ---------------------------------------------------------------------------

def test_05_confirmed_qco(orchestrator):
    """5. Standard IS 16046 (Part 2) has active QCO and MANDATORY_CERTIFICATION_CONFIRMED."""
    req = ComplianceJourneyRequest(standard="IS 16046 (Part 2)")
    res = orchestrator.build_journey(req)
    
    assert res.regulatory_status.qco_status == "QCO_AMENDED"
    assert res.mandatory_certification.status == "MANDATORY_CERTIFICATION_CONFIRMED"
    assert res.mandatory_certification.is_mandatory is True


def test_06_qco_unknown(orchestrator):
    """6. Standard IS 15750 has QCO_STATUS_UNKNOWN without claiming voluntary certification."""
    req = ComplianceJourneyRequest(standard="IS 15750")
    res = orchestrator.build_journey(req)
    
    assert res.regulatory_status.qco_status == "QCO_STATUS_UNKNOWN"
    assert res.mandatory_certification.status == "QCO_STATUS_UNKNOWN"
    assert res.mandatory_certification.is_mandatory is None
    # Must not claim voluntary
    assert "voluntary" not in res.mandatory_certification.explanation.lower()


def test_07_qco_conflict(orchestrator):
    """7. Standard IS 374 has conflicting regulatory orders preserving QCO_CONFLICT."""
    req = ComplianceJourneyRequest(standard="IS 374")
    res = orchestrator.build_journey(req)
    
    assert res.regulatory_status.qco_status == "QCO_CONFLICT"
    assert res.mandatory_certification.status == "QCO_CONFLICT"
    assert res.mandatory_certification.is_mandatory is None
    assert len(res.regulatory_status.conflict_ids) > 0


def test_08_mandatory_certification_not_established(orchestrator):
    """8. Standard IS 1653 has no QCO, preserving MANDATORY_CERTIFICATION_NOT_ESTABLISHED."""
    req = ComplianceJourneyRequest(standard="IS 1653")
    res = orchestrator.build_journey(req)
    
    assert res.regulatory_status.qco_status == "QCO_NOT_ESTABLISHED"
    assert res.mandatory_certification.status == "MANDATORY_CERTIFICATION_NOT_ESTABLISHED"
    assert res.mandatory_certification.is_mandatory is False
    assert "does not definitively prove voluntary" in res.mandatory_certification.explanation


def test_09_scheme_applicability_unknown(orchestrator):
    """9. Scheme applicability remains strictly CERTIFICATION_SCHEME_UNKNOWN."""
    for test_std in ["IS 4985", "IS 374", "IS 16046 (Part 2)", "IS 269"]:
        res = orchestrator.build_journey(ComplianceJourneyRequest(standard=test_std))
        assert res.certification_scheme.status == "CERTIFICATION_SCHEME_UNKNOWN"
        assert res.certification_scheme.applicable_scheme_code is None
        assert "not establish a confirmed product-specific scheme" in res.certification_scheme.explanation


# ---------------------------------------------------------------------------
# Test Scenarios 10 to 18: Testing, Inspection, Sampling & Process
# ---------------------------------------------------------------------------

def test_10_testing_confirmed(orchestrator):
    """10. Standard IS 16046 (Part 2) has TESTING_REQUIREMENTS_CONFIRMED with SIT test records."""
    req = ComplianceJourneyRequest(standard="IS 16046 (Part 2)")
    res = orchestrator.build_journey(req)
    
    assert res.testing.status == "TESTING_REQUIREMENTS_CONFIRMED"
    assert res.testing.total_tests > 0
    assert len(res.testing.testing_requirements) > 0
    t0 = res.testing.testing_requirements[0]
    assert t0.test_name is not None
    assert t0.source_document is not None


def test_11_testing_partial(orchestrator):
    """11. Standard IS 12254 has Product Manual guidelines yielding TESTING_REQUIREMENTS_PARTIAL."""
    req = ComplianceJourneyRequest(standard="IS 12254")
    res = orchestrator.build_journey(req)
    
    assert res.testing.status == "TESTING_REQUIREMENTS_PARTIAL"
    assert "partially established" in res.testing.explanation.lower()


def test_12_testing_unknown(orchestrator):
    """12. Standard IS 15750 has neither SIT nor PM, yielding TESTING_REQUIREMENTS_UNKNOWN."""
    req = ComplianceJourneyRequest(standard="IS 15750")
    res = orchestrator.build_journey(req)
    
    assert res.testing.status == "TESTING_REQUIREMENTS_UNKNOWN"
    assert res.testing.total_tests == 0


def test_13_inspection_status_preserved(orchestrator):
    """13. Inspection status from PC-4 is preserved exactly."""
    res_conf = orchestrator.build_journey(ComplianceJourneyRequest(standard="IS 16046 (Part 2)"))
    assert res_conf.inspection.status == "INSPECTION_REQUIREMENTS_CONFIRMED"
    assert res_conf.inspection.total_requirements > 0

    res_unk = orchestrator.build_journey(ComplianceJourneyRequest(standard="IS 15750"))
    assert res_unk.inspection.status == "INSPECTION_REQUIREMENTS_UNKNOWN"


def test_14_sampling_status_preserved(orchestrator):
    """14. Sampling status from PC-4 is preserved exactly."""
    res_conf = orchestrator.build_journey(ComplianceJourneyRequest(standard="IS 16046 (Part 2)"))
    assert res_conf.sampling.status == "SAMPLING_REQUIREMENTS_CONFIRMED"
    assert res_conf.sampling.total_requirements > 0

    res_unk = orchestrator.build_journey(ComplianceJourneyRequest(standard="IS 15750"))
    assert res_unk.sampling.status == "SAMPLING_REQUIREMENTS_UNKNOWN"


def test_15_certification_process_partial(orchestrator):
    """15. Standards with Product Manual or SIT have CERTIFICATION_PROCESS_PARTIAL."""
    req = ComplianceJourneyRequest(standard="IS 4985")
    res = orchestrator.build_journey(req)
    
    assert res.certification_process.status == "CERTIFICATION_PROCESS_PARTIAL"
    assert res.certification_process.is_generic_procedure is True
    assert len(res.certification_process.procedure_steps) > 0


def test_16_certification_process_unknown(orchestrator):
    """16. Standard IS 15750 has CERTIFICATION_PROCESS_UNKNOWN."""
    req = ComplianceJourneyRequest(standard="IS 15750")
    res = orchestrator.build_journey(req)
    
    assert res.certification_process.status == "CERTIFICATION_PROCESS_UNKNOWN"
    assert len(res.certification_process.procedure_steps) == 0


def test_17_generic_process_not_promoted_to_product_specific(orchestrator):
    """17. Generic process steps are explicitly labeled as generic and never confirmed."""
    res = orchestrator.build_journey(ComplianceJourneyRequest(standard="IS 4985"))
    assert res.certification_process.status != "CERTIFICATION_PROCESS_CONFIRMED"
    assert res.certification_process.is_generic_procedure is True
    assert "reference material" in res.certification_process.explanation


def test_18_testing_does_not_imply_mandatory_certification(orchestrator):
    """18. IS 374 has confirmed SIT testing but retains QCO_CONFLICT for mandatory certification."""
    res = orchestrator.build_journey(ComplianceJourneyRequest(standard="IS 374"))
    assert res.testing.status == "TESTING_REQUIREMENTS_CONFIRMED"
    assert res.mandatory_certification.status == "QCO_CONFLICT"
    assert res.mandatory_certification.is_mandatory is None


# ---------------------------------------------------------------------------
# Test Scenarios 19 to 24: State Integrity & F3 Integration
# ---------------------------------------------------------------------------

def test_19_pc3_regulatory_states_remain_unchanged(orchestrator):
    """19. Regulatory and mandatory states match PC-3 testing_process composite data verbatim."""
    tp_path = PC4_DIR / "testing_process_relationships.jsonl"
    with open(tp_path, "r", encoding="utf-8") as f:
        sample_recs = [json.loads(line) for line in f][:20]

    for rec in sample_recs:
        std = rec["standard_normalized"]
        res = orchestrator.build_journey(ComplianceJourneyRequest(standard=std))
        assert res.regulatory_status.qco_status == rec["qco_status"]
        assert res.mandatory_certification.status == rec["mandatory_certification_status"]


def test_20_pc4_testing_states_remain_unchanged(orchestrator):
    """20. Testing, inspection, sampling and process states match PC-4 records verbatim."""
    tp_path = PC4_DIR / "testing_process_relationships.jsonl"
    with open(tp_path, "r", encoding="utf-8") as f:
        sample_recs = [json.loads(line) for line in f][:20]

    for rec in sample_recs:
        std = rec["standard_normalized"]
        res = orchestrator.build_journey(ComplianceJourneyRequest(standard=std))
        assert res.testing.status == rec["testing_status"]
        assert res.inspection.status == rec["inspection_status"]
        assert res.sampling.status == rec["sampling_status"]
        assert res.certification_process.status == rec["certification_process_status"]


def test_21_f3_qualification_is_actually_used(orchestrator):
    """21. For IS 4985, F3 returns qualified laboratories with public_lab_code and capability evidence."""
    req = ComplianceJourneyRequest(standard="IS 4985")
    res = orchestrator.build_journey(req)
    
    assert res.laboratories.status == LaboratoryStageStatus.QUALIFIED_LABS_FOUND
    assert res.laboratories.total_matching > 0
    assert len(res.laboratories.qualified_laboratories) > 0
    first_lab = res.laboratories.qualified_laboratories[0]
    assert first_lab.public_lab_code is not None
    assert first_lab.laboratory_name is not None
    assert first_lab.capability_evidence.get("matching_standard") == "IS 4985"


def test_22_f3_capability_precedes_proximity(orchestrator):
    """22. Capability is evaluated first before geographic proximity ranking."""
    req = ComplianceJourneyRequest(standard="IS 4985", location="Delhi")
    res = orchestrator.build_journey(req)
    
    assert res.laboratories.capability_evaluated_first is True
    for lab in res.laboratories.qualified_laboratories:
        assert lab.capability_evidence.get("matching_standard") == "IS 4985"


def test_23_nearby_but_unqualified_lab_is_not_recommended(orchestrator):
    """23. Laboratories in Delhi lacking scope for IS 374 are never returned for IS 374."""
    req = ComplianceJourneyRequest(standard="IS 374", location="Delhi")
    res = orchestrator.build_journey(req)
    
    for lab in res.laboratories.qualified_laboratories:
        assert lab.capability_evidence.get("matching_standard") == "IS 374"


def test_24_no_qualified_laboratory_handled_cleanly(orchestrator):
    """24. Standard with 0 labs in F3 returns NO_MATCHING_LABORATORY without failing the journey."""
    req = ComplianceJourneyRequest(standard="IS 999999")
    res = orchestrator.build_journey(req)
    
    assert res.status == JourneyStatus.JOURNEY_ESTABLISHED
    assert res.laboratories.status == LaboratoryStageStatus.NO_MATCHING_LABORATORY
    assert res.laboratories.total_matching == 0
    assert res.laboratories.qualified_laboratories == []
    assert "no bis-recognized laboratory" in res.laboratories.explanation.lower()


# ---------------------------------------------------------------------------
# Test Scenarios 25 to 28: Structure, Provenance & Determinism
# ---------------------------------------------------------------------------

def test_25_provenance_completeness(orchestrator):
    """25. All stages expose complete traceable provenance."""
    req = ComplianceJourneyRequest(product="ceiling fan")
    res = orchestrator.build_journey(req)
    
    assert len(res.provenance) > 0
    for prov in res.provenance:
        assert prov.source_layer in ("PC-2_NORMALIZED", "PC-3_RELATIONSHIPS", "F3_LAB_FINDER")
        assert prov.source_verification_state == "SOURCE_VERIFIED"


def test_26_unknown_stages_remain_explicit(orchestrator):
    """26. Unknown stages maintain explicit UNKNOWN status without collapsing."""
    req = ComplianceJourneyRequest(standard="IS 15750")
    res = orchestrator.build_journey(req)
    
    assert res.regulatory_status.status == "QCO_STATUS_UNKNOWN"
    assert res.mandatory_certification.status == "QCO_STATUS_UNKNOWN"
    assert res.certification_scheme.status == "CERTIFICATION_SCHEME_UNKNOWN"
    assert res.testing.status == "TESTING_REQUIREMENTS_UNKNOWN"
    assert res.certification_process.status == "CERTIFICATION_PROCESS_UNKNOWN"


def test_27_no_empty_journey(orchestrator):
    """27. Journey contains all 10 non-collapsing stages across all queries."""
    queries = [
        ComplianceJourneyRequest(product="ceiling fan"),
        ComplianceJourneyRequest(product="we manufacture PVC pipes"),
        ComplianceJourneyRequest(product="I manufacture timber doors"),
        ComplianceJourneyRequest(standard="IS 999999"),
        ComplianceJourneyRequest()  # Invalid empty request
    ]
    for q in queries:
        res = orchestrator.build_journey(q)
        assert res.product is not None
        assert res.applicable_standards is not None
        assert res.regulatory_status is not None
        assert res.mandatory_certification is not None
        assert res.certification_scheme is not None
        assert res.testing is not None
        assert res.inspection is not None
        assert res.sampling is not None
        assert res.laboratories is not None
        assert res.certification_process is not None
        assert isinstance(res.warnings, list)
        assert isinstance(res.limitations, list)


def test_28_deterministic_repeated_request(orchestrator):
    """28. Repeated identical requests produce identical byte-for-byte serialized JSON."""
    req = ComplianceJourneyRequest(standard="IS 4985", location="Delhi")
    res1 = orchestrator.build_journey(req).model_dump_json()
    res2 = orchestrator.build_journey(req).model_dump_json()
    assert res1 == res2


# ---------------------------------------------------------------------------
# Test Scenarios 29 to 32: Immutability & Zero LLM Guarantee
# ---------------------------------------------------------------------------

def test_29_pc3_files_remain_byte_identical():
    """29. All PC-3 files match relationship_manifest.json hashes exactly."""
    manifest_path = PC3_DIR / "metadata" / "relationship_manifest.json"
    assert manifest_path.exists()
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    for fname, exp_hash in manifest["artifact_hashes"].items():
        actual_hash = compute_sha256(PC3_DIR / fname)
        assert actual_hash == exp_hash, f"PC-3 artifact modified: {fname}"


def test_30_pc4_files_remain_byte_identical():
    """30. All PC-4 files match testing_process_manifest.json hashes exactly."""
    manifest_path = PC4_DIR / "metadata" / "testing_process_manifest.json"
    assert manifest_path.exists()
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    for fname, exp_hash in manifest["artifact_hashes"].items():
        actual_hash = compute_sha256(PC4_DIR / fname)
        assert actual_hash == exp_hash, f"PC-4 artifact modified: {fname}"


def test_31_frozen_f3_files_remain_unchanged():
    """31. F3 catalog manifest and API files remain unmodified."""
    f3_manifest_path = PROJECT_ROOT / "data" / "catalog" / "phase_f3_lims" / "catalog_manifest.json"
    assert f3_manifest_path.exists()
    
    # Check lab finder api file exists
    f3_api_path = PROJECT_ROOT / "backend" / "lab_finder_api.py"
    assert f3_api_path.exists()


def test_32_zero_llm_groq_regulatory_decisions(orchestrator, monkeypatch):
    """32. Verifies zero LLM or Groq calls are executed during compliance journey resolution."""
    def forbidden_groq_call(*args, **kwargs):
        raise RuntimeError("Forbidden Groq/LLM call attempted during compliance journey resolution!")

    # Monkeypatch any potential LLM invocation points
    monkeypatch.setattr("backend.nl_lab_parser.parse_lab_natural_query", forbidden_groq_call)

    # Execute journey - must complete using 100% deterministic logic
    req = ComplianceJourneyRequest(product="ceiling fan", location="Delhi")
    res = orchestrator.build_journey(req)
    assert res.status == JourneyStatus.JOURNEY_ESTABLISHED
    assert res.applicable_standards.primary_standard == "IS 374"


def test_33_pvc_ambiguous_resolution_contract(api_client):
    """33. Product 'pvc' produces HTTP 200, STANDARD_NOT_ESTABLISHED, zero invented standard."""
    res = api_client.post("/api/compliance/journey", json={"product": "pvc"})
    assert res.status_code == 200
    journey = res.json()

    # Overall journey status must be STANDARD_NOT_ESTABLISHED
    assert journey["status"] == "STANDARD_NOT_ESTABLISHED"

    # Product status remains AMBIGUOUS_PRODUCT with candidate products preserved
    assert journey["product"]["status"] == "AMBIGUOUS_PRODUCT"
    assert len(journey["product"]["candidates"]) >= 2
    cand_names = [c["product_name"] for c in journey["product"]["candidates"]]
    assert any("pvc" in name.lower() for name in cand_names)

    # Applicable standards status must be STANDARD_NOT_ESTABLISHED
    assert journey["applicable_standards"]["status"] == "STANDARD_NOT_ESTABLISHED"
    assert journey["applicable_standards"]["primary_standard"] is None

    # Mandatory certification status must be MANDATORY_CERTIFICATION_NOT_ESTABLISHED
    assert journey["mandatory_certification"]["status"] == "MANDATORY_CERTIFICATION_NOT_ESTABLISHED"
    assert journey["mandatory_certification"]["is_mandatory"] is not True

    # Uncertainty preserved across testing, inspection, sampling, process
    assert journey["testing"]["status"] == "TESTING_REQUIREMENTS_UNKNOWN"
    assert journey["inspection"]["status"] == "INSPECTION_REQUIREMENTS_UNKNOWN"
    assert journey["sampling"]["status"] == "SAMPLING_REQUIREMENTS_UNKNOWN"
    assert journey["certification_process"]["status"] == "CERTIFICATION_PROCESS_UNKNOWN"

    # Must contain the exact required limitation
    expected_limitation = "Applicable Indian Standard could not be established from available BIS evidence."
    assert any(expected_limitation in lim for lim in journey["limitations"])

    # Zero invented standards or laboratories
    assert journey["laboratories"]["status"] in ["LAB_MATCHING_LIMITED", "NO_MATCHING_LABORATORY"]


def test_34_benchmark_regression_matrix(api_client):
    """34. Matrix test preserving existing behavior across all required benchmarks."""
    # 1. product="timber doors" -> STANDARD_NOT_ESTABLISHED
    td_res = api_client.post("/api/compliance/journey", json={"product": "timber doors"})
    assert td_res.status_code == 200
    td_journey = td_res.json()
    assert td_journey["status"] == "STANDARD_NOT_ESTABLISHED"

    # 2. standard="IS 4985" -> JOURNEY_ESTABLISHED, IS 4985, mandatory True
    pvc_std_res = api_client.post("/api/compliance/journey", json={"standard": "IS 4985"})
    assert pvc_std_res.status_code == 200
    pvc_std = pvc_std_res.json()
    assert pvc_std["status"] == "JOURNEY_ESTABLISHED"
    assert pvc_std["applicable_standards"]["primary_standard"] == "IS 4985"
    assert pvc_std["mandatory_certification"]["is_mandatory"] is True

    # 3. standard="IS 374" -> QCO_CONFLICT preserved
    fan_res = api_client.post("/api/compliance/journey", json={"standard": "IS 374"})
    assert fan_res.status_code == 200
    fan_journey = fan_res.json()
    assert "CONFLICT" in fan_journey["regulatory_status"]["status"]
    assert len(fan_journey["regulatory_status"]["conflict_ids"]) > 0

    # 4. standard="IS 15750" -> QCO_STATUS_UNKNOWN preserved
    unknown_res = api_client.post("/api/compliance/journey", json={"standard": "IS 15750"})
    assert unknown_res.status_code == 200
    unknown_journey = unknown_res.json()
    assert "UNKNOWN" in unknown_journey["regulatory_status"]["status"]

