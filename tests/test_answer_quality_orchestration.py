"""
Phase 14: Answer Quality & Intent Orchestration Tests

Tests for intent classification, conversational context resolution,
LAB_SEARCH dispatch, STANDARD_COMPARISON, amendment safety,
certification safety, and completeness caveats.
"""
import sys
import os
import re
import pytest
from unittest.mock import patch, MagicMock
from typing import Dict, Any, List

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts.phase12_f2_orchestrator import (
    classify_orchestrator_intent,
    resolve_conversational_context,
    check_statutory_mandatory_certification,
    check_amendment_evidence,
    analyze_query_context,
    INTENT_DEFINITION, INTENT_SCOPE, INTENT_TECHNICAL_REQUIREMENTS,
    INTENT_TESTING, INTENT_CERTIFICATION, INTENT_QCO,
    INTENT_AMENDMENT_HISTORY, INTENT_STANDARD_COMPARISON,
    INTENT_LAB_SEARCH, INTENT_PROCESS, INTENT_GENERAL, INTENT_AMBIGUOUS,
    AMENDMENT_CONSERVATIVE_MAP, MANDATORY_CONSERVATIVE_MAP, COMPLETENESS_CAVEAT_MAP,
    VALID_INTENTS
)


# ============================================================================
# 1. Intent Classification Tests
# ============================================================================
class TestIntentClassification:
    """Tests for classify_orchestrator_intent()"""

    def test_definition_intent(self):
        intent = classify_orchestrator_intent("What is IS 4985?", clean_stds=["IS 4985"])
        assert intent == INTENT_DEFINITION

    def test_scope_intent(self):
        intent = classify_orchestrator_intent("What is the scope of IS 4985?", clean_stds=["IS 4985"])
        assert intent == INTENT_SCOPE

    def test_testing_intent(self):
        intent = classify_orchestrator_intent("What tests are specified in IS 4985?", clean_stds=["IS 4985"])
        assert intent == INTENT_TESTING

    def test_certification_intent(self):
        intent = classify_orchestrator_intent("Is BIS certification mandatory for UPVC pipes?", clean_stds=[], product="upvc pipes")
        assert intent == INTENT_CERTIFICATION

    def test_qco_intent(self):
        intent = classify_orchestrator_intent("Is there a QCO for UPVC pipes?", clean_stds=[], product="upvc pipes")
        assert intent == INTENT_QCO

    def test_amendment_intent(self):
        intent = classify_orchestrator_intent("What is the latest amendment to IS 4985?", clean_stds=["IS 4985"])
        assert intent == INTENT_AMENDMENT_HISTORY

    def test_comparison_intent_two_standards(self):
        intent = classify_orchestrator_intent("Compare IS 4985 and IS 7328", clean_stds=["IS 4985", "IS 7328"])
        assert intent == INTENT_STANDARD_COMPARISON

    def test_comparison_intent_difference(self):
        intent = classify_orchestrator_intent("What is the difference between IS 4985 and IS 7328?", clean_stds=["IS 4985", "IS 7328"])
        assert intent == INTENT_STANDARD_COMPARISON

    def test_lab_search_intent(self):
        intent = classify_orchestrator_intent("Which labs can test IS 4985?", clean_stds=["IS 4985"])
        assert intent == INTENT_LAB_SEARCH

    def test_process_intent(self):
        intent = classify_orchestrator_intent("How do I get BIS certification?", clean_stds=[])
        assert intent == INTENT_PROCESS

    def test_general_intent(self):
        intent = classify_orchestrator_intent("Hello", clean_stds=[], is_conv=True)
        assert intent == INTENT_GENERAL

    def test_all_intents_valid(self):
        """All 12 intents are valid."""
        assert len(VALID_INTENTS) == 12

    def test_technical_requirements_intent(self):
        intent = classify_orchestrator_intent("What are the specifications for IS 4985?", clean_stds=["IS 4985"])
        assert intent == INTENT_TECHNICAL_REQUIREMENTS


# ============================================================================
# 2. Conversational Context Resolution Tests
# ============================================================================
class TestConversationalContext:
    """Tests for resolve_conversational_context()"""

    def test_no_history(self):
        q, std, prod, resolved = resolve_conversational_context("What is it?")
        assert not resolved

    def test_empty_history(self):
        q, std, prod, resolved = resolve_conversational_context("What is it?", [])
        assert not resolved

    def test_resolve_it_to_standard(self):
        history = [
            {"role": "user", "text": "What is IS 4985?"},
            {"role": "assistant", "text": "IS 4985 covers UPVC pipes."}
        ]
        q, std, prod, resolved = resolve_conversational_context("What is the scope of it?", history)
        assert resolved
        assert "IS 4985" in q
        assert std == "IS 4985"

    def test_resolve_these_tests(self):
        history = [
            {"role": "user", "text": "What tests are in IS 4985?"},
            {"role": "assistant", "text": "IS 4985 specifies hydrostatic, opacity tests."}
        ]
        q, std, prod, resolved = resolve_conversational_context("Where can I get these tests done?", history)
        assert resolved
        assert "IS 4985" in q

    def test_explicit_standard_not_resolved(self):
        history = [
            {"role": "user", "text": "What is IS 4985?"},
        ]
        q, std, prod, resolved = resolve_conversational_context("What is IS 7328?", history)
        assert not resolved  # Should NOT resolve since IS 7328 is explicit

    def test_resolve_this_standard(self):
        history = [
            {"role": "user", "text": "Tell me about IS 4985"},
        ]
        q, std, prod, resolved = resolve_conversational_context("What is the scope of this standard?", history)
        assert resolved
        assert "IS 4985" in q


# ============================================================================
# 3. Statutory/Mandatory Certification Check Tests
# ============================================================================
class TestStatutoryCertification:
    """Tests for check_statutory_mandatory_certification()"""

    def test_no_qco_in_evidence(self):
        evidence = [
            {"heading": "Hydrostatic Pressure Test", "text": "Normative Force: MANDATORY. Test at 42°C.", "standard_title": "IS 4985:2000"}
        ]
        has_qco, qco_name = check_statutory_mandatory_certification(evidence, [])
        assert not has_qco  # "Normative Force: MANDATORY" is clause-level, NOT QCO

    def test_qco_in_evidence(self):
        evidence = [
            {"heading": "Quality Control Order for UPVC Pipes", "text": "As per the Quality Control Order 2024, BIS certification is mandatory.", "standard_title": "IS 4985:2000"}
        ]
        has_qco, qco_name = check_statutory_mandatory_certification(evidence, [])
        assert has_qco
        assert "Quality Control Order" in qco_name

    def test_cro_in_evidence(self):
        evidence = [
            {"heading": "Registration", "text": "This product falls under Compulsory Registration Order.", "standard_title": "IS 4985:2000"}
        ]
        has_qco, qco_name = check_statutory_mandatory_certification(evidence, [])
        assert has_qco

    def test_empty_evidence(self):
        has_qco, qco_name = check_statutory_mandatory_certification([], [])
        assert not has_qco


# ============================================================================
# 4. Amendment Evidence Check Tests
# ============================================================================
class TestAmendmentEvidence:
    """Tests for check_amendment_evidence()"""

    def test_revision_found(self):
        evidence = [
            {"heading": "IS 4985:2000", "text": "Fourth Revision of IS 4985", "standard_title": "IS 4985:2000 (Fourth Revision)"}
        ]
        rev, amend = check_amendment_evidence(evidence)
        assert rev is not None
        assert "Fourth Revision" in rev

    def test_amendment_found(self):
        evidence = [
            {"heading": "IS 4985:2000", "text": "Amendment No. 1 dated March 2003", "standard_title": "IS 4985:2000"}
        ]
        rev, amend = check_amendment_evidence(evidence)
        assert amend is not None
        assert "Amendment" in amend

    def test_no_amendment(self):
        evidence = [
            {"heading": "Scope", "text": "This standard covers UPVC pipes.", "standard_title": "IS 4985:2000"}
        ]
        rev, amend = check_amendment_evidence(evidence)
        assert amend is None

    def test_empty_evidence(self):
        rev, amend = check_amendment_evidence([])
        assert rev is None
        assert amend is None


# ============================================================================
# 5. Safety Template Coverage Tests
# ============================================================================
SUPPORTED_LANGS = ["en", "hi", "bn", "te", "mr", "ta", "gu", "kn", "ml", "pa", "as", "or"]

class TestSafetyTemplates:
    """Verify all 12 language templates exist and are non-empty."""

    def test_amendment_map_12_languages(self):
        for lang in SUPPORTED_LANGS:
            assert lang in AMENDMENT_CONSERVATIVE_MAP, f"Missing amendment template for {lang}"
            assert len(AMENDMENT_CONSERVATIVE_MAP[lang]) > 10, f"Amendment template too short for {lang}"

    def test_mandatory_map_12_languages(self):
        for lang in SUPPORTED_LANGS:
            assert lang in MANDATORY_CONSERVATIVE_MAP, f"Missing mandatory template for {lang}"
            assert len(MANDATORY_CONSERVATIVE_MAP[lang]) > 10, f"Mandatory template too short for {lang}"

    def test_completeness_map_12_languages(self):
        for lang in SUPPORTED_LANGS:
            assert lang in COMPLETENESS_CAVEAT_MAP, f"Missing completeness template for {lang}"
            assert len(COMPLETENESS_CAVEAT_MAP[lang]) > 10, f"Completeness template too short for {lang}"

    def test_amendment_template_placeholders(self):
        for lang in SUPPORTED_LANGS:
            tmpl = AMENDMENT_CONSERVATIVE_MAP[lang]
            assert "{std}" in tmpl
            assert "{rev}" in tmpl

    def test_mandatory_template_placeholders(self):
        for lang in SUPPORTED_LANGS:
            tmpl = MANDATORY_CONSERVATIVE_MAP[lang]
            assert "{std}" in tmpl
            assert "{prod}" in tmpl

    def test_completeness_template_placeholders(self):
        for lang in SUPPORTED_LANGS:
            tmpl = COMPLETENESS_CAVEAT_MAP[lang]
            assert "{tests}" in tmpl
            assert "{std}" in tmpl

    def test_technical_identifiers_preserved(self):
        """BIS, QCO, IS should remain as-is in translated templates."""
        for lang in SUPPORTED_LANGS:
            tmpl = MANDATORY_CONSERVATIVE_MAP[lang]
            assert "QCO" in tmpl or "qco" in tmpl.lower(), f"QCO missing in {lang} mandatory template"


# ============================================================================
# 6. Analyze Query Context Integration Tests
# ============================================================================
class TestAnalyzeQueryContextIntegration:
    """Tests for the extended analyze_query_context()"""

    def test_intent_field_present(self):
        ctx = analyze_query_context("What is IS 4985?")
        assert "intent" in ctx
        assert ctx["intent"] in VALID_INTENTS

    def test_entities_field_present(self):
        ctx = analyze_query_context("What is IS 4985?")
        assert "entities" in ctx
        assert "standards" in ctx["entities"]

    def test_is_comprehensive_flag(self):
        ctx = analyze_query_context("List all the tests in IS 4985")
        assert ctx.get("is_comprehensive") is True

    def test_not_comprehensive(self):
        ctx = analyze_query_context("What is IS 4985?")
        assert ctx.get("is_comprehensive") is False

    def test_resolved_query_without_history(self):
        ctx = analyze_query_context("What is it?")
        assert ctx.get("was_context_resolved") is False

    def test_resolved_query_with_history(self):
        history = [
            {"role": "user", "text": "What is IS 4985?"},
            {"role": "assistant", "text": "IS 4985 specifies UPVC pipes."}
        ]
        ctx = analyze_query_context("What is the scope of it?", conversation_history=history)
        assert ctx.get("was_context_resolved") is True
        assert "IS 4985" in ctx.get("resolved_query", "")

    def test_lab_entity_extraction(self):
        ctx = analyze_query_context("Which laboratory can test IS 4985?")
        assert ctx["entities"]["laboratory"] is not None

    def test_location_entity_extraction(self):
        ctx = analyze_query_context("Find labs in Delhi for IS 4985")
        assert ctx["entities"]["location"] == "Delhi"

    def test_qco_entity_extraction(self):
        ctx = analyze_query_context("Is there a QCO for UPVC pipes?")
        assert ctx["entities"]["qco"] is not None


# ============================================================================
# 7. Orchestrator Integration Tests (with mocks)
# ============================================================================
class TestOrchestratorIntegration:
    """Tests for orchestrate_assistant_query() with mocked RAG/Groq"""

    @patch('scripts.phase12_f2_orchestrator.query_production_rag')
    def test_conversation_history_passed(self, mock_rag):
        """Verify conversation_history parameter is accepted."""
        mock_rag.return_value = {
            "status": "SUFFICIENT",
            "answer": "IS 4985 covers UPVC pipes.",
            "evidence": [{"text": "IS 4985 covers UPVC pipes", "heading": "Scope", "standard_title": "IS 4985:2000"}],
            "claims": []
        }
        from scripts.phase12_f2_orchestrator import orchestrate_assistant_query
        result = orchestrate_assistant_query(
            "What is the scope?",
            conversation_history=[
                {"role": "user", "text": "What is IS 4985?"},
                {"role": "assistant", "text": "IS 4985 covers UPVC pipes."}
            ]
        )
        assert result["status"] in ("SUFFICIENT", "PARTIAL", "INSUFFICIENT")

    @patch('scripts.phase12_f2_orchestrator.query_production_rag')
    def test_intent_in_response(self, mock_rag):
        """Verify the intent field is present in the response."""
        mock_rag.return_value = {
            "status": "SUFFICIENT",
            "answer": "IS 4985 covers UPVC pipes.",
            "evidence": [{"text": "IS 4985 covers UPVC pipes", "heading": "Scope", "standard_title": "IS 4985:2000"}],
            "claims": []
        }
        from scripts.phase12_f2_orchestrator import orchestrate_assistant_query
        result = orchestrate_assistant_query("What is IS 4985?")
        assert "intent" in result
        assert result["intent"] in VALID_INTENTS

    @patch('scripts.phase12_f2_orchestrator.query_production_rag')
    def test_amendment_safety_caveat(self, mock_rag):
        """When asking about amendments without explicit amendment evidence, caveat should appear."""
        mock_rag.return_value = {
            "status": "SUFFICIENT",
            "answer": "IS 4985 is in its Fourth Revision.",
            "evidence": [{"text": "IS 4985:2000 (Fourth Revision)", "heading": "Title", "standard_title": "IS 4985:2000 (Fourth Revision)"}],
            "claims": []
        }
        from scripts.phase12_f2_orchestrator import orchestrate_assistant_query
        result = orchestrate_assistant_query("What is the latest amendment to IS 4985?")
        # Should contain amendment caveat since no explicit "Amendment No." in evidence
        assert "amendment" in result["answer"].lower() or "संशोधन" in result["answer"]

    @patch('scripts.phase12_f2_orchestrator.query_production_rag')
    def test_certification_safety_caveat(self, mock_rag):
        """When asking about mandatory certification without QCO evidence, conservative caveat should appear."""
        mock_rag.return_value = {
            "status": "SUFFICIENT",
            "answer": "UPVC pipes require certification.",
            "evidence": [{"text": "Normative Force: MANDATORY. Hydrostatic test required.", "heading": "Testing", "standard_title": "IS 4985:2000"}],
            "claims": []
        }
        from scripts.phase12_f2_orchestrator import orchestrate_assistant_query
        result = orchestrate_assistant_query("Is BIS certification mandatory for UPVC pipes?")
        # Should contain certification caveat since no QCO in evidence
        answer_lower = result["answer"].lower()
        assert ("quality control order" in answer_lower or "qco" in answer_lower or
                "mandatory certification status could not be verified" in answer_lower or
                "could not be verified" in answer_lower)

    @patch('scripts.phase12_f2_orchestrator.query_production_rag')
    def test_completeness_caveat(self, mock_rag):
        """When asking for 'all tests', completeness caveat should appear."""
        mock_rag.return_value = {
            "status": "SUFFICIENT",
            "answer": "Key tests: Hydrostatic, Opacity, Vicat.",
            "evidence": [
                {"text": "Hydrostatic test at 42°C", "heading": "Hydrostatic Test", "standard_title": "IS 4985:2000"},
                {"text": "Opacity test", "heading": "Opacity Test", "standard_title": "IS 4985:2000"}
            ],
            "claims": []
        }
        from scripts.phase12_f2_orchestrator import orchestrate_assistant_query
        result = orchestrate_assistant_query("What are all the tests in IS 4985?")
        answer_lower = result["answer"].lower()
        assert ("complete" in answer_lower or "full" in answer_lower or
                "excerpt" in answer_lower or "exhaustive" in answer_lower or
                "refer to" in answer_lower)


# ============================================================================
# 8. Backward Compatibility Tests
# ============================================================================
class TestBackwardCompatibility:
    """Verify new features don't break existing behavior."""

    @patch('scripts.phase12_f2_orchestrator.query_production_rag')
    def test_empty_query(self, mock_rag):
        from scripts.phase12_f2_orchestrator import orchestrate_assistant_query
        result = orchestrate_assistant_query("")
        assert result["status"] == "INSUFFICIENT"
        assert result["answer"] == "Please provide a query to research."

    @patch('scripts.phase12_f2_orchestrator.query_production_rag')
    def test_no_conversation_history(self, mock_rag):
        """Calling without conversation_history should work (backward compat)."""
        mock_rag.return_value = {
            "status": "SUFFICIENT",
            "answer": "Test answer",
            "evidence": [],
            "claims": []
        }
        from scripts.phase12_f2_orchestrator import orchestrate_assistant_query
        result = orchestrate_assistant_query("What is IS 4985?")
        assert result["status"] in ("SUFFICIENT", "PARTIAL", "INSUFFICIENT")

    def test_analyze_query_context_backward_compat(self):
        """analyze_query_context still returns all original keys."""
        ctx = analyze_query_context("What is IS 4985?")
        required_keys = ["product", "user_role", "requested_scheme", "is_numbers",
                         "candidate_domain_mismatch", "search_intent", "language",
                         "response_language"]
        for key in required_keys:
            assert key in ctx, f"Missing key: {key}"

    def test_analyze_query_context_new_keys(self):
        """analyze_query_context returns new Phase 14 keys."""
        ctx = analyze_query_context("What is IS 4985?")
        new_keys = ["intent", "entities", "is_comprehensive", "resolved_query", "was_context_resolved"]
        for key in new_keys:
            assert key in ctx, f"Missing new key: {key}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
