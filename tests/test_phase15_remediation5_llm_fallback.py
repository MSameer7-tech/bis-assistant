# -*- coding: utf-8 -*-
"""
Test Suite for Phase 15 Remediation 5: Correct LLM Fallback Behavior for Non-Grounded Queries

Verifies:
1. TEST 1: General Knowledge Query ("What is retrieval augmented generation?")
   -> LLM_FALLBACK, source_layer: GENERAL_LLM_KNOWLEDGE, verified_against_bis: False, status: SUFFICIENT
2. TEST 2: Timber Doors Certification Query with previous turn IS 99
   -> IS 99 purged, intent: CERTIFICATION, LLM_FALLBACK, source_layer: GENERAL_LLM_KNOWLEDGE,
      status: SUFFICIENT, useful compliance guidance (IS 2202/1003, Scheme I, QCO), fallback disclaimer
3. TEST 3: Unknown Standard IS 9999999 Safe Refusal
   -> GROUNDED, status: INSUFFICIENT, source_layer: RAG, safe unverified limitation, no fabricated standard facts
4. TEST 4: Compound Hybrid Query ("Explain IS 4985 testing requirements and why hydrostatic pressure testing is important.")
   -> HYBRID, source_layer: RAG_PLUS_LLM, contains "### Verified BIS Information" and "### Additional General Information", hybrid disclaimer
5. TEST 5: Authoritative Grounded Query ("What is IS 4985?")
   -> GROUNDED, status: SUFFICIENT, source_layer: RAG, verified_against_bis: True, BIS evidence present
6. TEST 6: Production FastAPI Parity (/api/assistant/query and /api/phase12e/query)
   -> Both endpoints return generation_mode: LLM_FALLBACK and rich compliance guidance for timber doors
"""

import pytest
from fastapi.testclient import TestClient

from scripts.phase12_f2_orchestrator import (
    orchestrate_assistant_query,
    INTENT_CERTIFICATION,
    INTENT_TESTING,
    INTENT_DEFINITION,
    GroqClient,
)
from backend.app import app

client = TestClient(app)


class MockGroqClient:
    """Mock Groq client for deterministic testing."""
    def __init__(self):
        self.is_configured = True
        self.model_name = "openai/gpt-oss-120b"
        self.call_count = 0
        self.recorded_messages = []

    def chat_completion(self, messages, max_tokens=1200):
        self.call_count += 1
        self.recorded_messages.append(messages)
        user_content = messages[-1]["content"] if messages else ""
        system_content = messages[0]["content"] if messages else ""

        # General Knowledge (RAG)
        if "retrieval augmented generation" in user_content.lower():
            return (
                "### Answer\n\n"
                "Retrieval-Augmented Generation (RAG) is an AI architecture that enhances large language model "
                "responses by retrieving relevant, authoritative documents from an external knowledge base before "
                "synthesizing an answer, thereby improving factual accuracy and reducing hallucinations.\n\n"
                "> ⚠️ This answer is based on general knowledge and is not verified against BIS evidence."
            )

        # Timber Doors Certification
        if "timber door" in user_content.lower() or "wooden door" in user_content.lower():
            return (
                "### Answer\n\n"
                "For manufacturers of timber doors in India, the following general compliance and certification guidance applies:\n\n"
                "1. **Applicable Indian Standards:**\n"
                "- **IS 2202 (Part 1 & 2):** Specification for Wooden Flush Door Shutters.\n"
                "- **IS 1003 (Part 1 & 2):** Specification for Timber Panelled and Glazed Shutters.\n"
                "- **IS 4020 (Parts 1 to 16):** Methods of test for wooden door shutters.\n\n"
                "2. **Standard BIS Certification Process (Scheme I - ISI Mark):**\n"
                "- Identify the specific product standard applicable to your door construction.\n"
                "- Establish in-house testing facilities and quality management systems per BIS Scheme of Inspection and Testing (SIT).\n"
                "- Undergo a formal factory inspection and preliminary audit by BIS technical officers.\n"
                "- Have drawn samples independently tested at BIS or BIS-recognized laboratories.\n"
                "- Receive the grant of ISI mark license under Scheme I upon conformity verification.\n\n"
                "3. **Voluntary vs. Mandatory Certification:**\n"
                "- The existence of Indian Standards specifies technical benchmarks. Whether certification is legally mandatory depends "
                "on whether the Government of India has notified a Quality Control Order (QCO) for that specific door product category. "
                "Where no mandatory QCO applies, certification remains voluntary under Scheme I.\n\n"
                "> ⚠️ This answer is based on general knowledge and is not verified against BIS evidence."
            )

        # Compound Hybrid Query
        if "hybrid" in system_content.lower() or "hydrostatic" in user_content.lower():
            return (
                "### Verified BIS Information\n\n"
                "IS 4985 specifies requirements for unplasticized PVC pipes for potable water supplies. "
                "Clause 8 specifies mandatory hydrostatic pressure tests, including short-term and long-term hydrostatic testing at designated pressures.\n\n"
                "### Additional General Information\n\n"
                "Hydrostatic pressure testing is vital in piping systems to verify the mechanical integrity, burst resistance, "
                "and hoop-stress tolerance of the thermoplastic material under continuous operational fluid pressure, preventing structural leaks and catastrophic line failures.\n\n"
                "> ⚠️ Additional information is based on general knowledge and is not verified against BIS evidence."
            )

        # Grounded IS 4985
        return (
            "IS 4985 specifies requirements for unplasticized PVC pipes for potable water supplies.\n\n"
            "### Standard Details\n- Standard: IS 4985:2021\n- Revision: Fourth Revision"
        )


# =========================================================================
# TEST 1: General Knowledge Query -> LLM_FALLBACK
# =========================================================================
def test_01_general_knowledge_rag_query():
    """'What is retrieval augmented generation?' triggers LLM_FALLBACK with GENERAL_LLM_KNOWLEDGE."""
    mock_groq = MockGroqClient()
    res = orchestrate_assistant_query("What is retrieval augmented generation?", groq_client=mock_groq)

    assert res["generation_mode"] == "LLM_FALLBACK"
    assert res["provenance"]["source_layer"] == "GENERAL_LLM_KNOWLEDGE"
    assert res["provenance"]["verified_against_bis"] is False
    assert res["status"] == "SUFFICIENT"
    assert res["answer"] and len(res["answer"].strip()) > 50
    assert "### Answer" in res["answer"]
    assert "not verified against BIS evidence" in res["answer"]


# =========================================================================
# TEST 2: Timber Doors Certification Query -> LLM_FALLBACK
# =========================================================================
def test_02_timber_doors_certification_fallback():
    """Turn 1 'What is IS 99?' -> Turn 2 'I manufacture timber doors. What certifications do I need?'"""
    history = [
        {"role": "user", "text": "What is IS 99?"},
        {"role": "assistant", "text": "I could not verify IS 99 from available BIS records."}
    ]
    query = "I manufacture timber doors. What certifications do I need?"
    mock_groq = MockGroqClient()
    res = orchestrate_assistant_query(query, groq_client=mock_groq, conversation_history=history)

    # Context leakage verification: IS 99 must not be present
    assert "IS 99" not in res["answer"]
    assert "is 99" not in res["answer"].lower()

    # Intent and Mode verification
    assert res["intent"] == INTENT_CERTIFICATION
    assert res["generation_mode"] == "LLM_FALLBACK"
    assert res["provenance"]["source_layer"] == "GENERAL_LLM_KNOWLEDGE"
    assert res["provenance"]["verified_against_bis"] is False
    assert res["status"] == "SUFFICIENT"

    # Answer quality: Must contain rich compliance guidance, NOT solely a refusal
    ans = res["answer"]
    assert "timber door" in ans.lower() or "wooden door" in ans.lower()
    # Relevant Indian Standards mentioned (e.g. IS 2202 or IS 1003)
    assert "IS 2202" in ans or "IS 1003" in ans or "standard" in ans.lower()
    # Certification process mentioned (Scheme I / ISI Mark / Factory inspection / In-house testing)
    assert any(term in ans.lower() for term in ["scheme i", "isi mark", "factory", "in-house", "testing", "license", "licence"])
    # Voluntary vs Mandatory distinction mentioned
    assert any(term in ans.lower() for term in ["voluntary", "mandatory", "qco", "quality control order"])
    # Fallback disclaimer present
    assert "not verified against BIS evidence" in ans or "not verified against bis" in ans.lower()


# =========================================================================
# TEST 3: Unknown Standard IS 9999999 Safe Refusal
# =========================================================================
def test_03_unknown_standard_is9999999_safe():
    """'What is IS 9999999?' triggers GROUNDED safe inability refusal without inventing standard details."""
    mock_groq = MockGroqClient()
    res = orchestrate_assistant_query("What is IS 9999999?", groq_client=mock_groq)

    assert res["generation_mode"] == "GROUNDED"
    assert res["status"] == "INSUFFICIENT"
    assert res["provenance"]["source_layer"] == "RAG"
    assert res["provenance"]["verified_against_bis"] is False

    ans = res["answer"]
    assert "IS 9999999" in ans
    assert any(phrase in ans.lower() for phrase in ["could not verify", "not an active", "unrecognized", "cannot reliably identify"])
    # Never invent technical parameters
    assert "tensile strength" not in ans.lower()
    assert "hydrostatic pressure" not in ans.lower()


# =========================================================================
# TEST 4: Compound Hybrid Testing Query -> HYBRID Mode
# =========================================================================
def test_04_compound_hybrid_testing_query():
    """'Explain IS 4985 testing requirements and why hydrostatic pressure testing is important.' -> HYBRID mode."""
    mock_groq = MockGroqClient()
    res = orchestrate_assistant_query(
        "Explain IS 4985 testing requirements and why hydrostatic pressure testing is important.",
        groq_client=mock_groq
    )

    assert res["generation_mode"] == "HYBRID"
    assert res["provenance"]["source_layer"] == "RAG_PLUS_LLM"
    assert res["provenance"]["verified_against_bis"] is False

    ans = res["answer"]
    assert "### Verified BIS Information" in ans
    assert "### Additional General Information" in ans
    assert "Additional information is based on general knowledge and is not verified against BIS evidence" in ans
    assert "IS 4985" in ans


# =========================================================================
# TEST 5: Grounded IS 4985 Query -> GROUNDED Mode
# =========================================================================
def test_05_grounded_is4985_query():
    """'What is IS 4985?' triggers GROUNDED mode with authoritative BIS evidence."""
    mock_groq = MockGroqClient()
    res = orchestrate_assistant_query("What is IS 4985?", groq_client=mock_groq)

    assert res["generation_mode"] == "GROUNDED"
    assert res["status"] == "SUFFICIENT"
    assert res["provenance"]["source_layer"] == "RAG"
    assert res["provenance"]["verified_against_bis"] is True
    assert res["provenance"]["llm_fallback_used"] is False
    assert len(res["rag"].get("evidence", [])) > 0
    assert len(res.get("claims", [])) > 0


# =========================================================================
# TEST 6: Production FastAPI Endpoints Parity
# =========================================================================
def test_06_fastapi_endpoints_timber_doors_fallback():
    """Verifies both /api/assistant/query and /api/phase12e/query return LLM_FALLBACK for timber doors."""
    history = [
        {"role": "user", "text": "What is IS 99?"},
        {"role": "assistant", "text": "I could not verify information for IS 99."}
    ]
    payload = {
        "query": "I manufacture timber doors so tell me what certifications do I need",
        "history": history
    }

    # Test /api/assistant/query
    res1 = client.post("/api/assistant/query", json=payload)
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["intent"] == INTENT_CERTIFICATION
    assert data1["generation_mode"] == "LLM_FALLBACK"
    assert data1["provenance"]["source_layer"] == "GENERAL_LLM_KNOWLEDGE"
    assert data1["status"] == "SUFFICIENT"
    assert "IS 99" not in data1["answer"]
    assert "is 99" not in data1["answer"].lower()
    assert "timber door" in data1["answer"].lower() or "wooden door" in data1["answer"].lower()

    # Test /api/phase12e/query
    res2 = client.post("/api/phase12e/query", json=payload)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["intent"] == INTENT_CERTIFICATION
    assert data2["generation_mode"] == "LLM_FALLBACK"
    assert data2["provenance"]["source_layer"] == "GENERAL_LLM_KNOWLEDGE"
    assert data2["status"] == "SUFFICIENT"
    assert "IS 99" not in data2["answer"]
    assert "is 99" not in data2["answer"].lower()
    assert "timber door" in data2["answer"].lower() or "wooden door" in data2["answer"].lower()
