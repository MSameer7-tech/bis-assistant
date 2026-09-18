"""
tests/compliance/test_pc10_answer_correctness.py
Phase 6: Compliance Answer Correctness Engine Verification Suite.

Validates:
1. IS 15750:
   - no invented testing
   - no invented inspection
   - no invented sampling
   - QCO status preserved
   - generic guidance cannot become product requirement

2. IS 374:
   - QCO conflict preserved
   - actual tests preserved
   - no unsupported scheme inference

3. IS 4985:
   - QCO preserved
   - mandatory certification preserved
   - certification information preserved
   - scheme only if authoritative evidence exists

4. IS 16046 Part 2:
   - CRS/Scheme-II only when evidence supports it
   - no unsupported certification claim
   - no factory inspection claim

5. IS 1077:
   - standards answer correct
   - no unsupported "voluntary" claim unless authoritative evidence establishes it

6. timber doors:
   - no fabricated standard
   - no fabricated certification requirement

7. quantum photonic flux capacitor:
   - no invented compliance pathway

8. Internal evidence scoring report verification:
   - question_answered: true/false
   - authoritative_claims: count
   - unsupported_claims: count
   - general_claims: count
   - contradictions: count
   - evidence_coverage: score (0.0 - 1.0)
   - 4 internal evidence levels exist and never bleed into user-facing text
"""

import json
import subprocess
from pathlib import Path
import pytest
import re
from backend.compliance_rag_synthesizer import get_compliance_rag_synthesizer
from ai.compliance.journey_models import ComplianceJourneyRequest, JourneyStatus
from backend.compliance_correctness_engine import (
    EvidenceLevel,
    ComplianceCorrectnessEngine,
    StageQualityScore
)


@pytest.fixture(scope="module")
def synthesizer():
    return get_compliance_rag_synthesizer()


# ---------------------------------------------------------------------------
# Test 1: IS 15750
# ---------------------------------------------------------------------------
def test_is_15750_no_invented_requirements(synthesizer):
    """
    IS 15750:
    - no invented testing
    - no invented inspection
    - no invented sampling
    - QCO status preserved
    - generic guidance cannot become product requirement
    """
    req = ComplianceJourneyRequest(query="IS 15750")
    journey = synthesizer.process_journey(req)
    v2 = journey.get("compliance_answer_v2", {})
    trace = journey.get("_dev_trace", {})
    correctness = trace.get("correctness_report", {})

    # Status & standard
    assert journey["status"] == JourneyStatus.JOURNEY_ESTABLISHED
    assert journey.get("applicable_standards", {}).get("primary_standard") == "IS 15750"

    # Stage 6: Testing Requirements - must not invent tests
    stg6 = v2.get("testing", {})
    assert len(stg6.get("test_methods", [])) == 0, "IS 15750 must not have invented test methods"
    ans6 = stg6.get("answer", "").lower()
    assert ("not established" in ans6 or "could not be confirmed" in ans6 or "not specified" in ans6), (
        f"Stage 6 answer should clearly state testing not confirmed: {stg6.get('answer')}"
    )
    # Check deterministic stage details in journey_dict
    det_stg6 = journey.get("testing", {}).get("synthesis", {})
    assert det_stg6.get("primary_answer") == "Testing requirements not established"

    # Stage 7: Inspection Requirements - must not claim routine factory surveillance as product evidence
    stg7 = v2.get("inspection", {})
    ans7 = stg7.get("answer", "").lower()
    assert "routine manufacturing & surveillance inspection" not in ans7, (
        f"Stage 7 should not claim routine manufacturing & surveillance inspection as product requirement: {stg7.get('answer')}"
    )
    assert ("not established" in ans7 or "could not be confirmed" in ans7 or "not documented" in ans7)

    # Stage 8: Sampling Requirements - must not claim uniform batch/control unit as product evidence
    stg8 = v2.get("sampling", {})
    ans8 = stg8.get("answer", "").lower()
    assert "lot & control unit sampling requirements established" not in ans8
    assert not re.search(r"\b5\s*%", ans8), "Stage 8 should not contain fabricated sampling percentage"
    assert ("not established" in ans8 or "could not be confirmed" in ans8 or "not documented" in ans8)

    # Stage 5: Scheme must not be guessed as Scheme-I
    stg5 = v2.get("certification_scheme", {})
    assert stg5.get("scheme_name") is None, "IS 15750 should not assert an unconfirmed scheme"

    # Assessment direct answer
    assess_ans = v2.get("assessment", {}).get("answer", "")
    assert "ANSWER:" in assess_ans
    assert "REGULATORY BASIS:" in assess_ans
    assert "CERTIFICATION:" in assess_ans
    assert "WHAT TO DO NEXT:" in assess_ans


# ---------------------------------------------------------------------------
# Test 2: IS 374
# ---------------------------------------------------------------------------
def test_is_374_qco_conflict_and_actual_tests_preserved(synthesizer):
    """
    IS 374:
    - QCO conflict preserved
    - actual tests preserved
    - no unsupported scheme inference
    """
    req = ComplianceJourneyRequest(query="what certification is required for IS 374")
    journey = synthesizer.process_journey(req)
    v2 = journey.get("compliance_answer_v2", {})

    # QCO status / conflict preserved
    reg_status = v2.get("regulatory_status", {})
    assert "conflict" in reg_status.get("answer", "").lower() or "active regulatory review" in reg_status.get("answer", "").lower()

    # Stage 4: Mandatory certification cannot be asserted True when in conflict
    stg4 = v2.get("mandatory_certification", {})
    assert stg4.get("is_mandatory") is None or stg4.get("is_mandatory") is False

    # Stage 5: No unsupported scheme inference
    stg5 = v2.get("certification_scheme", {})
    assert stg5.get("scheme_name") is None

    # Stage 6: Actual tests preserved (Air Delivery / Service Value)
    stg6 = v2.get("testing", {})
    test_methods = stg6.get("test_methods", [])
    assert len(test_methods) > 0, "IS 374 actual tests must be preserved"
    assert any("air delivery" in t.lower() or "service value" in t.lower() for t in test_methods)

    # Assessment preserves conflict & tests
    assess_ans = v2.get("assessment", {}).get("answer", "")
    assert "conflict" in assess_ans.lower()
    assert "air delivery" in assess_ans.lower() or "service value" in assess_ans.lower()


# ---------------------------------------------------------------------------
# Test 3: IS 4985
# ---------------------------------------------------------------------------
def test_is_4985_qco_mandatory_and_certification_preserved(synthesizer):
    """
    IS 4985:
    - QCO preserved
    - mandatory certification preserved
    - certification information preserved
    - scheme only if authoritative evidence exists
    """
    req = ComplianceJourneyRequest(query="is certification mandatory for IS 4985")
    journey = synthesizer.process_journey(req)
    v2 = journey.get("compliance_answer_v2", {})

    # Mandatory certification preserved
    stg4 = v2.get("mandatory_certification", {})
    assert stg4.get("is_mandatory") is True, "IS 4985 mandatory status must be True"
    assert "mandatory" in stg4.get("answer", "").lower()

    # QCO preserved
    reg_stg = v2.get("regulatory_status", {})
    assert "pipes and fittings" in reg_stg.get("answer", "").lower() or "4512" in reg_stg.get("answer", "")

    # Scheme only if authoritative evidence exists (not fabricated Scheme-I)
    stg5 = v2.get("certification_scheme", {})
    assert stg5.get("scheme_name") is None

    # Assessment answers the mandatory question directly
    assess_ans = v2.get("assessment", {}).get("answer", "")
    assert "yes" in assess_ans.lower() and "mandatory" in assess_ans.lower()
    assert "pipes and fittings" in assess_ans.lower()


# ---------------------------------------------------------------------------
# Test 4: IS 16046 Part 2
# ---------------------------------------------------------------------------
def test_is_16046_part_2_crs_only_and_no_factory_inspection(synthesizer):
    """
    IS 16046 Part 2:
    - CRS/Scheme-II only when evidence supports it
    - no unsupported certification claim
    - no factory inspection claim
    """
    req = ComplianceJourneyRequest(query="what certification is required for IS 16046 Part 2")
    journey = synthesizer.process_journey(req)
    v2 = journey.get("compliance_answer_v2", {})

    # Scheme is CRS / Scheme-II (authoritative from CRO)
    stg5 = v2.get("certification_scheme", {})
    assert stg5.get("scheme_name") == "Compulsory Registration Scheme (CRS) / Scheme-II"
    assert "compulsory registration" in stg5.get("answer", "").lower() or "crs" in stg5.get("answer", "").lower()

    # Mandatory certification True
    stg4 = v2.get("mandatory_certification", {})
    assert stg4.get("is_mandatory") is True

    # Factory inspection: CRS has NO pre-license factory audit!
    stg7 = v2.get("inspection", {})
    ans7 = stg7.get("answer", "").lower()
    assert "not required" in ans7 or "test-report registration" in ans7 or "no routine pre-license" in ans7, (
        f"CRS stage 7 must state factory inspection is not required: {stg7.get('answer')}"
    )

    # Assessment includes CRS
    assess_ans = v2.get("assessment", {}).get("answer", "")
    assert "compulsory registration scheme" in assess_ans.lower() or "crs" in assess_ans.lower()


# ---------------------------------------------------------------------------
# Test 5: IS 1077
# ---------------------------------------------------------------------------
def test_is_1077_standards_correct_and_no_unsupported_voluntary_claim(synthesizer):
    """
    IS 1077:
    - standards answer correct
    - no unsupported "voluntary" claim unless authoritative evidence establishes it
    """
    req = ComplianceJourneyRequest(query="what standards apply to building bricks")
    journey = synthesizer.process_journey(req)
    v2 = journey.get("compliance_answer_v2", {})

    # Standard correct
    stds = v2.get("applicable_standards", {}).get("standards", [])
    assert any("1077" in s for s in stds)

    # Mandatory is False
    stg4 = v2.get("mandatory_certification", {})
    assert stg4.get("is_mandatory") is False
    ans4 = stg4.get("answer", "").lower()
    # No unsupported "voluntary" claim
    assert "voluntary" not in ans4, f"Stage 4 should not assert voluntary certification without evidence: {ans4}"
    assert "has not been established" in ans4 or "not established" in ans4

    # Assessment direct answer
    assess_ans = v2.get("assessment", {}).get("answer", "")
    assert "IS 1077" in assess_ans or "1077" in assess_ans


# ---------------------------------------------------------------------------
# Test 6: Timber Doors (Unestablished Standard)
# ---------------------------------------------------------------------------
def test_timber_doors_no_fabricated_standard(synthesizer):
    """
    timber doors:
    - no fabricated standard
    - no fabricated certification requirement
    """
    req = ComplianceJourneyRequest(query="timber doors")
    journey = synthesizer.process_journey(req)
    v2 = journey.get("compliance_answer_v2", {})

    # Standard not established
    assert journey["status"] == JourneyStatus.STANDARD_NOT_ESTABLISHED
    stg2 = v2.get("applicable_standards", {})
    assert len(stg2.get("standards", [])) == 0

    # No fabricated mandatory certification
    stg4 = v2.get("mandatory_certification", {})
    assert stg4.get("is_mandatory") is None or stg4.get("is_mandatory") is False

    # Assessment states standard not established
    assess_ans = v2.get("assessment", {}).get("answer", "")
    assert "No applicable Indian Standard was established" in assess_ans or "could not be confirmed" in assess_ans


# ---------------------------------------------------------------------------
# Test 7: Quantum Photonic Flux Capacitor (Fictitious Product)
# ---------------------------------------------------------------------------
def test_quantum_flux_capacitor_no_invented_pathway(synthesizer):
    """
    quantum photonic flux capacitor:
    - no invented compliance pathway
    """
    req = ComplianceJourneyRequest(query="quantum photonic flux capacitor")
    journey = synthesizer.process_journey(req)
    v2 = journey.get("compliance_answer_v2", {})

    assert journey["status"] == JourneyStatus.STANDARD_NOT_ESTABLISHED
    stg4 = v2.get("mandatory_certification", {})
    assert stg4.get("is_mandatory") is None or stg4.get("is_mandatory") is False

    assess_ans = v2.get("assessment", {}).get("answer", "")
    assert "No applicable Indian Standard was established" in assess_ans or "could not be confirmed" in assess_ans
    assert "No active Quality Control Order" in assess_ans


# ---------------------------------------------------------------------------
# Test 8: Evidence Levels & Internal Scoring Report Verification
# ---------------------------------------------------------------------------
def test_internal_scoring_report_and_evidence_levels(synthesizer):
    """
    Verification of 4 evidence levels in internal scoring report:
    - question_answered: true/false
    - authoritative_claims: count
    - unsupported_claims: count
    - general_claims: count
    - contradictions: count
    - evidence_coverage: score (0.0 - 1.0)
    - strictly internal: levels never leak into UI text
    """
    # Verify EvidenceLevel enum
    assert EvidenceLevel.AUTHORITATIVE_PRODUCT_FACT == "AUTHORITATIVE_PRODUCT_FACT"
    assert EvidenceLevel.AUTHORITATIVE_GENERIC_FACT == "AUTHORITATIVE_GENERIC_FACT"
    assert EvidenceLevel.LLM_GENERAL_GUIDANCE == "LLM_GENERAL_GUIDANCE"
    assert EvidenceLevel.UNSUPPORTED == "UNSUPPORTED"

    req = ComplianceJourneyRequest(query="IS 4985")
    journey = synthesizer.process_journey(req)

    trace = journey.get("_dev_trace", {})
    assert "correctness_report" in trace, "correctness_report must be in _dev_trace"
    report = trace["correctness_report"]

    assert "stages" in report
    assert "total_contradictions_detected" in report
    assert "contradictions_resolved" in report

    # Verify score schema for each stage
    for s_num, s_score in report["stages"].items():
        assert "question_answered" in s_score
        assert isinstance(s_score["question_answered"], bool)
        assert "authoritative_claims" in s_score
        assert isinstance(s_score["authoritative_claims"], int)
        assert "unsupported_claims" in s_score
        assert isinstance(s_score["unsupported_claims"], int)
        assert s_score["unsupported_claims"] == 0, f"Unsupported claims must be 0 for stage {s_num}"
        assert "general_claims" in s_score
        assert isinstance(s_score["general_claims"], int)
        assert "contradictions" in s_score
        assert isinstance(s_score["contradictions"], int)
        assert "evidence_coverage" in s_score
        assert 0.0 <= s_score["evidence_coverage"] <= 1.0

    # Verify that internal evidence level labels NEVER leak into user-facing v2 answers
    v2 = journey.get("compliance_answer_v2", {})
    v2_str = str(v2)
    for level in [
        "AUTHORITATIVE_PRODUCT_FACT",
        "AUTHORITATIVE_GENERIC_FACT",
        "LLM_GENERAL_GUIDANCE",
        "UNSUPPORTED"
    ]:
        assert level not in v2_str, f"Internal evidence level {level} leaked into user-facing response!"


# ---------------------------------------------------------------------------
# Test 9: Rendered Journey Card Contradiction Verification (IS 4985 & IS 15750)
# ---------------------------------------------------------------------------
def test_rendered_journey_has_no_stage7_8_10_contradictions(synthesizer):
    """
    Verifies that the rendered journey UI HTML eliminates visual and semantic contradictions:
    1. IS 4985 Stage 7: Does NOT say 'Product-specific inspection requirements not established'
       when SIT inspection routines are present.
    2. IS 4985 Stage 8: Does NOT say 'Product-specific sampling requirements not established'
       when SIT sampling schedule is present.
    3. IS 4985 Stage 10: Does NOT say 'applicability to this product has not been established'
       when mandatory certification under QCO is confirmed.
    4. IS 15750 Stage 10: DOES state applicability has not been established because
       neither mandatory certification nor certification scheme is confirmed.
    """
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    req = ComplianceJourneyRequest(query="IS 4985")
    journey_4985 = synthesizer.process_journey(req)

    node_script_4985 = f"""
    import {{ ComplianceJourneyComponent }} from './frontend/complianceJourneyComponent.js';
    const journeyData = {json.dumps(journey_4985)};
    const html = ComplianceJourneyComponent.renderJourneyCard(journeyData, {{
        t: (k, fb) => fb || k
    }});

    // Extract Stage 7
    const m7 = html.match(/data-stage-num="7"[\\s\\S]*?(?=data-stage-num="8")/);
    const stg7 = m7 ? m7[0] : '';
    if (stg7.includes('Product-specific inspection requirements not established')) {{
        console.error('CONTRADICTION_STAGE_7: Header claims inspection not established');
        process.exit(1);
    }}

    // Extract Stage 8
    const m8 = html.match(/data-stage-num="8"[\\s\\S]*?(?=data-stage-num="9")/);
    const stg8 = m8 ? m8[0] : '';
    if (stg8.includes('Product-specific sampling requirements not established')) {{
        console.error('CONTRADICTION_STAGE_8: Header claims sampling not established');
        process.exit(2);
    }}

    // Extract Stage 10
    const m10 = html.match(/data-stage-num="10"[\\s\\S]*?(?=<\\/div>\\s*<\\/div>\\s*$|$)/);
    const stg10 = m10 ? m10[0] : '';
    if (stg10.includes('applicability to this product has not been established')) {{
        console.error('CONTRADICTION_STAGE_10: Stage 10 claims applicability not established for IS 4985');
        process.exit(3);
    }}

    console.log('SUCCESS_IS4985_NO_CONTRADICTIONS');
    process.exit(0);
    """

    res = subprocess.run(
        ["node", "--input-type=module", "-e", node_script_4985],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True
    )
    assert res.returncode == 0, f"IS 4985 UI contradiction detected:\n{res.stderr}\n{res.stdout}"

    # Also verify IS 15750 correctly preserves the unestablished disclaimer
    req_15750 = ComplianceJourneyRequest(query="IS 15750")
    journey_15750 = synthesizer.process_journey(req_15750)

    node_script_15750 = f"""
    import {{ ComplianceJourneyComponent }} from './frontend/complianceJourneyComponent.js';
    const journeyData = {json.dumps(journey_15750)};
    const html = ComplianceJourneyComponent.renderJourneyCard(journeyData, {{
        t: (k, fb) => fb || k
    }});

    const m10 = html.match(/data-stage-num="10"[\\s\\S]*?(?=<\\/div>\\s*<\\/div>\\s*$|$)/);
    const stg10 = m10 ? m10[0] : '';
    if (!stg10.includes('applicability to this product has not been established')) {{
        console.error('STAGE_10_FALSE_CONFIRMATION: IS 15750 should indicate unestablished applicability');
        process.exit(4);
    }}

    console.log('SUCCESS_IS15750_ACCURATE_UNESTABLISHED');
    process.exit(0);
    """

    res_15750 = subprocess.run(
        ["node", "--input-type=module", "-e", node_script_15750],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True
    )
    assert res_15750.returncode == 0, f"IS 15750 UI unestablished check failed:\n{res_15750.stderr}\n{res_15750.stdout}"

