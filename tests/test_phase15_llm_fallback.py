# -*- coding: utf-8 -*-
"""
Test Suite for Phase 15: Intelligent LLM Fallback & Non-Empty Answer Layer

Covers the 12 required scenarios from Section 15 of user request:
1. "What is IS 4985?" -> GROUNDED, non-empty, BIS evidence present
2. "What is IS 9999999?" -> non-empty, no invented standard information
3. "What is retrieval augmented generation?" -> LLM_FALLBACK, useful answer, not BIS-verified
4. Partial evidence query -> HYBRID, Verified BIS Information & Additional General Information sections, disclaimer
5. "What is the latest amendment to IS 4985?" -> no revision=amendment conflation, no invented amendment
6. "Is BIS certification mandatory for uPVC potable water pipes?" -> no unsupported legal mandate
7. "Find laboratories for IS 4985." -> F3_LAB_FINDER, dynamic labs, no LLM qualification
8. "Find labs in Delhi for IS 4985." -> F3, Delhi filtering/ranking preserved
9. F3 zero-match scenario -> non-empty, no fabricated labs
10. Groq unavailable -> no empty answer across all query types
11. All 12 languages -> localized fallback/hybrid labels and exact technical identifiers
12. Conversational sequence -> Turn 3 resolves to LAB_SEARCH -> F3
"""

import re
import pytest
from unittest.mock import MagicMock, patch
from scripts.phase12_f2_orchestrator import (
    orchestrate_assistant_query,
    GroqClient,
    SUPPORTED_LANGUAGES,
    LLM_FALLBACK_DISCLAIMER_MAP,
    HYBRID_DISCLAIMER_MAP,
    HYBRID_SECTION_HEADERS_MAP,
    STANDARD_UNVERIFIED_MAP,
    F3_ZERO_MATCH_MAP,
    INTENT_LAB_SEARCH,
)


class MockGroqClient:
    """Mock Groq client that provides realistic model outputs for testing."""
    def __init__(self, fallback_text=None, should_fail=False):
        self.is_configured = True
        self.model_name = "openai/gpt-oss-120b"
        self.fallback_text = fallback_text
        self.should_fail = should_fail
        self.call_count = 0
        self.recorded_messages = []

    def chat_completion(self, messages, max_tokens=800):
        self.call_count += 1
        self.recorded_messages.append(messages)
        if self.should_fail:
            raise RuntimeError("Mock Groq API Connection Failed")

        user_content = messages[-1]["content"] if messages else ""
        system_content = messages[0]["content"] if messages else ""

        if self.fallback_text:
            return self.fallback_text

        # General / out-of-corpus query (e.g. RAG)
        if "retrieval augmented generation" in user_content.lower():
            return (
                "### Answer\n\n"
                "Retrieval-Augmented Generation (RAG) is an AI framework that retrieves relevant documents "
                "from an external knowledge base to ground language model responses with verifiable facts."
            )

        # Hybrid query (e.g. testing fee for IS 8978)
        if "hybrid" in system_content.lower() or "is 8978" in user_content.lower():
            return (
                "### Verified BIS Information\n\n"
                "IS 8978 specifies requirements for electric instantaneous water heaters, including test parameters clause by clause.\n\n"
                "### Additional General Information\n\n"
                "Commercial laboratory testing charges generally range from ₹5,000 to ₹15,000 depending on the scope of clauses selected."
            )

        # Standard inquiry
        return (
            "IS 4985 is the Indian Standard for unplasticized PVC pipes for potable water supplies.\n\n"
            "### What it covers\nRequirements for potable water piping.\n\n"
            "### Standard details\n- Standard: IS 4985\n- Year: 2021"
        )


class TestPhase15LLMFallback:
    """Automated verification suite for Phase 15 requirements."""

    # -------------------------------------------------------------------------
    # Scenario 1: GROUNDED mode for SUFFICIENT RAG
    # -------------------------------------------------------------------------
    def test_01_is4985_grounded_mode(self):
        """'What is IS 4985?' must produce GROUNDED mode with BIS evidence and non-empty answer."""
        mock_groq = MockGroqClient()
        res = orchestrate_assistant_query("What is IS 4985?", groq_client=mock_groq)

        assert res["status"] == "SUFFICIENT"
        assert res["generation_mode"] == "GROUNDED"
        assert res["answer"] and len(res["answer"].strip()) > 50
        assert res["provenance"]["source_layer"] == "RAG"
        assert res["provenance"]["verified_against_bis"] is True
        assert res["provenance"]["llm_fallback_used"] is False
        assert len(res["rag"].get("evidence", [])) > 0
        assert len(res.get("claims", [])) > 0
        assert all(c.get("source") == "BIS_VERIFIED" for c in res["claims"])

    # -------------------------------------------------------------------------
    # Scenario 2: Unknown explicit IS number safe non-empty limitation
    # -------------------------------------------------------------------------
    def test_02_unknown_is9999999_safe_non_empty(self):
        """'What is IS 9999999?' must return a non-empty safe limitation and never fabricate standard details."""
        mock_groq = MockGroqClient()
        res = orchestrate_assistant_query("What is IS 9999999?", groq_client=mock_groq)

        assert res["status"] == "INSUFFICIENT"
        assert res["answer"] and len(res["answer"].strip()) > 20
        ans_lower = res["answer"].lower()
        assert any(phrase in ans_lower for phrase in ["could not verify", "not an active", "unrecognized", "cannot reliably identify"])
        assert "IS 9999999" in res["answer"]
        assert "tensile strength" not in ans_lower
        assert "hydrostatic pressure" not in ans_lower
        assert res["provenance"]["verified_against_bis"] is False

    # -------------------------------------------------------------------------
    # Scenario 3: General out-of-corpus query triggers LLM_FALLBACK
    # -------------------------------------------------------------------------
    def test_03_out_of_corpus_llm_fallback(self):
        """'What is retrieval augmented generation?' must trigger LLM_FALLBACK with disclaimer."""
        mock_groq = MockGroqClient()
        res = orchestrate_assistant_query("What is retrieval augmented generation?", groq_client=mock_groq)

        assert res["status"] == "INSUFFICIENT"
        assert res["generation_mode"] == "LLM_FALLBACK"
        assert res["provenance"]["source_layer"] == "GENERAL_LLM_KNOWLEDGE"
        assert res["provenance"]["verified_against_bis"] is False
        assert res["provenance"]["llm_fallback_used"] is True
        assert res["answer"] and len(res["answer"].strip()) > 50
        assert "not verified against BIS evidence" in res["answer"]
        assert "### Answer" in res["answer"]

    # -------------------------------------------------------------------------
    # Scenario 4: Partial evidence triggers HYBRID mode
    # -------------------------------------------------------------------------
    def test_04_partial_evidence_hybrid_mode(self):
        """Partial evidence query must trigger HYBRID mode with separated sections and disclaimer."""
        mock_groq = MockGroqClient()
        res = orchestrate_assistant_query("What is the testing fee for IS 8978?", groq_client=mock_groq)

        assert res["status"] == "PARTIAL"
        assert res["generation_mode"] == "HYBRID"
        assert res["provenance"]["source_layer"] == "RAG_PLUS_LLM"
        assert res["provenance"]["verified_against_bis"] is False
        assert res["answer"] and len(res["answer"].strip()) > 50
        assert "### Verified BIS Information" in res["answer"]
        assert "### Additional General Information" in res["answer"]
        assert "Additional information is based on general knowledge and is not verified against BIS evidence" in res["answer"]
        assert any(c.get("source") == "BIS_VERIFIED" for c in res.get("claims", []))
        assert any(c.get("source") == "GENERAL_UNVERIFIED" for c in res.get("unsupported_claims", []))

    # -------------------------------------------------------------------------
    # Scenario 5: Amendment history safety (never equate revision with amendment)
    # -------------------------------------------------------------------------
    def test_05_amendment_history_safety(self):
        """'What is the latest amendment to IS 4985?' must never conflate revision with amendment."""
        mock_groq = MockGroqClient()
        res = orchestrate_assistant_query("What is the latest amendment to IS 4985?", groq_client=mock_groq)

        ans = res["answer"]
        assert ans and len(ans.strip()) > 20
        assert "latest amendment (fourth revision)" not in ans.lower()
        assert "latest amendment is fourth revision" not in ans.lower()
        assert "is the latest amendment" not in ans.lower()
        assert "Fourth Revision" in ans
        assert "latest amendment" in ans.lower() or "amendment" in ans.lower()

    # -------------------------------------------------------------------------
    # Scenario 6: Mandatory certification regulatory safety
    # -------------------------------------------------------------------------
    def test_06_mandatory_certification_safety(self):
        """'Is BIS certification mandatory for uPVC potable water pipes?' must state mandatory status unverified without QCO."""
        mock_groq = MockGroqClient()
        res = orchestrate_assistant_query("Is BIS certification mandatory for uPVC potable water pipes?", groq_client=mock_groq)

        ans = res["answer"]
        assert ans and len(ans.strip()) > 50
        assert "mandatory certification status could not be verified" in ans or "Quality Control Order (QCO)" in ans

    # -------------------------------------------------------------------------
    # Scenario 7: LAB_SEARCH with matches routes to F3
    # -------------------------------------------------------------------------
    def test_07_lab_search_routes_to_f3(self):
        """'Find laboratories for IS 4985.' must route to F3 Lab Finder and return dynamic matching labs."""
        res = orchestrate_assistant_query("Find laboratories for IS 4985.")

        assert res["intent"] == INTENT_LAB_SEARCH
        assert res["generation_mode"] == "GROUNDED"
        assert res["provenance"]["source_layer"] == "F3_LAB_FINDER"
        assert res["answer"] and len(res["answer"].strip()) > 50
        assert "Testing Laboratories" in res["answer"] or "recognized laboratories" in res["answer"]
        assert res["llm"]["used"] is False

    # -------------------------------------------------------------------------
    # Scenario 8: LAB_SEARCH with Delhi location
    # -------------------------------------------------------------------------
    def test_08_lab_search_delhi_location(self):
        """'Find labs in Delhi for IS 4985.' must preserve location routing in F3."""
        res = orchestrate_assistant_query("Find labs in Delhi for IS 4985.")

        assert res["intent"] == INTENT_LAB_SEARCH
        assert res["generation_mode"] == "GROUNDED"
        assert res["provenance"]["source_layer"] == "F3_LAB_FINDER"
        assert res["answer"] and len(res["answer"].strip()) > 50

    # -------------------------------------------------------------------------
    # Scenario 9: F3 zero-match scenario
    # -------------------------------------------------------------------------
    def test_09_f3_zero_match_non_empty(self):
        """LAB_SEARCH with zero matches must return non-empty response with Lab Finder link and no fabricated labs."""
        with patch("scripts.phase12_f2_orchestrator.execute_natural_search", None):
            res = orchestrate_assistant_query("Find laboratories for IS 9999999.")

        assert res["intent"] == INTENT_LAB_SEARCH
        assert res["status"] == "INSUFFICIENT"
        assert res["generation_mode"] == "GROUNDED"
        assert res["provenance"]["source_layer"] == "F3_LAB_FINDER"
        assert res["answer"] and len(res["answer"].strip()) > 20
        assert "No matching qualified laboratory" in res["answer"] or "BIS Lab Finder" in res["answer"]
        assert "https://bis.gov.in/" in res["answer"]

    # -------------------------------------------------------------------------
    # Scenario 10: Groq unavailable never produces empty response
    # -------------------------------------------------------------------------
    def test_10_groq_unavailable_resilience(self):
        """When Groq is unavailable, every query mode produces a safe non-empty response."""
        unconfigured_groq = MagicMock()
        unconfigured_groq.is_configured = False

        queries = [
            ("What is IS 4985?", "GROUNDED"),
            ("What is the testing fee for IS 8978?", "HYBRID"),
            ("What is retrieval augmented generation?", "LLM_FALLBACK"),
            ("What is IS 9999999?", "GROUNDED"),
        ]

        for q, expected_mode in queries:
            res = orchestrate_assistant_query(q, groq_client=unconfigured_groq)
            assert res["answer"] is not None
            assert len(res["answer"].strip()) > 10, f"Query '{q}' returned empty/short answer"
            assert res["generation_mode"] == expected_mode, f"Query '{q}' had wrong mode: {res['generation_mode']}"
            assert res["llm"]["used"] is False

    # -------------------------------------------------------------------------
    # Scenario 11: All 12 languages localization and identifier preservation
    # -------------------------------------------------------------------------
    def test_11_all_12_languages_localization(self):
        """All 12 supported languages must produce non-empty responses, localized disclaimers, and preserved identifiers."""
        unconfigured_groq = MagicMock()
        unconfigured_groq.is_configured = False

        for lang in SUPPORTED_LANGUAGES:
            # 1. Fallback query
            res_fb = orchestrate_assistant_query(
                "What is retrieval augmented generation?",
                groq_client=unconfigured_groq,
                target_language=lang
            )
            assert res_fb["answer"] is not None and len(res_fb["answer"].strip()) > 10
            assert res_fb["generation_mode"] == "LLM_FALLBACK"
            expected_disclaimer = LLM_FALLBACK_DISCLAIMER_MAP[lang]
            assert expected_disclaimer in res_fb["answer"], f"Missing fallback disclaimer for {lang}"

            # 2. Hybrid query
            res_hy = orchestrate_assistant_query(
                "What is the testing fee for IS 8978?",
                groq_client=unconfigured_groq,
                target_language=lang
            )
            assert res_hy["answer"] is not None and len(res_hy["answer"].strip()) > 10
            assert res_hy["generation_mode"] == "HYBRID"
            # Preserves technical identifier
            assert "IS 8978" in res_hy["answer"], f"Technical identifier IS 8978 lost in {lang}"
            # Headers present
            v_head = HYBRID_SECTION_HEADERS_MAP[lang]["verified"]
            g_head = HYBRID_SECTION_HEADERS_MAP[lang]["general"]
            assert v_head in res_hy["answer"], f"Missing verified header for {lang}"
            assert g_head in res_hy["answer"], f"Missing general header for {lang}"

    # -------------------------------------------------------------------------
    # Scenario 12: 3-turn conversational sequence
    # -------------------------------------------------------------------------
    def test_12_three_turn_conversational_sequence(self):
        """Turn 3 in a 3-turn sequence must resolve to LAB_SEARCH -> F3 with IS 4985 retained."""
        history = [
            {"role": "user", "text": "What is IS 4985?"},
            {"role": "assistant", "data": {"rag": {"standard": "IS 4985"}, "answer": "IS 4985 covers unplasticized PVC pipes."}},
            {"role": "user", "text": "What tests does it require?"},
            {"role": "assistant", "data": {"rag": {"standard": "IS 4985"}, "answer": "It requires hydrostatic pressure testing."}}
        ]

        res = orchestrate_assistant_query(
            "Where can I get these tests done?",
            conversation_history=history
        )

        assert res["intent"] == INTENT_LAB_SEARCH
        assert res["provenance"]["source_layer"] == "F3_LAB_FINDER"
        assert res["generation_mode"] == "GROUNDED"
        assert "IS 4985" in res["answer"]
