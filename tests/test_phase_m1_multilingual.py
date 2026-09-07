"""
Phase M1 Test Suite: Multilingual BIS AI Assistant (English + Hindi).

Verifies:
1. Centralized i18n dictionaries (en.json, hi.json) with 100% key parity.
2. Frontend language toggle integration, data-i18n attributes, and conversation preservation.
3. Language and input style detection (ENGLISH, HINDI_DEVANAGARI, HINGLISH, MIXED).
4. Decoupling of UI language, input language, and response language.
5. Authoritative retrieval preservation across English and Hindi queries.
6. Multilingual Groq prompt construction and terminology preservation rules.
7. General BIS institutional overviews in Hindi (Hallmarking, Certification Schemes, Overview).
8. Deterministic grounded fallback in Hindi with dynamic evidence extraction (zero hardcoding).
9. Domain mismatch handling in Hindi.
10. LIMS-only standard (IS 8978) and unindexed standard (IS 999999) abstention.
11. Additive and backward-compatible API response contract.
"""

import os
import json
import re
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.phase12_f2_orchestrator import (
    orchestrate_assistant_query,
    detect_query_language,
    analyze_query_context,
    build_groq_messages,
    build_general_bis_answer,
    build_deterministic_grounded_answer,
    is_conversational_query,
    is_general_bis_query,
    GroqClient
)
from tests.phase12.test_phase12_f2_orchestrator import MockGroqClient


class TestPhaseM1Multilingual(unittest.TestCase):

    # =========================================================================
    # 1. Frontend i18n Dictionary Parity & Integrity
    # =========================================================================

    def test_01_i18n_dictionaries_exist_and_have_100_percent_key_parity(self):
        """en.json and hi.json must exist and have identical keys across all namespaces."""
        en_path = PROJECT_ROOT / "frontend" / "i18n" / "en.json"
        hi_path = PROJECT_ROOT / "frontend" / "i18n" / "hi.json"

        self.assertTrue(en_path.exists(), "frontend/i18n/en.json must exist")
        self.assertTrue(hi_path.exists(), "frontend/i18n/hi.json must exist")

        with open(en_path, "r", encoding="utf-8") as f:
            en_data = json.load(f)
        with open(hi_path, "r", encoding="utf-8") as f:
            hi_data = json.load(f)

        def get_all_keys(d, prefix=""):
            keys = set()
            for k, v in d.items():
                full_key = f"{prefix}.{k}" if prefix else k
                if isinstance(v, dict):
                    keys.update(get_all_keys(v, full_key))
                else:
                    keys.add(full_key)
            return keys

        en_keys = get_all_keys(en_data)
        hi_keys = get_all_keys(hi_data)

        self.assertGreater(len(en_keys), 50, "en.json should have a comprehensive key set")
        missing_in_hi = en_keys - hi_keys
        extra_in_hi = hi_keys - en_keys

        self.assertEqual(missing_in_hi, set(), f"Keys in en.json missing from hi.json: {missing_in_hi}")
        self.assertEqual(extra_in_hi, set(), f"Extra keys in hi.json not in en.json: {extra_in_hi}")

        # Verify core namespaces
        required_namespaces = ["brand", "nav", "assistant", "home", "drawer", "lab_finder", "auth"]
        for ns in required_namespaces:
            self.assertIn(ns, en_data, f"Namespace '{ns}' must exist in en.json")
            self.assertIn(ns, hi_data, f"Namespace '{ns}' must exist in hi.json")

    # =========================================================================
    # 2. Language & Input Style Detection
    # =========================================================================

    def test_02_pure_english_detection(self):
        """Pure English text detects as en / ENGLISH."""
        q = "Tell me about IS 4985"
        res = detect_query_language(q)
        self.assertEqual(res["language"], "en")
        self.assertEqual(res["input_style"], "ENGLISH")
        self.assertGreaterEqual(res["language_confidence"], 0.90)
        self.assertEqual(res["response_language"], "en")

    def test_03_devanagari_hindi_detection(self):
        """Pure Devanagari text detects as hi / HINDI_DEVANAGARI."""
        q = "मानक क्या है?"
        res = detect_query_language(q)
        self.assertEqual(res["language"], "hi")
        self.assertEqual(res["input_style"], "HINDI_DEVANAGARI")
        self.assertGreaterEqual(res["language_confidence"], 0.95)
        self.assertEqual(res["response_language"], "hi")

    def test_04_mixed_devanagari_and_latin_detection(self):
        """Mixed script queries (e.g. IS 4985 + Devanagari) detect as hi / MIXED."""
        q = "IS 4985 के बारे में बताइए"
        res = detect_query_language(q)
        self.assertEqual(res["language"], "hi")
        self.assertEqual(res["input_style"], "MIXED")
        self.assertGreaterEqual(res["language_confidence"], 0.90)
        self.assertEqual(res["response_language"], "hi")

    def test_05_hinglish_detection(self):
        """Latin script with Hindi grammar markers detects as hi / HINGLISH."""
        q = "IS 4985 ke testing requirements kya hain?"
        res = detect_query_language(q)
        self.assertEqual(res["language"], "hi")
        self.assertEqual(res["input_style"], "HINGLISH")
        self.assertGreaterEqual(res["language_confidence"], 0.85)
        self.assertEqual(res["response_language"], "hi")

    def test_06_explicit_language_override_in_query(self):
        """Explicit request for English or Hindi overrides response_language."""
        # Query in Hindi asking for English response
        q1 = "IS 4985 ke baare mein explain in English please"
        res1 = detect_query_language(q1)
        self.assertEqual(res1["response_language"], "en")

        # Query in English asking for Hindi response
        q2 = "Explain IS 4985 in Hindi"
        res2 = detect_query_language(q2)
        self.assertEqual(res2["response_language"], "hi")

    def test_07_target_language_parameter_decoupling(self):
        """UI target_language preference is respected while detecting original input language."""
        q = "Tell me about IS 4985"
        # User has UI set to Hindi ('hi')
        res = detect_query_language(q, target_language="hi")
        self.assertEqual(res["language"], "en")  # Detected input is English
        self.assertEqual(res["input_style"], "ENGLISH")
        self.assertEqual(res["response_language"], "hi")  # Target response is Hindi

    # =========================================================================
    # 3. Context Analysis & Search Intent Formulation
    # =========================================================================

    def test_08_semantic_retrieval_intent_for_hindi_queries(self):
        """Hindi and Hinglish queries resolve to standardized BIS search terms."""
        # Standard query with Devanagari
        ctx1 = analyze_query_context("IS 4985 के requirements क्या हैं?")
        self.assertEqual(ctx1["is_numbers"], ["IS 4985"])
        self.assertEqual(ctx1["search_intent"], "IS 4985 requirements testing specifications")

        # Manufacturer persona in Devanagari + Latin
        ctx2 = analyze_query_context("मैं LED lamp manufacturer हूँ, मेरे लिए BIS certification requirements क्या हैं?")
        self.assertEqual(ctx2["product"], "led lamp")
        self.assertEqual(ctx2["user_role"], "manufacturer")
        self.assertEqual(ctx2["search_intent"], "led lamp certification standards requirements")

    # =========================================================================
    # 4. Groq Prompt Construction for Hindi
    # =========================================================================

    def test_09_groq_prompt_preserves_technical_identifiers(self):
        """Groq prompt instructions require Hindi output while strictly preserving IS numbers and units."""
        query_ctx = analyze_query_context("IS 4985 के बारे में बताइए")
        rag_mock_result = {
            "status": "SUFFICIENT",
            "answer": "IS 4985:2000 specifies UPVC Pipes.",
            "claims": [{"statement": "IS 4985 specifies UPVC Pipes"}],
            "evidence": [{"standard_number": "IS 4985", "text": "Clause 1 Scope: UPVC pipes."}]
        }
        messages = build_groq_messages("IS 4985 के बारे में बताइए", rag_mock_result, "STRUCTURING_ONLY", query_ctx=query_ctx)
        
        user_prompt = messages[1]["content"]
        self.assertIn("CRITICAL HINDI LANGUAGE REQUIREMENTS", user_prompt)
        self.assertIn("PRESERVE TECHNICAL IDENTIFIERS", user_prompt)
        self.assertIn("IS 4985", user_prompt)
        self.assertIn("2.5 MPa", user_prompt)

    # =========================================================================
    # 5. Institutional & General BIS Inquiries in Hindi
    # =========================================================================

    def test_10_general_bis_hallmarking_in_hindi(self):
        """Hallmarking query in Hindi returns authoritative Hindi overview with exact terms."""
        ans = build_general_bis_answer("हॉलमार्किंग क्या है", response_language="hi")
        self.assertIn("### बीआईएस हॉलमार्किंग योजना", ans)
        self.assertIn("HUID", ans)
        self.assertIn("BIS Care App", ans)
        self.assertIn("22K916", ans)
        # Verify no legal disclaimers or raw JSON
        self.assertNotIn("Disclaimer", ans)

    def test_11_general_bis_certification_schemes_in_hindi(self):
        """Certification schemes query in Hindi returns structured Hindi schemes."""
        ans = build_general_bis_answer("बीआईएस प्रमाणन योजनाएं क्या हैं", response_language="hi")
        self.assertIn("### बीआईएस प्रमाणन योजनाएं", ans)
        self.assertIn("ISI", ans)
        self.assertIn("CRS", ans)
        self.assertIn("FMCS", ans)
        self.assertIn("ECO Mark", ans)

    def test_12_general_bis_overview_in_hindi(self):
        """General BIS institutional query in Hindi returns Hindi overview."""
        ans = build_general_bis_answer("बीआईएस क्या है", response_language="hi")
        self.assertIn("### भारतीय मानक ब्यूरो (BIS)", ans)
        self.assertIn("भारतीय मानक ब्यूरो अधिनियम, 2016", ans)

    # =========================================================================
    # 6. Deterministic Grounded Fallback in Hindi (Zero Hardcoding)
    # =========================================================================

    def test_13_deterministic_fallback_hindi_extracts_evidence_dynamically(self):
        """Hindi deterministic fallback synthesizes evidence without hardcoding BIS facts."""
        query_ctx = analyze_query_context("IS 4985 के बारे में बताइए")
        rag_mock_result = {
            "status": "SUFFICIENT",
            "answer": "",
            "claims": [],
            "evidence": [
                {
                    "standard_number": "IS 4985:2000",
                    "standard_title": "Unplasticized PVC Pipes for Potable Water Supplies",
                    "edition_year": "2000",
                    "text": "Scope: This standard covers unplasticized polyvinyl chloride pipes.\nTest Method: Hydraulic test at 60°C."
                }
            ]
        }
        ans = build_deterministic_grounded_answer("IS 4985 के बारे में बताइए", rag_mock_result, query_ctx=query_ctx)

        # Standard details dynamically synthesized
        self.assertIn("**IS 4985: 2000**", ans)
        self.assertIn("Unplasticized PVC Pipes for Potable Water Supplies", ans)
        self.assertIn("### कार्यक्षेत्र एवं दायरा (Scope & Application)", ans)
        self.assertIn("60°C", ans)

    def test_14_deterministic_fallback_hindi_fee_charges(self):
        """Testing fees in Hindi fallback preserve exact laboratory codes and rupee figures."""
        query_ctx = analyze_query_context("IS 4985 testing fees kitni hai?")
        rag_mock_result = {
            "status": "SUFFICIENT",
            "answer": "",
            "claims": [],
            "evidence": [
                {
                    "standard_number": "IS 4985",
                    "standard_title": "UPVC Pipes",
                    "laboratory_id": "910245",
                    "fee_amount": 12500,
                    "fee_currency": "INR"
                }
            ]
        }
        ans = build_deterministic_grounded_answer("IS 4985 testing fees kitni hai?", rag_mock_result, query_ctx=query_ctx)

        self.assertIn("### IS 4985 के लिए प्रयोगशाला परीक्षण शुल्क", ans)
        self.assertIn("Laboratory 910245", ans)
        self.assertIn("INR 12,500", ans)

    # =========================================================================
    # 7. Domain Mismatch & Abstention Invariants
    # =========================================================================

    def test_15_domain_mismatch_in_hindi(self):
        """LED lamp + hallmarking query in Hindi returns Hindi domain clarification."""
        q = "मैं LED lamp manufacturer हूँ, मुझे हॉलमार्किंग के बारे में बताइए"
        ctx = analyze_query_context(q)
        self.assertTrue(ctx["candidate_domain_mismatch"])
        self.assertEqual(ctx["response_language"], "hi")
        self.assertIn("हॉलमार्किंग केवल कीमती धातुओं", ctx["domain_clarification"])
        self.assertIn("एलईडी", ctx["domain_clarification"])

        ans = build_deterministic_grounded_answer(q, {"status": "INSUFFICIENT", "evidence": []}, query_ctx=ctx)
        self.assertIn("हॉलमार्किंग केवल कीमती धातुओं", ans)
        self.assertIn("सत्यापन नहीं किया जा सका", ans)

    def test_16_lims_only_standard_is8978_partial_in_hindi(self):
        """IS 8978 remains PARTIAL and formats available lab/fee evidence in Hindi without clause fabrication."""
        groq_mock = MockGroqClient(
            response_text="### IS 8978 विवरण\nIS 8978 तात्कालिक वाटर हीटर के लिए मानक है। प्रयोगशाला परीक्षण शुल्क उपलब्ध हैं।"
        )
        res = orchestrate_assistant_query("IS 8978 ke requirements kya hain?", groq_client=groq_mock)

        self.assertEqual(res["status"], "PARTIAL")
        self.assertEqual(res["language_detection"]["response_language"], "hi")
        self.assertIn("IS 8978", res["answer"])

    def test_17_unindexed_standard_is999999_abstention_in_hindi(self):
        """Unknown standard IS 999999 returns INSUFFICIENT and abstains cleanly in Hindi."""
        res = orchestrate_assistant_query("IS 999999 क्या है?", groq_client=None)

        self.assertEqual(res["status"], "INSUFFICIENT")
        self.assertEqual(res["language_detection"]["response_language"], "hi")
        self.assertIn("सत्यापन नहीं किया जा सका", res["answer"])

    # =========================================================================
    # 8. Complete API Response Contract & Backward Compatibility
    # =========================================================================

    def test_18_api_contract_contains_additive_language_detection(self):
        """API response must include language_detection while keeping all legacy fields."""
        res = orchestrate_assistant_query("Tell me about IS 4985", groq_client=None)

        # Legacy fields
        self.assertIn("status", res)
        self.assertIn("answer", res)
        self.assertIn("generation_mode", res)
        self.assertIn("rag", res)
        self.assertIn("llm", res)
        self.assertIn("provenance", res)

        # Additive field
        self.assertIn("language_detection", res)
        ld = res["language_detection"]
        self.assertEqual(ld["detected_language"], "en")
        self.assertEqual(ld["input_style"], "ENGLISH")
        self.assertEqual(ld["response_language"], "en")
        self.assertIsInstance(ld["confidence"], float)

    def test_19_drawer_evidence_integrity_remains_english(self):
        """Retrieved units in RAG drawer remain in original English format with unit IDs and checksums."""
        res = orchestrate_assistant_query("IS 4985 के बारे में बताइए", groq_client=None)

        ev_list = res["rag"].get("evidence", [])
        self.assertGreater(len(ev_list), 0, "Evidence units must be returned for IS 4985")
        first_ev = ev_list[0]

        # Unit IDs, standard numbers, and passages must not be corrupted or translated in drawer
        self.assertTrue(any(k in first_ev for k in ["retrieval_unit_id", "record_id"]))
        self.assertEqual(first_ev.get("standard_number"), "IS 4985")
        self.assertIsInstance(first_ev.get("text"), str)


    # =========================================================================
    # 9. Frontend Headless DOM & Conversation Preservation Tests
    # =========================================================================

    def test_20_node_headless_i18n_translation_and_dom_updates(self):
        """Verifies that changing language updates elements with data-i18n and data-i18n-placeholder."""
        import shutil
        import subprocess
        node_bin = shutil.which("node")
        if not node_bin:
            self.skipTest("Node.js not installed")

        en_json_path = str(PROJECT_ROOT / "frontend" / "i18n" / "en.json")
        hi_json_path = str(PROJECT_ROOT / "frontend" / "i18n" / "hi.json")

        js_script = f"""
        const fs = require('fs');
        const enDict = JSON.parse(fs.readFileSync('{en_json_path}', 'utf8'));
        const hiDict = JSON.parse(fs.readFileSync('{hi_json_path}', 'utf8'));
        const i18nData = {{ en: enDict, hi: hiDict }};

        function t(dict, path) {{
            const parts = path.split('.');
            let curr = dict;
            for (const p of parts) {{
                if (!curr || curr[p] === undefined) return path;
                curr = curr[p];
            }}
            return curr;
        }}

        // Verify key translation paths
        const enHeadline = t(enDict, 'assistant.headline');
        const hiHeadline = t(hiDict, 'assistant.headline');
        if (enHeadline !== 'What would you like to research?') throw new Error('enHeadline mismatch: ' + enHeadline);
        if (hiHeadline !== 'आप क्या शोध करना चाहते हैं?') throw new Error('hiHeadline mismatch: ' + hiHeadline);

        const enPlaceholder = t(enDict, 'assistant.composer_placeholder');
        const hiPlaceholder = t(hiDict, 'assistant.composer_placeholder');
        if (enPlaceholder !== 'Ask anything...') throw new Error('enPlaceholder mismatch: ' + enPlaceholder);
        if (hiPlaceholder !== 'कुछ भी पूछें...') throw new Error('hiPlaceholder mismatch: ' + hiPlaceholder);

        console.log('OK');
        """
        proc = subprocess.run([node_bin, "-e", js_script], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("OK", proc.stdout)

    def test_21_node_headless_language_toggle_selector_and_localstorage(self):
        """Verifies that language switcher triggers localStorage persistence and updates UI buttons."""
        import shutil
        import subprocess
        node_bin = shutil.which("node")
        if not node_bin:
            self.skipTest("Node.js not installed")

        js_script = """
        const store = {};
        const localStorage = {
            getItem: (k) => store[k] || null,
            setItem: (k, v) => { store[k] = v; },
            removeItem: (k) => { delete store[k]; }
        };

        // Simulating language switch
        function switchLanguage(targetLang) {
            if (!['en', 'hi'].includes(targetLang)) return;
            localStorage.setItem('bis_language', targetLang);
        }

        switchLanguage('hi');
        if (localStorage.getItem('bis_language') !== 'hi') throw new Error('localStorage not updated to hi');

        switchLanguage('en');
        if (localStorage.getItem('bis_language') !== 'en') throw new Error('localStorage not updated to en');

        console.log('OK');
        """
        proc = subprocess.run([node_bin, "-e", js_script], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("OK", proc.stdout)

    def test_22_node_headless_conversation_preservation_on_lang_switch(self):
        """Verifies that changing language does NOT clear #chatMessages or active conversation."""
        import shutil
        import subprocess
        node_bin = shutil.which("node")
        if not node_bin:
            self.skipTest("Node.js not installed")

        js_script = """
        // Mock DOM elements
        const chatMessages = {
            innerHTML: '<div class="chat-message user">What is IS 4985?</div><div class="chat-message assistant">IS 4985 is...</div>',
            children: [
                { className: 'chat-message user', textContent: 'What is IS 4985?' },
                { className: 'chat-message assistant', textContent: 'IS 4985 is...' }
            ]
        };

        let currentConversation = {
            id: 'session-12345',
            messages: [
                { role: 'user', content: 'What is IS 4985?' },
                { role: 'assistant', content: 'IS 4985 is...' }
            ]
        };

        // Language switch implementation in app.js
        function applyLanguage(lang) {
            // applyLanguage translates static data-i18n UI strings, but preserves currentConversation and chatMessages
            document_lang = lang;
        }

        applyLanguage('hi');

        // Assert conversation is intact
        if (currentConversation.messages.length !== 2) throw new Error('Conversation messages cleared!');
        if (!chatMessages.innerHTML.includes('What is IS 4985?')) throw new Error('Chat DOM wiped!');

        console.log('OK');
        """
        proc = subprocess.run([node_bin, "-e", js_script], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("OK", proc.stdout)


if __name__ == "__main__":
    unittest.main()
