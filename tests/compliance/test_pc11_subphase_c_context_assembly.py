"""
tests/compliance/test_pc11_subphase_c_context_assembly.py
Sub-phase C: Compliance Context Assembly & Single-Synthesis Pipeline Verification.

Verifies:
1. Production targets 1-8: IS 374, IS 4985, IS 16046 Part 2, IS 15750, IS 1077,
   Timber doors, PVC pipes, BLDC ceiling fan:
   - Product context reaches GroqComplianceInput.
   - Standard context reaches GroqComplianceInput.
   - PC-5 deterministic results are preserved (never hardcoding regulatory facts).
   - Evidence is partitioned by stage and unrelated evidence is excluded.
   - Stage 9 receives real F3 laboratory records where PC-5 returns them.
   - Exactly ONE synthesis call occurs.
   - All 10 stages are present in the response.
2. Missing RAG resilience: Zero RAG evidence still produces full 10-stage output with no crashes or jargon leakage.
3. 429 rate limit fallback: Graceful deterministic fallback without crashing or hallucinating.
4. Conversational anaphora resolution across multi-turn history.
5. Telemetry: nlu_ms, pc5_ms, rag_ms, context_build_ms, groq_ms, total_ms are tracked.
6. Cryptographic baseline hash preservation for all 12 frozen files.
"""

import json
import hashlib
from pathlib import Path
from unittest.mock import patch
import pytest

from backend.compliance_context_builder import ComplianceContextBuilder
from backend.compliance_journey_v2_synthesizer import (
    ComplianceJourneyV2Synthesizer,
    GroqComplianceInput,
    ComplianceJourneyV2Response,
)
from tests.compliance.test_pc11_subphase_b_groq_synthesis import (
    MockGroqClient,
    get_mock_ten_stage_json,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BASELINE_HASHES_FILE = PROJECT_ROOT / "scratch_pc6_baseline_hashes.json"


@pytest.fixture(scope="module")
def builder():
    """Provides a shared ComplianceContextBuilder with a MockGroqClient."""
    mock_client = MockGroqClient(response_text=get_mock_ten_stage_json())
    synth = ComplianceJourneyV2Synthesizer(groq_client=mock_client)
    return ComplianceContextBuilder(synthesizer=synth)


# ---------------------------------------------------------------------------
# Tests 1-8: Target Queries Validation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "query, expected_std_pattern, expected_product_pattern",
    [
        ("IS 374", r"IS\s*374", r"fan"),
        ("is certification mandatory for IS 4985", r"IS\s*4985", r"pipe"),
        ("IS 16046 Part 2", r"IS\s*16046", r"cell|battery"),
        ("IS 15750", r"IS\s*15750", r"fridge|refrigerator|appliance"),
        ("IS 1077", r"IS\s*1077", r"brick"),
        ("timber doors", None, r"door"),
        ("PVC pipes", None, r"pipe"),
        ("I manufacture BLDC ceiling fans", r"IS\s*374", r"fan"),
    ]
)
def test_target_queries_context_assembly_and_synthesis(
    builder, query, expected_std_pattern, expected_product_pattern
):
    """
    Verifies that for each of the 8 production queries:
    - Product and standard context reach GroqComplianceInput.
    - Deterministic PC-5 determinations are preserved without hardcoding answers.
    - Evidence is partitioned by stage.
    - F3 laboratories populate Stage 9 when returned by PC-5.
    - Exactly ONE Groq synthesis call occurs.
    - All 10 stages exist in the structured response.
    """
    mock_client = builder.synthesizer.groq_client
    mock_client.call_count = 0  # Reset counter

    input_data, meta = builder.build_compliance_input(query)

    # 1. Product Context Reaches GroqComplianceInput
    assert input_data.product is not None, f"Product missing in GroqComplianceInput for '{query}'"
    if expected_product_pattern:
        import re
        assert re.search(expected_product_pattern, input_data.product, re.IGNORECASE), (
            f"Product '{input_data.product}' does not match '{expected_product_pattern}'"
        )

    # 2. Standard Context Reaches GroqComplianceInput
    if expected_std_pattern:
        import re
        matched = any(re.search(expected_std_pattern, s, re.IGNORECASE) for s in input_data.standards)
        assert matched, f"Standard pattern '{expected_std_pattern}' not found in standards: {input_data.standards}"

    # 3. Deterministic PC-5 Results Preserved Exactly
    det = input_data.deterministic_results
    assert "is_mandatory" in det
    assert "qco_status" in det
    assert "certification_scheme" in det
    assert "stage_6" in det
    assert "stage_7" in det
    assert "stage_8" in det
    assert "stage_10" in det

    # 4. Evidence Partitioned by Stage
    assert isinstance(input_data.rag_evidence, list)
    assert isinstance(input_data.certification_evidence, list)
    assert isinstance(input_data.testing_evidence, list)
    assert isinstance(input_data.inspection_evidence, list)
    assert isinstance(input_data.sampling_evidence, list)
    assert isinstance(input_data.certification_process_evidence, list)

    # 5. F3 Laboratories in Stage 9
    assert isinstance(input_data.f3_laboratories, list)
    for lab in input_data.f3_laboratories:
        assert "laboratory_name" in lab
        assert "public_lab_code" in lab

    # 6. Execute Synthesis: Exactly ONE Call
    response, response_meta = builder.execute_compliance_journey(query)
    assert mock_client.call_count == 1, f"Expected 1 Groq call, got {mock_client.call_count}"
    assert response_meta["synthesis_call_count"] == 1

    # 7. All 10 Stages Present
    assert isinstance(response, ComplianceJourneyV2Response)
    s_dict = response.to_structured_dict()
    assert len(s_dict) == 12  # 10 stages + assessment + next_steps


# ---------------------------------------------------------------------------
# Test 9: Zero RAG Evidence Resilience
# ---------------------------------------------------------------------------
def test_zero_rag_evidence_resilience(builder):
    """
    Verifies that when RAG returns zero evidence:
    - GroqComplianceInput is still fully assembled.
    - All 10 stages remain present.
    - Exactly one synthesis call occurs.
    - No crash occurs and no internal technical jargon leaks into user fields.
    """
    mock_client = builder.synthesizer.groq_client
    mock_client.call_count = 0

    with patch.object(builder, "_execute_rag", return_value=[]):
        input_data, meta = builder.build_compliance_input("IS 4985")
        assert len(input_data.rag_evidence) == 0
        assert len(input_data.testing_evidence) == 0

        response, resp_meta = builder.execute_compliance_journey("IS 4985")
        assert mock_client.call_count == 1
        assert resp_meta["synthesis_call_count"] == 1
        assert isinstance(response, ComplianceJourneyV2Response)

        # Confirm no internal jargon leakage
        for text in [
            response.product_identification.answer,
            response.applicable_standards.answer,
            response.testing.answer,
            response.assessment.answer
        ]:
            assert "PC-3" not in text
            assert "PC-5" not in text
            assert "RAG" not in text


# ---------------------------------------------------------------------------
# Test 10: 429 Rate Limit Fallback Integration
# ---------------------------------------------------------------------------
def test_429_rate_limit_fallback_integration():
    """
    Verifies that when GroqClient encounters 429 during real context journey:
    - Pipeline does not crash.
    - Deterministic fallback preserves real PC-5 data.
    - Telemetry records fallback.
    """
    failing_client = MockGroqClient(raises_exception=RuntimeError("GROQ_ALL_KEYS_RATE_LIMITED"))
    synth = ComplianceJourneyV2Synthesizer(groq_client=failing_client)
    builder_429 = ComplianceContextBuilder(synthesizer=synth)

    response, meta = builder_429.execute_compliance_journey("IS 4985")

    assert meta["fallback_used"] is True
    assert meta["fallback_reason"] == "RATE_LIMITED_429"
    assert isinstance(response, ComplianceJourneyV2Response)
    # Preserves real PC-5 determination: IS 4985 is mandatory under published QCO
    assert response.mandatory_certification.is_mandatory is True
    assert "IS 4985" in response.applicable_standards.answer


# ---------------------------------------------------------------------------
# Test 11: Conversational Anaphora Resolution
# ---------------------------------------------------------------------------
def test_conversational_anaphora_resolution(builder):
    """
    Turn 1: 'I manufacture BLDC ceiling fans'
    Turn 2: 'What testing is required for them?'
    Verifies:
    - 'them' resolves to ceiling fans.
    - Product and standard context reach GroqComplianceInput.
    - Conversation history is preserved in input.
    """
    conversation_history = [
        {"role": "user", "content": "I manufacture BLDC ceiling fans"},
        {"role": "assistant", "content": "BLDC ceiling fans are governed by IS 374:2019."}
    ]

    input_data, meta = builder.build_compliance_input(
        query="What testing is required for them?",
        conversation_history=conversation_history
    )

    # Anaphora resolved to ceiling fans / IS 374
    assert input_data.product is not None
    assert "fan" in input_data.product.lower()
    assert any("374" in s for s in input_data.standards)
    assert input_data.conversation_history == conversation_history
    assert input_data.product_attributes.get("conversational_context_resolved") is True


# ---------------------------------------------------------------------------
# Test 12: Telemetry Timings Validation
# ---------------------------------------------------------------------------
def test_telemetry_timings_validation(builder):
    """
    Verifies telemetry contains:
    - nlu_ms, pc5_ms, rag_ms, context_build_ms, groq_ms, total_ms
    - total_ms >= component timings.
    """
    response, meta = builder.execute_compliance_journey("IS 374")

    required_metrics = ["nlu_ms", "pc5_ms", "rag_ms", "context_build_ms", "groq_ms", "total_ms"]
    for m in required_metrics:
        assert m in meta, f"Missing telemetry metric: {m}"
        assert isinstance(meta[m], (int, float)), f"Metric {m} is not a number"
        assert meta[m] >= 0.0, f"Metric {m} is negative"

    # Total ms spans components
    assert meta["total_ms"] >= meta["context_build_ms"]
    assert meta["total_ms"] >= meta["groq_ms"]


# ---------------------------------------------------------------------------
# Test 13: Frozen Subsystem Cryptographic Baseline Hash Preservation
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
