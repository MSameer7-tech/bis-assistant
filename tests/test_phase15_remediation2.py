# -*- coding: utf-8 -*-
"""
Test Suite for Phase 15 Remediation 2: Production Conversation, Evidence Relevance & F3 Integration

Verifies:
1. Turn 1 "What is IS 4985?" -> INTENT_DEFINITION, concise definition, no repetitive boilerplate.
2. Turn 2 "What tests does it require?" with history -> INTENT_TESTING, resolved standard = IS 4985, 0% spoon chunks.
3. Turn 3 "Where can I get these tests done?" with history -> INTENT_LAB_SEARCH, resolved standard = IS 4985, F3 invoked, 28 labs.
4. Direct lab search -> F3_LAB_FINDER, 28 labs, claims & evidence at top level.
5. Location-filtered lab search -> Delhi -> 2 labs.
6. Standard comparison ("IS 4985 vs IS 13592") -> both present, evidence and claims at top level.
7. Amendment safety ("latest amendment to IS 4985") -> PARTIAL/INSUFFICIENT, Fourth Revision verified, amendment unverified, verified_against_bis = False.
8. Regulatory cautious phrasing -> no absolute claims ("is not mandatory", "no requirement").
9. Unknown standard ("IS 9999999") -> unverified standard notice, no invented standard.
10. Out-of-corpus query ("What is retrieval augmented generation?") -> LLM_FALLBACK, GENERAL_LLM_KNOWLEDGE, verified_against_bis = False.
11. Markup sanitization -> no leaked raw markdown image or raw SVG markup in answer.
12. Relevance gate unit tests -> spoon chunks dropped for IS 4985.
13. Production FastAPI parity -> /api/assistant/query and /api/phase12e/query.
"""

import re
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from scripts.phase12_f2_orchestrator import (
    orchestrate_assistant_query,
    filter_and_validate_evidence_relevance,
    strip_unverified_disclaimers,
    INTENT_DEFINITION,
    INTENT_TESTING,
    INTENT_LAB_SEARCH,
    INTENT_STANDARD_COMPARISON,
    INTENT_AMENDMENT_HISTORY,
    INTENT_CERTIFICATION,
)
from backend.app import app


client = TestClient(app)


# =========================================================================
# 1. Turn 1: Definition Query Concise Formatting
# =========================================================================
def test_definition_query_concise():
    """Test 1: 'What is IS 4985?' returns a concise, intent-focused definition."""
    res = orchestrate_assistant_query("What is IS 4985?")
    assert res["status"] == "SUFFICIENT"
    assert res["intent"] == INTENT_DEFINITION
    assert res["generation_mode"] == "GROUNDED"
    assert res["provenance"]["verified_against_bis"] is True

    ans = res["answer"]
    assert "IS 4985" in ans
    assert "Standard Designation" in ans or "मानक संख्या" in ans
    assert "Revision" in ans or "पुनरीक्षण" in ans or "2021" in ans
    assert "Official Title" in ans or "शीर्षक" in ans or "uPVC" in ans or "Unplasticized" in ans

    # Must NOT contain the 4 verbose boilerplate sections
    assert "### In Simple Terms" not in ans
    assert "### Standard Details" not in ans


# =========================================================================
# 2. Turn 2: Conversational Follow-Up Without Spoon Chunks
# =========================================================================
def test_conversational_follow_up_no_spoon_chunks():
    """Test 2: 'What tests does it require?' following IS 4985 resolves to IS 4985 without spoon chunks."""
    history = [
        {"role": "user", "text": "What is IS 4985?"},
        {
            "role": "assistant",
            "text": "IS 4985 specifies requirements for uPVC pipes for potable water supplies.",
            "data": {"standard": "IS 4985", "intent": "DEFINITION"}
        }
    ]
    res = orchestrate_assistant_query("What tests does it require?", conversation_history=history)
    assert res["status"] == "SUFFICIENT"
    assert res["intent"] == INTENT_TESTING
    assert res["generation_mode"] == "GROUNDED"

    evidence = res.get("evidence", [])
    assert len(evidence) > 0

    # Critical Assertion: Zero spoon / cutlery chunks (IS 16286) can survive
    for ev in evidence:
        ev_str = str(ev).lower()
        assert "16286" not in ev_str, f"Spoon standard IS 16286 leaked into evidence: {ev}"
        assert "spoon" not in ev_str, f"Spoon chunk leaked into evidence: {ev}"
        assert "cutlery" not in ev_str, f"Cutlery chunk leaked into evidence: {ev}"

    # Verify answer mentions pipe or testing requirements, never spoons
    assert "spoon" not in res["answer"].lower()
    assert "cutlery" not in res["answer"].lower()


# =========================================================================
# 3. Turn 3: Conversational Follow-Up to F3 Lab Search
# =========================================================================
def test_conversational_turn3_f3_lab_search():
    """Test 3: 'Where can I get these tests done?' in 3-turn sequence invokes F3 Lab Finder."""
    history = [
        {"role": "user", "text": "What is IS 4985?"},
        {
            "role": "assistant",
            "text": "IS 4985 specifies requirements for uPVC pipes.",
            "data": {"standard": "IS 4985", "intent": "DEFINITION"}
        },
        {"role": "user", "text": "What tests does it require?"},
        {
            "role": "assistant",
            "text": "Key tests include hydrostatic pressure test, impact resistance, and opacity.",
            "data": {"standard": "IS 4985", "intent": "TESTING"}
        }
    ]
    res = orchestrate_assistant_query("Where can I get these tests done?", conversation_history=history)
    assert res["status"] == "SUFFICIENT"
    assert res["intent"] == INTENT_LAB_SEARCH
    assert res["provenance"]["source_layer"] == "F3_LAB_FINDER"
    assert res["provenance"]["verified_against_bis"] is True

    ans = res["answer"]
    assert "BIS-Recognized Testing Laboratories for IS 4985" in ans
    assert "28" in ans  # 28 recognized laboratories for IS 4985
    assert "SIIR, Delhi" in ans or "Shriram Institute" in ans


# =========================================================================
# 4. Direct Lab Search via F3
# =========================================================================
def test_direct_lab_search_f3():
    """Test 4: Direct query 'Find BIS-recognized laboratories that can test according to IS 4985.' routes to F3."""
    res = orchestrate_assistant_query("Find BIS-recognized laboratories that can test according to IS 4985.")
    assert res["status"] == "SUFFICIENT"
    assert res["intent"] == INTENT_LAB_SEARCH
    assert res["provenance"]["source_layer"] == "F3_LAB_FINDER"
    assert "claims" in res
    assert "evidence" in res
    assert "28" in res["answer"]


# =========================================================================
# 5. Location-Filtered Lab Search (Delhi)
# =========================================================================
def test_delhi_lab_search_f3():
    """Test 5: 'Find BIS-recognized laboratories in Delhi for IS 4985.' returns 2 Delhi labs."""
    res = orchestrate_assistant_query("Find BIS-recognized laboratories in Delhi for IS 4985.")
    assert res["status"] == "SUFFICIENT"
    assert res["intent"] == INTENT_LAB_SEARCH
    assert res["provenance"]["source_layer"] == "F3_LAB_FINDER"
    assert "Found **2** recognized laboratories" in res["answer"]


# =========================================================================
# 6. Standard Comparison (IS 4985 vs IS 13592)
# =========================================================================
def test_standard_comparison_both_standards():
    """Test 6: 'What is the difference between IS 4985 and IS 13592?' compares both standards."""
    res = orchestrate_assistant_query("What is the difference between IS 4985 and IS 13592?")
    assert res["status"] == "SUFFICIENT"
    assert res["intent"] == INTENT_STANDARD_COMPARISON
    assert "claims" in res
    assert "unsupported_claims" in res
    assert "evidence" in res
    assert len(res["evidence"]) > 0

    ans = res["answer"]
    assert "IS 4985" in ans
    assert "IS 13592" in ans
    assert "No BIS evidence was found for IS 13592" not in ans


# =========================================================================
# 7. Amendment Verification Safety
# =========================================================================
def test_amendment_verification_safety():
    """Test 7: 'What is the latest amendment to IS 4985?' acknowledges Fourth Revision without false verification."""
    res = orchestrate_assistant_query("What is the latest amendment to IS 4985?")
    assert res["intent"] == INTENT_AMENDMENT_HISTORY
    assert res["status"] in ("PARTIAL", "INSUFFICIENT")
    assert res["provenance"]["verified_against_bis"] is False

    ans = res["answer"]
    assert "Fourth Revision" in ans
    # Must NOT state that the Fourth Revision is an amendment
    assert "latest amendment (fourth revision)" not in ans.lower()
    # Must state that subsequent amendments are not verified in indexed records
    assert "could not verify the latest amendment" in ans.lower() or "not verified" in ans.lower()


# =========================================================================
# 8. Regulatory Cautious Phrasing
# =========================================================================
def test_regulatory_cautious_phrasing():
    """Test 8: 'Is BIS certification mandatory for uPVC pipes?' does not make absolute legal assertions."""
    res = orchestrate_assistant_query("Is BIS certification mandatory for uPVC pipes?")
    assert res["intent"] == INTENT_CERTIFICATION

    ans = res["answer"]
    # Must NOT state absolute non-mandatory statements
    assert "there is no requirement for mandatory certification" not in ans.lower()
    assert "certification is not mandatory" not in ans.lower()
    assert "it is voluntary" not in ans.lower()

    # Must contain cautious explanation referencing QCOs
    assert "quality control order" in ans.lower() or "qco" in ans.lower()
    assert "could not be verified" in ans.lower() or "does not establish" in ans.lower()


# =========================================================================
# 9. Unknown Standard Safe Response
# =========================================================================
def test_unknown_standard_safe_non_empty():
    """Test 9: 'What is IS 9999999?' returns safe non-empty response without inventing details."""
    res = orchestrate_assistant_query("What is IS 9999999?")
    assert res["status"] == "INSUFFICIENT"
    assert res["generation_mode"] == "GROUNDED"
    assert res["provenance"]["verified_against_bis"] is False

    ans = res["answer"]
    assert "IS 9999999" in ans
    assert "could not verify" in ans.lower() or "not an active" in ans.lower()


# =========================================================================
# 10. Out-of-Corpus Query -> LLM_FALLBACK
# =========================================================================
def test_out_of_corpus_llm_fallback():
    """Test 10: 'What is retrieval augmented generation?' triggers LLM_FALLBACK."""
    res = orchestrate_assistant_query("What is retrieval augmented generation?")
    assert res["generation_mode"] == "LLM_FALLBACK"
    assert res["provenance"]["source_layer"] == "GENERAL_LLM_KNOWLEDGE"
    assert res["provenance"]["verified_against_bis"] is False

    ans = res["answer"]
    assert ans.startswith("### Answer")
    assert "retrieval augmented generation" in ans.lower() or "rag" in ans.lower()
    assert "not been verified against authoritative bis" in ans.lower() or "not verified against bis" in ans.lower()


# =========================================================================
# 11. Raw Image & SVG Sanitization
# =========================================================================
def test_markup_sanitization():
    """Test 11: Raw image markdown, local URLs, and raw SVG tags are sanitized from answers."""
    dirty_text = (
        "Here is the answer.\n\n"
        "![Avatar](http://localhost:8000/static/avatar.png)\n\n"
        "[image](http://localhost:3000/static/favicon.svg)\n\n"
        "<svg width='24' height='24'><path d='M10 10'/></svg>\n\n"
        "svgsvg\n\n"
        "Final conclusion."
    )
    cleaned = strip_unverified_disclaimers(dirty_text)
    assert "![Avatar]" not in cleaned
    assert "[image]" not in cleaned
    assert "localhost" not in cleaned
    assert "<svg" not in cleaned
    assert "svgsvg" not in cleaned
    assert "Here is the answer." in cleaned
    assert "Final conclusion." in cleaned


# =========================================================================
# 12. Relevance Gate Unit Tests (Spoon Chunks Rejection)
# =========================================================================
def test_relevance_gate_rejects_spoon_chunks():
    """Test 12: Relevance gate filters out conflicting IS-16286 spoon chunks when IS 4985 is requested."""
    synthetic_rag = {
        "status": "SUFFICIENT",
        "evidence": [
            {
                "retrieval_unit_id": "PM-SRC-006-32-IS-16286-2014-PRODUCT-MANUAL-FOR-SPOO",
                "standard_number": "IS 16286",
                "standard_title": "Product Manual for Stainless Steel Spoons",
                "text": "Cutlery testing specifications for spoons and tableware according to IS 16286:2014."
            },
            {
                "retrieval_unit_id": "IS-4985-2021-SEC-01",
                "standard_number": "IS 4985",
                "standard_title": "Unplasticized Polyvinyl Chloride (uPVC) Pipes",
                "text": "Hydrostatic pressure test requirements for uPVC pipes according to IS 4985."
            }
        ],
        "claims": [
            {"statement": "IS 16286 requires cutlery bend testing.", "subject_entity": "IS 16286"},
            {"statement": "IS 4985 specifies hydrostatic pressure test.", "subject_entity": "IS 4985"}
        ],
        "answer": "Spoons and pipes testing requirements."
    }
    query_ctx = {
        "is_numbers": ["IS 4985"],
        "product": "upvc pipes",
        "intent": INTENT_TESTING,
        "response_language": "en"
    }
    filtered_rag, status = filter_and_validate_evidence_relevance(synthetic_rag, query_ctx, "What tests does IS 4985 require?")

    ev_list = filtered_rag["evidence"]
    assert len(ev_list) == 1
    assert ev_list[0]["standard_number"] == "IS 4985"
    assert "16286" not in str(ev_list[0])

    claims_list = filtered_rag["claims"]
    assert len(claims_list) == 1
    assert claims_list[0]["subject_entity"] == "IS 4985"


# =========================================================================
# 13. Production FastAPI Parity Tests
# =========================================================================
def test_fastapi_production_assistant_query():
    """Test 13a: POST /api/assistant/query with conversation history."""
    payload = {
        "query": "Where can I get these tests done?",
        "response_style": "Detailed & Explanatory",
        "history": [
            {"role": "user", "text": "What is IS 4985?"},
            {"role": "assistant", "text": "IS 4985 specifies requirements for uPVC pipes.", "data": {"standard": "IS 4985", "intent": "DEFINITION"}},
            {"role": "user", "text": "What tests does it require?"},
            {"role": "assistant", "text": "Hydrostatic pressure test.", "data": {"standard": "IS 4985", "intent": "TESTING"}}
        ]
    }
    resp = client.post("/api/assistant/query", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUFFICIENT"
    assert data["intent"] == "LAB_SEARCH"
    assert data["provenance"]["source_layer"] == "F3_LAB_FINDER"
    assert "28" in data["answer"]


def test_fastapi_production_phase12e_query():
    """Test 13b: POST /api/phase12e/query with conversation history."""
    payload = {
        "query": "Where can I get these tests done?",
        "response_style": "Detailed & Explanatory",
        "history": [
            {"role": "user", "text": "What is IS 4985?"},
            {"role": "assistant", "text": "IS 4985 specifies requirements for uPVC pipes.", "data": {"standard": "IS 4985", "intent": "DEFINITION"}},
            {"role": "user", "text": "What tests does it require?"},
            {"role": "assistant", "text": "Hydrostatic pressure test.", "data": {"standard": "IS 4985", "intent": "TESTING"}}
        ]
    }
    resp = client.post("/api/phase12e/query", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUFFICIENT"
    assert data["intent"] == "LAB_SEARCH"
    assert data["provenance"]["source_layer"] == "F3_LAB_FINDER"
    assert "28" in data["answer"]
