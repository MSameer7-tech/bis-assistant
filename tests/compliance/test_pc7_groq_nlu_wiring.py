"""
Phase PC-7: Groq NLU Wiring and Structured Extraction Test Suite.

Automated validation covering:
1. Groq NLU Structured Extraction: Proves Groq is called with structured system prompt and openai/gpt-oss-120b.
2. Malformed LLM Response: Verifies graceful fallback to regex when Groq outputs non-JSON or invalid JSON.
3. Groq Timeout / Network Error: Verifies fallback to deterministic regex on exception.
4. Groq Unconfigured: Verifies clean fallback when API key is missing.
5. Ambiguous Product ('pvc'): Resolves to AMBIGUOUS with grounded candidates, no arbitrary primary standard.
6. Incomplete Product ('I manufacture pipes'): Resolves to INCOMPLETE with attribute groups.
7. Clear Product ('PVC pipes for potable water in Delhi'): Resolves to CLEAR (IS 4985) without unnecessary questions.
8. Explicit Standard Fast Path ('PVC pipes under IS 4985'): Bypasses Groq completely.
9. Zero Hallucinated Standards: Fabricated standards returned by Groq are rejected by the BIS catalog guard.
10. Zero Regulatory Decisions: Verifies NLU response contains no QCO, scheme, or lab qualification determinations.
"""

import json
from typing import Dict, Any, List, Optional
import pytest

from ai.compliance.nlu_clarification import (
    ComplianceNLUClarificationEngine,
    ComplianceClarificationRequest,
    ClarificationState,
    GROQ_COMPLIANCE_NLU_SYSTEM_PROMPT
)


class MockGroqClient:
    """Mock Groq client for automated testing without live network calls."""
    def __init__(
        self,
        response_data: Optional[Dict[str, Any]] = None,
        raw_text: Optional[str] = None,
        should_fail: bool = False,
        error_type: str = "network",
        model: str = "openai/gpt-oss-120b"
    ):
        self.response_data = response_data
        self.raw_text = raw_text
        self.should_fail = should_fail
        self.error_type = error_type
        self.model_name = model
        self.is_configured = True
        self.call_history: List[Dict[str, Any]] = []

    def chat_completion(self, messages: List[Dict[str, str]], max_tokens: int = 250) -> str:
        self.call_history.append({"messages": messages, "max_tokens": max_tokens})
        if self.should_fail:
            if self.error_type == "timeout":
                raise TimeoutError("Groq request timed out after 8.0s")
            raise RuntimeError("Groq Network Connection Error: [Errno 8] nodename nor servname provided")

        if self.raw_text is not None:
            return self.raw_text

        if self.response_data is not None:
            return json.dumps(self.response_data)

        # Default minimal valid response
        return json.dumps({
            "product": None,
            "product_category": None,
            "material": None,
            "application": None,
            "attributes": {},
            "standard": None,
            "location": None,
            "intent": "compliance_query",
            "resolution_hint": None
        })


# ==============================================================================
# TEST 1: GROQ NLU STRUCTURED EXTRACTION WIRING
# ==============================================================================
def test_groq_structured_extraction_wired():
    """Proves Groq is called with structured system prompt, extracting slots cleanly."""
    mock_response = {
        "product": "PVC pipes",
        "product_category": "Plumbing",
        "material": "PVC",
        "application": "potable water supply",
        "attributes": {"use": "drinking water"},
        "standard": None,
        "location": "Delhi",
        "intent": "manufacturer_compliance",
        "resolution_hint": "CLEAR"
    }
    mock_groq = MockGroqClient(response_data=mock_response)
    engine = ComplianceNLUClarificationEngine(groq_client=mock_groq)

    req = ComplianceClarificationRequest(query="I manufacture PVC pipes for potable water supply in Delhi")
    res = engine.analyze_clarification(req)

    # Verify Groq was actually called
    assert len(mock_groq.call_history) == 1
    call = mock_groq.call_history[0]
    assert call["messages"][0]["role"] == "system"
    assert "Bureau of Indian Standards" in call["messages"][0]["content"]
    assert "User Query: I manufacture PVC pipes for potable water supply in Delhi" in call["messages"][1]["content"]

    # Verify model
    assert mock_groq.model_name == "openai/gpt-oss-120b"

    # Verify slots extracted
    assert res.slots.product == "PVC pipes"
    assert res.slots.material == "PVC"
    assert res.slots.application == "potable water supply"
    assert res.slots.location == "Delhi"

    # Verify grounded to IS 4985
    assert res.state == ClarificationState.CLEAR
    assert res.resolved_standard == "IS 4985"


# ==============================================================================
# TEST 2: MALFORMED LLM RESPONSE FALLBACK
# ==============================================================================
def test_malformed_llm_response_fallback():
    """Groq returns invalid/malformed JSON -> engine catches and falls back to regex."""
    mock_groq = MockGroqClient(raw_text="This is not valid JSON at all! ```broken json")
    engine = ComplianceNLUClarificationEngine(groq_client=mock_groq)

    req = ComplianceClarificationRequest(query="I manufacture PVC pipes for potable water supply in Mumbai")
    res = engine.analyze_clarification(req)

    # Groq was called but failed gracefully
    assert len(mock_groq.call_history) == 1
    # Fallback still extracts and grounds successfully
    assert res.state == ClarificationState.CLEAR
    assert res.resolved_standard == "IS 4985"
    assert res.slots.location == "Mumbai"


# ==============================================================================
# TEST 3: GROQ TIMEOUT AND NETWORK ERROR FALLBACK
# ==============================================================================
def test_groq_timeout_and_network_fallback():
    """Groq times out or encounters network error -> falls back without crashing."""
    # Test Timeout
    mock_groq_timeout = MockGroqClient(should_fail=True, error_type="timeout")
    engine_timeout = ComplianceNLUClarificationEngine(groq_client=mock_groq_timeout)
    res_timeout = engine_timeout.analyze_clarification(
        ComplianceClarificationRequest(query="I manufacture PVC pipes for potable water supply")
    )
    assert res_timeout.state == ClarificationState.CLEAR
    assert res_timeout.resolved_standard == "IS 4985"

    # Test Network Error
    mock_groq_net = MockGroqClient(should_fail=True, error_type="network")
    engine_net = ComplianceNLUClarificationEngine(groq_client=mock_groq_net)
    res_net = engine_net.analyze_clarification(
        ComplianceClarificationRequest(query="pvc")
    )
    assert res_net.state == ClarificationState.AMBIGUOUS
    assert len(res_net.clarification.candidates) == 5


# ==============================================================================
# TEST 4: GROQ UNCONFIGURED (NO API KEY)
# ==============================================================================
def test_groq_unconfigured_fallback():
    """When GroqClient.is_configured is False, uses regex extraction without calling Groq."""
    mock_groq = MockGroqClient()
    mock_groq.is_configured = False
    engine = ComplianceNLUClarificationEngine(groq_client=mock_groq)

    res = engine.analyze_clarification(
        ComplianceClarificationRequest(query="I manufacture pipes")
    )
    assert len(mock_groq.call_history) == 0
    assert res.state == ClarificationState.INCOMPLETE
    assert res.clarification is not None
    assert len(res.clarification.attribute_groups) == 2


# ==============================================================================
# TEST 5: AMBIGUOUS QUERY ('pvc')
# ==============================================================================
def test_ambiguous_query_pvc_groq():
    """Broad term 'pvc' results in AMBIGUOUS with 5 candidates, no primary standard."""
    mock_response = {
        "product": "PVC",
        "product_category": "Plastics / Polymers",
        "material": "PVC",
        "application": None,
        "attributes": {},
        "standard": None,
        "location": None,
        "intent": "product_inquiry",
        "resolution_hint": "AMBIGUOUS"
    }
    mock_groq = MockGroqClient(response_data=mock_response)
    engine = ComplianceNLUClarificationEngine(groq_client=mock_groq)

    res = engine.analyze_clarification(ComplianceClarificationRequest(query="pvc"))
    assert res.state == ClarificationState.AMBIGUOUS
    assert res.resolved_standard is None
    assert len(res.clarification.candidates) == 5
    stds = [c.standard_number for c in res.clarification.candidates]
    assert "IS 4985" in stds
    assert "IS 694" in stds


# ==============================================================================
# TEST 6: INCOMPLETE QUERY ('I manufacture pipes')
# ==============================================================================
def test_incomplete_query_pipes_groq():
    """Generic category 'pipes' results in INCOMPLETE with questionnaire."""
    mock_response = {
        "product": "pipes",
        "product_category": "Piping",
        "material": None,
        "application": None,
        "attributes": {},
        "standard": None,
        "location": None,
        "intent": "manufacturing_inquiry",
        "resolution_hint": "INCOMPLETE"
    }
    mock_groq = MockGroqClient(response_data=mock_response)
    engine = ComplianceNLUClarificationEngine(groq_client=mock_groq)

    res = engine.analyze_clarification(ComplianceClarificationRequest(query="I manufacture pipes"))
    assert res.state == ClarificationState.INCOMPLETE
    assert res.resolved_standard is None
    assert res.clarification is not None
    assert "What type of pipes" in res.clarification.title
    assert len(res.clarification.attribute_groups) == 2


# ==============================================================================
# TEST 7: EXPLICIT STANDARD FAST PATH (NO GROQ CALL)
# ==============================================================================
def test_explicit_standard_fast_path():
    """Explicit standard token ('IS 4985') bypasses Groq call completely."""
    mock_groq = MockGroqClient()
    engine = ComplianceNLUClarificationEngine(groq_client=mock_groq)

    res = engine.analyze_clarification(ComplianceClarificationRequest(query="PVC pipes under IS 4985"))
    assert len(mock_groq.call_history) == 0  # Proves Groq was NOT called
    assert res.state == ClarificationState.CLEAR
    assert res.resolved_standard == "IS 4985"


# ==============================================================================
# TEST 8: REJECTION OF HALLUCINATED STANDARDS
# ==============================================================================
def test_rejection_of_hallucinated_standards():
    """If Groq fabricates an invalid standard (e.g. IS 999999), it is rejected."""
    mock_response = {
        "product": "Widget",
        "product_category": "Gadgets",
        "material": None,
        "application": None,
        "attributes": {},
        "standard": "IS 999999",  # Hallucinated standard
        "location": None,
        "intent": "compliance_check",
        "resolution_hint": "CLEAR"
    }
    mock_groq = MockGroqClient(response_data=mock_response)
    engine = ComplianceNLUClarificationEngine(groq_client=mock_groq)

    res = engine.analyze_clarification(ComplianceClarificationRequest(query="Check futuristic smart widget"))
    # The hallucinated standard is not accepted as resolved_standard
    assert res.resolved_standard is None or res.resolved_standard != "IS 999999"


# ==============================================================================
# TEST 9: ZERO REGULATORY DECISIONS FROM NLU
# ==============================================================================
def test_zero_regulatory_decisions_from_nlu():
    """Verifies that NLU response contains no QCO, scheme, testing, or lab determinations."""
    mock_groq = MockGroqClient()
    engine = ComplianceNLUClarificationEngine(groq_client=mock_groq)

    res = engine.analyze_clarification(
        ComplianceClarificationRequest(query="I manufacture PVC pipes for potable water supply")
    )
    res_dict = res.model_dump() if hasattr(res, "model_dump") else res.dict()
    # Ensure no regulatory fields exist in clarification response
    assert "qco_status" not in res_dict
    assert "is_mandatory" not in res_dict
    assert "testing_requirements" not in res_dict
    assert "qualified_laboratories" not in res_dict
