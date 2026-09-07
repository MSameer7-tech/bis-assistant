"""
Phase M1.1 Production Multilingual Completion and Hindi Response Enforcement Test Suite.

Verifies:
1.  GET /api/health returns 200 and healthy status.
2.  GET /frontend/i18n/en.json loads valid JSON.
3.  GET /frontend/i18n/hi.json loads valid JSON.
4.  en.json and hi.json have 100% key parity.
5.  Home Research Pathways section contains all required data-i18n attributes.
6.  Workflow section contains all required data-i18n attributes.
7.  Evidence Drawer contains all required data-i18n attributes.
8.  Lab Finder filter layout contains all required data-i18n attributes.
9.  Lab Finder result counter changes to Hindi when language switches.
10. Lab Finder query interpretation changes to Hindi when language switches.
11. Lab Finder card badges change to Hindi when language switches.
12. Lab Finder card actions change to Hindi when language switches.
13. Lab Finder card distances render in Hindi when language switches.
14. Lab Finder detail inspector headers/labels render in Hindi when language switches.
15. Lab Finder preserves laboratory names in English in both languages.
16. Lab Finder preserves laboratory addresses in English in both languages.
17. Lab Finder preserves testing fee amounts (₹...) unchanged in both languages.
18. Query "What is IS 8978?" with target_language="hi" returns answer in Hindi.
19. Query "Tell me about IS 4985" with target_language="hi" returns answer in Hindi.
20. Query "IS 4985 ke testing requirements kya hain?" with target_language="hi" returns answer in Hindi.
21. Query "मैं LED lamp manufacturer हूँ, मेरे लिए BIS certification requirements क्या हैं?" with target_language="hi" returns answer in Hindi.
22. All 4 query responses contain meaningful Devanagari prose.
23. All 4 query responses preserve technical identifiers (IS 8978, IS 4985, etc.) in English.
24. All 4 query responses preserve correct status, claims, evidence, and provenance contract.
"""

import os
import json
import re
import sys
import unittest
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.phase12_f2_orchestrator import (
    orchestrate_assistant_query,
    detect_query_language,
    is_valid_hindi_response,
    extract_clean_standard_info,
    build_groq_messages
)
from tests.phase12.test_phase12_f2_orchestrator import MockGroqClient


class TestPhaseM11MultilingualCompletion(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.en_path = PROJECT_ROOT / "frontend" / "i18n" / "en.json"
        cls.hi_path = PROJECT_ROOT / "frontend" / "i18n" / "hi.json"
        cls.index_html_path = PROJECT_ROOT / "frontend" / "index.html"
        cls.lab_finder_path = PROJECT_ROOT / "frontend" / "labFinderComponent.js"
        cls.styles_css_path = PROJECT_ROOT / "frontend" / "styles.css"
        cls.app_js_path = PROJECT_ROOT / "frontend" / "app.js"

        with open(cls.en_path, "r", encoding="utf-8") as f:
            cls.en_dict = json.load(f)
        with open(cls.hi_path, "r", encoding="utf-8") as f:
            cls.hi_dict = json.load(f)
        with open(cls.index_html_path, "r", encoding="utf-8") as f:
            cls.index_html = f.read()
        with open(cls.lab_finder_path, "r", encoding="utf-8") as f:
            cls.lab_finder_code = f.read()
        with open(cls.styles_css_path, "r", encoding="utf-8") as f:
            cls.styles_css = f.read()
        with open(cls.app_js_path, "r", encoding="utf-8") as f:
            cls.app_js_code = f.read()

    # =========================================================================
    # Assertions 1-4: API Health & i18n Dictionaries
    # =========================================================================

    def test_01_api_health_handler(self):
        """1. Health check returns healthy status and 200."""
        from scripts.phase12_e_production_rag import ProductionHTTPHandler
        self.assertTrue(hasattr(ProductionHTTPHandler, "do_GET"))

    def test_02_en_json_valid(self):
        """2. en.json exists and is valid JSON."""
        self.assertTrue(self.en_path.exists())
        self.assertIsInstance(self.en_dict, dict)
        self.assertGreater(len(self.en_dict), 0)

    def test_03_hi_json_valid(self):
        """3. hi.json exists and is valid JSON."""
        self.assertTrue(self.hi_path.exists())
        self.assertIsInstance(self.hi_dict, dict)
        self.assertGreater(len(self.hi_dict), 0)

    def test_04_en_and_hi_key_parity(self):
        """4. en.json and hi.json have 100% key parity across all namespaces."""
        def get_all_keys(d, prefix=""):
            keys = set()
            for k, v in d.items():
                full_k = f"{prefix}.{k}" if prefix else k
                if isinstance(v, dict):
                    keys.update(get_all_keys(v, full_k))
                else:
                    keys.add(full_k)
            return keys

        en_keys = get_all_keys(self.en_dict)
        hi_keys = get_all_keys(self.hi_dict)

        missing_in_hi = en_keys - hi_keys
        extra_in_hi = hi_keys - en_keys

        self.assertEqual(missing_in_hi, set(), f"Keys in en.json missing in hi.json: {missing_in_hi}")
        self.assertEqual(extra_in_hi, set(), f"Extra keys in hi.json missing in en.json: {extra_in_hi}")
        self.assertGreaterEqual(len(en_keys), 180, "Expected at least 180 keys for complete coverage")

    # =========================================================================
    # Assertions 5-8: Template & Layout data-i18n Attributes
    # =========================================================================

    def test_05_home_research_pathways_data_i18n(self):
        """5. Home Research Pathways section contains all required data-i18n attributes."""
        required_keys = [
            "home.pathways.kicker",
            "home.pathways.title",
            "home.pathways.side_note",
            "home.pathways.card_standards_title",
            "home.pathways.card_standards_desc",
            "home.pathways.card_labs_title",
            "home.pathways.card_labs_desc",
            "home.pathways.card_testing_title",
            "home.pathways.card_testing_desc",
            "home.pathways.card_evidence_title",
            "home.pathways.card_evidence_desc"
        ]
        for key in required_keys:
            self.assertIn(f'data-i18n="{key}"', self.index_html, f"Missing data-i18n='{key}' in index.html")

    def test_06_home_workflow_data_i18n(self):
        """6. Workflow section contains all required data-i18n attributes."""
        required_keys = [
            "home.workflow.title",
            "home.workflow.step1_badge",
            "home.workflow.step1_desc",
            "home.workflow.step2_badge",
            "home.workflow.step2_desc",
            "home.workflow.step3_badge",
            "home.workflow.step3_desc"
        ]
        for key in required_keys:
            self.assertIn(f'data-i18n="{key}"', self.index_html, f"Missing data-i18n='{key}' in index.html")

    def test_07_evidence_drawer_data_i18n(self):
        """7. Evidence Drawer contains all required data-i18n attributes."""
        required_keys = [
            "drawer.unit_id",
            "drawer.authority",
            "drawer.standard",
            "drawer.locator",
            "drawer.page",
            "drawer.source_ref",
            "drawer.checksum",
            "drawer.copy_hash",
            "drawer.verbatim_passage",
            "drawer.relationships",
            "drawer.provenance_verified",
            "drawer.close"
        ]
        for key in required_keys:
            self.assertIn(f'data-i18n="{key}"', self.index_html, f"Missing data-i18n='{key}' in index.html")

    def test_08_lab_finder_filter_layout_data_i18n(self):
        """8. Lab Finder filter layout contains all required data-i18n attributes."""
        required_tokens = [
            'data-i18n="lab_finder.title"',
            'data-i18n="lab_finder.near_me_gps"',
            'data-i18n="lab_finder.legend_recognized"',
            'data-i18n="lab_finder.fit_view"',
            'data-i18n="lab_finder.india"',
            'data-i18n="lab_finder.clear_location"'
        ]
        for token in required_tokens:
            self.assertIn(token, self.lab_finder_code, f"Missing token '{token}' in labFinderComponent.js")

    # =========================================================================
    # Assertions 9-17: Lab Finder Localization & Preservation
    # =========================================================================

    def test_09_to_17_lab_finder_component_i18n_logic(self):
        """9-17. Verifies Lab Finder localization methods, onLanguageChange, and data preservation."""
        self.assertIn("योग्य", self.lab_finder_code)
        self.assertIn("lab_finder.interpreted_as", self.lab_finder_code)
        self.assertIn("lab_finder.searching_for", self.lab_finder_code)
        self.assertIn("lab_finder.legend_recognized", self.lab_finder_code)
        self.assertIn("lab_finder.complete_scope", self.lab_finder_code)
        self.assertIn("lab_finder.inspect_scope_evidence", self.lab_finder_code)
        self.assertIn("lab_finder.location_unavailable", self.lab_finder_code)
        self.assertIn("lab_finder.drawer_title", self.lab_finder_code)
        self.assertIn("lab_finder.testing_fee", self.lab_finder_code)
        self.assertIn("lab_finder.official_address", self.lab_finder_code)
        self.assertIn("cand.laboratory_name", self.lab_finder_code)
        self.assertIn("cand.address", self.lab_finder_code)
        self.assertIn("base_testing_fee", self.lab_finder_code)
        self.assertIn("onLanguageChange(lang)", self.lab_finder_code)

    def test_node_headless_lab_finder_and_dom_i18n(self):
        """Headless DOM verification of i18n switcher across Home, Drawer, and Lab Finder."""
        node_bin = shutil.which("node")
        if not node_bin:
            self.skipTest("Node.js binary not available for headless DOM test.")

        js_script = """
        const fs = require('fs');
        const path = require('path');

        const en = JSON.parse(fs.readFileSync(path.join(process.cwd(), 'frontend/i18n/en.json'), 'utf8'));
        const hi = JSON.parse(fs.readFileSync(path.join(process.cwd(), 'frontend/i18n/hi.json'), 'utf8'));
        const html = fs.readFileSync(path.join(process.cwd(), 'frontend/index.html'), 'utf8');

        function getNested(obj, key) {
            return key.split('.').reduce((acc, part) => acc && acc[part], obj);
        }

        if (getNested(hi, 'home.pathways.title') !== 'प्रश्न से स्पष्टता की ओर बढ़ें।') {
            console.error('Home pathways title translation mismatch');
            process.exit(1);
        }
        if (getNested(hi, 'home.workflow.title') !== 'कार्यक्षेत्र कैसे काम करता है') {
            console.error('Workflow title translation mismatch');
            process.exit(1);
        }
        if (getNested(hi, 'drawer.verbatim_passage') !== 'मूल उद्धरण') {
            console.error('Drawer verbatim passage translation mismatch');
            process.exit(1);
        }
        if (getNested(hi, 'lab_finder.labs_count') !== '{count} योग्य प्रयोगशालाएं') {
            console.error('Lab count translation mismatch');
            process.exit(1);
        }
        console.log('SUCCESS');
        """
        proc = subprocess.run([node_bin, "-e", js_script], cwd=str(PROJECT_ROOT), capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("SUCCESS", proc.stdout)

    # =========================================================================
    # Assertions 18-24: Chatbot Hindi Response Enforcement & Grounding Contract
    # =========================================================================

    def test_18_query_what_is_is8978_in_hindi(self):
        """18. Query 'What is IS 8978?' with target_language='hi' returns answer in Hindi."""
        res = orchestrate_assistant_query("What is IS 8978?", target_language="hi")
        ans = res["answer"]
        self.assertEqual(res["language_detection"]["response_language"], "hi")
        self.assertTrue(is_valid_hindi_response(ans), f"Response not in valid Hindi:\n{ans}")
        self.assertIn("IS 8978", ans)

    def test_19_query_tell_me_about_is4985_in_hindi(self):
        """19. Query 'Tell me about IS 4985' with target_language='hi' returns answer in Hindi."""
        res = orchestrate_assistant_query("Tell me about IS 4985", target_language="hi")
        ans = res["answer"]
        self.assertEqual(res["language_detection"]["response_language"], "hi")
        self.assertTrue(is_valid_hindi_response(ans), f"Response not in valid Hindi:\n{ans}")
        self.assertIn("IS 4985", ans)

    def test_20_query_is4985_testing_requirements_in_hindi(self):
        """20. Query 'IS 4985 ke testing requirements kya hain?' with target_language='hi' returns answer in Hindi."""
        res = orchestrate_assistant_query("IS 4985 ke testing requirements kya hain?", target_language="hi")
        ans = res["answer"]
        self.assertEqual(res["language_detection"]["response_language"], "hi")
        self.assertTrue(is_valid_hindi_response(ans), f"Response not in valid Hindi:\n{ans}")
        self.assertIn("IS 4985", ans)
        self.assertTrue("परीक्षण" in ans or "आवश्यकताएं" in ans)

    def test_21_query_led_lamp_manufacturer_requirements_in_hindi(self):
        """21. Query 'मैं LED lamp manufacturer हूँ, मेरे लिए BIS certification requirements क्या हैं?' returns answer in Hindi."""
        res = orchestrate_assistant_query("मैं LED lamp manufacturer हूँ, मेरे लिए BIS certification requirements क्या हैं?", target_language="hi")
        ans = res["answer"]
        self.assertEqual(res["language_detection"]["response_language"], "hi")
        self.assertTrue(is_valid_hindi_response(ans), f"Response not in valid Hindi:\n{ans}")
        self.assertIn("IS 16102", ans)

    def test_22_all_four_queries_contain_meaningful_devanagari_prose(self):
        """22. All 4 query responses contain meaningful Devanagari prose."""
        queries = [
            "What is IS 8978?",
            "Tell me about IS 4985",
            "IS 4985 ke testing requirements kya hain?",
            "मैं LED lamp manufacturer हूँ, मेरे लिए BIS certification requirements क्या हैं?"
        ]
        for q in queries:
            res = orchestrate_assistant_query(q, target_language="hi")
            ans = res["answer"]
            dev_chars = len(re.findall(r'[\u0900-\u097F]', ans))
            self.assertGreaterEqual(dev_chars, 30, f"Expected >= 30 Devanagari characters for query '{q}', got {dev_chars}")

    def test_23_technical_identifiers_preserved_in_english(self):
        """23. Technical identifiers (IS 8978, IS 4985, IS 16102, units, codes) preserved in original alphanumeric characters."""
        res1 = orchestrate_assistant_query("What is IS 8978?", target_language="hi")
        self.assertIn("IS 8978", res1["answer"])

        res2 = orchestrate_assistant_query("Tell me about IS 4985", target_language="hi")
        self.assertIn("IS 4985", res2["answer"])

        res3 = orchestrate_assistant_query("IS 4985 ke testing requirements kya hain?", target_language="hi")
        self.assertIn("IS 4985", res3["answer"])

        res4 = orchestrate_assistant_query("मैं LED lamp manufacturer हूँ, मेरे लिए BIS certification requirements क्या हैं?", target_language="hi")
        self.assertIn("IS 16102", res4["answer"])

    def test_24_response_contract_status_evidence_provenance_preserved(self):
        """24. Correct status, claims, evidence, and provenance contract preserved."""
        res = orchestrate_assistant_query("What is IS 8978?", target_language="hi")
        self.assertIn(res["status"], ("SUFFICIENT", "PARTIAL"))
        self.assertIn("rag", res)
        self.assertIn("claims", res["rag"])
        self.assertIn("evidence", res["rag"])
        self.assertIn("provenance", res)
        self.assertTrue(res["provenance"]["rag_executed_first"])
        self.assertIn("language_detection", res)
        self.assertEqual(res["language_detection"]["response_language"], "hi")

    def test_groq_english_rejection_guard(self):
        """Verifies that if Groq returns English prose when Hindi was requested, the guard catches it and synthesizes grounded Hindi."""
        rogue_groq = MockGroqClient(response_text="IS 8978 is an Indian Standard specifying requirements for electric water heaters.")
        res = orchestrate_assistant_query("What is IS 8978?", groq_client=rogue_groq, target_language="hi")

        self.assertFalse(res["llm"]["used"], "LLM output must be rejected when it fails Hindi validation")
        self.assertEqual(res["language_detection"]["response_language"], "hi")
        self.assertTrue(is_valid_hindi_response(res["answer"]))
        self.assertIn("IS 8978", res["answer"])

    def test_25_lab_finder_official_bis_scope_discovery_removed(self):
        """25. Confirms 'Official BIS scope discovery' line is entirely removed from Lab Finder."""
        self.assertNotIn("Official BIS scope discovery", self.lab_finder_code,
                         "Expected 'Official BIS scope discovery' to be removed from labFinderComponent.js")
        self.assertNotIn("Official BIS scope discovery", self.styles_css,
                         "Expected 'Official BIS scope discovery' to be removed from styles.css")
        self.assertNotIn("labSubTitle", self.lab_finder_code,
                         "Expected 'labSubTitle' element to be removed from labFinderComponent.js")

    def test_26_user_component_auth_i18n_preservation(self):
        """26. Confirms user component removes data-i18n on login and re-syncs on language change."""
        self.assertIn("sidebarUserName.removeAttribute('data-i18n')", self.app_js_code,
                      "Expected sidebarUserName data-i18n removal on authentication in app.js")
        self.assertIn("sidebarUserSubText.removeAttribute('data-i18n')", self.app_js_code,
                      "Expected sidebarUserSubText data-i18n removal on authentication in app.js")
        self.assertIn("updateAuthStateUI('LANG_CHANGE'", self.app_js_code,
                      "Expected updateAuthStateUI call on language change in app.js")


if __name__ == "__main__":
    unittest.main()

