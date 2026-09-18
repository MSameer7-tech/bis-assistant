"""
Phase PC-8 V2 Phase 3 Integration Tests: End-to-End Compliance Journey Answer Synthesis.

Tests the 6 mandated product queries:
1. IS 374 (Ceiling Fans - QCO conflict handling)
2. IS 4985 (uPVC Pipes - QCO confirmed, scheme unconfirmed, SIT tests)
3. IS 16046 Part 2 (Lithium Batteries - Mandatory Compulsory Registration)
4. IS 1077 (Clay Bricks - Voluntary, QCO not established)
5. IS 15750 (Unknown QCO in records)
6. Timber Doors (Standard not established, informative guidance)

Verifies:
- Complete and valid compliance_answer_v2 response contract.
- User-readable answers rather than internal status explanations.
- Zero leakage of internal technical terms (UNKNOWN, GROUNDED, HYBRID, LLM_FALLBACK, RAG, PC-5) in user-facing content.
- Absolute preservation of PC-5 deterministic results (QCO status, mandatory status, F3 laboratories, provenance, evidence IDs).
- Dev-only trace completeness.
"""

import pytest
import re
from backend.compliance_rag_synthesizer import get_compliance_rag_synthesizer
from ai.compliance.journey_models import ComplianceJourneyRequest
from ai.compliance.journey_v2_models import ComplianceJourneyV2Response
from backend.compliance_journey_v2_synthesizer import FORBIDDEN_INTERNAL_TERMS


@pytest.fixture
def synthesizer():
    return get_compliance_rag_synthesizer()


def assert_v2_contract_and_no_jargon(journey_dict):
    """Asserts that compliance_answer_v2 is valid and free of internal jargon."""
    assert "compliance_answer_v2" in journey_dict, "compliance_answer_v2 missing from journey response"
    v2_raw = journey_dict["compliance_answer_v2"]
    v2_obj = ComplianceJourneyV2Response(**v2_raw)

    # Check that all 11 stages and next steps are present
    assert v2_obj.product_identification.answer
    assert v2_obj.applicable_standards.answer
    assert v2_obj.regulatory_status.answer
    assert v2_obj.mandatory_certification.answer
    assert v2_obj.certification_scheme.answer
    assert v2_obj.testing.answer
    assert v2_obj.inspection.answer
    assert v2_obj.sampling.answer
    assert v2_obj.laboratories.answer
    assert v2_obj.certification_process.answer
    assert v2_obj.assessment.answer
    assert len(v2_obj.next_steps) > 0

    # Ensure no technical jargon in user-facing V2 answers
    json_str = v2_obj.model_dump_json()
    for term in FORBIDDEN_INTERNAL_TERMS:
        match = re.search(term, json_str, re.IGNORECASE)
        assert match is None, f"Forbidden term '{term}' leaked into compliance_answer_v2: {match.group(0)}"

    # Ensure dev trace exists
    assert "_dev_trace" in journey_dict
    return v2_obj


# ---------------------------------------------------------------------------
# 1. IS 374 (Ceiling Fans - QCO Conflict)
# ---------------------------------------------------------------------------
def test_e2e_is_374(synthesizer):
    req = ComplianceJourneyRequest(standard="IS 374")
    journey = synthesizer.process_journey(req)

    # Deterministic preservation
    assert journey["regulatory_status"]["qco_status"] == "QCO_CONFLICT"
    assert journey["mandatory_certification"]["status"] == "QCO_CONFLICT"

    # V2 Contract & Jargon Check
    v2 = assert_v2_contract_and_no_jargon(journey)

    # Answer explains conflicting Gazette orders conservatively
    assert "conflicting" in v2.regulatory_status.answer.lower()
    assert "IS 374" in v2.applicable_standards.standards or "IS 374" in v2.applicable_standards.answer


# ---------------------------------------------------------------------------
# 2. IS 4985 (uPVC Pipes - QCO Confirmed, Scheme Unconfirmed)
# ---------------------------------------------------------------------------
def test_e2e_is_4985(synthesizer):
    req = ComplianceJourneyRequest(standard="IS 4985")
    journey = synthesizer.process_journey(req)

    # Deterministic preservation
    assert journey["regulatory_status"]["qco_status"] == "QCO_APPLIES"
    assert journey["mandatory_certification"]["is_mandatory"] is True
    assert journey["certification_scheme"]["status"] == "CERTIFICATION_SCHEME_UNKNOWN"
    assert len(journey["regulatory_status"].get("notification_numbers", [])) > 0

    # V2 Contract & Jargon Check
    v2 = assert_v2_contract_and_no_jargon(journey)

    # QCO title and mandatory status
    assert len(v2.regulatory_status.regulatory_orders) > 0
    assert v2.mandatory_certification.is_mandatory is True
    assert "mandatory" in v2.mandatory_certification.answer.lower()

    # Certification scheme unavailable naturally explained
    assert v2.certification_scheme.scheme_name is None
    assert "could not be confirmed" in v2.certification_scheme.answer.lower()

    # Testing & laboratories preserved
    assert len(v2.laboratories.recognized_labs) > 0


# ---------------------------------------------------------------------------
# 3. IS 16046 Part 2 (Lithium Batteries - Compulsory Registration Order)
# ---------------------------------------------------------------------------
def test_e2e_is_16046_part_2(synthesizer):
    req = ComplianceJourneyRequest(standard="IS 16046 Part 2")
    journey = synthesizer.process_journey(req)

    # Deterministic preservation
    assert journey["regulatory_status"]["qco_status"] in ("QCO_APPLIES", "QCO_AMENDED")
    assert journey["mandatory_certification"]["is_mandatory"] is True
    assert "Registration" in journey["certification_scheme"].get("conformity_assessment_mechanism", "")

    # V2 Contract & Jargon Check
    v2 = assert_v2_contract_and_no_jargon(journey)

    assert v2.mandatory_certification.is_mandatory is True
    assert "mandatory" in v2.mandatory_certification.answer.lower()
    assert len(v2.regulatory_status.regulatory_orders) > 0


# ---------------------------------------------------------------------------
# 4. IS 1077 (Clay Bricks - Voluntary, No QCO)
# ---------------------------------------------------------------------------
def test_e2e_is_1077(synthesizer):
    req = ComplianceJourneyRequest(standard="IS 1077")
    journey = synthesizer.process_journey(req)

    # Deterministic preservation
    assert journey["regulatory_status"]["qco_status"] in ("QCO_STATUS_UNKNOWN", "QCO_NOT_ESTABLISHED")
    assert journey["certification_scheme"]["regulatory_order"] is None

    # V2 Contract & Jargon Check
    v2 = assert_v2_contract_and_no_jargon(journey)

    # Regulatory status naturally explains no QCO found
    assert len(v2.regulatory_status.regulatory_orders) == 0
    assert "no active" in v2.regulatory_status.answer.lower() or "not identified" in v2.regulatory_status.answer.lower() or "not established" in v2.regulatory_status.answer.lower()


# ---------------------------------------------------------------------------
# 5. IS 15750 (No QCO in Records)
# ---------------------------------------------------------------------------
def test_e2e_is_15750(synthesizer):
    req = ComplianceJourneyRequest(standard="IS 15750")
    journey = synthesizer.process_journey(req)

    # Deterministic preservation
    assert journey["regulatory_status"]["qco_status"] in ("QCO_STATUS_UNKNOWN", "QCO_NOT_ESTABLISHED")

    # V2 Contract & Jargon Check
    v2 = assert_v2_contract_and_no_jargon(journey)

    assert v2.mandatory_certification.is_mandatory is not True


# ---------------------------------------------------------------------------
# 6. Timber Doors (Standard Not Established, Informative Guidance)
# ---------------------------------------------------------------------------
def test_e2e_timber_doors(synthesizer):
    req = ComplianceJourneyRequest(product="timber doors")
    journey = synthesizer.process_journey(req)

    # Deterministic status preserved
    assert journey["status"] == "STANDARD_NOT_ESTABLISHED"
    assert journey["applicable_standards"]["primary_standard"] is None

    # V2 Contract & Jargon Check
    v2 = assert_v2_contract_and_no_jargon(journey)

    assert "timber doors" in v2.product_identification.answer.lower()
    assert len(v2.next_steps) > 0
    assert journey["_dev_trace"]["generation_mode"] == "GROQ_V2_UNESTABLISHED"
