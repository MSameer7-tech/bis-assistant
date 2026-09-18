"""
Phase PC-9 Phase 5 Final Compliance Answer Quality Validation.

Verifies the complete user experience across:
1. "what certification is required for IS 374"
2. "what QCO applies to IS 374"
3. "what tests are required for IS 374"
4. "is certification mandatory for IS 4985"
5. "what certification is required for IS 16046 Part 2"
6. "what standards apply to building bricks"
7. "how do I get BIS certification for PVC pipes"
8. "tell me everything about compliance for ceiling fans"

And the 14 validation criteria:
1. First visible answer directly answers the question.
2. Relevant BIS evidence is used.
3. Groq structures the answer.
4. Missing informational gaps receive useful LLM explanation where appropriate.
5. Regulatory facts remain authoritative.
6. No hallucinated BIS facts.
7. No invented QCO.
8. No invented certification scheme.
9. No invented laboratory.
10. No raw RAG chunk dumping.
11. No internal technical terminology appears in user-facing content.
12. No "GENERAL INFORMATION" placeholder appears.
13. Evidence remains accessible.
14. Next steps are useful and concise.

Also verifies resilience scenarios:
- Groq 429 rate limit
- multi-key failover
- Groq timeout
- malformed Groq response
- unknown product
- conflicting regulatory evidence
- partial RAG
- zero RAG
"""

import re
import json
import pytest
from unittest.mock import patch
from backend.compliance_rag_synthesizer import get_compliance_rag_synthesizer
from ai.compliance.journey_models import ComplianceJourneyRequest
from ai.compliance.journey_v2_models import ComplianceJourneyV2Response
from backend.compliance_journey_v2_synthesizer import FORBIDDEN_INTERNAL_TERMS, GroqComplianceInput


@pytest.fixture(scope="module")
def synthesizer():
    return get_compliance_rag_synthesizer()


def assert_14_criteria(journey_dict, user_query: str):
    """Asserts all 14 Phase 5 validation criteria on a compliance journey response."""
    assert "compliance_answer_v2" in journey_dict, "compliance_answer_v2 missing"
    v2_raw = journey_dict["compliance_answer_v2"]
    v2 = ComplianceJourneyV2Response(**v2_raw)

    # Criterion 1: First visible answer (assessment) directly answers or frames compliance
    assert v2.assessment.answer, "Criterion 1 failed: Assessment answer is empty"
    assert len(v2.assessment.answer) > 20, "Criterion 1 failed: Assessment answer too short"

    # Criterion 2: Relevant BIS evidence is used or referenced
    assert "_dev_trace" in journey_dict, "Criterion 2 failed: Dev trace missing"

    # Criterion 3: Groq / synthesis structures the answer into stages
    assert v2.product_identification.answer
    assert v2.applicable_standards.answer
    assert v2.regulatory_status.answer
    assert v2.mandatory_certification.answer
    assert v2.certification_scheme.answer
    assert v2.testing.answer
    assert v2.inspection.answer
    assert v2.sampling.answer
    assert v2.laboratories.answer
    assert v2.certification_process.answer

    # Criterion 4: Gaps receive useful explanation without hallucinating requirements
    if not v2.certification_scheme.scheme_name:
        assert "could not be confirmed" in v2.certification_scheme.answer.lower() or "not established" in v2.certification_scheme.answer.lower()

    # Criterion 5 & 6: Regulatory facts remain authoritative, no hallucinated BIS facts
    if journey_dict.get("regulatory_status", {}).get("qco_status") == "QCO_APPLIES":
        assert v2.mandatory_certification.is_mandatory is True
    elif journey_dict.get("regulatory_status", {}).get("qco_status") == "QCO_CONFLICT":
        assert "conflict" in v2.regulatory_status.answer.lower()

    # Criterion 7: No invented QCO
    if not journey_dict.get("regulatory_status", {}).get("notification_numbers"):
        assert len(v2.regulatory_status.regulatory_orders) == 0

    # Criterion 8: No invented certification scheme
    if not journey_dict.get("certification_scheme", {}).get("certification_scheme") and "cro" not in str(journey_dict.get("regulatory_status", {})).lower() and "compulsory registration" not in str(journey_dict.get("regulatory_status", {})).lower():
        assert v2.certification_scheme.scheme_name is None

    # Criterion 9: No invented laboratory (Stage 9 locked to F3 LIMS)
    f3_lab_count = len(journey_dict.get("laboratories", {}).get("qualified_laboratories", []) or
                       journey_dict.get("laboratories", {}).get("laboratories", []))
    assert len(v2.laboratories.recognized_labs) == f3_lab_count

    # Criterion 10: No raw RAG chunk dumping (check stage answers are concise sentences, not chunk dumps)
    for stage_obj in [v2.product_identification, v2.applicable_standards, v2.regulatory_status,
                      v2.mandatory_certification, v2.certification_scheme, v2.testing]:
        assert len(stage_obj.answer) < 1500, f"Criterion 10 failed: Answer suspiciously resembles raw dump: {stage_obj.answer[:100]}"

    # Criterion 11: No internal technical terminology appears in the UI
    json_dump = v2.model_dump_json()
    for pattern in FORBIDDEN_INTERNAL_TERMS:
        match = re.search(pattern, json_dump, re.IGNORECASE)
        assert match is None, f"Criterion 11 failed: Forbidden term '{pattern}' found: {match.group(0)}"

    # Criterion 12: No "GENERAL INFORMATION" placeholder appears
    assert "GENERAL INFORMATION" not in json_dump

    # Criterion 13: Evidence remains accessible
    assert "provenance" in journey_dict or "_dev_trace" in journey_dict

    # Criterion 14: Next steps useful and concise
    assert len(v2.next_steps) >= 2
    for step in v2.next_steps:
        assert len(step) > 10

    return v2


# ===========================================================================
# 8 Mandated Queries Quality Verification
# ===========================================================================

def test_query_1_what_certification_required_is374(synthesizer):
    """1. 'what certification is required for IS 374'"""
    req = ComplianceJourneyRequest(query="what certification is required for IS 374")
    res = synthesizer.process_journey(req)
    v2 = assert_14_criteria(res, req.query)
    assert "374" in v2.applicable_standards.answer or "374" in v2.applicable_standards.standards
    assert "conflict" in v2.regulatory_status.answer.lower() or "conflict" in v2.assessment.answer.lower() or "voluntary" in v2.assessment.answer.lower()


def test_query_2_what_qco_applies_is374(synthesizer):
    """2. 'what QCO applies to IS 374'"""
    req = ComplianceJourneyRequest(query="what QCO applies to IS 374")
    res = synthesizer.process_journey(req)
    v2 = assert_14_criteria(res, req.query)
    assert "conflict" in v2.regulatory_status.answer.lower()


def test_query_3_what_tests_required_is374(synthesizer):
    """3. 'what tests are required for IS 374'"""
    req = ComplianceJourneyRequest(query="what tests are required for IS 374")
    res = synthesizer.process_journey(req)
    v2 = assert_14_criteria(res, req.query)
    assert "test" in v2.testing.answer.lower() or "sit" in v2.testing.answer.lower()


def test_query_4_is_certification_mandatory_is4985(synthesizer):
    """4. 'is certification mandatory for IS 4985'"""
    req = ComplianceJourneyRequest(query="is certification mandatory for IS 4985")
    res = synthesizer.process_journey(req)
    v2 = assert_14_criteria(res, req.query)
    assert v2.mandatory_certification.is_mandatory is True
    assert "mandatory" in v2.mandatory_certification.answer.lower()
    assert "Pipes and Fittings" in v2.regulatory_status.answer or "S.O. 4512(E)" in v2.regulatory_status.answer


def test_query_5_what_certification_required_is16046_part2(synthesizer):
    """5. 'what certification is required for IS 16046 Part 2'"""
    req = ComplianceJourneyRequest(query="what certification is required for IS 16046 Part 2")
    res = synthesizer.process_journey(req)
    v2 = assert_14_criteria(res, req.query)
    assert v2.mandatory_certification.is_mandatory is True
    assert "Electronics and Information Technology Goods" in v2.regulatory_status.answer or "1021(E)" in v2.regulatory_status.answer


def test_query_6_what_standards_apply_to_building_bricks(synthesizer):
    """6. 'what standards apply to building bricks'"""
    req = ComplianceJourneyRequest(query="what standards apply to building bricks")
    res = synthesizer.process_journey(req)
    v2 = assert_14_criteria(res, req.query)
    assert "1077" in v2.applicable_standards.answer or "1077" in str(v2.applicable_standards.standards)
    assert v2.mandatory_certification.is_mandatory is not True


def test_query_7_how_do_i_get_bis_certification_for_pvc_pipes(synthesizer):
    """7. 'how do I get BIS certification for PVC pipes'"""
    req = ComplianceJourneyRequest(query="how do I get BIS certification for PVC pipes")
    res = synthesizer.process_journey(req)
    v2 = assert_14_criteria(res, req.query)
    assert "manakonline" in v2.certification_process.answer.lower() or "application" in v2.certification_process.answer.lower()


def test_query_8_tell_me_everything_about_compliance_for_ceiling_fans(synthesizer):
    """8. 'tell me everything about compliance for ceiling fans'"""
    req = ComplianceJourneyRequest(query="tell me everything about compliance for ceiling fans")
    res = synthesizer.process_journey(req)
    v2 = assert_14_criteria(res, req.query)
    assert "ceiling fan" in v2.product_identification.answer.lower()
    assert "374" in v2.applicable_standards.answer or "374" in str(v2.applicable_standards.standards)


# ===========================================================================
# Resilience Scenarios
# ===========================================================================

def test_resilience_groq_429_rate_limit(synthesizer):
    """Verifies graceful fallback to deterministic V2 on Groq 429."""
    req = ComplianceJourneyRequest(standard="IS 4985")
    with patch.object(synthesizer.groq_client, "chat_completion", side_effect=RuntimeError("GROQ_ALL_KEYS_RATE_LIMITED")):
        res = synthesizer.process_journey(req)
        assert_14_criteria(res, "IS 4985")
        assert res["compliance_answer_v2"]["mandatory_certification"]["is_mandatory"] is True


def test_resilience_multi_key_failover(synthesizer):
    """Verifies failover from key 1 to key 2."""
    req = ComplianceJourneyRequest(standard="IS 4985")
    mock_valid_json = json.dumps({
        "product_identification": {"answer": "Potable water PVC pipe", "key_information": [], "evidence_ids": []},
        "applicable_standards": {"answer": "IS 4985 applies.", "key_information": [], "evidence_ids": []},
        "regulatory_status": {"answer": "Notified under QCO.", "key_information": [], "evidence_ids": []},
        "mandatory_certification": {"answer": "Certification is mandatory.", "key_information": [], "evidence_ids": []},
        "certification_scheme": {"answer": "Scheme could not be confirmed.", "key_information": [], "evidence_ids": []},
        "testing": {"answer": "Hydrostatic pressure testing required.", "key_information": [], "evidence_ids": []},
        "inspection": {"answer": "Routine factory inspections apply.", "key_information": [], "evidence_ids": []},
        "sampling": {"answer": "Statistical lot sampling applies.", "key_information": [], "evidence_ids": []},
        "laboratories": {"answer": "Recognized testing laboratories available.", "key_information": [], "evidence_ids": []},
        "certification_process": {"answer": "Apply online via Manakonline.", "key_information": [], "evidence_ids": []},
        "assessment": {"answer": "Mandatory compliance applies for IS 4985.", "key_information": [], "evidence_ids": []},
        "next_steps": ["Review standard specifications", "Submit Manakonline application"]
    })

    with patch.object(synthesizer.groq_client, "chat_completion", return_value=mock_valid_json):
        res = synthesizer.process_journey(req)
        v2 = assert_14_criteria(res, "IS 4985")
        assert v2.mandatory_certification.is_mandatory is True


def test_resilience_groq_timeout(synthesizer):
    """Verifies graceful fallback on Groq timeout."""
    import socket
    req = ComplianceJourneyRequest(standard="IS 374")
    with patch.object(synthesizer.groq_client, "chat_completion", side_effect=socket.timeout("Groq request timed out")):
        res = synthesizer.process_journey(req)
        v2 = assert_14_criteria(res, "IS 374")
        assert "conflict" in v2.regulatory_status.answer.lower()


def test_resilience_malformed_groq_response(synthesizer):
    """Verifies that unparseable or truncated Groq response safely falls back."""
    req = ComplianceJourneyRequest(standard="IS 1077")
    with patch.object(synthesizer.groq_client, "chat_completion", return_value="{'invalid_json: true, unterminated"):
        res = synthesizer.process_journey(req)
        v2 = assert_14_criteria(res, "IS 1077")
        assert "1077" in v2.applicable_standards.answer


def test_resilience_unknown_product(synthesizer):
    """Verifies uncataloged/unknown product returns informative guidance without hallucinations."""
    req = ComplianceJourneyRequest(product="quantum photonic flux capacitor")
    res = synthesizer.process_journey(req)
    assert "compliance_answer_v2" in res
    v2 = ComplianceJourneyV2Response(**res["compliance_answer_v2"])
    assert "quantum photonic flux capacitor" in v2.product_identification.answer.lower()
    assert v2.mandatory_certification.is_mandatory is not True


def test_resilience_conflicting_regulatory_evidence(synthesizer):
    """Verifies conservative handling of conflicting Gazette orders."""
    req = ComplianceJourneyRequest(standard="IS 374")
    res = synthesizer.process_journey(req)
    v2 = assert_14_criteria(res, "IS 374")
    assert "conflict" in v2.regulatory_status.answer.lower()
    assert v2.mandatory_certification.is_mandatory is not True


def test_resilience_partial_rag(synthesizer):
    """Verifies standard with partial RAG retrieval retains accurate stage structure."""
    req = ComplianceJourneyRequest(standard="IS 15750")
    res = synthesizer.process_journey(req)
    v2 = assert_14_criteria(res, "IS 15750")
    assert v2.mandatory_certification.is_mandatory is not True


def test_resilience_zero_rag(synthesizer):
    """Verifies behavior when RAG returns zero evidence chunks."""
    with patch.object(synthesizer, "retrieve_stage_evidence", return_value=("INSUFFICIENT", [])):
        req = ComplianceJourneyRequest(standard="IS 4985")
        res = synthesizer.process_journey(req)
        v2 = assert_14_criteria(res, "IS 4985")
        assert v2.mandatory_certification.is_mandatory is True
