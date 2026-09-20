"""
tests/compliance/test_pc11_subphase_b_groq_synthesis.py
Sub-phase B: One-Call Ten-Question Groq Synthesis & Output Parsing Verification.

Verifies:
1. Exactly ONE Groq call generates the complete 10-stage compliance journey.
2. Structured output parsing and shape validation for all 10 stages, assessment, and next_steps.
3. Preferred flow (direct JSON) vs defensive recovery (extract_json_payload).
4. Graceful deterministic fallback on 429 rate limit, timeout, unconfigured client, and malformed JSON.
5. Invariant preservation: Stage 9 (Laboratories) is strictly locked to authoritative F3 LIMS data.
6. User-facing terminology sanitization: technical jargon is purged from user-facing fields while preserved in internal traces.
7. Semantic correctness engine is NOT executed in Sub-phase B (deferred to Sub-phase D).
8. Frozen subsystem cryptographic baseline hash preservation.
"""

import json
import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from ai.compliance.journey_v2_models import ComplianceJourneyV2Response
from backend.compliance_journey_v2_synthesizer import (
    GroqComplianceInput,
    ComplianceJourneyV2Synthesizer,
    extract_json_payload,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BASELINE_HASHES_FILE = PROJECT_ROOT / "scratch_pc6_baseline_hashes.json"


def get_mock_ten_stage_json():
    """Generates a complete, valid 10-stage Groq compliance response."""
    return json.dumps({
        "product_identification": {
            "title": "Product Identification",
            "answer": "The user is inquiring about BLDC ceiling fans, which are electronically commutated, energy-efficient electric ceiling fans.",
            "key_information": ["Category: Electric Ceiling Fans", "Motor Technology: Brushless DC"],
            "evidence_ids": ["ev_prod_01"]
        },
        "applicable_standards": {
            "title": "Applicable Indian Standards",
            "answer": "The primary Indian Standard governing electric ceiling fans is IS 374:2019, covering safety, performance, and energy efficiency.",
            "key_information": ["Primary Standard: IS 374:2019"],
            "evidence_ids": ["ev_std_01"]
        },
        "regulatory_status": {
            "title": "QCO / Regulatory Status",
            "answer": "Electric ceiling fans are notified under the mandatory Quality Control Order issued by the Ministry of Heavy Industries.",
            "key_information": ["Regulated under Ministry Quality Control Order"],
            "evidence_ids": ["ev_qco_01"]
        },
        "mandatory_certification": {
            "title": "Mandatory Certification",
            "answer": "BIS certification is legally mandatory. Manufacturers must secure a BIS licence prior to commercial distribution.",
            "key_information": ["Statutory Obligation: Mandatory", "Legal Prerequisite for Sale"],
            "evidence_ids": ["ev_mand_01"]
        },
        "certification_scheme": {
            "title": "Certification Scheme",
            "answer": "Certification operates under Scheme-I (ISI Mark) of the BIS (Conformity Assessment) Regulations, 2018.",
            "key_information": ["Scheme: Scheme-I (ISI Mark)", "Factory Audit Required"],
            "evidence_ids": ["ev_sch_01"]
        },
        "testing": {
            "title": "Required Testing",
            "answer": "Testing requires verification of air delivery, service value, electrical safety, insulation resistance, and temperature rise.",
            "key_information": ["Key Tests: Air Delivery, Service Value, Electrical Safety"],
            "evidence_ids": ["ev_test_01"]
        },
        "inspection": {
            "title": "Factory Inspection",
            "answer": "BIS officers conduct a preliminary factory inspection to assess manufacturing infrastructure, quality systems, and in-house testing facilities.",
            "key_information": ["Factory audit is a prerequisite for licence grant"],
            "evidence_ids": ["ev_insp_01"]
        },
        "sampling": {
            "title": "Lot & Control Unit Sampling",
            "answer": "Sampling of control units is performed during the audit for independent laboratory testing, along with routine lot-level quality checks.",
            "key_information": ["Representative audit sample drawn for independent testing"],
            "evidence_ids": ["ev_samp_01"]
        },
        "laboratories": {
            "title": "Qualified BIS Laboratories",
            "answer": "Testing can be conducted across recognized BIS central and regional laboratories.",
            "key_information": ["Independent laboratory test reports required"],
            "evidence_ids": ["ev_lab_01"]
        },
        "certification_process": {
            "title": "Certification Process",
            "answer": "The manufacturer submits an application on Manakonline, prepares in-house test equipment, undergoes factory audit, and obtains the Grant of Licence.",
            "key_information": ["Step 1: Online application on Manakonline", "Step 2: Factory Inspection", "Step 3: Grant of Licence"],
            "evidence_ids": ["ev_proc_01"]
        },
        "assessment": {
            "title": "Assessment",
            "answer": "Yes, manufacturing BLDC ceiling fans requires mandatory BIS certification under IS 374:2019 Scheme-I before you can sell them in India.",
            "key_information": ["Mandatory: Yes", "Standard: IS 374:2019", "Scheme: Scheme-I"],
            "evidence_ids": ["ev_assess_01"]
        },
        "next_steps": [
            "Obtain and review IS 374:2019 specifications.",
            "Set up required in-house test equipment in accordance with the Scheme of Inspection and Testing.",
            "Register and submit your application on the BIS Manakonline portal."
        ]
    })


class MockGroqClient:
    """Mock Groq client for controlled testing of Sub-phase B."""

    def __init__(self, response_text: str = "", raises_exception: Exception = None, is_configured: bool = True):
        self.response_text = response_text
        self.raises_exception = raises_exception
        self._configured = is_configured
        self.call_count = 0
        self.last_messages = None
        self.last_max_tokens = None

    @property
    def is_configured(self) -> bool:
        return self._configured

    def chat_completion(self, messages, max_tokens=800, trace_info=None):
        self.call_count += 1
        self.last_messages = messages
        self.last_max_tokens = max_tokens
        if trace_info is not None:
            trace_info["selected_key_id"] = "MOCK_KEY_1"
            trace_info["failover_used"] = False
        if self.raises_exception:
            raise self.raises_exception
        return self.response_text


# ---------------------------------------------------------------------------
# Test 1: Complete 10-Stage Single-Call Synthesis
# ---------------------------------------------------------------------------
def test_single_call_ten_stage_synthesis_success():
    """Verify exactly ONE Groq call populates all 10 stages, assessment, and next_steps."""
    mock_client = MockGroqClient(response_text=get_mock_ten_stage_json())
    synthesizer = ComplianceJourneyV2Synthesizer(groq_client=mock_client)

    input_data = GroqComplianceInput(
        user_question="I manufacture BLDC ceiling fans. What compliance applies?",
        product="BLDC ceiling fans",
        standards=["IS 374:2019"],
        deterministic_results={"is_mandatory": True, "certification_scheme": "Scheme-I (ISI Mark)"}
    )

    response = synthesizer.synthesize(input_data)

    # Invariant: EXACTLY ONE Groq call per journey
    assert mock_client.call_count == 1, f"Expected exactly 1 Groq call, made {mock_client.call_count}"
    assert synthesizer.last_trace["call_count"] == 1
    assert synthesizer.last_trace["fallback_used"] is False
    assert synthesizer.last_trace["groq_invoked"] is True

    # Assert response type
    assert isinstance(response, ComplianceJourneyV2Response)

    # Assert all 10 stages exist and are populated
    assert response.product_identification.title == "Product Identification"
    assert "BLDC" in response.product_identification.answer
    assert response.applicable_standards.title == "Applicable Indian Standards"
    assert "IS 374" in response.applicable_standards.answer
    assert response.regulatory_status.title == "QCO / Regulatory Status"
    assert response.mandatory_certification.title == "Mandatory Certification"
    assert response.mandatory_certification.is_mandatory is True
    assert response.certification_scheme.title == "Certification Scheme"
    assert response.testing.title == "Required Testing"
    assert response.inspection.title == "Factory Inspection"
    assert response.sampling.title == "Lot & Control Unit Sampling"
    assert response.laboratories.title == "Qualified BIS Laboratories"
    assert response.certification_process.title == "Certification Process"
    assert response.assessment.title == "Assessment"
    assert "mandatory" in response.assessment.answer.lower()
    assert len(response.next_steps) == 3

    # Assert to_structured_dict conversion
    s_dict = response.to_structured_dict()
    assert len(s_dict) == 12  # 10 stages + assessment + next_steps


# ---------------------------------------------------------------------------
# Test 2: Preferred Flow (Direct JSON) vs Markdown Code Block
# ---------------------------------------------------------------------------
def test_preferred_structured_json_with_code_block():
    """Verify standard markdown code block json is parsed directly without fallback."""
    fenced_json = f"```json\n{get_mock_ten_stage_json()}\n```"
    mock_client = MockGroqClient(response_text=fenced_json)
    synthesizer = ComplianceJourneyV2Synthesizer(groq_client=mock_client)

    input_data = GroqComplianceInput(
        user_question="Ceiling fan compliance",
        product="Ceiling fan",
        standards=["IS 374"]
    )

    response = synthesizer.synthesize(input_data)
    assert mock_client.call_count == 1
    assert synthesizer.last_trace["fallback_used"] is False
    assert response.product_identification.title == "Product Identification"
    assert "BLDC" in response.product_identification.answer


# ---------------------------------------------------------------------------
# Test 3: Defensive Recovery (extract_json_payload) on Preamble & Postamble
# ---------------------------------------------------------------------------
def test_defensive_recovery_from_preamble_and_postamble():
    """Verify extract_json_payload recovers JSON when model includes conversational text."""
    dirty_text = (
        "Here is the structured compliance journey analysis for your product:\n\n"
        + get_mock_ten_stage_json()
        + "\n\nPlease let me know if you need additional BIS regulatory assistance!"
    )
    mock_client = MockGroqClient(response_text=dirty_text)
    synthesizer = ComplianceJourneyV2Synthesizer(groq_client=mock_client)

    input_data = GroqComplianceInput(
        user_question="Ceiling fan compliance",
        product="Ceiling fan",
        standards=["IS 374"]
    )

    response = synthesizer.synthesize(input_data)
    assert mock_client.call_count == 1
    assert synthesizer.last_trace["fallback_used"] is False
    assert synthesizer.last_trace["json_recovery_used"] is True
    assert response.applicable_standards.title == "Applicable Indian Standards"


# ---------------------------------------------------------------------------
# Test 4: extract_json_payload Standalone Recovery Capabilities
# ---------------------------------------------------------------------------
def test_extract_json_payload_resilience():
    """Verify extract_json_payload handles fences, slice extraction, and trailing commas."""
    # 1. Direct JSON
    assert extract_json_payload('{"a": 1}') == {"a": 1}

    # 2. Markdown fence
    assert extract_json_payload('```json\n{"b": 2}\n```') == {"b": 2}

    # 3. Outer text wrapper
    assert extract_json_payload('Prefix text {"c": 3} Suffix text') == {"c": 3}

    # 4. Trailing comma recovery
    assert extract_json_payload('{"items": [1, 2, ], "d": 4, }') == {"items": [1, 2], "d": 4}

    # 5. Invalid text returns None
    assert extract_json_payload("No json here at all") is None
    assert extract_json_payload("") is None
    assert extract_json_payload(None) is None


# ---------------------------------------------------------------------------
# Test 5: Fallback on 429 Rate Limit (All Keys Exhausted)
# ---------------------------------------------------------------------------
def test_fallback_on_429_rate_limit():
    """Verify 429 error triggers deterministic fallback without raising an exception."""
    mock_client = MockGroqClient(raises_exception=RuntimeError("GROQ_ALL_KEYS_RATE_LIMITED"))
    synthesizer = ComplianceJourneyV2Synthesizer(groq_client=mock_client)

    input_data = GroqComplianceInput(
        user_question="Is certification mandatory for IS 4985?",
        standards=["IS 4985"],
        deterministic_results={"is_mandatory": True, "standards": ["IS 4985"]}
    )

    # Must NOT raise exception
    response = synthesizer.synthesize(input_data)

    assert mock_client.call_count == 1
    assert synthesizer.last_trace["fallback_used"] is True
    assert synthesizer.last_trace["fallback_reason"] == "RATE_LIMITED_429"

    # Structurally valid response
    assert isinstance(response, ComplianceJourneyV2Response)
    assert response.applicable_standards.standards == ["IS 4985"]
    assert response.mandatory_certification.is_mandatory is True
    assert len(response.next_steps) > 0


# ---------------------------------------------------------------------------
# Test 6: Fallback on Timeout or Network Error
# ---------------------------------------------------------------------------
def test_fallback_on_timeout_error():
    """Verify timeout triggers deterministic fallback gracefully."""
    mock_client = MockGroqClient(raises_exception=TimeoutError("Request timed out after 10s"))
    synthesizer = ComplianceJourneyV2Synthesizer(groq_client=mock_client)

    input_data = GroqComplianceInput(
        user_question="Testing parameters for IS 374",
        standards=["IS 374"],
        deterministic_results={"is_mandatory": True}
    )

    response = synthesizer.synthesize(input_data)
    assert mock_client.call_count == 1
    assert synthesizer.last_trace["fallback_used"] is True
    assert synthesizer.last_trace["fallback_reason"] == "EXCEPTION_TimeoutError"
    assert isinstance(response, ComplianceJourneyV2Response)


# ---------------------------------------------------------------------------
# Test 7: Fallback on Unconfigured Groq Client
# ---------------------------------------------------------------------------
def test_fallback_on_unconfigured_client():
    """Verify unconfigured GroqClient uses deterministic fallback with 0 API calls."""
    mock_client = MockGroqClient(is_configured=False)
    synthesizer = ComplianceJourneyV2Synthesizer(groq_client=mock_client)

    input_data = GroqComplianceInput(
        user_question="Compliance requirements for cement",
        product="Cement"
    )

    response = synthesizer.synthesize(input_data)
    assert mock_client.call_count == 0  # No API call made
    assert synthesizer.last_trace["fallback_used"] is True
    assert synthesizer.last_trace["fallback_reason"] == "GROQ_NOT_CONFIGURED"
    assert isinstance(response, ComplianceJourneyV2Response)


# ---------------------------------------------------------------------------
# Test 8: Fallback on Completely Unparseable Garbage Output
# ---------------------------------------------------------------------------
def test_fallback_on_unparseable_garbage():
    """Verify non-JSON garbage triggers fallback without crashing."""
    mock_client = MockGroqClient(response_text="I am sorry, but I cannot assist with this regulatory query at this time.")
    synthesizer = ComplianceJourneyV2Synthesizer(groq_client=mock_client)

    input_data = GroqComplianceInput(
        user_question="Compliance inquiry",
        standards=["IS 1077"]
    )

    response = synthesizer.synthesize(input_data)
    assert mock_client.call_count == 1
    assert synthesizer.last_trace["fallback_used"] is True
    assert synthesizer.last_trace["fallback_reason"] == "MALFORMED_JSON"
    assert isinstance(response, ComplianceJourneyV2Response)
    assert response.applicable_standards.standards == ["IS 1077"]


# ---------------------------------------------------------------------------
# Test 9: Stage 9 (Laboratories) Invariant - 100% Locked to F3 LIMS
# ---------------------------------------------------------------------------
def test_stage_9_f3_laboratories_invariant_preservation():
    """Verify that Groq NEVER creates laboratory records; F3 input strictly overrides."""
    # Groq response contains hallucinated laboratories
    groq_resp_with_fake_labs = json.loads(get_mock_ten_stage_json())
    groq_resp_with_fake_labs["laboratories"] = {
        "title": "Qualified BIS Laboratories",
        "answer": "Testing is conducted at Fake Hallucinated Testing Corp and Imaginary Lab.",
        "recognized_labs": ["Fake Hallucinated Testing Corp", "Imaginary Lab"],
        "evidence_ids": ["hallucinated_id_999"]
    }

    mock_client = MockGroqClient(response_text=json.dumps(groq_resp_with_fake_labs))
    synthesizer = ComplianceJourneyV2Synthesizer(groq_client=mock_client)

    authoritative_f3_labs = [
        {"laboratory_name": "BIS Central Laboratory Ghaziabad", "public_lab_code": "CL-01", "city": "Ghaziabad"},
        {"laboratory_name": "National Test House Kolkata", "public_lab_code": "NTH-02", "city": "Kolkata"}
    ]

    input_data = GroqComplianceInput(
        user_question="Which labs can test ceiling fans?",
        standards=["IS 374:2019"],
        f3_laboratories=authoritative_f3_labs
    )

    response = synthesizer.synthesize(input_data)

    # Invariant: recognized_labs strictly contains the F3 laboratories
    assert response.laboratories.recognized_labs == [
        "BIS Central Laboratory Ghaziabad",
        "National Test House Kolkata"
    ]
    # Hallucinated lab records must be completely absent
    assert "Fake Hallucinated Testing Corp" not in response.laboratories.recognized_labs
    assert "Imaginary Lab" not in response.laboratories.recognized_labs
    # Evidence IDs strictly match F3 records
    assert set(response.laboratories.evidence_ids) == {"CL-01", "NTH-02"}


# ---------------------------------------------------------------------------
# Test 10: User-Facing Internal Terminology Sanitization
# ---------------------------------------------------------------------------
def test_user_facing_terminology_sanitization():
    """Verify internal engine labels are purged from user-facing fields while preserved in trace."""
    polluted_json = json.loads(get_mock_ten_stage_json())
    polluted_json["product_identification"]["answer"] = "Identified via PC-3 relationship engine as GROUNDED fan."
    polluted_json["applicable_standards"]["answer"] = "Standards verified from RAG evidence corpus and PC-5 journey."
    polluted_json["mandatory_certification"]["answer"] = "Mandatory under GROUNDED regulatory baseline with LLM_FALLBACK."
    polluted_json["assessment"]["answer"] = "Overall assessment based on PC-4 testing and retrieval status HYBRID."
    polluted_json["next_steps"] = ["Check PC-3 engine", "Review RAG corpus", "Apply via portal"]

    mock_client = MockGroqClient(response_text=json.dumps(polluted_json))
    synthesizer = ComplianceJourneyV2Synthesizer(groq_client=mock_client)

    input_data = GroqComplianceInput(user_question="Ceiling fan query", standards=["IS 374"])
    response = synthesizer.synthesize(input_data)

    forbidden_patterns = [
        "PC-3", "PC-4", "PC-5", "RAG", "UNKNOWN", "GROUNDED", "HYBRID",
        "LLM_FALLBACK", "evidence corpus", "retrieval status"
    ]

    # Verify user-facing fields have NO forbidden technical jargon
    for field_text in [
        response.product_identification.answer,
        response.applicable_standards.answer,
        response.mandatory_certification.answer,
        response.assessment.answer,
        *response.next_steps
    ]:
        for forbidden in forbidden_patterns:
            assert forbidden not in field_text, f"Forbidden term '{forbidden}' leaked into: '{field_text}'"

    # Verify trace telemetry still retains internal diagnostic keys (Correction 6)
    assert "groq_invoked" in synthesizer.last_trace
    assert "call_count" in synthesizer.last_trace
    assert synthesizer.last_trace["call_count"] == 1


# ---------------------------------------------------------------------------
# Test 11: Correctness Engine NOT Executed in Sub-phase B
# ---------------------------------------------------------------------------
def test_no_semantic_correctness_engine_in_subphase_b():
    """Verify ComplianceCorrectnessEngine.enforce_semantic_consistency is NOT invoked (Correction 2)."""
    mock_client = MockGroqClient(response_text=get_mock_ten_stage_json())
    synthesizer = ComplianceJourneyV2Synthesizer(groq_client=mock_client, enable_correctness_guarding=False)

    input_data = GroqComplianceInput(
        user_question="Is certification mandatory for IS 4985?",
        standards=["IS 4985"],
        deterministic_results={"is_mandatory": True}
    )

    with patch(
        "backend.compliance_correctness_engine.ComplianceCorrectnessEngine.enforce_semantic_consistency"
    ) as mock_enforce:
        response = synthesizer.synthesize(input_data)
        # Sub-phase B responsibility boundary: MUST NOT invoke enforce_semantic_consistency
        mock_enforce.assert_not_called()

    assert isinstance(response, ComplianceJourneyV2Response)


# ---------------------------------------------------------------------------
# Test 12: Frozen Subsystem Cryptographic Baseline Hash Preservation
# ---------------------------------------------------------------------------
def test_baseline_hashes_unaltered():
    """Verify all 12 frozen files in scratch_pc6_baseline_hashes.json are 100% unaltered."""
    if not BASELINE_HASHES_FILE.exists(): pytest.skip("hashes missing")

    with open(BASELINE_HASHES_FILE, "r", encoding="utf-8") as f:
        baseline_hashes = json.load(f)

    for rel_path, expected_hash in baseline_hashes.items():
        full_path = PROJECT_ROOT / rel_path
        assert full_path.exists(), f"Target file missing: {rel_path}"

        hasher = hashlib.sha256()
        with open(full_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        actual_hash = hasher.hexdigest()

        assert actual_hash == expected_hash, (
            f"FROZEN CODE MODIFIED! Hash mismatch for {rel_path}:\n"
            f"Expected: {expected_hash}\n"
            f"Actual:   {actual_hash}"
        )
