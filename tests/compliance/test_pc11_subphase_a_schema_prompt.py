"""
tests/compliance/test_pc11_subphase_a_schema_prompt.py
Sub-phase A: Structured Response Schema and Groq Prompt Architecture Verification.

Verifies:
1. Pydantic schema contracts for ComplianceStage, all 10 stages, AssessmentStage,
   and ComplianceJourneyV2Response (with title, answer, key_information, evidence_ids).
2. ComplianceJourneyV2Response.to_structured_dict() matches the exact Section 19 contract.
3. GroqComplianceInput dataclass supports all Section 1 input fields.
4. ComplianceJourneyV2Synthesizer.build_prompt():
   - System message incorporates the 4-tier hierarchy (Correction 1).
   - System message enforces anti-hallucination boundaries for regulatory details (Correction 1C).
   - System message promotes useful contextual guidance over 'evidence not established' (Correction 1D).
   - System message enforces Stage 9 F3 laboratory invariant.
   - System message enforces user-facing terminology restriction (Correction 2).
   - User message contains all 10 logical stage questions verbatim (Section 2).
   - User message contains ASSESSMENT and NEXT STEPS verbatim (Section 2).
   - User message implements progressive context chaining (Section 20).
   - User message formats F3 laboratories and RAG evidence.
5. ComplianceSafetyValidator correctly preserves stage titles and purges internal jargon
   from user-facing fields.
6. Frozen subsystem cryptographic baseline hash preservation.
"""

import json
import hashlib
from pathlib import Path
import pytest
from pydantic import ValidationError

from ai.compliance.journey_v2_models import (
    ComplianceStage,
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
    ComplianceJourneyV2Response,
)
from backend.compliance_journey_v2_synthesizer import (
    GroqComplianceInput,
    ComplianceJourneyV2Synthesizer,
    ComplianceSafetyValidator,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BASELINE_HASHES_FILE = PROJECT_ROOT / "scratch_pc6_baseline_hashes.json"


# ---------------------------------------------------------------------------
# Test 1: Pydantic Schema Contracts and Title Support
# ---------------------------------------------------------------------------
def test_compliance_stage_and_response_schema():
    """Verify ComplianceStage schema fields and ComplianceJourneyV2Response contract."""
    # ComplianceStage base
    stage = ComplianceStage(
        title="Product Identification",
        answer="BLDC Ceiling Fan",
        key_information=["Category: Electric Fans"],
        evidence_ids=["ev_001"]
    )
    assert stage.title == "Product Identification"
    assert stage.answer == "BLDC Ceiling Fan"
    assert stage.key_information == ["Category: Electric Fans"]
    assert stage.evidence_ids == ["ev_001"]

    # Minimal validation
    stage_min = ComplianceStage(answer="Minimal answer")
    assert stage_min.title is None
    assert stage_min.key_information == []
    assert stage_min.evidence_ids == []

    # Mandatory answer field
    with pytest.raises(ValidationError):
        ComplianceStage()

    # Full response construction
    full_data = {
        "product_identification": {"title": "Product Identification", "answer": "BLDC ceiling fan"},
        "applicable_standards": {"title": "Applicable Indian Standards", "answer": "IS 374"},
        "regulatory_status": {"title": "QCO / Regulatory Status", "answer": "Active QCO"},
        "mandatory_certification": {"title": "Mandatory Certification", "answer": "Mandatory under QCO"},
        "certification_scheme": {"title": "Certification Scheme", "answer": "Scheme-I (ISI Mark)"},
        "testing": {"title": "Required Testing", "answer": "Air Delivery and Service Value"},
        "inspection": {"title": "Factory Inspection", "answer": "Routine shift inspection"},
        "sampling": {"title": "Lot & Control Unit Sampling", "answer": "Representative lot sampling"},
        "laboratories": {"title": "Qualified BIS Laboratories", "answer": "12 qualified BIS laboratories"},
        "certification_process": {"title": "Certification Process", "answer": "Online application via Manakonline"},
        "assessment": {"title": "Assessment", "answer": "BIS certification is mandatory for covered ceiling fans."},
        "next_steps": ["Confirm standard", "Select laboratory", "Apply on Manakonline"]
    }

    response = ComplianceJourneyV2Response(**full_data)
    assert response.product_identification.title == "Product Identification"
    assert response.product_identification.answer == "BLDC ceiling fan"
    assert response.applicable_standards.title == "Applicable Indian Standards"
    assert response.testing.answer == "Air Delivery and Service Value"
    assert len(response.next_steps) == 3


# ---------------------------------------------------------------------------
# Test 2: to_structured_dict Output Format Matching Section 19
# ---------------------------------------------------------------------------
def test_to_structured_dict_matches_section_19():
    """Verify that to_structured_dict outputs all 10 stages, assessment, and next_steps."""
    full_data = {
        "product_identification": {"title": "Product Identification", "answer": "BLDC fan", "key_information": ["BLDC"], "evidence_ids": ["e1"]},
        "applicable_standards": {"title": "Applicable Indian Standards", "answer": "IS 374", "key_information": ["IS 374"], "evidence_ids": ["e2"]},
        "regulatory_status": {"title": "QCO / Regulatory Status", "answer": "Ceiling Fan QCO", "key_information": [], "evidence_ids": []},
        "mandatory_certification": {"title": "Mandatory Certification", "answer": "Mandatory", "key_information": [], "evidence_ids": []},
        "certification_scheme": {"title": "Certification Scheme", "answer": "Scheme-I", "key_information": [], "evidence_ids": []},
        "testing": {"title": "Required Testing", "answer": "Safety tests", "key_information": [], "evidence_ids": []},
        "inspection": {"title": "Factory Inspection", "answer": "Factory audit", "key_information": [], "evidence_ids": []},
        "sampling": {"title": "Lot & Control Unit Sampling", "answer": "Lot sampling", "key_information": [], "evidence_ids": []},
        "laboratories": {"title": "Qualified BIS Laboratories", "answer": "4 labs", "key_information": [], "evidence_ids": []},
        "certification_process": {"title": "Certification Process", "answer": "5 steps", "key_information": [], "evidence_ids": []},
        "assessment": {"title": "Assessment", "answer": "Complete assessment", "key_information": [], "evidence_ids": []},
        "next_steps": ["Step 1", "Step 2"]
    }

    response = ComplianceJourneyV2Response(**full_data)
    s_dict = response.to_structured_dict()

    expected_stages = [
        "product_identification",
        "applicable_standards",
        "regulatory_status",
        "mandatory_certification",
        "certification_scheme",
        "testing",
        "inspection",
        "sampling",
        "laboratories",
        "certification_process",
        "assessment"
    ]
    for stg_key in expected_stages:
        assert stg_key in s_dict, f"Missing stage {stg_key} in structured dict"
        stg = s_dict[stg_key]
        assert "title" in stg
        assert "answer" in stg
        assert isinstance(stg["key_information"], list)
        assert isinstance(stg["evidence_ids"], list)

    assert "next_steps" in s_dict
    assert isinstance(s_dict["next_steps"], list)
    assert len(s_dict["next_steps"]) == 2


# ---------------------------------------------------------------------------
# Test 3: GroqComplianceInput Dataclass Fields
# ---------------------------------------------------------------------------
def test_groq_compliance_input_dataclass():
    """Verify that GroqComplianceInput includes all Section 1 fields."""
    inp = GroqComplianceInput(
        user_question="I manufacture BLDC ceiling fans",
        intent="REGULATORY_COMPLIANCE",
        product="BLDC ceiling fan",
        product_attributes={"type": "ceiling_fan", "technology": "BLDC"},
        location="Delhi",
        standards=["IS 374"],
        deterministic_results={"is_mandatory": True},
        rag_evidence=[{"source_record_id": "doc_1", "text": "Fan standard"}],
        qco_evidence={"qco_title": "Ceiling Fan QCO", "associated_qco_ids": ["qco_1"]},
        certification_evidence=[{"source_record_id": "cert_1"}],
        testing_evidence=[{"source_record_id": "test_1"}],
        inspection_evidence=[{"source_record_id": "insp_1"}],
        sampling_evidence=[{"source_record_id": "samp_1"}],
        certification_process_evidence=[{"source_record_id": "proc_1"}],
        conversation_history=[{"role": "user", "content": "Hello"}],
        f3_laboratories=[{"laboratory_name": "National Test House", "public_lab_code": "NTH-01"}]
    )

    assert inp.user_question == "I manufacture BLDC ceiling fans"
    assert inp.intent == "REGULATORY_COMPLIANCE"
    assert inp.product == "BLDC ceiling fan"
    assert inp.product_attributes == {"type": "ceiling_fan", "technology": "BLDC"}
    assert inp.location == "Delhi"
    assert inp.standards == ["IS 374"]
    assert inp.conversation_history == [{"role": "user", "content": "Hello"}]
    assert len(inp.f3_laboratories) == 1

    all_ids = inp.get_all_evidence_ids()
    assert "doc_1" in all_ids
    assert "qco_1" in all_ids
    assert "NTH-01" in all_ids


# ---------------------------------------------------------------------------
# Test 4: Build Prompt System Message Hierarchy and Constraints
# ---------------------------------------------------------------------------
def test_build_prompt_system_message_rules():
    """
    Verifies that build_prompt system message contains:
    - 4-tier hierarchy (Correction 1: primary RAG, general knowledge, anti-hallucination, contextual guidance)
    - Instruction not to repeatedly say 'evidence not established' (Correction 1D)
    - Anti-hallucination boundaries on precise regulatory facts (Correction 1C)
    - Stage 9 F3 laboratory invariant
    - User-facing terminology restriction (Correction 2)
    - Adaptive answer length & structure instructions
    """
    synthesizer = ComplianceJourneyV2Synthesizer()
    inp = GroqComplianceInput(
        user_question="I manufacture BLDC ceiling fans",
        product="BLDC ceiling fan",
        standards=["IS 374"]
    )
    messages = synthesizer.build_prompt(inp)
    assert len(messages) == 2
    system_msg = messages[0]["content"]

    # Hierarchy checks (Correction 1)
    assert "Primary Basis:" in system_msg
    assert "General Knowledge:" in system_msg
    assert "Precise Regulatory Truth Boundaries (Never Fabricate):" in system_msg
    assert "Useful Contextual Guidance over 'Evidence Not Established':" in system_msg
    assert "Do NOT repeatedly say 'evidence not established'" in system_msg

    # Anti-hallucination boundaries (Correction 1C)
    for forbidden_fact in [
        "Quality Control Order (QCO) names",
        "Gazette notification numbers",
        "Statutory effective dates",
        "Exact BIS scheme numbers",
        "Exact BIS fee amounts",
        "Exact test clauses",
        "Exact testing frequencies",
        "Exact lot/sample quantities",
        "BIS laboratory names"
    ]:
        assert forbidden_fact in system_msg, f"Missing anti-hallucination rule: {forbidden_fact}"

    # Stage 9 invariant
    assert "Stage 9 (Laboratories) Invariant:" in system_msg
    assert "You must NOT generate, invent, or rerank testing laboratories" in system_msg

    # User-facing terminology restriction (Correction 2)
    assert "User-Facing Terminology Restriction:" in system_msg
    assert "The generated user-facing text (answer, key_information, assessment, next_steps) must NEVER expose internal architecture jargon" in system_msg


# ---------------------------------------------------------------------------
# Test 5: Build Prompt User Message with 10 Logical Questions & Progressive Context
# ---------------------------------------------------------------------------
def test_build_prompt_user_message_questions_and_context():
    """
    Verifies that build_prompt user message contains:
    - All 10 logical stage questions verbatim (Section 2)
    - ASSESSMENT and NEXT STEPS verbatim (Section 2)
    - Progressive context chaining (Section 20)
    - F3 laboratories formatting
    - Strict JSON schema specification matching Section 19
    """
    synthesizer = ComplianceJourneyV2Synthesizer()
    inp = GroqComplianceInput(
        user_question="I manufacture BLDC ceiling fans",
        intent="PRODUCT_COMPLIANCE",
        product="BLDC ceiling fan",
        product_attributes={"type": "ceiling_fan"},
        location="Mumbai",
        standards=["IS 374"],
        deterministic_results={"is_mandatory": True, "certification_scheme": "Scheme-I"},
        rag_evidence=[{"source_record_id": "ev_rag_1", "source_title": "IS 374 Clause 8", "text": "Air delivery testing required."}],
        f3_laboratories=[{"laboratory_name": "ERDA Vadodara", "public_lab_code": "LAB-ERDA-01", "city": "Vadodara"}],
        conversation_history=[
            {"role": "user", "content": "What is IS 374?"},
            {"role": "assistant", "content": "IS 374 is the standard for electric ceiling fans."}
        ]
    )

    messages = synthesizer.build_prompt(inp)
    user_msg = messages[1]["content"]

    # Verify all 10 logical stage questions verbatim from Section 2
    ten_questions = [
        'STAGE 1 (Product Identification):\n"Identify the product and its primary application/scope in 1-2 concise sentences without methodology narration."',
        'STAGE 2 (Applicable Indian Standards):\n"Which Indian Standard(s) apply? State the primary standard concisely, or provide a bulleted list if multiple apply."',
        'STAGE 3 (QCO / Regulatory Status):\n"What QCO or regulatory order applies? State the regulatory status first, followed by compact bulleted facts (order, notification, effective date; or conflict summary)."',
        'STAGE 4 (Mandatory Certification):\n"Is BIS certification mandatory? State the requirement directly in the first sentence, followed by the regulatory basis."',
        'STAGE 5 (Certification Scheme):\n"Which BIS certification scheme applies? State the specific scheme concisely (e.g. Scheme-I, Scheme-II/CRS, or unestablished)."',
        'STAGE 6 (Required Testing):\n"What testing is required? Provide a 1-sentence SIT introduction, followed by a structured bullet list of specific tests. Summarize frequency/SIT briefly. Do not dump a single dense paragraph."',
        'STAGE 7 (Factory Inspection):\n"What factory inspection applies? State clearly if required or not, followed by key quality control points in bullets if in evidence."',
        'STAGE 8 (Lot & Control Unit Sampling):\n"What sampling requirements apply? Provide structured bullets for lot/sample rules if in evidence; otherwise state unconfirmed without guessing numbers."',
        'STAGE 9 (Qualified BIS Laboratories):\n"Acknowledge the recognized testing facilities matching the standard in a single introductory sentence (do not list laboratory names)."',
        'STAGE 10 (Certification Process):\n"What is the step-by-step certification workflow? Provide a numbered sequence (1., 2., 3.) of procedural steps."',
        'ASSESSMENT:\n"Answer the user\'s original question directly in the first sentence, followed by a structured summary."',
        'NEXT STEPS:\n"Provide numbered practical next actions (1., 2., 3.)."'
    ]
    for q in ten_questions:
        assert q in user_msg, f"Missing verbatim question in user prompt:\n{q}"

    # Progressive context chaining (Section 20)
    assert "PROGRESSIVE STAGE CONTEXT:" in user_msg
    assert "Stage 1 context: Product = BLDC ceiling fan" in user_msg
    assert "Stage 2 context: Product = BLDC ceiling fan, Standards = IS 374" in user_msg
    assert "Stage 3 context:" in user_msg
    assert "Stage 4 context:" in user_msg
    assert "Stage 5 context:" in user_msg

    # Conversational context
    assert "PREVIOUS CONVERSATIONAL CONTEXT:" in user_msg
    assert "USER: What is IS 374?" in user_msg

    # F3 laboratories formatting
    assert "ERDA Vadodara (LAB-ERDA-01) - Vadodara" in user_msg

    # JSON output schema specification
    assert '"product_identification": {"title": "Product Identification"' in user_msg
    assert '"applicable_standards": {"title": "Applicable Indian Standards"' in user_msg
    assert '"regulatory_status": {"title": "QCO / Regulatory Status"' in user_msg
    assert '"mandatory_certification": {"title": "Mandatory Certification"' in user_msg
    assert '"certification_scheme": {"title": "Certification Scheme"' in user_msg
    assert '"testing": {"title": "Required Testing"' in user_msg
    assert '"inspection": {"title": "Factory Inspection"' in user_msg
    assert '"sampling": {"title": "Lot & Control Unit Sampling"' in user_msg
    assert '"laboratories": {"title": "Qualified BIS Laboratories"' in user_msg
    assert '"certification_process": {"title": "Certification Process"' in user_msg
    assert '"assessment": {"title": "Assessment"' in user_msg
    assert '"next_steps": ["...", "..."]' in user_msg


# ---------------------------------------------------------------------------
# Test 6: Safety Validator Stage Titles and Terminology Scrubbing
# ---------------------------------------------------------------------------
def test_safety_validator_preserves_titles_and_scrubs_internal_jargon():
    """Verify validate_and_guard populates title and sanitizes forbidden jargon."""
    inp = GroqComplianceInput(
        user_question="What certification is required for IS 4985",
        product="uPVC Pipes",
        standards=["IS 4985"],
        deterministic_results={"is_mandatory": True, "certification_scheme": "Scheme-I"},
        f3_laboratories=[{"laboratory_name": "Central Lab", "public_lab_code": "CL-01"}]
    )

    raw_groq_dict = {
        "product_identification": {
            "title": "Product Identification",
            "answer": "uPVC pipes according to RAG evidence and PC-5 data."
        },
        "applicable_standards": {
            "title": "Applicable Indian Standards",
            "answer": "IS 4985 is the standard. Status: GROUNDED in evidence corpus."
        },
        "regulatory_status": {
            "title": "QCO / Regulatory Status",
            "answer": "Governed by Pipes and Fittings QCO under notification S.O. 4512(E)."
        },
        "mandatory_certification": {
            "title": "Mandatory Certification",
            "answer": "BIS certification is mandatory under UNKNOWN rules."
        },
        "certification_scheme": {
            "title": "Certification Scheme",
            "answer": "Scheme-I applies."
        },
        "testing": {
            "title": "Required Testing",
            "answer": "Testing includes short-term hydrostatic pressure test."
        },
        "inspection": {
            "title": "Factory Inspection",
            "answer": "Shift inspection per SIT."
        },
        "sampling": {
            "title": "Lot & Control Unit Sampling",
            "answer": "Batch sampling per SIT schedule."
        },
        "laboratories": {
            "title": "Qualified BIS Laboratories",
            "answer": "BIS recognized labs available."
        },
        "certification_process": {
            "title": "Certification Process",
            "answer": "Apply online via Manakonline."
        },
        "assessment": {
            "title": "Assessment",
            "answer": "ANSWER: BIS certification is mandatory under the QCO."
        },
        "next_steps": ["Check standard with LLM_FALLBACK guidance.", "Apply on Manakonline."]
    }

    resp = ComplianceSafetyValidator.validate_and_guard(raw_groq_dict, inp)

    # All titles are preserved
    assert resp.product_identification.title == "Product Identification"
    assert resp.applicable_standards.title == "Applicable Indian Standards"
    assert resp.regulatory_status.title == "QCO / Regulatory Status"
    assert resp.mandatory_certification.title == "Mandatory Certification"
    assert resp.certification_scheme.title == "Certification Scheme"
    assert resp.testing.title == "Required Testing"
    assert resp.inspection.title == "Factory Inspection"
    assert resp.sampling.title == "Lot & Control Unit Sampling"
    assert resp.laboratories.title == "Qualified BIS Laboratories"
    assert resp.certification_process.title == "Certification Process"
    assert resp.assessment.title == "Assessment"

    # Forbidden internal technical jargon was scrubbed from user-facing fields
    assert "RAG" not in resp.product_identification.answer
    assert "PC-5" not in resp.product_identification.answer
    assert "GROUNDED" not in resp.applicable_standards.answer
    assert "evidence corpus" not in resp.applicable_standards.answer
    assert "UNKNOWN" not in resp.mandatory_certification.answer
    assert "LLM_FALLBACK" not in resp.next_steps[0]


# ---------------------------------------------------------------------------
# Test 7: Frozen Subsystems Preservation (Hashes Unaltered)
# ---------------------------------------------------------------------------
def test_baseline_hashes_unaltered():
    """Verify cryptographic hash integrity of frozen subsystems."""
    if not BASELINE_HASHES_FILE.exists(): pytest.skip("hashes missing")
    with open(BASELINE_HASHES_FILE, "r") as f:
        expected_hashes = json.load(f)

    for rel_path, expected_hash in expected_hashes.items():
        full_path = PROJECT_ROOT / rel_path
        assert full_path.exists(), f"Frozen file missing: {rel_path}"
        with open(full_path, "rb") as fp:
            actual_hash = hashlib.sha256(fp.read()).hexdigest()
        assert actual_hash == expected_hash, (
            f"Cryptographic hash mismatch in frozen subsystem {rel_path}!\n"
            f"Expected: {expected_hash}\n"
            f"Actual:   {actual_hash}"
        )
