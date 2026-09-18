import pytest
from backend.compliance_rag_synthesizer import get_compliance_rag_synthesizer
from ai.compliance.journey_models import ComplianceJourneyRequest

@pytest.fixture
def synthesizer():
    return get_compliance_rag_synthesizer()

def test_is_16046_part_2_stage5(synthesizer):
    req = ComplianceJourneyRequest(standard="IS 16046 Part 2", product="IS 16046 Part 2")
    journey = synthesizer.process_journey(req)
    stage5 = journey.get("certification_scheme", {})
    
    # Must preserve regulatory order and mechanism
    assert stage5.get("regulatory_order") is not None
    assert "Registration" in stage5.get("regulatory_order", "") or "Information Technology" in stage5.get("regulatory_order", "")
    assert "Registration" in stage5.get("conformity_assessment_mechanism", "")
    assert stage5.get("status") == "CERTIFICATION_SCHEME_UNKNOWN"
    
    synth = stage5.get("synthesis", {})
    assert synth is not None
    
    # General Info must exist but not overrule verified details
    gen_info = synth.get("general_information", "")
    assert len(gen_info) > 10

def test_is_4985_stage5(synthesizer):
    req = ComplianceJourneyRequest(standard="IS 4985", product="IS 4985")
    journey = synthesizer.process_journey(req)
    stage5 = journey.get("certification_scheme", {})
    
    assert stage5.get("regulatory_order") is not None
    assert "Pipes" in stage5.get("regulatory_order", "")
    assert "ISI Mark" in stage5.get("conformity_assessment_mechanism", "")
    assert stage5.get("status") == "CERTIFICATION_SCHEME_UNKNOWN"

def test_is_1077_stage5(synthesizer):
    req = ComplianceJourneyRequest(standard="IS 1077", product="IS 1077")
    journey = synthesizer.process_journey(req)
    stage5 = journey.get("certification_scheme", {})
    
    # No QCO, so no regulatory order
    assert stage5.get("regulatory_order") is None
    assert stage5.get("status") == "CERTIFICATION_SCHEME_UNKNOWN"

def test_is_15750_stage5(synthesizer):
    req = ComplianceJourneyRequest(standard="IS 15750", product="IS 15750")
    journey = synthesizer.process_journey(req)
    stage5 = journey.get("certification_scheme", {})
    
    assert stage5.get("status") == "CERTIFICATION_SCHEME_UNKNOWN"

def test_groq_hallucination_prevention(synthesizer):
    # Test that validate_and_guard_synthesis rejects hallucinated schemes when expected UNKNOWN
    pc5_stage = {
        "status": "CERTIFICATION_SCHEME_UNKNOWN",
        "certification_requirement": "Mandatory",
        "regulatory_order": "Test Order",
        "conformity_assessment_mechanism": "Test Mechanism",
        "certification_scheme": None,
        "scheme_applicability": "NOT_ESTABLISHED",
        "applicable_scheme_code": None,
        "applicability_basis": "NO_AUTHORITATIVE_APPLICABILITY_RECORD_IN_CORPUS",
        "explanation": "Test explanation."
    }
    
    hallucinated_synthesis = {
        "primary_answer": "Product-specific certification scheme confirmed", # Hallucinated
        "key_information": [
            {"label": "Applicable scheme", "value": "Scheme-I", "source": "BIS_EVIDENCE"} # Hallucinated
        ],
        "explanation": "I made this up.",
        "general_information": "Test gen info."
    }
    
    fallback = synthesizer.synthesize_stage_deterministic(5, pc5_stage, "SUFFICIENT", [], None, "IS 1234")
    
    guarded = synthesizer.validate_and_guard_synthesis(
        stage_num=5,
        pc5_stage=pc5_stage,
        synthesis=hallucinated_synthesis,
        rag_evidence=[],
        qco_info=None,
        fallback=fallback,
        target_standard="IS 1234"
    )
    
    # Assert it was rolled back to fallback
    assert guarded["primary_answer"] == fallback["primary_answer"]
    assert guarded["key_information"] == fallback["key_information"]

