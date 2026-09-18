"""
tests/compliance/test_pc11_subphase_d_validation_guarding.py
Sub-phase D: Comprehensive Response Validation, Correctness Guarding, and Failure Handling Suite.

Validates:
1. Narrow intent completeness ("IS 374" with intent "DEFINITION") -> all 10 stages survive.
2. Stage 6 testing fidelity: dynamic detection and removal of unsupported frequencies/clauses.
3. Stage 7 inspection fidelity: dynamic detection/removal of unsupported schedules + CRS factory audit rules.
4. Stage 8 sampling fidelity: dynamic detection and removal of unsupported quantities/percentages.
5. Stage 4 authority lock: PC-5 mandatory status strictly wins over contradictory LLM claims.
6. Stage 3 authority lock: hallucinated Gazette S.O. notification numbers scrubbed.
7. Stage 3 QCO conflict: conflicting Gazette status preserved against overconfident claims.
8. Stage 5 scheme lock: unsupported Scheme-I/Scheme-II claims not presented as confirmed facts.
9. Stage 9 F3 laboratory tamper resistance: 100% locked to authoritative F3 LIMS data.
10. Jargon sanitization: zero leakage of internal implementation tokens into user-facing output.
11. Failure modes: 429 rate limit, timeout, malformed JSON fallback validation.
12. Canonical queries: dynamic validation comparing output directly against input context.
13. Cross-query contamination: sequential runs (IS 4985 -> IS 374 -> timber doors) maintain strict isolation.
14. Fallback correctness: deterministic fallback responses pass the exact same correctness validation.
15. Stage completeness and quality report structure: deterministic scoring and zero remaining unsupported claims.
16. Live Groq measurement: verified against real Groq endpoint if configured.
"""

import json
import pytest
import re
import time
from unittest.mock import patch, MagicMock

from ai.compliance.journey_v2_models import (
    ComplianceJourneyV2Response,
    ProductIdentificationStage,
    ApplicableStandardsStage,
    RegulatoryStatusStage,
    MandatoryCertificationStage,
    CertificationSchemeStage,
    ComplianceTestingStage,
    InspectionStage,
    SamplingStage,
    LaboratoriesStage,
    CertificationProcessStage,
    AssessmentStage,
)
from backend.compliance_journey_v2_synthesizer import (
    ComplianceJourneyV2Synthesizer,
    GroqComplianceInput,
    DEFAULT_V2_MODEL,
)
from backend.compliance_context_builder import ComplianceContextBuilder
from backend.compliance_correctness_engine import (
    ComplianceCorrectnessEngine,
    StageQualityScore,
)
from scripts.phase12_f2_orchestrator import GroqClient


# ---------------------------------------------------------------------------
# Mock Helpers
# ---------------------------------------------------------------------------

class MockGroqClient:
    def __init__(self, response_text=None, is_configured=True, should_raise=None):
        self.response_text = response_text
        self.is_configured = is_configured
        self.should_raise = should_raise
        self.model = DEFAULT_V2_MODEL
        self.call_count = 0

    def chat_completion(self, messages, max_tokens=3500, trace_info=None):
        self.call_count += 1
        if self.should_raise:
            raise self.should_raise
        return self.response_text


def get_base_mock_payload() -> dict:
    return {
        "product_identification": {
            "title": "Product Identification",
            "answer": "Electric ceiling fan manufactured for domestic use.",
            "key_information": ["Domestic ceiling fan"],
            "evidence_ids": ["ev_1"]
        },
        "applicable_standards": {
            "title": "Applicable Indian Standards",
            "answer": "The primary applicable standard is IS 374.",
            "key_information": ["IS 374: Electric Ceiling Fans"],
            "evidence_ids": ["ev_2"],
            "standards": ["IS 374"]
        },
        "regulatory_status": {
            "title": "QCO / Regulatory Status",
            "answer": "Regulated under the Ceiling Fans Quality Control Order, S.O. 4512(E).",
            "key_information": ["Notified under QCO"],
            "evidence_ids": ["ev_3"]
        },
        "mandatory_certification": {
            "title": "Mandatory Certification",
            "answer": "BIS certification is mandatory under the statutory Quality Control Order.",
            "key_information": ["Mandatory under QCO"],
            "evidence_ids": ["ev_4"]
        },
        "certification_scheme": {
            "title": "Certification Scheme",
            "answer": "Certification operates under Scheme-I (ISI Mark).",
            "key_information": ["Scheme-I (ISI Mark)"],
            "evidence_ids": ["ev_5"]
        },
        "testing": {
            "title": "Required Testing",
            "answer": "Testing requires verification of air delivery and service value.",
            "key_information": ["Air delivery, service value"],
            "evidence_ids": ["ev_6"],
            "test_methods": ["Air delivery", "Service value"]
        },
        "inspection": {
            "title": "Factory Inspection",
            "answer": "Factory inspection verifies manufacturing equipment and test registers per SIT.",
            "key_information": ["Inspection per SIT"],
            "evidence_ids": ["ev_7"]
        },
        "sampling": {
            "title": "Lot & Control Unit Sampling",
            "answer": "Sampling is conducted on representative production lots in accordance with statistical criteria.",
            "key_information": ["Representative lot sampling"],
            "evidence_ids": ["ev_8"]
        },
        "laboratories": {
            "title": "Qualified BIS Laboratories",
            "answer": "Testing can be conducted across recognized laboratories.",
            "key_information": ["Recognized laboratories"],
            "evidence_ids": ["ev_9"]
        },
        "certification_process": {
            "title": "Certification Process",
            "answer": "1. Online application on Manakonline 2. SIT setup 3. Factory audit 4. Grant of licence.",
            "key_information": ["Manakonline application"],
            "evidence_ids": ["ev_10"],
            "process_steps": ["1. Online application", "2. Factory audit", "3. Grant of licence"]
        },
        "assessment": {
            "title": "Assessment",
            "answer": "ANSWER: BIS certification is mandatory for IS 374 ceiling fans.",
            "key_information": ["Mandatory: Yes"],
            "evidence_ids": ["ev_11"]
        },
        "next_steps": [
            "Review latest standard specifications.",
            "Ensure testing facilities meet SIT requirements."
        ]
    }


# ---------------------------------------------------------------------------
# 1. Narrow Intent: "IS 374" with intent "DEFINITION"
# ---------------------------------------------------------------------------
def test_narrow_intent_is374_completeness():
    """Verify that a concise query 'IS 374' with intent 'DEFINITION' yields all 10 stages."""
    builder = ComplianceContextBuilder()
    resp, meta = builder.execute_compliance_journey(query="IS 374")

    # Verify all 10 stages exist as distinct attributes
    assert isinstance(resp.product_identification, ProductIdentificationStage)
    assert isinstance(resp.applicable_standards, ApplicableStandardsStage)
    assert isinstance(resp.regulatory_status, RegulatoryStatusStage)
    assert isinstance(resp.mandatory_certification, MandatoryCertificationStage)
    assert isinstance(resp.certification_scheme, CertificationSchemeStage)
    assert isinstance(resp.testing, ComplianceTestingStage)
    assert isinstance(resp.inspection, InspectionStage)
    assert isinstance(resp.sampling, SamplingStage)
    assert isinstance(resp.laboratories, LaboratoriesStage)
    assert isinstance(resp.certification_process, CertificationProcessStage)
    assert isinstance(resp.assessment, AssessmentStage)

    # Verify no stage is empty or obviously truncated
    stages = [
        resp.product_identification,
        resp.applicable_standards,
        resp.regulatory_status,
        resp.mandatory_certification,
        resp.certification_scheme,
        resp.testing,
        resp.inspection,
        resp.sampling,
        resp.laboratories,
        resp.certification_process,
    ]
    for s in stages:
        assert s.answer is not None, f"Stage {s.title} has None answer"
        assert len(s.answer.strip()) >= 10, f"Stage {s.title} answer is suspiciously short: {s.answer}"

    # Verify quality report in metadata
    report = meta.get("correctness_report", {})
    assert report.get("unsupported_claims_remaining") == 0


# ---------------------------------------------------------------------------
# 2. Stage 6 Testing Fidelity: Unsupported Frequency & Clause Removal
# ---------------------------------------------------------------------------
def test_stage6_unsupported_frequency_and_clause_removal():
    """Verify dynamic detection and removal of unsupported testing frequencies and clauses."""
    payload = get_base_mock_payload()
    # Inject unsupported clause and frequency
    payload["testing"]["answer"] = "Routine testing must be performed every batch under Clause 99.4 with daily verification."

    mock_client = MockGroqClient(response_text=json.dumps(payload))
    synthesizer = ComplianceJourneyV2Synthesizer(groq_client=mock_client)

    input_data = GroqComplianceInput(
        user_question="testing requirements for ceiling fans",
        standards=["IS 374"],
        deterministic_results={
            "stage_6": {
                "total_tests": 2,
                "testing_requirements": [
                    {"test_name": "Air Delivery", "test_clause": "8.1", "frequency": "periodic"},
                    {"test_name": "Service Value", "test_clause": "8.2", "frequency": "type test"}
                ]
            }
        },
        testing_evidence=[{"text": "Air delivery testing clause 8.1 periodic verification"}]
    )

    resp = synthesizer.synthesize(input_data)
    ans = resp.testing.answer

    # Clause 99.4 and unsupported frequencies must be sanitized
    assert "Clause 99.4" not in ans
    assert "every batch" not in ans.lower()
    assert "daily verification" not in ans.lower()

    # Report checks
    report = synthesizer.last_trace.get("correctness_report", {})
    assert report["unsupported_claims_detected"] > 0
    assert report["unsupported_claims_remaining"] == 0


# ---------------------------------------------------------------------------
# 3. Stage 7 Inspection Fidelity: Unsupported Routine & CRS Factory Invariant
# ---------------------------------------------------------------------------
def test_stage7_unsupported_inspection_schedule_and_crs():
    """Verify dynamic inspection scrubbing and CRS factory inspection exemption."""
    # Test A: Non-CRS product with fabricated inspection schedule
    payload = get_base_mock_payload()
    payload["inspection"]["answer"] = "Officers conduct a daily factory inspection and weekly surveillance audit."

    mock_client = MockGroqClient(response_text=json.dumps(payload))
    synthesizer = ComplianceJourneyV2Synthesizer(groq_client=mock_client)

    input_data = GroqComplianceInput(
        user_question="factory inspection for ceiling fans",
        standards=["IS 374"],
        deterministic_results={
            "stage_7": {
                "total_requirements": 1,
                "inspection_requirements": [
                    {"inspection_reference": "Routine manufacturing verification per SIT", "frequency": "per lot"}
                ]
            }
        }
    )

    resp = synthesizer.synthesize(input_data)
    ans = resp.inspection.answer
    assert "daily factory inspection" not in ans.lower()
    assert "weekly surveillance audit" not in ans.lower()
    assert synthesizer.last_trace["correctness_report"]["unsupported_claims_remaining"] == 0

    # Test B: CRS product - factory audit MUST be declared not required
    payload_crs = get_base_mock_payload()
    payload_crs["inspection"]["answer"] = "BIS officers will visit the factory to conduct a preliminary audit."
    mock_client_crs = MockGroqClient(response_text=json.dumps(payload_crs))
    synthesizer_crs = ComplianceJourneyV2Synthesizer(groq_client=mock_client_crs)

    input_data_crs = GroqComplianceInput(
        user_question="inspection for IS 16046",
        standards=["IS 16046"],
        deterministic_results={"certification_scheme": "Compulsory Registration Scheme (CRS) / Scheme-II"},
        qco_evidence={"qco_title": "Electronics and Information Technology Goods (Requirement for Compulsory Registration) Order"}
    )

    resp_crs = synthesizer_crs.synthesize(input_data_crs)
    ans_crs = resp_crs.inspection.answer.lower()
    assert "not required" in ans_crs or "test-report registration" in ans_crs


# ---------------------------------------------------------------------------
# 4. Stage 8 Sampling Fidelity: Unsupported Quantity & Percentage Removal
# ---------------------------------------------------------------------------
def test_stage8_unsupported_sampling_quantity_and_percentage_removal():
    """Verify dynamic scrubbing of fabricated sample sizes ('8 units', '5%')."""
    payload = get_base_mock_payload()
    payload["sampling"]["answer"] = "Sampling requires drawing a minimum of 8 units or 5% of the lot every batch."

    mock_client = MockGroqClient(response_text=json.dumps(payload))
    synthesizer = ComplianceJourneyV2Synthesizer(groq_client=mock_client)

    input_data = GroqComplianceInput(
        user_question="sampling for fans",
        standards=["IS 374"],
        deterministic_results={
            "stage_8": {
                "total_requirements": 1,
                "sampling_requirements": [
                    {"sampling_reference": "Sampling as per SIT Table 1", "sample_size": "statistical criteria", "lot_definition": "production lot"}
                ]
            }
        }
    )

    resp = synthesizer.synthesize(input_data)
    ans = resp.sampling.answer
    assert "8 units" not in ans
    assert "5%" not in ans
    assert synthesizer.last_trace["correctness_report"]["unsupported_claims_remaining"] == 0


# ---------------------------------------------------------------------------
# 5. Stage 4 Authority Lock: Mandatory Certification Boolean & Claims
# ---------------------------------------------------------------------------
def test_stage4_mandatory_authority_lock():
    """Verify PC-5 deterministic mandatory status strictly overrides contradictory LLM claims."""
    # Scenario A: Deterministic Mandatory = True, LLM claims Voluntary
    payload = get_base_mock_payload()
    payload["mandatory_certification"]["answer"] = "Certification is entirely voluntary and optional."

    mock_client = MockGroqClient(response_text=json.dumps(payload))
    synthesizer = ComplianceJourneyV2Synthesizer(groq_client=mock_client)

    input_data_true = GroqComplianceInput(
        user_question="is IS 4985 mandatory",
        standards=["IS 4985"],
        deterministic_results={"is_mandatory": True},
        qco_evidence={"qco_title": "Pipes and Fittings QCO"}
    )

    resp = synthesizer.synthesize(input_data_true)
    assert resp.mandatory_certification.is_mandatory is True
    ans = resp.mandatory_certification.answer.lower()
    assert "voluntary" not in ans
    assert "optional" not in ans
    assert "mandatory" in ans

    # Scenario B: Deterministic Mandatory = False, LLM claims Mandatory
    payload_false = get_base_mock_payload()
    payload_false["mandatory_certification"]["answer"] = "Certification is strictly mandatory for all producers."
    mock_client_false = MockGroqClient(response_text=json.dumps(payload_false))
    synthesizer_false = ComplianceJourneyV2Synthesizer(groq_client=mock_client_false)

    input_data_false = GroqComplianceInput(
        user_question="is IS 1077 mandatory",
        standards=["IS 1077"],
        deterministic_results={"is_mandatory": False}
    )

    resp_false = synthesizer_false.synthesize(input_data_false)
    assert resp_false.mandatory_certification.is_mandatory is False
    ans_f = resp_false.mandatory_certification.answer.lower()
    assert "not been established" in ans_f or "not mandatory" in ans_f


# ---------------------------------------------------------------------------
# 6. Stage 3 Authority Lock: Hallucinated S.O. Notification Removal
# ---------------------------------------------------------------------------
def test_stage3_hallucinated_so_notification_removal():
    """Verify that hallucinated Gazette notification numbers not in evidence are purged."""
    payload = get_base_mock_payload()
    payload["regulatory_status"]["answer"] = "Governed under S.O. 9999(E) and S.O. 4512(E)."

    mock_client = MockGroqClient(response_text=json.dumps(payload))
    synthesizer = ComplianceJourneyV2Synthesizer(groq_client=mock_client)

    input_data = GroqComplianceInput(
        user_question="QCO for IS 4985",
        standards=["IS 4985"],
        deterministic_results={"qco_status": "QCO_NOTIFIED"},
        qco_evidence={
            "qco_title": "Pipes and Fittings QCO",
            "notification_numbers": ["S.O. 4512(E)"]
        }
    )

    resp = synthesizer.synthesize(input_data)
    ans = resp.regulatory_status.answer
    assert "S.O. 9999(E)" not in ans
    assert "4512" in ans
    assert synthesizer.last_trace["correctness_report"]["unsupported_claims_remaining"] == 0


# ---------------------------------------------------------------------------
# 7. Stage 3 Authority Lock: QCO Conflict Preservation
# ---------------------------------------------------------------------------
def test_stage3_qco_conflict_preservation():
    """Verify that when PC-5 reports a conflict, the answer preserves the conflict warning."""
    payload = get_base_mock_payload()
    payload["regulatory_status"]["answer"] = "The statutory status is completely settled under single notification."

    mock_client = MockGroqClient(response_text=json.dumps(payload))
    synthesizer = ComplianceJourneyV2Synthesizer(groq_client=mock_client)

    input_data = GroqComplianceInput(
        user_question="QCO for IS 374",
        standards=["IS 374"],
        deterministic_results={"qco_status": "CONFLICT: Gazette notices under review"}
    )

    resp = synthesizer.synthesize(input_data)
    ans = resp.regulatory_status.answer.lower()
    assert "conflict" in ans or "active regulatory review" in ans or "under review" in ans
    assert synthesizer.last_trace["correctness_report"]["unsupported_claims_remaining"] == 0


# ---------------------------------------------------------------------------
# 8. Stage 5 Authority Lock: Unsupported Scheme Not Confirmed
# ---------------------------------------------------------------------------
def test_stage5_unsupported_scheme_not_confirmed():
    """Verify that when scheme is unknown, Scheme-I or Scheme-II cannot be asserted as confirmed."""
    payload = get_base_mock_payload()
    payload["certification_scheme"]["answer"] = "This product strictly requires certification under Scheme-I (ISI Mark)."
    payload["certification_scheme"]["scheme_name"] = "Scheme-I"

    mock_client = MockGroqClient(response_text=json.dumps(payload))
    synthesizer = ComplianceJourneyV2Synthesizer(groq_client=mock_client)

    input_data = GroqComplianceInput(
        user_question="scheme for IS 15750",
        standards=["IS 15750"],
        deterministic_results={"certification_scheme": None}
    )

    resp = synthesizer.synthesize(input_data)
    assert resp.certification_scheme.scheme_name is None
    ans = resp.certification_scheme.answer.lower()
    assert "could not be confirmed" in ans or "not established" in ans


# ---------------------------------------------------------------------------
# 9. Stage 9 F3 Laboratory Tamper Resistance
# ---------------------------------------------------------------------------
def test_stage9_f3_laboratory_tamper_resistance():
    """Verify that Groq cannot modify, invent, or drop F3 laboratories."""
    payload = get_base_mock_payload()
    payload["laboratories"]["recognized_labs"] = ["Fake AI Lab Gurgaon", "Invented Testing Facility"]

    mock_client = MockGroqClient(response_text=json.dumps(payload))
    synthesizer = ComplianceJourneyV2Synthesizer(groq_client=mock_client)

    f3_authoritative_labs = [
        {"laboratory_name": "National Test House (WR)", "public_lab_code": "NTH-01", "city": "Mumbai"},
        {"laboratory_name": "Central Lab Sahibabad", "public_lab_code": "CL-02", "city": "Sahibabad"}
    ]

    input_data = GroqComplianceInput(
        user_question="labs for IS 374",
        standards=["IS 374"],
        f3_laboratories=f3_authoritative_labs
    )

    resp = synthesizer.synthesize(input_data)
    labs = resp.laboratories.recognized_labs

    # Output labs MUST match authoritative F3 laboratories exactly
    assert "Fake AI Lab Gurgaon" not in labs
    assert "Invented Testing Facility" not in labs
    assert "National Test House (WR)" in labs
    assert "Central Lab Sahibabad" in labs
    assert len(labs) == 2


# ---------------------------------------------------------------------------
# 10. Jargon Sanitization: Zero Leakage of Internal Implementation Tokens
# ---------------------------------------------------------------------------
def test_internal_jargon_sanitization():
    """Verify that internal system tokens do not reach user-facing output."""
    payload = get_base_mock_payload()
    payload["assessment"]["answer"] = "PC-3 identified product, PC-5 deterministic baseline reports UNKNOWN status, RAG retrieved GROUNDED evidence corpus, LLM_FALLBACK used."

    mock_client = MockGroqClient(response_text=json.dumps(payload))
    synthesizer = ComplianceJourneyV2Synthesizer(groq_client=mock_client)

    input_data = GroqComplianceInput(
        user_question="compliance status",
        standards=["IS 374"],
        deterministic_results={"is_mandatory": True}
    )

    resp = synthesizer.synthesize(input_data)
    v2_str = json.dumps(resp.to_structured_dict())

    forbidden_tokens = ["PC-3", "PC-4", "PC-5", "RAG", "GROUNDED", "HYBRID", "LLM_FALLBACK", "UNKNOWN", "NOT_ESTABLISHED", "evidence corpus"]
    for token in forbidden_tokens:
        assert token not in v2_str, f"Forbidden internal token '{token}' leaked into user-facing output"


# ---------------------------------------------------------------------------
# 11. Failure Modes: 429 Rate Limit, Timeout, Malformed JSON
# ---------------------------------------------------------------------------
def test_failure_modes_and_fallback():
    """Verify clean deterministic fallback on 429, timeout, and malformed JSON with quality report."""
    input_data = GroqComplianceInput(
        user_question="Is certification mandatory for IS 4985?",
        standards=["IS 4985"],
        deterministic_results={"is_mandatory": True},
        qco_evidence={"qco_title": "Pipes and Fittings QCO"}
    )

    # 429 Rate Limit
    mock_429 = MockGroqClient(should_raise=Exception("429 Rate limit exceeded"))
    synth_429 = ComplianceJourneyV2Synthesizer(groq_client=mock_429)
    resp_429 = synth_429.synthesize(input_data)
    assert synth_429.last_trace["fallback_used"] is True
    assert synth_429.last_trace["fallback_reason"] == "RATE_LIMITED_429"
    assert resp_429.mandatory_certification.is_mandatory is True
    assert synth_429.last_trace["correctness_report"]["unsupported_claims_remaining"] == 0

    # Timeout
    mock_timeout = MockGroqClient(should_raise=TimeoutError("Request timed out"))
    synth_timeout = ComplianceJourneyV2Synthesizer(groq_client=mock_timeout)
    resp_timeout = synth_timeout.synthesize(input_data)
    assert synth_timeout.last_trace["fallback_used"] is True
    assert "TimeoutError" in synth_timeout.last_trace["fallback_reason"]
    assert resp_timeout.mandatory_certification.is_mandatory is True

    # Malformed JSON
    mock_malformed = MockGroqClient(response_text="This is not JSON at all.")
    synth_malformed = ComplianceJourneyV2Synthesizer(groq_client=mock_malformed)
    resp_malformed = synth_malformed.synthesize(input_data)
    assert synth_malformed.last_trace["fallback_used"] is True
    assert synth_malformed.last_trace["fallback_reason"] == "MALFORMED_JSON"
    assert resp_malformed.mandatory_certification.is_mandatory is True


# ---------------------------------------------------------------------------
# 12. Canonical Queries: Dynamic Validation Against Real Contexts
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("query,expected_std,expected_mandatory", [
    ("IS 4985", "IS 4985", True),
    ("what standards apply to building bricks", "IS 1077", False),
    ("what certification is required for IS 16046 Part 2", "IS 16046", True),
])
def test_canonical_queries_dynamic_validation(query, expected_std, expected_mandatory):
    """Verify that canonical queries validate dynamically against their PC-5 deterministic inputs."""
    builder = ComplianceContextBuilder()
    resp, meta = builder.execute_compliance_journey(query=query)

    # Validate standards
    stds = resp.applicable_standards.standards
    assert any(expected_std in s for s in stds)

    # Validate mandatory status
    assert resp.mandatory_certification.is_mandatory == expected_mandatory

    # Validate zero remaining unsupported claims
    report = meta.get("correctness_report", {})
    assert report.get("unsupported_claims_remaining") == 0


# ---------------------------------------------------------------------------
# 13. Cross-Query Progressive Context Contamination Safety
# ---------------------------------------------------------------------------
def test_cross_query_contamination_isolation():
    """Verify that sequential queries (IS 4985 -> IS 374 -> timber doors) do not leak context."""
    builder = ComplianceContextBuilder()

    # Query 1: IS 4985 (pipes)
    resp1, meta1 = builder.execute_compliance_journey(query="IS 4985")
    assert any("4985" in s for s in resp1.applicable_standards.standards)

    # Query 2: IS 374 (fans)
    resp2, meta2 = builder.execute_compliance_journey(query="IS 374")
    v2_str2 = json.dumps(resp2.to_structured_dict())
    assert "4985" not in v2_str2, "IS 4985 leaked into IS 374 response!"
    assert "pvc" not in v2_str2.lower(), "PVC pipe context leaked into IS 374 response!"

    # Query 3: timber doors (unestablished standard)
    resp3, meta3 = builder.execute_compliance_journey(query="timber doors")
    v2_str3 = json.dumps(resp3.to_structured_dict())
    assert "374" not in v2_str3, "IS 374 leaked into timber doors response!"
    assert "4985" not in v2_str3, "IS 4985 leaked into timber doors response!"
    assert "ceiling fan" not in v2_str3.lower()


# ---------------------------------------------------------------------------
# 14. Fallback Correctness: Respects Authority Locks
# ---------------------------------------------------------------------------
def test_fallback_respects_authority_locks():
    """Verify that deterministic fallback paths strictly preserve PC-5 authority locks."""
    builder = ComplianceContextBuilder()
    # Force fallback by mocking GroqClient to raise
    builder.synthesizer._groq_client = MockGroqClient(should_raise=Exception("Simulated API failure"))

    # Mandatory = True fallback
    resp_mand, meta_mand = builder.execute_compliance_journey(query="IS 4985")
    assert meta_mand["fallback_used"] is True
    assert resp_mand.mandatory_certification.is_mandatory is True
    assert "mandatory" in resp_mand.mandatory_certification.answer.lower()

    # Mandatory = False fallback
    resp_vol, meta_vol = builder.execute_compliance_journey(query="what standards apply to building bricks")
    assert meta_vol["fallback_used"] is True
    assert resp_vol.mandatory_certification.is_mandatory is False
    assert "has not been established" in resp_vol.mandatory_certification.answer.lower() or "not established" in resp_vol.mandatory_certification.answer.lower()


# ---------------------------------------------------------------------------
# 15. Stage Completeness & Quality Report Structure
# ---------------------------------------------------------------------------
def test_stage_completeness_and_quality_report_structure():
    """Verify all 10 stages exist and quality report exposes exact deterministic metrics."""
    builder = ComplianceContextBuilder()
    resp, meta = builder.execute_compliance_journey(query="IS 374")

    report = meta.get("correctness_report", {})
    assert "total_contradictions_detected" in report
    assert "contradictions_resolved" in report
    assert "unsupported_claims_detected" in report
    assert "unsupported_claims_resolved" in report
    assert "unsupported_claims_remaining" in report
    assert report["unsupported_claims_remaining"] == 0

    assert "stage_quality_scores" in report
    scores = report["stage_quality_scores"]
    assert len(scores) == 10

    for s_num, score in scores.items():
        assert score["question_answered"] is True
        assert isinstance(score["authoritative_claims"], int)
        assert isinstance(score["unsupported_claims"], int)
        assert score["unsupported_claims"] == 0, f"Stage {s_num} has unresolved unsupported claims"
        assert 0.0 <= score["evidence_coverage"] <= 1.0


# ---------------------------------------------------------------------------
# 16. Live Groq Measurement (Conditional on Available API Configuration)
# ---------------------------------------------------------------------------
def test_live_groq_measurement_if_configured():
    """Verify live Groq synthesis call, measuring single-call execution, latency, and correctness."""
    gc = GroqClient()
    if not gc.is_configured:
        pytest.skip("GroqClient is not configured with active API keys.")

    builder = ComplianceContextBuilder()
    t0 = time.time()
    resp, meta = builder.execute_compliance_journey(query="IS 374")
    elapsed_sec = round(time.time() - t0, 3)

    # Verify exactly one synthesis call
    assert meta.get("synthesis_call_count") == 1

    # Verify structured response is complete
    assert resp.product_identification.answer
    assert resp.applicable_standards.standards
    assert resp.assessment.answer

    # Verify correctness validation executed cleanly
    report = meta.get("correctness_report", {})
    assert report.get("unsupported_claims_remaining") == 0

    # Record telemetry
    print(f"\n[LIVE GROQ MEASUREMENT] Query='IS 374' Total Pipeline: {meta.get('total_ms')}ms, Groq: {meta.get('groq_ms')}ms, Fallback: {meta.get('fallback_used')}")
