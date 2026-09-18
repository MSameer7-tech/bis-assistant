"""
Unit tests for Conversation Title Generation API (backend/conversation_api.py).
"""

import pytest
from backend.conversation_api import (
    _deterministic_title_fallback,
    _clean_llm_title,
    generate_conversation_title,
    ConversationTitleRequest
)


def test_deterministic_fallback_standard_priority():
    # 1. Standard + Task
    assert _deterministic_title_fallback("Is certification mandatory for IS 4985?") == "IS 4985 Certification Requirements"
    assert _deterministic_title_fallback("Find labs for IS 4985 in Delhi") == "IS 4985 Labs in Delhi"
    assert _deterministic_title_fallback("what is IS 374") == "IS 374 Standard Overview"
    assert _deterministic_title_fallback("Testing parameters under IS 16046 Part 2") == "IS 16046 Part 2 Testing Requirements"


def test_deterministic_fallback_product_priority():
    # 2. Product + Task
    res_fan = _deterministic_title_fallback("What testing is required for ceiling fans?")
    assert "Ceiling Fans" in res_fan and "Testing" in res_fan

    res_pvc = _deterministic_title_fallback("How do I get BIS license for PVC pipes?")
    assert "PVC Pipes" in res_pvc and "Certification" in res_pvc


def test_clean_llm_title():
    # Quoted strings
    assert _clean_llm_title('"IS 4985 Testing Requirements"') == "IS 4985 Testing Requirements"
    assert _clean_llm_title("'PVC Pipe Certification'") == "PVC Pipe Certification"
    
    # Prefixes
    assert _clean_llm_title("Title: Ceiling Fan Compliance") == "Ceiling Fan Compliance"
    assert _clean_llm_title("Summary: IS 374 Standard Overview") == "IS 374 Standard Overview"

    # Trailing punctuation
    assert _clean_llm_title("IS 4985 Labs in Delhi.") == "IS 4985 Labs in Delhi"
    assert _clean_llm_title("Ceiling Fan Testing Guide!") == "Ceiling Fan Testing Guide"

    # Length bounds (too short or too long)
    assert _clean_llm_title("SingleWord") is None
    assert _clean_llm_title("This is way way way too many words in a title that exceeds all acceptable boundaries") is None
    assert _clean_llm_title("Eight Words Are Clamped If Acceptable Right Now") is not None


@pytest.mark.anyio
async def test_generate_conversation_title_endpoint():
    req = ConversationTitleRequest(first_message="Is BIS certification mandatory for PVC pipes used for potable water?")
    resp = await generate_conversation_title(req)
    assert resp.title
    assert len(resp.title.split()) >= 2
    assert resp.source in ("groq", "fallback")
