"""
Phase 13 Adversarial & Hallucination Resistance Test Suite

Adversarial Verification Requirements:
1. False Clause Injection on LIMS-only standard (IS 8978) -> Enforces honest abstention, zero fabricated clauses.
2. Non-Existent Standard (IS 99999) -> Returns INSUFFICIENT, zero false positives.
3. Identifier Spoofing (IS 1050000) -> Boundary isolation; does not match IS 10500.
4. Authority Inversion (Tier 2 LIMS attempting to ground Tier 1 Normative requirement) -> ClaimValidator rejects.
5. Fee Detachment (IS 8978 fee attributed to IS 10500) -> ClaimValidator rejects.
6. Cross-Standard Contamination (query with mixed product terms) -> Identifier boost isolates correct standard.
"""

import os
import pytest
from pathlib import Path

# Force offline mode
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

from scripts.phase13_hybrid_retrieval import (
    Phase13RetrievalData,
    Phase13HybridRetrievalEngine,
    canonical_std,
    extract_query_identifiers
)
from scripts.phase13_grounded_rag import Phase13GroundedRAGEngine
from data.derived.phase12.grounded_rag_v1.claim_validator import validate_claim
from data.derived.phase12.grounded_rag_v1.schemas import (
    Claim,
    EvidenceObject,
    SupportStatus,
    QueryIntent
)


@pytest.fixture(scope="module")
def shared_data():
    return Phase13RetrievalData()


@pytest.fixture(scope="module")
def grounded_engine(shared_data):
    return Phase13GroundedRAGEngine(shared_data)


# -----------------------------------------------------------------------------
# Adversarial Test 1: Fabricated Clause Query on LIMS-Only Standard (IS 8978)
# -----------------------------------------------------------------------------

def test_adversarial_is8978_clause_abstention(grounded_engine):
    """
    Query asserts a non-existent technical clause 14.2 for IS 8978 water heaters.
    System MUST abstain, flag abstention_triggered=True, and NOT hallucinate clause text.
    """
    res = grounded_engine.answer(
        "What specific requirement is defined in Clause 14.2 of IS 8978 for thermal cutouts?",
        top_k=5
    )

    assert res["abstention_triggered"] is True
    assert "IS 8978" in res["standard_coverage"]
    assert res["standard_coverage"]["IS 8978"]["is_lims_only"] is True
    assert res["standard_coverage"]["IS 8978"]["has_normative_clauses"] is False

    # The answer MUST contain explicit abstention text
    assert "Only laboratory scope & fee evidence is available" in res["answer"]
    assert "Normative clause text is not in corpus" in res["answer"]

    # Unsupported claims must record the unverified clause
    assert len(res["unsupported_claims"]) > 0
    unsupported_texts = [c["text"] for c in res["unsupported_claims"]]
    assert any("IS 8978" in t for t in unsupported_texts)

    # Invariant: No retrieved evidence for IS 8978 can have Tier 1 Normative
    for ev in res["evidence"]:
        if ev.get("standard_number") and "8978" in ev["standard_number"]:
            assert ev.get("authority_tier") != "TIER_1_NORMATIVE"


# -----------------------------------------------------------------------------
# Adversarial Test 2: Non-Existent Standard (IS 99999)
# -----------------------------------------------------------------------------

def test_adversarial_nonexistent_standard(grounded_engine):
    """
    Query references completely fictitious standard IS 99999.
    System MUST return INSUFFICIENT or NOT_IN_CORPUS.
    """
    res = grounded_engine.answer(
        "What are the tensile testing parameters prescribed by IS 99999?",
        top_k=5
    )

    cov = res["standard_coverage"].get("IS 99999", {})
    assert cov.get("max_evidence_depth") == "NOT_IN_CORPUS"
    assert cov.get("has_normative_clauses") is False


# -----------------------------------------------------------------------------
# Adversarial Test 3: Identifier Spoofing / Substring Boundary Isolation
# -----------------------------------------------------------------------------

def test_adversarial_identifier_spoofing(shared_data):
    """
    Query references 'IS 1050000' (a typo/spoof of IS 10500).
    The index must NOT match IS 10500 units for IS 1050000.
    """
    unit_indices = shared_data.is_number_index.get("IS 1050000", [])
    assert len(unit_indices) == 0

    unit_indices_legit = shared_data.is_number_index.get("IS 10500", [])
    assert len(unit_indices_legit) > 0


# -----------------------------------------------------------------------------
# Adversarial Test 4: Authority Boundary Inversion (ClaimValidator Gate)
# -----------------------------------------------------------------------------

def test_adversarial_authority_inversion_rejected():
    """
    Attempt to use a Tier 2 LIMS scope record to substantiate a normative clause requirement.
    ClaimValidator MUST reject this claim as UNSUPPORTED.
    """
    # Create synthetic LIMS evidence object (lacks normative clause text)
    lims_evidence = EvidenceObject(
        source_record_id="LIMS-8978-001",
        standard_number="IS 8978",
        document_title="BIS Laboratory Accreditation Scope for Instantaneous Water Heaters",
        source_title="LIMS Record",
        laboratory_id="112",
        text="Official BIS LIMS scope: Testing of electric instantaneous water heaters according to IS 8978."
    )

    # Claim asserting that IS 8978 prescribes thermal cutoff clause text
    inversion_claim = Claim(
        claim_id="adversarial_inversion",
        claim_type="BIS_FACT",
        text="Clause 14.2 specifies thermal cutout cutoff at 95 degrees C",
        subject_entity="STANDARD:IS 8978",
        predicate="HAS_PROCEDURE",
        supporting_evidence_ids=["LIMS-8978-001"],
        support_status=SupportStatus.UNSUPPORTED
    )

    validated = validate_claim(
        inversion_claim,
        [lims_evidence],
        QueryIntent.TESTING_REQUIREMENT,
        ["IS 8978"]
    )

    assert validated.support_status == SupportStatus.UNSUPPORTED, (
        "ClaimValidator violated authority boundary: LIMS evidence must not support normative clause claim"
    )


# -----------------------------------------------------------------------------
# Adversarial Test 5: Fee Detachment & Cross-Standard Reattribution
# -----------------------------------------------------------------------------

def test_adversarial_fee_detachment_rejected():
    """
    Attempt to claim that the testing fee (₹22,000) for IS 8978 applies to IS 10500.
    ClaimValidator MUST reject the cross-standard fee attribution.
    """
    fee_evidence = EvidenceObject(
        source_record_id="FEE-8978-001",
        standard_number="IS 8978",
        fee_amount=22000.0,
        relationships=[{"subject": "IS 8978", "predicate": "HAS_FEE", "object": "22000"}],
        text="Testing fee for IS 8978 is 22000 INR."
    )

    detached_claim = Claim(
        claim_id="adversarial_detached_fee",
        claim_type="BIS_FACT",
        text="Testing fee for IS 10500 is 22000 INR",
        subject_entity="STANDARD:IS 10500",
        predicate="HAS_FEE",
        object_entity="22000",
        supporting_evidence_ids=["FEE-8978-001"],
        support_status=SupportStatus.UNSUPPORTED
    )

    validated = validate_claim(
        detached_claim,
        [fee_evidence],
        QueryIntent.TESTING_FEE,
        ["IS 10500"]
    )

    assert validated.support_status == SupportStatus.UNSUPPORTED, (
        "ClaimValidator allowed cross-standard fee detachment"
    )


# -----------------------------------------------------------------------------
# Adversarial Test 6: Cross-Standard Keyword Contamination
# -----------------------------------------------------------------------------

def test_adversarial_cross_standard_keyword_contamination(shared_data):
    """
    Query mixes keywords from another standard:
    'LED lamp self-ballasted drivers under IS 4985'
    The standard identifier 'IS 4985' MUST dominate over 'LED' keywords.
    """
    engine = Phase13HybridRetrievalEngine(shared_data)
    res = engine.search("LED lamp self-ballasted drivers under IS 4985", top_k=5)

    # Top result MUST be from IS 4985 due to exact identifier boost
    top_standard = res["results"][0]["standard_number"]
    assert "4985" in top_standard, f"Expected IS 4985 to dominate, but got {top_standard}"


# -----------------------------------------------------------------------------
# Remediation Tests for the 4 Migration Defects
# -----------------------------------------------------------------------------

def test_remediation_defect1_unknown_standard_isolation(grounded_engine):
    """
    Defect 1: What is IS 999999? must return INSUFFICIENT with NOT_IN_CORPUS coverage,
    and zero unrelated cross-standard evidence units.
    """
    res = grounded_engine.answer("What is IS 999999?", top_k=5)
    assert res["status"] == "INSUFFICIENT"
    assert len(res["evidence"]) == 0
    assert len(res["claims"]) == 0
    cov = res["standard_coverage"].get("IS 999999")
    assert cov is not None
    assert cov["max_evidence_depth"] == "NOT_IN_CORPUS"
    assert cov["has_normative_clauses"] is False


def test_remediation_defect2_empty_query_handling(grounded_engine):
    """
    Defect 2: Empty or whitespace query must immediately return INSUFFICIENT
    with the exact required prompt message and zero retrieval overhead.
    """
    for empty_q in ["", "   ", "\t\n"]:
        res = grounded_engine.answer(empty_q)
        assert res["status"] == "INSUFFICIENT"
        assert res["answer"] == "Please provide a query to research."
        assert len(res["evidence"]) == 0
        assert len(res["claims"]) == 0
        assert res["duration_ms"] == 0.0


def test_remediation_defect3_requirements_intent(shared_data, grounded_engine):
    """
    Defect 3: extract_query_identifiers must classify 'requirement' / 'requirements'
    as REQUIREMENTS intent, and trigger clause abstention on LIMS-only standards.
    """
    ids = extract_query_identifiers("What are the requirements of IS 8978?")
    assert ids["intent"] == "REQUIREMENTS"

    ids_sing = extract_query_identifiers("What is the requirement under IS 4985?")
    assert ids_sing["intent"] == "REQUIREMENTS"

    # End-to-end on IS 8978
    res = grounded_engine.answer("What are the requirements of IS 8978?")
    assert res["status"] == "PARTIAL"
    assert res["abstention_triggered"] is True
    assert "Only laboratory scope & fee evidence is available" in res["answer"]


def test_remediation_defect4_lims_only_standard_partial(grounded_engine):
    """
    Defect 4: IS 8978 fee, scope, and general queries must return PARTIAL with authoritative
    LIMS data, and never claim full SUFFICIENT normative coverage.
    """
    fee_res = grounded_engine.answer("What is the testing fee for IS 8978?")
    assert fee_res["status"] == "PARTIAL"
    assert len(fee_res["evidence"]) > 0
    for ev in fee_res["evidence"]:
        assert ev.get("authority_tier") == "TIER_2_LIMS"

    lab_res = grounded_engine.answer("Which laboratories explicitly have scope for IS 8978?")
    assert lab_res["status"] == "PARTIAL"
    assert len(lab_res["evidence"]) > 0
    for ev in lab_res["evidence"]:
        assert ev.get("authority_tier") == "TIER_2_LIMS"


# -----------------------------------------------------------------------------
# Targeted Remediation Tests: Answer Quality & Product Context Preservation
# -----------------------------------------------------------------------------

def test_adversarial_is4985_answer_quality_and_structure(grounded_engine):
    """
    Asserts that queries like 'tell me about IS 4985' produce a clean, natural,
    structured markdown answer instead of raw internal retrieval debug text.
    Raw retrieval units must remain strictly in evidence[].
    """
    from scripts.phase12_f2_orchestrator import orchestrate_assistant_query, GroqClient

    res = grounded_engine.answer("tell me about IS 4985", top_k=10)
    assert res["status"] == "SUFFICIENT"
    assert len(res["evidence"]) == 10

    # Verify no raw retrieval debug text in answer
    ans = res["answer"]
    assert "Authoritative BIS Retrieval Results" not in ans
    assert "### 1." not in ans
    assert "Authority Tier:" not in ans
    assert "Evidence Text:" not in ans

    # Verify structured presentation
    assert "IS 4985" in ans
    assert "Scope" in ans or "Specification" in ans

    # End-to-end through orchestrator offline fallback
    mock_groq = GroqClient(api_key="")
    orch_res = orchestrate_assistant_query("tell me about IS 4985", groq_client=mock_groq)
    assert orch_res["status"] == "SUFFICIENT"
    assert "Authoritative BIS Retrieval Results" not in orch_res["answer"]
    assert "### 1." not in orch_res["answer"]
    assert len(orch_res["rag"]["evidence"]) == 10


def test_adversarial_led_lamp_hallmarking_domain_mismatch():
    """
    Query: 'I am a LED lamp manufacturer tell me about hallmarking certifications and everything about it'
    Must:
    1. Clarify that hallmarking applies to precious metals, not LED lamps.
    2. Not return the gold/jewellery hallmarking essay as applicable to LED lamps.
    3. Dynamically discover applicable LED lamp standards (e.g. IS 16102) from evidence without hardcoding.
    4. Deduplicate: domain clarification must appear exactly once.
    """
    from scripts.phase12_f2_orchestrator import orchestrate_assistant_query, GroqClient

    mock_groq = GroqClient(api_key="")
    q = "I am a LED lamp manufacturer tell me about hallmarking certifications and everything about it"
    res = orchestrate_assistant_query(q, groq_client=mock_groq)

    assert res["status"] in ("SUFFICIENT", "PARTIAL")
    ans = res["answer"]

    # 1. Domain clarification is present
    assert "precious-metal" in ans or "precious metal" in ans
    assert "hallmarking" in ans.lower()
    assert "led lamp" in ans.lower()

    # 2. Deduplication check
    assert ans.count("The query combines") == 1

    # 3. Discovers LED lamp standard dynamically from evidence
    assert "16102" in ans

    # 4. Invariant: Evidence is populated with LED lamp standards, NOT gold hallmarking standards (IS 1417)
    ev_stds = [e.get("standard_number", "") for e in res["rag"]["evidence"]]
    assert any("16102" in s for s in ev_stds)
    assert not any("1417" in s for s in ev_stds)


def test_adversarial_unindexed_product_hallmarking_refusal():
    """
    Query: 'I am a wooden dining chair manufacturer tell me about hallmarking certifications and everything about it'
    Must:
    1. Clarify that hallmarking applies to precious metals, not wooden dining chairs.
    2. State that the evidence does not contain standards or testing specifications for wooden dining chairs.
    3. Zero hallucinations of fictitious standards.
    """
    from scripts.phase12_f2_orchestrator import orchestrate_assistant_query, GroqClient

    mock_groq = GroqClient(api_key="")
    q = "I am a wooden dining chair manufacturer tell me about hallmarking certifications and everything about it"
    res = orchestrate_assistant_query(q, groq_client=mock_groq)

    ans = res["answer"]
    assert "precious-metal" in ans or "precious metal" in ans
    assert "wooden dining chair" in ans.lower()
    assert "could not verify" in ans.lower() or "do not contain standards" in ans.lower()


def test_deterministic_grounded_fallback_dynamically_synthesized():
    """
    Ensures that build_deterministic_grounded_answer builds answer dynamically from
    retrieved evidence without hardcoding any standard numbers, fees, or labs.
    """
    from scripts.phase12_f2_orchestrator import build_deterministic_grounded_answer

    fake_rag_result = {
        "status": "SUFFICIENT",
        "answer": "",
        "evidence": [
            {
                "standard_number": "IS 12345",
                "authority_tier": "TIER_1_NORMATIVE",
                "text": "IS 12345 : 2025 Synthetic Polymer Widgets Specification. Scope covers polymer widgets. Test Method: Impact Resistance Test."
            },
            {
                "standard_number": "IS 12345",
                "authority_tier": "TIER_2_OPERATIONAL",
                "text": "Product Manual for Synthetic Polymer Widgets according to IS 12345. Guidelines for marking and factory testing."
            }
        ],
        "claims": []
    }

    ans = build_deterministic_grounded_answer("Explain IS 12345", fake_rag_result)
    assert "IS 12345" in ans
    assert "Synthetic Polymer Widgets" in ans
    assert "Scope & Application" in ans
    assert "Impact Resistance Test" in ans

