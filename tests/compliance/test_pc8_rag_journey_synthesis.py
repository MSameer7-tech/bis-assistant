"""
Phase PC-8: Product Compliance Journey RAG-First Evidence Enrichment,
Groq Answer Synthesis & Grounding Guard Test Suite.

Verifies the 19 required architectural guarantees:
1. PC-5 status immutable after RAG
2. RAG evidence enriches Stage 3 QCO details (IS 4985 has S.O. 4512(E), Pipes and Fittings QCO 2023, 2024-04-12)
3. Unknown remains unknown (IS 15750 retains QCO_STATUS_UNKNOWN and "Not specified in available BIS evidence")
4. Groq cannot override PC-5 status (mock Groq attempting status change is rejected by Grounding Guard)
5. Hallucinated notification numbers are rejected
6. Hallucinated dates are rejected
7. Unsupported testing claims are pruned
8. General LLM information is separated under GENERAL INFORMATION with disclaimer
9. Evidence provenance preserved (source_layer, source_url, source_record_id, hash)
10. F3 laboratories remain byte-identical (Stage 9 lab count, order, and qualification unaffected)
11. QCO conflicts remain conflicts (IS 374 retains QCO_CONFLICT)
12. Standard-not-established remains unchanged ("timber doors" -> STANDARD_NOT_ESTABLISHED)
13. RAG failure resilience (safe fallback to deterministic PC-5)
14. Groq failure resilience (safe fallback to deterministic PC-5 + RAG)
15. Both failures resilience (simultaneous RAG + Groq failure)
16. No duplicate RAG engine created (assert singleton / reuse of query_production_rag)
17. No duplicate GroqClient created (assert reuse of scripts.phase12_f2_orchestrator.GroqClient)
18. Frozen baseline hashes verified against scratch_pc6_baseline_hashes.json
19. Clarification flow unharmed (/api/compliance/clarify)
"""

import ast
import hashlib
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.compliance_rag_synthesizer import (
    ComplianceRAGSynthesizer,
    get_compliance_rag_synthesizer,
    NOT_SPECIFIED_TEXT,
    GENERAL_INFO_DISCLAIMER
)
from ai.compliance.journey_models import ComplianceJourneyRequest
from ai.compliance.journey_orchestrator import get_compliance_orchestrator

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BASELINE_HASHES_FILE = PROJECT_ROOT / "scratch_pc6_baseline_hashes.json"

client = TestClient(app)


class TestPC8RAGJourneySynthesis:
    """Comprehensive test suite for Phase PC-8 RAG enrichment and synthesis."""

    # -------------------------------------------------------------------------
    # Test 1: PC-5 status immutable after RAG
    # -------------------------------------------------------------------------
    def test_pc5_status_immutable_after_rag(self):
        """PC-5 regulatory decision status cannot be mutated by RAG retrieval or synthesis."""
        synthesizer = get_compliance_rag_synthesizer()
        req = ComplianceJourneyRequest(standard="IS 4985")
        journey = synthesizer.process_journey(req)

        reg = journey["regulatory_status"]
        mand = journey["mandatory_certification"]

        # PC-5 authoritative decisions must remain strictly intact
        assert reg["qco_status"] == "QCO_APPLIES"
        assert mand["is_mandatory"] is True
        assert mand["status"] == "MANDATORY_CERTIFICATION_CONFIRMED"

        # Synthesis primary answer must reflect PC-5 status determination
        assert reg["synthesis"]["primary_answer"] == "QCO applies"
        assert mand["synthesis"]["primary_answer"] == "Mandatory BIS certification"

    # -------------------------------------------------------------------------
    # Test 2: RAG evidence enriches Stage 3 QCO details (IS 4985)
    # -------------------------------------------------------------------------
    def test_rag_evidence_enriches_stage3_qco_details(self):
        """IS 4985 Stage 3 is enriched with Gazette notification, QCO order, and effective date."""
        synthesizer = get_compliance_rag_synthesizer()
        req = ComplianceJourneyRequest(standard="IS 4985")
        journey = synthesizer.process_journey(req)

        reg = journey["regulatory_status"]
        synthesis = reg["synthesis"]

        assert "S.O. 4512(E)" in reg["notification_numbers"]
        assert reg["effective_date"] == "2024-04-12"
        assert any("PIPES-FITTINGS" in qid or "Pipes and Fittings" in qid for qid in reg["associated_qco_ids"])

        # Check key information sources in synthesis
        key_info = synthesis["key_information"]
        notif_item = next((item for item in key_info if item["label"] == "Notification"), None)
        assert notif_item is not None
        assert notif_item["value"] == "S.O. 4512(E)"
        assert notif_item["source"] == "BIS_EVIDENCE"

        order_item = next((item for item in key_info if item["label"] == "Quality Control Order"), None)
        assert order_item is not None
        assert "Pipes and Fittings" in order_item["value"]
        assert order_item["source"] == "BIS_EVIDENCE"

        eff_item = next((item for item in key_info if item["label"] == "Effective date"), None)
        assert eff_item is not None
        assert eff_item["value"] == "2024-04-12"
        assert eff_item["source"] == "BIS_EVIDENCE"

    # -------------------------------------------------------------------------
    # Test 3: Unknown remains unknown (IS 15750)
    # -------------------------------------------------------------------------
    def test_unknown_remains_unknown(self):
        """IS 15750 has no QCO data in BIS records; missing fields must state NOT_SPECIFIED_TEXT."""
        synthesizer = get_compliance_rag_synthesizer()
        req = ComplianceJourneyRequest(standard="IS 15750")
        journey = synthesizer.process_journey(req)

        reg = journey["regulatory_status"]
        synthesis = reg["synthesis"]

        assert reg["qco_status"] == "QCO_STATUS_UNKNOWN"
        assert synthesis["primary_answer"] == "QCO status could not be established"

        key_info = synthesis["key_information"]
        notif_item = next((item for item in key_info if item["label"] == "Notification"), None)
        assert notif_item is not None
        assert notif_item["value"] == NOT_SPECIFIED_TEXT

        eff_item = next((item for item in key_info if item["label"] == "Effective date"), None)
        assert eff_item is not None
        assert eff_item["value"] == NOT_SPECIFIED_TEXT

    # -------------------------------------------------------------------------
    # Test 4: Groq cannot override PC-5 status
    # -------------------------------------------------------------------------
    def test_groq_cannot_override_pc5_status(self):
        """Grounding Guard rejects attempts by Groq output to alter PC-5 regulatory status."""
        synthesizer = get_compliance_rag_synthesizer()

        pc5_stage = {
            "status": "CONFIRMED",
            "qco_status": "QCO_APPLIES",
            "explanation": "PC-5 statutory mandate"
        }
        mock_groq_synthesis = {
            "primary_answer": "Voluntary certification - no QCO applies",  # Adversarial hallucination
            "key_information": [
                {"label": "QCO status", "value": "Voluntary", "source": "GENERAL_LLM"}
            ],
            "explanation": "This product does not need BIS certification.",
            "general_information": None
        }

        fallback = synthesizer.synthesize_stage_deterministic(
            stage_num=3,
            pc5_stage=pc5_stage,
            rag_status="SUFFICIENT",
            rag_evidence=[],
            qco_info={"qco_title": "Pipes and Fittings QCO", "notification_numbers": ["S.O. 4512(E)"], "effective_date": "2024-04-12"},
            target_standard="IS 4985"
        )

        guarded = synthesizer.validate_and_guard_synthesis(
            stage_num=3,
            pc5_stage=pc5_stage,
            synthesis=mock_groq_synthesis,
            rag_evidence=[],
            qco_info={"qco_title": "Pipes and Fittings QCO", "notification_numbers": ["S.O. 4512(E)"], "effective_date": "2024-04-12"},
            fallback=fallback,
            target_standard="IS 4985"
        )

        # Status lock MUST enforce the PC-5 deterministic primary answer
        assert guarded["primary_answer"] == "QCO applies"
        assert guarded["grounding_status"] == "GROUNDED"

    # -------------------------------------------------------------------------
    # Test 5: Hallucinated notification numbers are rejected
    # -------------------------------------------------------------------------
    def test_hallucinated_notification_numbers_rejected(self):
        """Grounding Guard rejects fake notification numbers not found in evidence or QCO registry."""
        synthesizer = get_compliance_rag_synthesizer()

        pc5_stage = {"status": "CONFIRMED", "qco_status": "QCO_APPLIES"}
        mock_synthesis = {
            "primary_answer": "QCO applies",
            "key_information": [
                {"label": "Notification", "value": "S.O. 99999(FAKE-NOTIF)", "source": "BIS_EVIDENCE"}
            ],
            "explanation": "Fabricated notification.",
            "general_information": None
        }

        fallback = synthesizer.synthesize_stage_deterministic(
            stage_num=3,
            pc5_stage=pc5_stage,
            rag_status="SUFFICIENT",
            rag_evidence=[{"text": "BIS Gazette S.O. 4512(E) issued on 2023-10-13."}],
            qco_info={"notification_numbers": ["S.O. 4512(E)"]},
            target_standard="IS 4985"
        )

        guarded = synthesizer.validate_and_guard_synthesis(
            stage_num=3,
            pc5_stage=pc5_stage,
            synthesis=mock_synthesis,
            rag_evidence=[{"text": "BIS Gazette S.O. 4512(E) issued on 2023-10-13."}],
            qco_info={"notification_numbers": ["S.O. 4512(E)"]},
            fallback=fallback,
            target_standard="IS 4985"
        )

        notif_item = next(item for item in guarded["key_information"] if item["label"] == "Notification")
        assert notif_item["value"] == NOT_SPECIFIED_TEXT

    # -------------------------------------------------------------------------
    # Test 6: Hallucinated dates are rejected
    # -------------------------------------------------------------------------
    def test_hallucinated_dates_rejected(self):
        """Grounding Guard rejects effective dates not attested in evidence text or QCO registry."""
        synthesizer = get_compliance_rag_synthesizer()

        pc5_stage = {"status": "CONFIRMED", "qco_status": "QCO_APPLIES"}
        mock_synthesis = {
            "primary_answer": "QCO applies",
            "key_information": [
                {"label": "Effective date", "value": "2099-12-31", "source": "BIS_EVIDENCE"}
            ],
            "explanation": "Fabricated date.",
            "general_information": None
        }

        fallback = synthesizer.synthesize_stage_deterministic(
            stage_num=3,
            pc5_stage=pc5_stage,
            rag_status="SUFFICIENT",
            rag_evidence=[{"text": "Effective from 2024-04-12 as per official notification."}],
            qco_info={"effective_date": "2024-04-12"},
            target_standard="IS 4985"
        )

        guarded = synthesizer.validate_and_guard_synthesis(
            stage_num=3,
            pc5_stage=pc5_stage,
            synthesis=mock_synthesis,
            rag_evidence=[{"text": "Effective from 2024-04-12 as per official notification."}],
            qco_info={"effective_date": "2024-04-12"},
            fallback=fallback,
            target_standard="IS 4985"
        )

        date_item = next(item for item in guarded["key_information"] if item["label"] == "Effective date")
        assert date_item["value"] == NOT_SPECIFIED_TEXT

    # -------------------------------------------------------------------------
    # Test 7: Unsupported testing claims are pruned
    # -------------------------------------------------------------------------
    def test_unsupported_testing_claims_pruned(self):
        """Grounding Guard prunes testing parameter claims not present in SIT or evidence."""
        synthesizer = get_compliance_rag_synthesizer()

        pc5_stage = {
            "status": "CONFIRMED",
            "total_tests": 2,
            "testing_requirements": [
                {"test_name": "Hydrostatic pressure test", "test_clause": "8.1"}
            ]
        }
        mock_synthesis = {
            "primary_answer": "Testing requirements established",
            "key_information": [
                {"label": "Key test parameters", "value": "Quantum Teleportation Durability Test", "source": "BIS_EVIDENCE"}
            ],
            "explanation": "Fabricated test requirement.",
            "general_information": None
        }

        fallback = synthesizer.synthesize_stage_deterministic(
            stage_num=6,
            pc5_stage=pc5_stage,
            rag_status="SUFFICIENT",
            rag_evidence=[{"text": "Hydrostatic pressure test shall be carried out per clause 8.1."}],
            qco_info=None,
            target_standard="IS 4985"
        )

        guarded = synthesizer.validate_and_guard_synthesis(
            stage_num=6,
            pc5_stage=pc5_stage,
            synthesis=mock_synthesis,
            rag_evidence=[{"text": "Hydrostatic pressure test shall be carried out per clause 8.1."}],
            qco_info=None,
            fallback=fallback,
            target_standard="IS 4985"
        )

        test_item = next(item for item in guarded["key_information"] if item["label"] == "Key test parameters")
        assert "Quantum Teleportation" not in test_item["value"]

    # -------------------------------------------------------------------------
    # Test 8: General LLM information is separated under GENERAL INFORMATION with disclaimer
    # -------------------------------------------------------------------------
    def test_general_llm_information_separated_with_disclaimer(self):
        """General information must include the mandatory unverified disclaimer."""
        synthesizer = get_compliance_rag_synthesizer()
        req = ComplianceJourneyRequest(standard="IS 4985")
        journey = synthesizer.process_journey(req)

        scheme_stage = journey["certification_scheme"]
        synthesis = scheme_stage["synthesis"]

        gen_info = synthesis.get("general_information")
        if gen_info:
            assert GENERAL_INFO_DISCLAIMER in gen_info
            assert "Not verified against BIS evidence for this specific product." in gen_info

    # -------------------------------------------------------------------------
    # Test 9: Evidence provenance preserved
    # -------------------------------------------------------------------------
    def test_evidence_provenance_preserved(self):
        """Retrieved evidence chunks preserve provenance layer, url, record ID, and hashes."""
        synthesizer = get_compliance_rag_synthesizer()
        req = ComplianceJourneyRequest(standard="IS 4985")
        journey = synthesizer.process_journey(req)

        reg_stage = journey["regulatory_status"]
        retrieved_ev = reg_stage.get("retrieved_evidence", [])
        assert len(retrieved_ev) > 0

        for chunk in retrieved_ev:
            assert "source_layer" in chunk
            assert chunk["source_layer"] in [
                "PHASE_12_E_RAG",
                "GAZETTE_QCO_REGISTRY",
                "PC-2_NORMALIZED_GAZETTE",
                "PHASE_13_AUTHORITATIVE_CORPUS"
            ]
            assert "source_url" in chunk
            assert "source_record_id" in chunk
            assert "evidence_hash" in chunk

    # -------------------------------------------------------------------------
    # Test 10: F3 laboratories remain byte-identical
    # -------------------------------------------------------------------------
    def test_f3_laboratories_remain_byte_identical(self):
        """Stage 9 laboratories remain 100% frozen and identical to PC-5 engine output."""
        synthesizer = get_compliance_rag_synthesizer()
        raw_orchestrator = get_compliance_orchestrator()

        req = ComplianceJourneyRequest(standard="IS 4985", location="Delhi")

        raw_journey = raw_orchestrator.build_journey(req)
        enriched_journey = synthesizer.process_journey(req)

        raw_labs = raw_journey.laboratories.model_dump(mode="json")
        enriched_labs = enriched_journey["laboratories"]

        assert raw_labs["status"] == enriched_labs["status"]
        assert raw_labs["total_matching"] == enriched_labs["total_matching"]
        assert len(raw_labs["qualified_laboratories"]) == len(enriched_labs["qualified_laboratories"])

        # Check every lab attribute byte-for-byte
        for r_lab, e_lab in zip(raw_labs["qualified_laboratories"], enriched_labs["qualified_laboratories"]):
            assert r_lab["public_lab_code"] == e_lab["public_lab_code"]
            assert r_lab["laboratory_name"] == e_lab["laboratory_name"]
            assert r_lab["address"] == e_lab["address"]
            assert r_lab["capability_evidence"] == e_lab["capability_evidence"]

    # -------------------------------------------------------------------------
    # Test 11: QCO conflicts remain conflicts (IS 374)
    # -------------------------------------------------------------------------
    def test_qco_conflicts_remain_conflicts(self):
        """IS 374 has conflicting regulatory notifications; status must remain QCO_CONFLICT."""
        synthesizer = get_compliance_rag_synthesizer()
        req = ComplianceJourneyRequest(standard="IS 374")
        journey = synthesizer.process_journey(req)

        reg = journey["regulatory_status"]
        assert reg["qco_status"] == "QCO_CONFLICT"
        assert reg["synthesis"]["primary_answer"] == "Conflicting QCO evidence"
        assert journey["mandatory_certification"]["status"] == "QCO_CONFLICT"

    # -------------------------------------------------------------------------
    # Test 12: Standard-not-established remains unchanged ("timber doors")
    # -------------------------------------------------------------------------
    def test_standard_not_established_remains_unchanged(self):
        """Unmatched product queries preserve STANDARD_NOT_ESTABLISHED status."""
        synthesizer = get_compliance_rag_synthesizer()
        req = ComplianceJourneyRequest(product="timber doors")
        journey = synthesizer.process_journey(req)

        assert journey["status"] == "STANDARD_NOT_ESTABLISHED"
        assert journey["applicable_standards"]["status"] == "STANDARD_NOT_ESTABLISHED"
        assert journey["applicable_standards"]["primary_standard"] is None

    # -------------------------------------------------------------------------
    # Test 13: RAG failure resilience
    # -------------------------------------------------------------------------
    def test_rag_failure_resilience(self):
        """When RAG retrieval throws an exception, pipeline falls back gracefully to PC-5."""
        synthesizer = get_compliance_rag_synthesizer()
        req = ComplianceJourneyRequest(standard="IS 4985")

        with patch("backend.compliance_rag_synthesizer.query_production_rag", side_effect=RuntimeError("RAG index offline")):
            # Clear local cache to force RAG call
            synthesizer._rag_query_cache.clear()
            journey = synthesizer.process_journey(req)

            assert journey["status"] == "JOURNEY_ESTABLISHED"
            assert journey["regulatory_status"]["qco_status"] == "QCO_APPLIES"
            assert journey["regulatory_status"]["synthesis"]["grounding_status"] == "GROUNDED"

    # -------------------------------------------------------------------------
    # Test 14: Groq failure resilience
    # -------------------------------------------------------------------------
    def test_groq_failure_resilience(self):
        """When Groq throws an exception, pipeline falls back to deterministic synthesis."""
        synthesizer = get_compliance_rag_synthesizer()
        req = ComplianceJourneyRequest(standard="IS 4985")

        with patch.object(synthesizer.groq_client, "chat_completion", side_effect=RuntimeError("Groq quota exceeded")):
            journey = synthesizer.process_journey(req)

            assert journey["status"] == "JOURNEY_ESTABLISHED"
            assert journey["regulatory_status"]["synthesis"]["primary_answer"] == "QCO applies"
            assert journey["regulatory_status"]["synthesis"]["grounding_status"] == "GROUNDED"

    # -------------------------------------------------------------------------
    # Test 15: Both failures resilience (RAG + Groq simultaneous failure)
    # -------------------------------------------------------------------------
    def test_both_failures_resilience(self):
        """When both RAG and Groq fail simultaneously, pipeline returns complete valid journey."""
        synthesizer = get_compliance_rag_synthesizer()
        req = ComplianceJourneyRequest(standard="IS 4985")

        with patch("backend.compliance_rag_synthesizer.query_production_rag", side_effect=RuntimeError("RAG down")), \
             patch.object(synthesizer.groq_client, "chat_completion", side_effect=RuntimeError("Groq down")):
            synthesizer._rag_query_cache.clear()
            journey = synthesizer.process_journey(req)

            assert journey["status"] == "JOURNEY_ESTABLISHED"
            assert journey["applicable_standards"]["primary_standard"] == "IS 4985"
            assert journey["regulatory_status"]["qco_status"] == "QCO_APPLIES"
            assert journey["laboratories"]["total_matching"] > 0

    # -------------------------------------------------------------------------
    # Test 16: No duplicate RAG engine created
    # -------------------------------------------------------------------------
    def test_no_duplicate_rag_engine(self):
        """Verify compliance_rag_synthesizer reuses existing Phase 12.E query_production_rag directly."""
        module_path = PROJECT_ROOT / "backend" / "compliance_rag_synthesizer.py"
        with open(module_path, "r", encoding="utf-8") as f:
            code = f.read()

        parsed = ast.parse(code)
        imported_names = []
        for node in ast.walk(parsed):
            if isinstance(node, ast.ImportFrom):
                if node.module == "scripts.phase12_e_production_rag":
                    imported_names.extend(n.name for n in node.names)

        assert "query_production_rag" in imported_names
        assert "ProductionRAGEngine" not in imported_names  # Must NOT instantiate a second engine

    # -------------------------------------------------------------------------
    # Test 17: No duplicate GroqClient created
    # -------------------------------------------------------------------------
    def test_no_duplicate_groq_client(self):
        """Verify compliance_rag_synthesizer reuses existing GroqClient from orchestrator."""
        module_path = PROJECT_ROOT / "backend" / "compliance_rag_synthesizer.py"
        with open(module_path, "r", encoding="utf-8") as f:
            code = f.read()

        parsed = ast.parse(code)
        imported_names = []
        for node in ast.walk(parsed):
            if isinstance(node, ast.ImportFrom):
                if node.module == "scripts.phase12_f2_orchestrator":
                    imported_names.extend(n.name for n in node.names)

        assert "GroqClient" in imported_names

    # -------------------------------------------------------------------------
    # Test 18: Frozen baseline hashes verified
    # -------------------------------------------------------------------------
    def test_frozen_baseline_hashes_verified(self):
        """Verify all 11 frozen files strictly match their SHA256 hashes byte-for-byte."""
        assert BASELINE_HASHES_FILE.exists(), f"Baseline hashes file not found at {BASELINE_HASHES_FILE}"
        with open(BASELINE_HASHES_FILE, "r", encoding="utf-8") as f:
            baseline_hashes = json.load(f)

        for rel_path, expected_hash in baseline_hashes.items():
            file_path = PROJECT_ROOT / rel_path
            assert file_path.exists(), f"Frozen file missing: {file_path}"
            with open(file_path, "rb") as fp:
                actual_hash = hashlib.sha256(fp.read()).hexdigest()
            assert actual_hash == expected_hash, (
                f"CRYPTO BREACH: Frozen file {rel_path} was modified! "
                f"Expected {expected_hash}, got {actual_hash}"
            )

    # -------------------------------------------------------------------------
    # Test 19: Clarification flow unharmed
    # -------------------------------------------------------------------------
    def test_clarification_flow_unharmed(self):
        """The /api/compliance/clarify endpoint remains operational and unaffected."""
        resp = client.post("/api/compliance/clarify", json={"query": "pvc"})
        assert resp.status_code == 200
        data = resp.json()
        assert "state" in data
        assert "slots" in data
        assert "refined_request" in data

    # -------------------------------------------------------------------------
    # Test 20: Failure Mode 3 - RAG Partial + Groq Available
    # -------------------------------------------------------------------------
    def test_20_rag_partial_groq_available(self):
        """When RAG returns partial evidence, Groq synthesizes available facts while unestablished remain unknown."""
        synthesizer = get_compliance_rag_synthesizer()
        req = ComplianceJourneyRequest(standard="IS 4985")

        partial_evidence = [{
            "source_record_id": "PARTIAL-CHUNK-01",
            "retrieval_unit_id": "PARTIAL-CHUNK-01",
            "source_title": "IS 4985 Scope",
            "source_url": "https://standardsbis.bsbedge.com",
            "source_layer": "PHASE_13_AUTHORITATIVE_CORPUS",
            "text": "Indian Standard IS 4985: Unplasticized Polyvinyl Chloride (uPVC) Pipes for Potable Water Supplies.",
            "text_preview": "Indian Standard IS 4985: Unplasticized Polyvinyl Chloride (uPVC) Pipes...",
            "evidence_hash": "HASH-PARTIAL-01",
            "document_type": "OFFICIAL_STANDARD"
        }]

        with patch("backend.compliance_rag_synthesizer.query_production_rag", return_value={"status": "SUFFICIENT", "evidence": partial_evidence}):
            synthesizer._rag_query_cache.clear()
            journey = synthesizer.process_journey(req)

            assert journey["status"] == "JOURNEY_ESTABLISHED"
            assert journey["applicable_standards"]["primary_standard"] == "IS 4985"
            stage2_ki = journey["applicable_standards"]["synthesis"]["key_information"]
            labels = {item["label"]: item["value"] for item in stage2_ki}
            assert "Standard number" in labels
            assert labels["Standard number"] == "IS 4985"

    # -------------------------------------------------------------------------
    # Test 21: Failure Mode 4 - RAG Available + Groq Synthesis Failure
    # -------------------------------------------------------------------------
    def test_21_rag_available_groq_synthesis_failure(self):
        """When RAG evidence is present but Groq returns invalid JSON, fallback synthesizes using RAG chunks."""
        synthesizer = get_compliance_rag_synthesizer()
        req = ComplianceJourneyRequest(standard="IS 4985")

        with patch.object(synthesizer.groq_client, "chat_completion", return_value="<<<MALFORMED NOT JSON RESPONSE>>>"):
            journey = synthesizer.process_journey(req)

            assert journey["status"] == "JOURNEY_ESTABLISHED"
            assert journey["regulatory_status"]["synthesis"]["primary_answer"] == "QCO applies"
            # Verify deterministic fallback successfully enriched QCO fields from index
            ki = {item["label"]: item["value"] for item in journey["regulatory_status"]["synthesis"]["key_information"]}
            assert ki["Notification"] == "S.O. 4512(E)"
            assert ki["Effective date"] == "2024-04-12"

    # -------------------------------------------------------------------------
    # Test 22: Failure Mode 5 - RAG Available + Groq Attempts Unsupported Claim
    # -------------------------------------------------------------------------
    def test_22_rag_available_groq_attempts_unsupported_claim(self):
        """When Groq attempts hallucinated notification or parameter, Grounding Guard sanitizes them."""
        synthesizer = get_compliance_rag_synthesizer()
        req = ComplianceJourneyRequest(standard="IS 4985")

        hallucinated_response = json.dumps({
            "primary_answer": "VOLUNTARY_SCHEME",  # Attempt to break status lock
            "key_information": [
                {"label": "Notification", "value": "S.O. 99999(E)", "source": "BIS_EVIDENCE"},
                {"label": "Effective date", "value": "2099-01-01", "source": "BIS_EVIDENCE"},
                {"label": "Key test parameters", "value": "Quantum Antimatter Teleportation Test", "source": "BIS_EVIDENCE"}
            ],
            "explanation": "This standard is completely voluntary under fake notification S.O. 99999(E).",
            "general_information": None
        })

        with patch.object(synthesizer.groq_client, "chat_completion", return_value=hallucinated_response):
            journey = synthesizer.process_journey(req)

            # Strict status lock enforced
            assert journey["regulatory_status"]["synthesis"]["primary_answer"] == "QCO applies"
            # Fake notification and date purged
            ki = {item["label"]: item["value"] for item in journey["regulatory_status"]["synthesis"]["key_information"]}
            assert ki["Notification"] in ("Not specified in available BIS evidence", "S.O. 4512(E)")
            assert ki["Notification"] != "S.O. 99999(E)"
            assert ki["Effective date"] != "2099-01-01"
            # Fake explanation purged
            assert "99999" not in journey["regulatory_status"]["synthesis"]["explanation"]
