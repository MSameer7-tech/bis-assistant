import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from backend.app import app
from scripts.phase12_f2_orchestrator import (
    SUPPORTED_LANGUAGES,
    normalize_language_code,
    detect_query_language,
    is_valid_language_response,
    analyze_query_context,
    build_groq_messages,
    orchestrate_assistant_query,
    GroqClient
)

client = TestClient(app)

ALL_12_LANGUAGES = ["en", "hi", "bn", "te", "mr", "ta", "gu", "kn", "ml", "pa", "as", "or"]

class MockMultilingualGroqClient:
    def __init__(self):
        self.is_configured = True
        self.model_name = "openai/gpt-oss-120b"
        self.last_messages = None

    def chat_completion(self, messages, max_tokens=800):
        self.last_messages = messages
        sys_c = messages[0]["content"]
        user_c = messages[1]["content"]
        
        # Determine language from system prompt
        detected_lang = "en"
        for code in ALL_12_LANGUAGES:
            if f"Target Language: {SUPPORTED_LANGUAGES[code]['name']}" in sys_c:
                detected_lang = code
                break

        # Generate mock responses with technical identifiers preserved and appropriate script
        sample_responses = {
            "en": "IS 4985 specifies requirements for unplasticized PVC pipes for potable water supplies. Governed by Clause 8.1.",
            "hi": "IS 4985 पेयजल आपूर्ति के लिए अनप्लास्टिकाइज़्ड पीवीसी पाइपों के विनिर्देशों को निर्धारित करता है। Clause 8.1 के तहत परीक्षण।",
            "bn": "IS 4985 পানীয় জল সরবরাহের জন্য পিভিসি পাইপের প্রযুক্তিগত মান নির্ধারণ করে। Clause 8.1 অনুযায়ী পরীক্ষা।",
            "te": "IS 4985 తాగునీటి సరఫరా కోసం అన్‌ప్లాస్టిసైజ్డ్ PVC పైపుల ప్రమాణాలను నిర్దేశిస్తుంది. Clause 8.1 ప్రకారం నాణ్యత పరీక్షలు.",
            "mr": "IS 4985 पिण्याच्या पाण्याच्या पुरवठ्यासाठी अनप्लास्टिकाइज्ड पीव्हीसी पाईप्सचे तपशील निर्धारित करते. Clause 8.1 अंतर्गत चाचणी.",
            "ta": "IS 4985 குடிநீர் விநியோகத்திற்கான PVC குழாய்களின் தர விவரக்குறிப்புகளைக் குறிப்பிடுகிறது. Clause 8.1 கீழ் சோதனை.",
            "gu": "IS 4985 પીવાના પાણીના પુરવઠા માટે અનપ્લાસ્ટિસાઇઝ્ડ PVC પાઇપના સ્પષ્ટીકરણો નક્કી કરે છે. Clause 8.1 હેઠળ પરીક્ષણ.",
            "kn": "IS 4985 ಕುಡಿಯುವ ನೀರಿನ ಸರಬರಾಜುಗಾಗಿ PVC ಪೈಪ್‌ಗಳ ಗುಣಮಟ್ಟದ ಮಾನದಂಡಗಳನ್ನು ನಿರ್ದಿಷ್ಟಪಡಿಸುತ್ತದೆ. Clause 8.1 ಅಡಿಯಲ್ಲಿ ಪರೀಕ್ಷೆ.",
            "ml": "IS 4985 കുടിവെള്ള വിതരണത്തിനായുള്ള അൺപ്ലാസ്റ്റിസൈസ്ഡ് PVC പൈപ്പുകളുടെ മാനദണ്ഡങ്ങൾ വ്യക്തമാക്കുന്നു. Clause 8.1 പ്രകാരമുള്ള പരിശോധന.",
            "pa": "IS 4985 ਪੀਣ ਵਾਲੇ ਪਾਣੀ ਦੀ ਸਪਲਾਈ ਲਈ ਅਨਪਲਾਸਟਿਕਾਈਜ਼ਡ ਪੀਵੀਸੀ ਪਾਈਪਾਂ ਲਈ ਨਿਯਮ ਨਿਰਧਾਰਤ ਕਰਦਾ ਹੈ। Clause 8.1 ਅਧੀਨ ਟੈਸਟਿੰਗ।",
            "as": "IS 4985 খোৱাপানী যোগানৰ বাবে পিভিচি পাইপৰ প্রযুক্তিগত মান নিৰ্ধাৰণ কৰে। Clause 8.1 অনুসৰি পৰীক্ষা।",
            "or": "IS 4985 ପାନୀୟ ଜଳ ଯୋଗାଣ ପାଇଁ PVC ପାଇପଗୁଡ଼ିକର ବୈଷୟିକ ମାନକ ନିର୍ଦ୍ଧାରଣ କରେ। Clause 8.1 ଅନୁଯାୟୀ ପରୀକ୍ଷଣ।"
        }
        return sample_responses.get(detected_lang, sample_responses["en"])


class TestPhase2Multilingual:

    def test_01_supported_languages_registry(self):
        """Verify all 12 languages are registered with proper metadata and unicode regex."""
        assert len(SUPPORTED_LANGUAGES) == 12
        for lang in ALL_12_LANGUAGES:
            assert lang in SUPPORTED_LANGUAGES
            meta = SUPPORTED_LANGUAGES[lang]
            assert "name" in meta and len(meta["name"]) > 0
            assert "native_name" in meta and len(meta["native_name"]) > 0
            assert "script" in meta and len(meta["script"]) > 0
            assert "regex" in meta

    def test_02_normalize_language_code(self):
        """Verify normalization handles standard codes, BCP-47, casing, and fallbacks."""
        # Standard 12 codes
        for lang in ALL_12_LANGUAGES:
            assert normalize_language_code(lang) == lang
            assert normalize_language_code(lang.upper()) == lang

        # BCP-47 / locale tags
        assert normalize_language_code("hi-IN") == "hi"
        assert normalize_language_code("bn-BD") == "bn"
        assert normalize_language_code("mr_IN") == "mr"
        assert normalize_language_code("ta-IN") == "ta"
        assert normalize_language_code("te-IN") == "te"
        assert normalize_language_code("gu-IN") == "gu"
        assert normalize_language_code("kn-IN") == "kn"
        assert normalize_language_code("ml-IN") == "ml"
        assert normalize_language_code("pa-IN") == "pa"
        assert normalize_language_code("as-IN") == "as"
        assert normalize_language_code("or-IN") == "or"
        assert normalize_language_code("en-US") == "en"
        assert normalize_language_code("en-GB") == "en"

        # Fallbacks to English for unknown / None / empty / auto
        assert normalize_language_code(None) == "en"
        assert normalize_language_code("") == "en"
        assert normalize_language_code("auto") == "en"
        assert normalize_language_code("fr") == "en"
        assert normalize_language_code("es") == "en"
        assert normalize_language_code("zh") == "en"
        assert normalize_language_code("unknown_xyz") == "en"

    def test_03_detect_query_language(self):
        """Verify script detection across major Indian scripts and target_language precedence."""
        # Latin
        d_en = detect_query_language("What is IS 4985?")
        assert d_en["detected_language"] == "en"
        assert d_en["response_language"] == "en"

        # Devanagari (Hindi)
        d_hi = detect_query_language("आईएस 4985 क्या है?")
        assert d_hi["detected_language"] == "hi"
        assert d_hi["response_language"] == "hi"

        # Bengali
        d_bn = detect_query_language("IS 4985 এর মান কী?")
        assert d_bn["detected_language"] == "bn"
        assert d_bn["response_language"] == "bn"

        # Tamil
        d_ta = detect_query_language("IS 4985 என்றால் என்ன?")
        assert d_ta["detected_language"] == "ta"
        assert d_ta["response_language"] == "ta"

        # Telugu
        d_te = detect_query_language("IS 4985 అంటే ఏమిటి?")
        assert d_te["detected_language"] == "te"
        assert d_te["response_language"] == "te"

        # Gujarati
        d_gu = detect_query_language("IS 4985 શું છે?")
        assert d_gu["detected_language"] == "gu"
        assert d_gu["response_language"] == "gu"

        # Target language precedence
        d_target_mr = detect_query_language("What is IS 4985?", target_language="mr")
        assert d_target_mr["response_language"] == "mr"

        d_target_kn = detect_query_language("What is IS 4985?", target_language="kn")
        assert d_target_kn["response_language"] == "kn"

    def test_04_is_valid_language_response(self):
        """Verify response language validator ensures regional scripts are present while tolerating technical IDs."""
        # English always valid if non-empty
        assert is_valid_language_response("This is IS 4985 standard specifications.", "en") is True

        # Hindi valid when Devanagari present with technical IDs
        hi_good = "IS 4985 पेयजल आपूर्ति के लिए मानक है। Clause 8.1 के तहत 0.5 MPa दबाव।"
        assert is_valid_language_response(hi_good, "hi") is True

        # Hindi rejected if pure English
        hi_bad = "IS 4985 is the standard for unplasticized PVC pipes."
        assert is_valid_language_response(hi_bad, "hi") is False

        # Bengali valid with Bengali script
        bn_good = "IS 4985 পানীয় জলের পাইপের মান নির্ধারণ করে। Clause 8.1 আবশ্যক।"
        assert is_valid_language_response(bn_good, "bn") is True
        assert is_valid_language_response(hi_bad, "bn") is False

        # Tamil valid with Tamil script
        ta_good = "IS 4985 குடிநீர் விநியோகத்திற்கான குழாய் விவரக்குறிப்பு. Clause 8.1 சோதனை."
        assert is_valid_language_response(ta_good, "ta") is True
        assert is_valid_language_response(hi_bad, "ta") is False

    def test_05_canonical_search_query_invariance(self):
        """Canonical search_intent must be identical ('IS 4985') regardless of query language."""
        queries = [
            ("What is IS 4985?", "en"),
            ("IS 4985 क्या है?", "hi"),
            ("IS 4985 काय आहे?", "mr"),
            ("IS 4985 কী?", "bn"),
            ("IS 4985 అంటే ఏమిటి?", "te"),
            ("IS 4985 என்றால் என்ன?", "ta"),
            ("IS 4985 શું છે?", "gu")
        ]
        for q, lang in queries:
            ctx = analyze_query_context(q, target_language=lang)
            assert ctx["search_intent"] == "IS 4985", f"Search intent diverged for {lang}: {ctx['search_intent']}"

    def test_06_evidence_retrieval_invariance_across_all_12_languages(self):
        """Evidence selection, ordering, passages, citations, and claims must be 100% identical across all 12 languages."""
        mock_groq = MockMultilingualGroqClient()
        results = {}
        for lang in ALL_12_LANGUAGES:
            res = orchestrate_assistant_query("What is IS 4985?", groq_client=mock_groq, target_language=lang)
            assert res["status"] == "SUFFICIENT", f"Status altered for {lang}: {res['status']}"
            assert res["language_detection"]["response_language"] == lang
            results[lang] = res

        # Base reference is English
        ref_ev_ids = [e.get("retrieval_unit_id") or e.get("unit_id") for e in results["en"]["rag"]["evidence"]]
        ref_ev_texts = [e.get("text") for e in results["en"]["rag"]["evidence"]]
        ref_citations = results["en"]["rag"].get("citations", [])
        ref_claims = [c.get("claim_id") for c in results["en"]["rag"].get("claims", [])]

        assert len(ref_ev_ids) > 0, "No evidence retrieved for reference query"

        for lang in ALL_12_LANGUAGES[1:]:
            ev_ids = [e.get("retrieval_unit_id") or e.get("unit_id") for e in results[lang]["rag"]["evidence"]]
            ev_texts = [e.get("text") for e in results[lang]["rag"]["evidence"]]
            citations = results[lang]["rag"].get("citations", [])
            claims = [c.get("claim_id") for c in results[lang]["rag"].get("claims", [])]

            assert ev_ids == ref_ev_ids, f"Evidence IDs diverged for {lang}: {ev_ids} vs {ref_ev_ids}"
            assert ev_texts == ref_ev_texts, f"Evidence text diverged for {lang}"
            assert citations == ref_citations, f"Citations diverged for {lang}"
            assert claims == ref_claims, f"Claims diverged for {lang}"

    def test_07_grounding_status_invariance_is8978_partial(self):
        """IS 8978 (LIMS-only standard) must remain PARTIAL across all 12 languages, never upgraded."""
        mock_groq = MockMultilingualGroqClient()
        for lang in ALL_12_LANGUAGES:
            res = orchestrate_assistant_query("What are the clause requirements for IS 8978?", groq_client=mock_groq, target_language=lang)
            assert res["status"] == "PARTIAL", f"Status altered for IS 8978 in {lang}: {res['status']}"

    def test_08_grounding_status_invariance_is9999999_insufficient(self):
        """IS 9999999 (unindexed standard) must remain INSUFFICIENT across all 12 languages, never upgraded."""
        mock_groq = MockMultilingualGroqClient()
        for lang in ALL_12_LANGUAGES:
            res = orchestrate_assistant_query("What are the mandatory clauses in IS 9999999?", groq_client=mock_groq, target_language=lang)
            assert res["status"] == "INSUFFICIENT", f"Status altered for IS 9999999 in {lang}: {res['status']}"

    def test_09_api_query_accepts_all_12_languages(self):
        """POST /api/assistant/query accepts all 12 language codes and returns proper response_language."""
        for lang in ALL_12_LANGUAGES:
            resp = client.post(
                "/api/assistant/query",
                json={"query": "What is IS 4985?", "language": lang}
            )
            assert resp.status_code == 200, f"API failed for language {lang}: {resp.text}"
            data = resp.json()
            assert data["status"] == "SUFFICIENT"
            assert data["language_detection"]["response_language"] == lang

    def test_10_api_bcp47_and_invalid_language_normalization(self):
        """POST /api/assistant/query normalizes BCP-47 and invalid languages safely."""
        # BCP-47 tag
        resp = client.post(
            "/api/assistant/query",
            json={"query": "What is IS 4985?", "language": "te-IN"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["language_detection"]["response_language"] == "te"

        # Invalid language code falls back to en
        resp_invalid = client.post(
            "/api/assistant/query",
            json={"query": "What is IS 4985?", "language": "invalid-code-99"}
        )
        assert resp_invalid.status_code == 200
        data_inv = resp_invalid.json()
        assert data_inv["language_detection"]["response_language"] == "en"

    def test_11_multilingual_combinations_with_response_styles(self):
        """Verify matrix of multilingual prompts and response styles."""
        mock_groq = MockMultilingualGroqClient()
        test_matrix = [
            ("hi", "quick"),
            ("bn", "detailed"),
            ("ta", "professional"),
            ("mr", "quick"),
            ("te", "detailed"),
            ("gu", "professional")
        ]
        for lang, style in test_matrix:
            res = orchestrate_assistant_query("What is IS 4985?", groq_client=mock_groq, target_language=lang, response_style=style)
            assert res["status"] == "SUFFICIENT"
            assert res["language_detection"]["response_language"] == lang
            # Check that prompt sent to Groq contains language instruction and style instruction
            last_msgs = mock_groq.last_messages
            assert last_msgs is not None
            sys_prompt = last_msgs[0]["content"]
            assert SUPPORTED_LANGUAGES[lang]["name"] in sys_prompt
            assert SUPPORTED_LANGUAGES[lang]["script"] in sys_prompt

    def test_12_fallback_when_groq_unavailable_multilingual(self):
        """Offline fallback preserves grounding status and structure across languages."""
        unconfigured_groq = MagicMock()
        unconfigured_groq.is_configured = False
        unconfigured_groq.client = None

        for lang in ["en", "hi", "bn", "mr"]:
            res = orchestrate_assistant_query("What is IS 4985?", groq_client=unconfigured_groq, target_language=lang)
            assert res["status"] == "SUFFICIENT"
            assert res["llm"]["used"] is False
            assert res["provenance"]["source_layer"] == "RAG"
            assert len(res["rag"]["evidence"]) > 0
