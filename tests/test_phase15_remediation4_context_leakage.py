# -*- coding: utf-8 -*-
"""
Test Suite for Phase 15 Remediation 4: Context Leakage Fix

Verifies:
1. TEST 1: Turn 1 'What is IS 99?' -> Turn 2 'I manufacture timber doors so tell me what certifications do I need'
   - Intent = CERTIFICATION
   - IS 99 not inherited
   - IS 99 absent from effective entities
   - IS 99 absent from rewritten query
   - IS 99 absent from answer
   - Timber doors recognized as product
2. TEST 2: Turn 1 'What is IS 4985?' -> Turn 2 'I manufacture timber doors. What certifications do I need?'
   - IS 4985 not inherited
   - Timber doors recognized as product
   - Intent = CERTIFICATION
3. TEST 3: Turn 1 'What is IS 4985?' -> Turn 2 'What tests does it require?'
   - IS 4985 inherited
   - Intent = TESTING
4. TEST 4: Turn 1 'What tests does IS 4985 require?' -> Turn 2 'Where can I get these tests done?'
   - IS 4985 inherited
   - Intent = LAB_SEARCH
   - F3 invoked
   - Dynamically qualified labs returned
5. TEST 5: Turn 1 'What is IS 4985?' -> Turn 2 'What tests does IS 13592 require?'
   - IS 13592 wins
   - IS 4985 does not contaminate retrieval
6. TEST 6: Turn 1 'Find labs for IS 4985.' -> Turn 2 'Show me ones in Delhi.'
   - IS 4985 retained
   - Delhi added
   - Intent = LAB_SEARCH
   - F3 invoked, laboratories satisfy requested standard and Delhi location
7. TEST 7: Turn 1 'What is IS 4985?' -> Turn 2 'How does BIS certification work?'
   - Standalone query
   - IS 4985 not inherited
8. TEST 8: Turn 1 'What is IS 4985?' -> Turn 2 'Does this standard require hydrostatic testing?'
   - IS 4985 inherited
   - Intent = TESTING
9. TEST 9: 4-turn context reset:
   Turn 1 -> Turn 2 -> Turn 3 -> Turn 4 ('I manufacture timber doors. What certifications do I need?')
   - Turn 4 does NOT contain IS 4985
10. TEST 10: Production API Parity:
    POST /api/assistant/query and POST /api/phase12e/query with real history
"""

import re
import pytest
from fastapi.testclient import TestClient

from scripts.phase12_f2_orchestrator import (
    orchestrate_assistant_query,
    analyze_query_context,
    resolve_conversational_context,
    has_referential_language,
    extract_product_from_query,
    INTENT_DEFINITION,
    INTENT_TESTING,
    INTENT_LAB_SEARCH,
    INTENT_CERTIFICATION,
    INTENT_PROCESS,
)
from backend.app import app

client = TestClient(app)


# =========================================================================
# TEST 1: No IS 99 Leakage to Timber Doors Certification
# =========================================================================
def test_01_no_leakage_is99_to_timber_doors():
    """TEST 1: 'What is IS 99?' -> 'I manufacture timber doors so tell me what certifications do I need'"""
    history = [
        {"role": "user", "text": "What is IS 99?"},
        {
            "role": "assistant",
            "text": "I could not verify information for IS 99 from the available BIS evidence.",
            "data": {"standard": "IS 99", "intent": "DEFINITION"}
        }
    ]
    query = "I manufacture timber doors so tell me what certifications do I need"

    # Verify query context analysis in isolation
    ctx = analyze_query_context(query, conversation_history=history)
    assert ctx["intent"] == INTENT_CERTIFICATION
    assert "IS 99" not in ctx.get("is_numbers", [])
    assert "IS 99" not in ctx.get("entities", {}).get("standards", [])
    assert "IS 99" not in ctx.get("search_intent", "")
    assert ctx.get("product") == "timber doors"
    assert ctx.get("was_context_resolved") is False

    # Verify full orchestrator response
    res = orchestrate_assistant_query(query, conversation_history=history)
    assert res["intent"] == INTENT_CERTIFICATION
    ans = res["answer"]
    assert "IS 99" not in ans
    assert "is 99" not in ans.lower()
    # Safe non-absolute wording present
    assert "not establish the applicable certification requirement for timber doors" in ans or "timber doors" in ans.lower()


# =========================================================================
# TEST 2: Product Change Breaks Standard Context (IS 4985 -> Timber Doors)
# =========================================================================
def test_02_product_change_breaks_context_is4985():
    """TEST 2: 'What is IS 4985?' -> 'I manufacture timber doors. What certifications do I need?'"""
    history = [
        {"role": "user", "text": "What is IS 4985?"},
        {
            "role": "assistant",
            "text": "IS 4985 covers UPVC pipes for potable water supplies.",
            "data": {"standard": "IS 4985", "product": "upvc pipes", "intent": "DEFINITION"}
        }
    ]
    query = "I manufacture timber doors. What certifications do I need?"

    ctx = analyze_query_context(query, conversation_history=history)
    assert ctx["intent"] == INTENT_CERTIFICATION
    assert "IS 4985" not in ctx.get("is_numbers", [])
    assert ctx.get("product") == "timber doors"
    assert ctx.get("was_context_resolved") is False

    res = orchestrate_assistant_query(query, conversation_history=history)
    assert res["intent"] == INTENT_CERTIFICATION
    assert "IS 4985" not in res["answer"]


# =========================================================================
# TEST 3: Valid Follow-up 'What tests does it require?'
# =========================================================================
def test_03_valid_followup_it_requires():
    """TEST 3: 'What is IS 4985?' -> 'What tests does it require?' inherits IS 4985"""
    history = [
        {"role": "user", "text": "What is IS 4985?"},
        {
            "role": "assistant",
            "text": "IS 4985 covers UPVC pipes for potable water supplies.",
            "data": {"standard": "IS 4985", "intent": "DEFINITION"}
        }
    ]
    query = "What tests does it require?"

    ctx = analyze_query_context(query, conversation_history=history)
    assert ctx["was_context_resolved"] is True
    assert "IS 4985" in ctx["is_numbers"]
    assert ctx["intent"] == INTENT_TESTING

    res = orchestrate_assistant_query(query, conversation_history=history)
    assert res["intent"] == INTENT_TESTING
    assert res["status"] == "SUFFICIENT"
    assert "IS 4985" in res["answer"]


# =========================================================================
# TEST 4: Valid Follow-up 'Where can I get these tests done?' -> F3 Lab Search
# =========================================================================
def test_04_valid_followup_where_tests_done_f3():
    """TEST 4: 'What tests does IS 4985 require?' -> 'Where can I get these tests done?' invokes F3"""
    history = [
        {"role": "user", "text": "What tests does IS 4985 require?"},
        {
            "role": "assistant",
            "text": "IS 4985 requires hydrostatic pressure tests, opacity, and impact resistance.",
            "data": {"standard": "IS 4985", "intent": "TESTING"}
        }
    ]
    query = "Where can I get these tests done?"

    ctx = analyze_query_context(query, conversation_history=history)
    assert ctx["was_context_resolved"] is True
    assert "IS 4985" in ctx["is_numbers"]
    assert ctx["intent"] == INTENT_LAB_SEARCH

    res = orchestrate_assistant_query(query, conversation_history=history)
    assert res["intent"] == INTENT_LAB_SEARCH
    assert res["provenance"]["source_layer"] == "F3_LAB_FINDER"
    # F3 dynamic qualification returns matching labs
    assert "BIS-Recognized Testing Laboratories for IS 4985" in res["answer"]
    assert "laboratories" in res["answer"].lower()


# =========================================================================
# TEST 5: Explicit Current Standard Wins (IS 4985 vs IS 13592)
# =========================================================================
def test_05_explicit_standard_wins_is13592():
    """TEST 5: 'What is IS 4985?' -> 'What tests does IS 13592 require?' -> IS 13592 wins"""
    history = [
        {"role": "user", "text": "What is IS 4985?"},
        {
            "role": "assistant",
            "text": "IS 4985 covers UPVC pipes.",
            "data": {"standard": "IS 4985", "intent": "DEFINITION"}
        }
    ]
    query = "What tests does IS 13592 require?"

    ctx = analyze_query_context(query, conversation_history=history)
    assert ctx["is_numbers"] == ["IS 13592"]
    assert "IS 4985" not in ctx["is_numbers"]
    assert ctx["intent"] == INTENT_TESTING

    res = orchestrate_assistant_query(query, conversation_history=history)
    assert res["intent"] == INTENT_TESTING
    assert "IS 13592" in res["answer"]
    assert "IS 4985" not in res["answer"]


# =========================================================================
# TEST 6: Elliptical Location Follow-up 'Show me ones in Delhi.' -> F3
# =========================================================================
def test_06_valid_followup_location_delhi_f3():
    """TEST 6: 'Find labs for IS 4985.' -> 'Show me ones in Delhi.' retains IS 4985, adds Delhi, invokes F3"""
    history = [
        {"role": "user", "text": "Find labs for IS 4985."},
        {
            "role": "assistant",
            "text": "Found 28 recognized laboratories for IS 4985.",
            "data": {"standard": "IS 4985", "intent": "LAB_SEARCH"}
        }
    ]
    query = "Show me ones in Delhi."

    ctx = analyze_query_context(query, conversation_history=history)
    assert ctx["was_context_resolved"] is True
    assert "IS 4985" in ctx["is_numbers"]
    assert ctx["entities"].get("location") == "Delhi"
    assert ctx["intent"] == INTENT_LAB_SEARCH

    res = orchestrate_assistant_query(query, conversation_history=history)
    assert res["intent"] == INTENT_LAB_SEARCH
    assert res["provenance"]["source_layer"] == "F3_LAB_FINDER"
    # Verified Delhi laboratories returned
    assert "Delhi" in res["answer"]


# =========================================================================
# TEST 7: Standalone Process Query 'How does BIS certification work?'
# =========================================================================
def test_07_standalone_certification_process_no_leakage():
    """TEST 7: 'What is IS 4985?' -> 'How does BIS certification work?' -> Standalone query, no IS 4985"""
    history = [
        {"role": "user", "text": "What is IS 4985?"},
        {
            "role": "assistant",
            "text": "IS 4985 covers UPVC pipes.",
            "data": {"standard": "IS 4985", "intent": "DEFINITION"}
        }
    ]
    query = "How does BIS certification work?"

    ctx = analyze_query_context(query, conversation_history=history)
    assert ctx["was_context_resolved"] is False
    assert "IS 4985" not in ctx.get("is_numbers", [])
    assert ctx["intent"] == INTENT_PROCESS


# =========================================================================
# TEST 8: Valid Follow-up 'Does this standard require hydrostatic testing?'
# =========================================================================
def test_08_valid_followup_this_standard_hydrostatic():
    """TEST 8: 'What is IS 4985?' -> 'Does this standard require hydrostatic testing?' inherits IS 4985"""
    history = [
        {"role": "user", "text": "What is IS 4985?"},
        {
            "role": "assistant",
            "text": "IS 4985 covers UPVC pipes.",
            "data": {"standard": "IS 4985", "intent": "DEFINITION"}
        }
    ]
    query = "Does this standard require hydrostatic testing?"

    ctx = analyze_query_context(query, conversation_history=history)
    assert ctx["was_context_resolved"] is True
    assert "IS 4985" in ctx["is_numbers"]
    assert ctx["intent"] == INTENT_TESTING

    res = orchestrate_assistant_query(query, conversation_history=history)
    assert res["intent"] == INTENT_TESTING
    assert "IS 4985" in res["answer"]


# =========================================================================
# TEST 9: Four-Turn Context Reset
# =========================================================================
def test_09_four_turn_context_reset():
    """TEST 9: Multi-turn sequence proves context is reset on a new product turn."""
    history = [
        {"role": "user", "text": "What is IS 4985?"},
        {
            "role": "assistant",
            "text": "IS 4985 specifies requirements for UPVC pipes.",
            "data": {"standard": "IS 4985", "intent": "DEFINITION"}
        },
        {"role": "user", "text": "What tests does it require?"},
        {
            "role": "assistant",
            "text": "It requires hydrostatic pressure tests and opacity tests.",
            "data": {"standard": "IS 4985", "intent": "TESTING"}
        },
        {"role": "user", "text": "Where can I get these tests done?"},
        {
            "role": "assistant",
            "text": "Found recognized laboratories for IS 4985.",
            "data": {"standard": "IS 4985", "intent": "LAB_SEARCH"}
        }
    ]
    query = "I manufacture timber doors. What certifications do I need?"

    ctx = analyze_query_context(query, conversation_history=history)
    assert ctx["was_context_resolved"] is False
    assert "IS 4985" not in ctx.get("is_numbers", [])
    assert ctx.get("product") == "timber doors"
    assert ctx["intent"] == INTENT_CERTIFICATION

    res = orchestrate_assistant_query(query, conversation_history=history)
    assert "IS 4985" not in res["answer"]
    assert res["intent"] == INTENT_CERTIFICATION


# =========================================================================
# TEST 10: Production API Parity (/api/assistant/query and /api/phase12e/query)
# =========================================================================
def test_10_production_fastapi_parity():
    """TEST 10: Verifies both FastAPI endpoints handle history and prevent context leakage."""
    history = [
        {"role": "user", "text": "What is IS 99?"},
        {"role": "assistant", "text": "I could not verify information for IS 99 from available BIS evidence."}
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
    assert "IS 99" not in data1["answer"]
    assert "is 99" not in data1["answer"].lower()

    # Test /api/phase12e/query
    res2 = client.post("/api/phase12e/query", json=payload)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["intent"] == INTENT_CERTIFICATION
    assert "IS 99" not in data2["answer"]
    assert "is 99" not in data2["answer"].lower()
