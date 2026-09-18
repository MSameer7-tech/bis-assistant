"""
Phase PC-8 V2: Comprehensive Tests for Groq Compliance Answer Synthesis & Safety Layer.

Verifies:
1. Complete RAG
2. Partial RAG
3. Missing RAG
4. QCO Confirmed
5. QCO Conflict
6. Certification Scheme Unavailable
7. Testing Partial
8. Unknown Product
9. F3 Laboratories (Exact Preservation, Zero Hallucination)
10. Unsupported LLM Claims (Authority Locking & Jargon Purging)
"""

import pytest
from ai.compliance.journey_v2_models import ComplianceJourneyV2Response
from backend.compliance_journey_v2_synthesizer import (
    GroqComplianceInput,
    ComplianceJourneyV2Synthesizer,
    ComplianceSafetyValidator,
    FORBIDDEN_INTERNAL_TERMS,
)


def assert_no_internal_jargon(response: ComplianceJourneyV2Response):
    """Helper to verify no internal status labels or technical terms leak into user-facing output."""
    data_str = response.model_dump_json()
    import re
    for term in FORBIDDEN_INTERNAL_TERMS:
        match = re.search(term, data_str, re.IGNORECASE)
        assert match is None, f"Found forbidden internal term '{term}' in response: {match.group(0)}"


# ---------------------------------------------------------------------------
# 1. Complete RAG
# ---------------------------------------------------------------------------
def test_complete_rag():
    input_data = GroqComplianceInput(
        user_question="What are the compliance requirements for uPVC pipes under IS 4985?",
        product="uPVC Pipes",
        standards=["IS 4985"],
        deterministic_results={
            "is_mandatory": True,
            "qco_status": "QCO_APPLIES",
            "certification_scheme": None,
            "testing_requirements": [
                {"test_name": "Hydrostatic Pressure Test", "test_clause": "8.1"},
                {"test_name": "Opacity Test", "test_clause": "9.2"}
            ]
        },
        rag_evidence=[
            {
                "retrieval_unit_id": "ev_is4985_01",
                "source_title": "IS 4985 Specification for uPVC Pipes",
                "text": "Clause 8.1 specifies internal hydrostatic pressure testing."
            }
        ],
        qco_evidence={
            "qco_title": "Pipes and Fittings (Quality Control) Order, 2023",
            "notification_numbers": ["S.O. 1234(E)"],
            "effective_date": "2023-12-31",
            "associated_qco_ids": ["qco_pipes_2023"]
        },
        testing_evidence=[
            {
                "retrieval_unit_id": "ev_test_4985",
                "source_title": "IS 4985 Clause 8.1",
                "text": "Hydrostatic testing must be conducted at 27 deg C."
            }
        ],
        f3_laboratories=[
            {"id": "LAB_001", "name": "National Test House, Kolkata", "city": "Kolkata"},
            {"id": "LAB_002", "name": "CIPET, Chennai", "city": "Chennai"}
        ]
    )

    synthesizer = ComplianceJourneyV2Synthesizer()
    response = synthesizer.synthesize(input_data)

    assert isinstance(response, ComplianceJourneyV2Response)
    assert response.applicable_standards.standards == ["IS 4985"]
    assert "Pipes and Fittings" in response.regulatory_status.regulatory_orders[0]
    assert response.mandatory_certification.is_mandatory is True
    assert "Hydrostatic" in response.testing.answer or "testing" in response.testing.answer.lower()
    assert len(response.laboratories.recognized_labs) == 2
    assert "National Test House, Kolkata" in response.laboratories.recognized_labs
    assert "LAB_001" in response.laboratories.evidence_ids
    assert_no_internal_jargon(response)


# ---------------------------------------------------------------------------
# 2. Partial RAG
# ---------------------------------------------------------------------------
def test_partial_rag():
    input_data = GroqComplianceInput(
        user_question="Is IS 1077 mandatory?",
        product="Common Burnt Clay Bricks",
        standards=["IS 1077"],
        deterministic_results={
            "is_mandatory": False,
            "qco_status": "QCO_NOT_ESTABLISHED",
            "certification_scheme": None,
            "testing_requirements": []
        },
        rag_evidence=[
            {
                "retrieval_unit_id": "ev_is1077_01",
                "source_title": "IS 1077 Common Burnt Clay Bricks",
                "text": "Specification for common burnt clay building bricks."
            }
        ],
        qco_evidence=None,
        testing_evidence=[],
        f3_laboratories=[]
    )

    synthesizer = ComplianceJourneyV2Synthesizer()
    response = synthesizer.synthesize(input_data)

    assert response.mandatory_certification.is_mandatory is False
    assert len(response.regulatory_status.regulatory_orders) == 0
    assert "not established" in response.regulatory_status.answer.lower() or "no active" in response.regulatory_status.answer.lower()
    assert len(response.laboratories.recognized_labs) == 0
    assert_no_internal_jargon(response)


# ---------------------------------------------------------------------------
# 3. Missing RAG
# ---------------------------------------------------------------------------
def test_missing_rag():
    input_data = GroqComplianceInput(
        user_question="How to certify quantum widgets under IS 99999?",
        product="Quantum Widgets",
        standards=["IS 99999"],
        deterministic_results={
            "is_mandatory": None,
            "qco_status": "QCO_NOT_ESTABLISHED",
            "certification_scheme": None
        },
        rag_evidence=[],
        qco_evidence=None,
        testing_evidence=[],
        f3_laboratories=[]
    )

    synthesizer = ComplianceJourneyV2Synthesizer()
    response = synthesizer.synthesize(input_data)

    assert response.regulatory_status.regulatory_orders == []
    assert response.mandatory_certification.is_mandatory is None
    assert "could not be confirmed" in response.applicable_standards.answer.lower() or "is 99999" in response.applicable_standards.answer.lower()
    assert_no_internal_jargon(response)


# ---------------------------------------------------------------------------
# 4. QCO Confirmed
# ---------------------------------------------------------------------------
def test_qco_confirmed():
    input_data = GroqComplianceInput(
        user_question="Mandatory status of lithium batteries",
        product="Lithium Ion Secondary Cells",
        standards=["IS 16046 (Part 2)"],
        deterministic_results={
            "is_mandatory": True,
            "qco_status": "QCO_APPLIES",
            "certification_scheme": "Compulsory Registration Scheme"
        },
        qco_evidence={
            "qco_title": "Electronics and Information Technology Goods (Requirement for Compulsory Registration) Order, 2021",
            "notification_numbers": ["S.O. 5432(E)"],
            "effective_date": "2021-04-01",
            "associated_qco_ids": ["qco_cro_2021"]
        }
    )

    synthesizer = ComplianceJourneyV2Synthesizer()
    response = synthesizer.synthesize(input_data)

    assert response.mandatory_certification.is_mandatory is True
    assert "mandatory" in response.mandatory_certification.answer.lower()
    assert len(response.regulatory_status.regulatory_orders) > 0
    assert "Compulsory Registration" in response.regulatory_status.regulatory_orders[0]
    assert_no_internal_jargon(response)


# ---------------------------------------------------------------------------
# 5. QCO Conflict
# ---------------------------------------------------------------------------
def test_qco_conflict():
    input_data = GroqComplianceInput(
        user_question="Ceiling fan regulations under IS 374",
        product="Electric Ceiling Fans",
        standards=["IS 374"],
        deterministic_results={
            "is_mandatory": True,
            "qco_status": "QCO_CONFLICT",
            "certification_scheme": None
        },
        qco_evidence={
            "qco_title": "Ceiling Fans Quality Control Order",
            "notification_numbers": ["S.O. 1111(E)", "S.O. 2222(E)"],
            "conflict_ids": ["conf_01", "conf_02"]
        }
    )

    synthesizer = ComplianceJourneyV2Synthesizer()
    response = synthesizer.synthesize(input_data)

    # Response must reflect conflicting Gazette orders and conservative regulatory review
    assert "conflicting" in response.regulatory_status.answer.lower()
    assert_no_internal_jargon(response)


# ---------------------------------------------------------------------------
# 6. Certification Scheme Unavailable
# ---------------------------------------------------------------------------
def test_certification_scheme_unavailable():
    input_data = GroqComplianceInput(
        user_question="Which certification scheme for IS 4985?",
        product="Pipes",
        standards=["IS 4985"],
        deterministic_results={
            "is_mandatory": True,
            "qco_status": "QCO_APPLIES",
            "certification_scheme": None  # Scheme not established in records
        }
    )

    # Mock raw dict simulating Groq attempting to invent Scheme-I as a confirmed fact
    fake_llm_output = {
        "certification_scheme": {
            "answer": "Under the BIS Act, Scheme-I (ISI Mark) is confirmed and required for IS 4985.",
            "scheme_name": "Scheme-I"
        }
    }

    guarded = ComplianceSafetyValidator.validate_and_guard(fake_llm_output, input_data)

    # The safety guard must prevent Groq from confirming Scheme-I
    assert guarded.certification_scheme.scheme_name is None
    assert "could not be confirmed" in guarded.certification_scheme.answer.lower()
    assert_no_internal_jargon(guarded)


# ---------------------------------------------------------------------------
# 7. Testing Partial
# ---------------------------------------------------------------------------
def test_testing_partial():
    input_data = GroqComplianceInput(
        user_question="Testing parameters for IS 1234",
        standards=["IS 1234"],
        deterministic_results={
            "testing_requirements": [
                {"test_name": "Tensile Strength Test", "test_clause": None}
            ]
        },
        testing_evidence=[
            {
                "source_title": "IS 1234 Tensile Requirements",
                "text": "Tensile strength shall not be less than 400 MPa."
            }
        ]
    )

    # Simulated Groq output inventing a fake clause "Clause 99.4"
    fake_llm_output = {
        "testing": {
            "answer": "The product must undergo Tensile Strength Test per Clause 99.4.",
            "test_methods": ["Tensile Strength Test"]
        }
    }

    guarded = ComplianceSafetyValidator.validate_and_guard(fake_llm_output, input_data)

    # Clause 99.4 was not in evidence, so safety validator must sanitize it
    assert "Clause 99.4" not in guarded.testing.answer
    assert "Tensile Strength Test" in guarded.testing.test_methods
    assert_no_internal_jargon(guarded)


# ---------------------------------------------------------------------------
# 8. Unknown Product
# ---------------------------------------------------------------------------
def test_unknown_product():
    input_data = GroqComplianceInput(
        user_question="Compliance for mythical anti-gravity boots",
        product="Anti-gravity boots",
        standards=[],
        deterministic_results={
            "is_mandatory": None,
            "qco_status": "QCO_NOT_ESTABLISHED",
            "certification_scheme": None
        }
    )

    synthesizer = ComplianceJourneyV2Synthesizer()
    response = synthesizer.synthesize(input_data)

    assert "anti-gravity boots" in response.product_identification.answer.lower()
    assert response.applicable_standards.standards == []
    assert response.mandatory_certification.is_mandatory is None
    assert_no_internal_jargon(response)


# ---------------------------------------------------------------------------
# 9. F3 Laboratories (Exact Preservation, Zero Hallucination)
# ---------------------------------------------------------------------------
def test_f3_laboratories():
    input_data = GroqComplianceInput(
        user_question="Where can I test my product?",
        standards=["IS 4985"],
        f3_laboratories=[
            {"id": "LAB_NORTH_1", "laboratory_name": "Northern Regional Laboratory, Sahibabad", "city": "Ghaziabad"},
            {"id": "LAB_WEST_2", "laboratory_name": "Western Regional Laboratory, Mumbai", "city": "Mumbai"}
        ]
    )

    # Simulated Groq output attempting to hallucinate a 3rd fake lab
    fake_llm_output = {
        "laboratories": {
            "answer": "You can test at Northern Regional Lab, Western Regional Lab, and Super Fast Lab Delhi.",
            "recognized_labs": [
                "Northern Regional Laboratory, Sahibabad",
                "Western Regional Laboratory, Mumbai",
                "Super Fast Lab Delhi"  # Hallucinated!
            ],
            "evidence_ids": ["LAB_NORTH_1", "LAB_WEST_2", "LAB_FAKE_99"]
        }
    }

    guarded = ComplianceSafetyValidator.validate_and_guard(fake_llm_output, input_data)

    # Must contain ONLY the 2 F3 laboratories
    assert len(guarded.laboratories.recognized_labs) == 2
    assert "Super Fast Lab Delhi" not in guarded.laboratories.recognized_labs
    assert "Northern Regional Laboratory, Sahibabad" in guarded.laboratories.recognized_labs
    assert "Western Regional Laboratory, Mumbai" in guarded.laboratories.recognized_labs
    # Fake evidence ID must be pruned
    assert "LAB_FAKE_99" not in guarded.laboratories.evidence_ids
    assert "LAB_NORTH_1" in guarded.laboratories.evidence_ids
    assert_no_internal_jargon(guarded)


# ---------------------------------------------------------------------------
# 10. Unsupported LLM Claims (Authority Locking & Jargon Purging)
# ---------------------------------------------------------------------------
def test_unsupported_llm_claims():
    input_data = GroqComplianceInput(
        user_question="Is certification mandatory?",
        standards=["IS 4985"],
        deterministic_results={
            "is_mandatory": True,
            "qco_status": "QCO_APPLIES"
        },
        qco_evidence={
            "qco_title": "Pipes and Fittings (Quality Control) Order, 2023",
            "notification_numbers": ["S.O. 1234(E)"]
        }
    )

    # Simulated hostile/hallucinatory Groq output:
    # 1. Claims voluntary despite mandatory QCO
    # 2. Hallucinates a fake notification S.O. 99999(E)
    # 3. Leaks internal jargon: UNKNOWN, GROUNDED, PC-5, deterministic baseline
    fake_llm_output = {
        "regulatory_status": {
            "answer": "Notified under S.O. 99999(E) per PC-5 deterministic baseline retrieval status.",
            "key_information": ["Status: UNKNOWN in evidence corpus"]
        },
        "mandatory_certification": {
            "answer": "Certification is voluntary and optional according to GROUNDED evaluations.",
            "is_mandatory": False  # Overridden!
        }
    }

    guarded = ComplianceSafetyValidator.validate_and_guard(fake_llm_output, input_data)

    # 1. Mandatory status MUST be re-locked to True
    assert guarded.mandatory_certification.is_mandatory is True
    assert "mandatory" in guarded.mandatory_certification.answer.lower()
    assert "voluntary" not in guarded.mandatory_certification.answer.lower()

    # 2. Fake notification S.O. 99999(E) must be stripped
    assert "S.O. 99999(E)" not in guarded.regulatory_status.answer

    # 3. Technical jargon must be purged
    assert_no_internal_jargon(guarded)
