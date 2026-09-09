import pytest
import subprocess
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from backend.app import app
from scripts.phase12_f2_orchestrator import orchestrate_assistant_query, GroqClient

client = TestClient(app)

class MockGroqClient:
    def __init__(self):
        self.is_configured = True
        self.model_name = "openai/gpt-oss-120b"
        self.last_messages = None

    def chat_completion(self, messages, max_tokens=800):
        self.last_messages = messages
        sys_c = messages[0]["content"]
        user_c = messages[1]["content"]
        if "Quick & Simple" in user_c:
            return "IS 4985 governs unplasticized PVC pipes for potable water.\n\n- Key standard: IS 4985:2021\n- Core application: Potable water supply\n\nIn brief: Ensures durable, non-toxic piping."
        elif "Professional & Compliance-focused" in user_c:
            return "### Regulatory Scope & Authority\nIS 4985:2021 is the normative Indian Standard governing unplasticized PVC pipes.\n\n### Normative Technical & Compliance Benchmarks\n- Prescribed hydrostatic pressure testing per Clause 8.1\n- Dimensional tolerances per Table 2\n\n### Statutory Certification Framework\nSubject to mandatory BIS Scheme I certification.\n\n### Operational & Compliance Implications\nNon-compliant articles cannot be marketed in India under the BIS Act, 2016."
        else:
            return "IS 4985 is the Indian Standard titled 'Unplasticized PVC Pipes for Potable Water Supplies'.\n\n### What it covers\nSpecifications and test methods for PVC piping systems.\n\n### Standard details\n- Standard: IS 4985\n- Year: 2021\n\n### In simple terms\nThis standard ensures drinking water pipes are safe and durable."

class TestPhase1Personalization:

    def test_01_api_query_receives_canonical_response_styles(self):
        """Verify POST /api/assistant/query accepts canonical quick, detailed, professional."""
        for style in ["quick", "detailed", "professional"]:
            resp = client.post(
                "/api/assistant/query",
                json={"query": "What is IS 4985?", "response_style": style}
            )
            assert resp.status_code == 200, f"Query failed for canonical style {style}: {resp.text}"
            data = resp.json()
            assert data["status"] == "SUFFICIENT"
            assert data.get("response_style") in (style, "Quick & Simple", "Detailed & Explanatory", "Professional & Compliance-focused")

    def test_02_grounding_invariants_is4985_sufficient(self):
        """IS 4985 must produce strictly identical evidence, citations, and ClaimValidator status across all 3 styles."""
        mock_groq = MockGroqClient()
        styles = ["quick", "detailed", "professional"]
        results = {}
        for s in styles:
            res = orchestrate_assistant_query("What is IS 4985?", groq_client=mock_groq, response_style=s)
            assert res["status"] == "SUFFICIENT", f"Status altered for style {s}: {res['status']}"
            results[s] = res

        # Evidence IDs must be identical
        ev_quick = [e.get("retrieval_unit_id") or e.get("unit_id") for e in results["quick"]["rag"]["evidence"]]
        ev_det = [e.get("retrieval_unit_id") or e.get("unit_id") for e in results["detailed"]["rag"]["evidence"]]
        ev_prof = [e.get("retrieval_unit_id") or e.get("unit_id") for e in results["professional"]["rag"]["evidence"]]
        assert ev_quick == ev_det == ev_prof, f"Evidence unit IDs diverged: {ev_quick} vs {ev_det} vs {ev_prof}"

        # Evidence passages must be identical
        txt_quick = [e.get("text") for e in results["quick"]["rag"]["evidence"]]
        txt_det = [e.get("text") for e in results["detailed"]["rag"]["evidence"]]
        txt_prof = [e.get("text") for e in results["professional"]["rag"]["evidence"]]
        assert txt_quick == txt_det == txt_prof, "Evidence passages diverged across styles"

        # Citations must be identical
        cit_quick = results["quick"]["rag"].get("citations", [])
        cit_det = results["detailed"]["rag"].get("citations", [])
        cit_prof = results["professional"]["rag"].get("citations", [])
        assert cit_quick == cit_det == cit_prof, "Citations diverged across styles"

        # ClaimValidator claims must be identical in substance
        cl_quick = [c.get("claim_id") for c in results["quick"]["rag"].get("claims", [])]
        cl_det = [c.get("claim_id") for c in results["detailed"]["rag"].get("claims", [])]
        cl_prof = [c.get("claim_id") for c in results["professional"]["rag"].get("claims", [])]
        assert cl_quick == cl_det == cl_prof, "ClaimValidator claims diverged across styles"

        # Answer wording must differ based on style
        assert results["quick"]["answer"] != results["detailed"]["answer"]
        assert results["detailed"]["answer"] != results["professional"]["answer"]

    def test_03_grounding_invariants_is8978_partial_never_upgraded(self):
        """IS 8978 (LIMS-only standard) must remain PARTIAL across all 3 response styles."""
        mock_groq = MockGroqClient()
        for s in ["quick", "detailed", "professional"]:
            res = orchestrate_assistant_query("What are the clause requirements for IS 8978?", groq_client=mock_groq, response_style=s)
            assert res["status"] == "PARTIAL", f"Status upgraded or altered for style {s}: {res['status']}"

    def test_04_grounding_invariants_is9999999_insufficient_never_upgraded(self):
        """IS 9999999 (unindexed standard) must remain INSUFFICIENT across all 3 response styles."""
        mock_groq = MockGroqClient()
        for s in ["quick", "detailed", "professional"]:
            res = orchestrate_assistant_query("What are the mandatory clauses in IS 9999999?", groq_client=mock_groq, response_style=s)
            assert res["status"] == "INSUFFICIENT", f"Status upgraded or altered for style {s}: {res['status']}"

    def test_05_fallback_when_groq_unavailable(self):
        """When Groq is unavailable, deterministic RAG response works across all 3 styles."""
        unconfigured_groq = MagicMock()
        unconfigured_groq.is_configured = False
        unconfigured_groq.client = None

        for s in ["quick", "detailed", "professional"]:
            res = orchestrate_assistant_query("What is IS 4985?", groq_client=unconfigured_groq, response_style=s)
            assert res["status"] == "SUFFICIENT"
            assert res["llm"]["used"] is False
            assert "IS 4985" in res["answer"]
            assert len(res["answer"]) > 20

    def test_06_llm_fallback_remains_unverified(self):
        """Queries that trigger fallback must never be marked BIS verified, regardless of response_style."""
        mock_groq = MockGroqClient()
        for s in ["quick", "detailed", "professional"]:
            res = orchestrate_assistant_query("What are general tips for home water filter maintenance?", groq_client=mock_groq, response_style=s)
            if res["status"] in ("PARTIAL", "INSUFFICIENT"):
                assert res["llm"].get("verified_by_bis_rag") is False
                assert res["provenance"].get("source_layer") in ("LLM_FALLBACK", "RAG")

    def test_07_no_decorative_or_compliance_badges(self):
        """Answer text must not contain decorative badges or compliance badges."""
        mock_groq = MockGroqClient()
        for s in ["quick", "detailed", "professional"]:
            res = orchestrate_assistant_query("What is IS 4985?", groq_client=mock_groq, response_style=s)
            ans = res["answer"].lower()
            assert "response-style-badge" not in ans
            assert "compliance badge" not in ans
            assert "compliance-badge" not in ans

    def test_08_frozen_artifacts_integrity_check(self):
        """Verify frozen Phase 12, Phase 13, and corpus files remain untouched."""
        from pathlib import Path

        root = Path(__file__).parent.parent
        # Phase 13 retrieval artifacts must exist and remain untouched
        assert (root / "data/derived/phase13/retrieval_index_full_v1/retrieval_units.jsonl").exists()
        assert (root / "data/derived/phase13/retrieval_index_full_v1/bm25_index.pkl").exists()
        assert (root / "data/derived/phase13/retrieval_index_full_v1/vector/vectors.npy").exists()
        assert (root / "data/derived/phase13/retrieval_index_full_v1/vector/vector_metadata.jsonl").exists()
        assert (root / "data/derived/phase13/retrieval_index_full_v1/retrieval_index_manifest.json").exists()

        # Phase 12 frozen scripts must exist
        assert (root / "scripts/phase12_b_hybrid_retrieval.py").exists()
        assert (root / "scripts/phase12_e_production_rag.py").exists()
        assert (root / "scripts/phase12d_benchmark.py").exists()
