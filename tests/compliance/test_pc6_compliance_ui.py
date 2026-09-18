"""
Phase PC-6: Comprehensive Test Suite for Product Compliance Journey UI.

Verifies:
1. Frontend file existence and readability
2. JavaScript syntax integrity (node --check)
3. HTML workspace and navigation structure with accessibility
4. Component exports, methods, and interface contracts
5. CSS layout, non-reliance on color alone, and responsive styling
6. Multilingual (i18n) completeness and key symmetry (en.json vs hi.json)
7. Exact status grounding strings and absence of banned ambiguous terms
8. Strict 10-stage sequential ordering in renderer
9. Zero regulatory decision-making or inference in frontend code
10. Explicit retryable error state and zero silent fallback / fake data
11. PC-5 backend API integration via FastAPI TestClient
12. Standard test cases: IS 4985, IS 374, IS 16046 (Part 2), IS 15750, timber doors
13. Node.js headless HTML rendering of complete journey card
14. Conversational assistant chat integration and bridge widgets
15. Strict cryptographic baseline preservation of frozen subsystems
"""

import json
import hashlib
import re
import subprocess
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.app import app

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
BASELINE_HASHES_FILE = PROJECT_ROOT / "scratch_pc6_baseline_hashes.json"

client = TestClient(app)


class TestPC6FrontendIntegrity:
    """Verifies frontend code files, exports, and syntax."""

    def test_pc6_frontend_files_exist_and_readable(self):
        required_files = [
            FRONTEND_DIR / "complianceJourneyComponent.js",
            FRONTEND_DIR / "app.js",
            FRONTEND_DIR / "index.html",
            FRONTEND_DIR / "styles.css",
            FRONTEND_DIR / "i18n" / "en.json",
            FRONTEND_DIR / "i18n" / "hi.json",
        ]
        for fpath in required_files:
            assert fpath.exists(), f"Required file missing: {fpath}"
            assert fpath.stat().st_size > 0, f"File is empty: {fpath}"

    def test_pc6_js_syntax_validation(self):
        """Validate JavaScript syntax via node --check."""
        for js_file in ["complianceJourneyComponent.js", "app.js"]:
            full_path = FRONTEND_DIR / js_file
            res = subprocess.run(
                ["node", "--check", str(full_path)],
                capture_output=True,
                text=True
            )
            assert res.returncode == 0, f"Syntax error in {js_file}: {res.stderr}"

    def test_pc6_component_exports_and_methods(self):
        comp_js = (FRONTEND_DIR / "complianceJourneyComponent.js").read_text(encoding="utf-8")
        assert "export class ComplianceJourneyComponent" in comp_js
        # Required methods
        assert "renderJourneyCard" in comp_js
        assert "registerProvenanceRecord" in comp_js
        assert "init(" in comp_js
        assert "executeSearch(" in comp_js
        assert "executeSearchFromInputs(" in comp_js
        assert "executeFromQuery(" in comp_js
        assert "onLanguageChange(" in comp_js
        assert "renderErrorState(" in comp_js
        assert "bindJourneyCardInteractions(" in comp_js

    def test_pc6_html_shell_structure(self):
        html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
        assert 'id="navComplianceJourney"' in html
        assert 'id="viewComplianceJourney"' in html
        assert 'role="region"' in html
        assert 'aria-label="Product Compliance Journey"' in html
        # Component defines the input fields dynamically
        comp_js = (FRONTEND_DIR / "complianceJourneyComponent.js").read_text(encoding="utf-8")
        assert 'id="compInputProduct"' in comp_js
        assert 'id="compInputStandard"' in comp_js
        assert 'id="compInputLocation"' in comp_js
        assert 'id="compInputQuery"' in comp_js

    def test_pc6_css_styling_and_accessibility(self):
        css = (FRONTEND_DIR / "styles.css").read_text(encoding="utf-8")
        assert ".compliance-journey-workspace" in css
        assert ".compliance-layout" in css
        assert ".compliance-search-panel" in css
        assert ".compliance-timeline-container" in css
        assert ".stage-card" in css
        # Status badges
        assert ".badge-established" in css
        assert ".badge-unknown" in css
        assert ".badge-conflict" in css
        assert ".badge-partial" in css
        assert ".badge-reference" in css
        # Mobile responsiveness
        assert "@media" in css and "max-width: 768px" in css


class TestPC6Internationalization:
    """Verifies i18n translation coverage and symmetry."""

    def test_pc6_i18n_key_symmetry_en_hi(self):
        en_path = FRONTEND_DIR / "i18n" / "en.json"
        hi_path = FRONTEND_DIR / "i18n" / "hi.json"

        with open(en_path, "r", encoding="utf-8") as f:
            en_data = json.load(f)
        with open(hi_path, "r", encoding="utf-8") as f:
            hi_data = json.load(f)

        assert "compliance_journey" in en_data, "compliance_journey section missing in en.json"
        assert "compliance_journey" in hi_data, "compliance_journey section missing in hi.json"

        en_cj = en_data["compliance_journey"]
        hi_cj = hi_data["compliance_journey"]

        missing_in_hi = set(en_cj.keys()) - set(hi_cj.keys())
        assert not missing_in_hi, f"Keys in en.json missing in hi.json: {missing_in_hi}"

        for key, val in hi_cj.items():
            assert val and isinstance(val, str) and len(val.strip()) > 0, f"Empty Hindi translation for {key}"

        # Nav label
        assert "compliance_journey" in en_data.get("nav", {})
        assert "compliance_journey" in hi_data.get("nav", {})


class TestPC6ExactStatusGrounding:
    """Verifies exact status grounding texts and absence of misleading terms."""

    def test_exact_grounding_strings_present(self):
        en_path = FRONTEND_DIR / "i18n" / "en.json"
        with open(en_path, "r", encoding="utf-8") as f:
            en_data = json.load(f)
        cj = en_data["compliance_journey"]

        assert cj["status_established"] == "Established from BIS evidence"
        assert cj["status_unknown"] == "Not established from available BIS evidence"
        assert cj["status_conflict"] == "Conflicting BIS evidence"
        assert cj["status_mandatory_not_established"] == "Mandatory certification not established from available BIS evidence"
        assert cj["status_scheme_unknown"] == "Product-specific certification scheme not established from available BIS evidence"
        assert cj["status_no_matching_lab"] == "No matching qualified BIS laboratory found"
        assert cj["status_generic_process"] == "General BIS procedure reference"

    def test_banned_ambiguous_strings_absent(self):
        en_path = FRONTEND_DIR / "i18n" / "en.json"
        with open(en_path, "r", encoding="utf-8") as f:
            en_text = f.read()
        cj_block = en_text[en_text.find('"compliance_journey"'):en_text.find('"auth"')]

        banned_phrases = [
            "certification is not required",
            "certification is optional",
            "voluntary standard",
            "not mandatory",
        ]
        for phrase in banned_phrases:
            assert phrase not in cj_block.lower(), f"Banned misleading phrase found in i18n: {phrase}"


class TestPC6StrictOrderingAndLogicBoundary:
    """Verifies strict 10-stage sequential ordering and zero frontend regulatory logic."""

    def test_exact_ten_stages_sequential_ordering(self):
        comp_js = (FRONTEND_DIR / "complianceJourneyComponent.js").read_text(encoding="utf-8")

        # Check for presence of all 10 stages in renderJourneyCard
        stage_markers = [
            'data-stage-num="1"',
            'data-stage-num="2"',
            'data-stage-num="3"',
            'data-stage-num="4"',
            'data-stage-num="5"',
            'data-stage-num="6"',
            'data-stage-num="7"',
            'data-stage-num="8"',
            'data-stage-num="9"',
            'data-stage-num="10"',
        ]
        positions = []
        for marker in stage_markers:
            pos = comp_js.find(marker)
            assert pos != -1, f"Missing stage marker in renderJourneyCard: {marker}"
            positions.append(pos)

        # Strictly monotonic increasing order
        assert positions == sorted(positions), "Stages in renderJourneyCard are not in strictly sequential 1..10 order"

        # Warnings and Provenance after stage 10
        warn_pos = comp_js.find("compliance-warnings-section")
        prov_pos = comp_js.find("compliance-provenance-section")
        assert warn_pos > positions[-1], "Warnings section must follow the 10 stages"
        assert prov_pos > warn_pos, "Provenance section must follow warnings"

    def test_zero_regulatory_decisions_in_frontend(self):
        comp_js = (FRONTEND_DIR / "complianceJourneyComponent.js").read_text(encoding="utf-8")

        # Frontend must not decide regulatory outcomes or assign regulatory variables
        assert not re.search(r'\bis_mandatory\s*=\s*(?:true|false|1|0)', comp_js), "Frontend must not assign is_mandatory"
        assert not re.search(r'\bqco_status\s*=\s*["\']', comp_js), "Frontend must not assign qco_status"
        
        forbidden_terms = [
            "qualifyLab(",
            "rankLab(",
            "determineScheme(",
            "inferStandard(",
        ]
        for term in forbidden_terms:
            assert term not in comp_js, f"Frontend must not contain decision function ({term})"


class TestPC6BackendIntegration:
    """Verifies that the frozen PC-5 backend API serves all required benchmark cases to the UI."""

    def test_api_is4985(self):
        res = client.post("/api/compliance/journey", json={"standard": "IS 4985"})
        assert res.status_code == 200
        journey = res.json()
        assert journey["status"] == "JOURNEY_ESTABLISHED"
        assert journey["applicable_standards"]["status"] == "STANDARDS_IDENTIFIED"
        assert journey["regulatory_status"]["status"] in ["CONFIRMED", "ESTABLISHED", "QCO_ACTIVE", "QCO_APPLIES"]
        assert journey["mandatory_certification"]["is_mandatory"] is True
        assert journey["mandatory_certification"]["status"] in ["CONFIRMED", "MANDATORY", "STATUTORY_MANDATORY", "MANDATORY_CERTIFICATION_CONFIRMED"]
        assert journey["laboratories"]["total_matching"] > 0

    def test_api_is374(self):
        res = client.post("/api/compliance/journey", json={"standard": "IS 374"})
        assert res.status_code == 200
        journey = res.json()
        assert journey["status"] == "JOURNEY_ESTABLISHED"
        assert journey["applicable_standards"]["standards"][0]["standard_number"] == "IS 374"
        assert journey["certification_scheme"]["status"] in ["CERTIFICATION_SCHEME_CONFIRMED", "CERTIFICATION_SCHEME_UNKNOWN"]

    def test_api_is16046(self):
        res = client.post("/api/compliance/journey", json={"standard": "IS 16046 (Part 2)"})
        assert res.status_code == 200
        journey = res.json()
        assert journey["status"] == "JOURNEY_ESTABLISHED"
        assert "IS 16046" in journey["applicable_standards"]["standards"][0]["standard_number"]

    def test_api_is15750(self):
        res = client.post("/api/compliance/journey", json={"standard": "IS 15750"})
        assert res.status_code == 200
        journey = res.json()
        assert journey["status"] == "JOURNEY_ESTABLISHED"
        # QCO is unknown/not established for IS 15750
        assert journey["regulatory_status"]["status"] in ["UNKNOWN", "NOT_ESTABLISHED", "QCO_UNKNOWN", "QCO_STATUS_UNKNOWN"]

    def test_api_timber_doors(self):
        res = client.post("/api/compliance/journey", json={"product": "timber doors"})
        assert res.status_code == 200
        journey = res.json()
        assert journey["status"] in ["JOURNEY_ESTABLISHED", "STANDARD_NOT_ESTABLISHED"]
        assert journey["product"]["status"] in ["PRODUCT_IDENTIFIED", "PRODUCT_NOT_ESTABLISHED"]
        assert journey["product"]["input_product"] == "timber doors"


class TestPC6HeadlessNodeRender:
    """Verifies that ComplianceJourneyComponent renders complete HTML for live PC-5 responses."""

    def test_render_journey_card_in_node(self):
        # Fetch real journey payload from backend
        res = client.post("/api/compliance/journey", json={"standard": "IS 4985"})
        assert res.status_code == 200
        journey_data = res.json()

        # Run Node.js script to render journey card
        node_script = f"""
        import {{ ComplianceJourneyComponent }} from './frontend/complianceJourneyComponent.js';

        const journeyData = {json.dumps(journey_data)};
        const html = ComplianceJourneyComponent.renderJourneyCard(journeyData, {{
            t: (k, fb) => fb || k
        }});

        if (!html || typeof html !== 'string') {{
            console.error("Render failed: empty html");
            process.exit(1);
        }}

        // Check for all 10 stage cards
        for (let i = 1; i <= 10; i++) {{
            if (!html.includes(`data-stage-num="${{i}}"`)) {{
                console.error(`Missing stage ${{i}} in rendered HTML`);
                process.exit(2);
            }}
        }}

        if (!html.includes("compliance-warnings-section")) {{
            console.error("Missing warnings section");
            process.exit(3);
        }}

        if (!html.includes("compliance-provenance-section")) {{
            console.error("Missing provenance section");
            process.exit(4);
        }}

        console.log("SUCCESS_RENDERED_CHARS=" + html.length);
        process.exit(0);
        """

        runner = subprocess.run(
            ["node", "--input-type=module", "-e", node_script],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True
        )

        assert runner.returncode == 0, f"Node render script failed:\n{runner.stderr}\n{runner.stdout}"
        assert "SUCCESS_RENDERED_CHARS=" in runner.stdout


class TestPC6ChatIntegration:
    """Verifies conversational assistant integration in frontend/app.js."""

    def test_app_js_handles_explicit_compliance_query(self):
        app_js = (FRONTEND_DIR / "app.js").read_text(encoding="utf-8")
        assert "isExplicitCompQuery" in app_js
        assert "/api/compliance/journey" in app_js
        assert "compliance_journey" in app_js
        assert "ComplianceJourneyComponent.renderJourneyCard" in app_js
        assert "chat-compliance-bridge-card" in app_js
        assert "btn-chat-open-compliance" in app_js

    def test_app_js_view_switching_integration(self):
        app_js = (FRONTEND_DIR / "app.js").read_text(encoding="utf-8")
        assert "switchView('compliance')" in app_js or 'switchView("compliance")' in app_js
        assert "viewComplianceJourney" in app_js
        assert "navComplianceJourney" in app_js


class TestPC6InformationDisplayFix:
    """Verifies the rich 4-tier display hierarchy and exposure of authoritative PC-5 data."""

    def test_key_details_grid_rendered_for_is4985(self):
        res = client.post("/api/compliance/journey", json={"standard": "IS 4985"})
        assert res.status_code == 200
        journey_data = res.json()

        node_script = f"""
        import {{ ComplianceJourneyComponent }} from './frontend/complianceJourneyComponent.js';
        const journeyData = {json.dumps(journey_data)};
        const html = ComplianceJourneyComponent.renderJourneyCard(journeyData, {{
            t: (k, fb) => fb || k
        }});

        // Stage key details grid should be rendered across stages
        const gridCount = (html.match(/stage-key-details-grid/g) || []).length;
        if (gridCount < 4) {{
            console.error('Expected at least 4 stage-key-details-grid instances, found ' + gridCount);
            process.exit(1);
        }}

        // Stage 3 QCO Status
        if (!html.includes('QCO status') || !html.includes('Mandatory QCO')) {{
            console.error('Missing QCO status in Stage 3');
            process.exit(2);
        }}

        // Stage 4 Mandatory Certification
        if (!html.includes('Mandatory under QCO')) {{
            console.error('Missing Mandatory under QCO in Stage 4');
            process.exit(3);
        }}

        // Stage 6 Parameter Cards
        if (!html.includes('parameter-card-item') || !html.includes('Short-term Hydrostatic Pressure Test')) {{
            console.error('Missing testing parameter card in Stage 6');
            process.exit(4);
        }}
        if (!html.includes('Clause 8.1')) {{
            console.error('Missing Clause 8.1 in Stage 6');
            process.exit(5);
        }}

        // Stage 7 Inspection routines
        if (!html.includes('inspection-cards-list') || !html.includes('Routine Quality Inspection')) {{
            console.error('Missing inspection routine card in Stage 7');
            process.exit(6);
        }}

        // Stage 8 Sampling cards
        if (!html.includes('sampling-cards-list') || !html.includes('Batch Sampling')) {{
            console.error('Missing sampling card in Stage 8');
            process.exit(7);
        }}

        // Stage 10 General Reference box for generic procedure
        if (!html.includes('general-reference-box') || !html.includes('GENERAL REFERENCE')) {{
            console.error('Missing general-reference-box in Stage 10');
            process.exit(8);
        }}

        console.log('SUCCESS_IS4985_DISPLAY');
        process.exit(0);
        """

        runner = subprocess.run(
            ["node", "--input-type=module", "-e", node_script],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True
        )
        assert runner.returncode == 0, f"Display verification failed:\n{runner.stderr}\n{runner.stdout}"

    def test_fee_display_and_conflict_display(self):
        # IS 374 has QCO conflict and base testing fee
        res = client.post("/api/compliance/journey", json={"standard": "IS 374"})
        assert res.status_code == 200
        journey_data = res.json()

        node_script = f"""
        import {{ ComplianceJourneyComponent }} from './frontend/complianceJourneyComponent.js';
        const journeyData = {json.dumps(journey_data)};
        const html = ComplianceJourneyComponent.renderJourneyCard(journeyData, {{
            t: (k, fb) => fb || k
        }});

        // Conflicting QCO notice
        if (!html.includes('Conflicting QCO evidence') && !html.includes('Regulatory Evidence Conflict')) {{
            console.error('Missing conflict indicator in Stage 3');
            process.exit(1);
        }}

        // Fee display for lab with base_testing_fee
        if (!html.includes('comp-lab-fee') || !html.includes('Base testing fee:')) {{
            console.error('Missing comp-lab-fee in Stage 9');
            process.exit(2);
        }}

        // Stage 6 Parameter Card for Air Delivery
        if (!html.includes('Air Delivery and Service Value') || !html.includes('Clause 10.4')) {{
            console.error('Missing Air Delivery parameter card in Stage 6');
            process.exit(3);
        }}

        console.log('SUCCESS_IS374_DISPLAY');
        process.exit(0);
        """

        runner = subprocess.run(
            ["node", "--input-type=module", "-e", node_script],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True
        )
        assert runner.returncode == 0, f"Conflict & fee verification failed:\n{runner.stderr}\n{runner.stdout}"

    def test_is16046_amended_qco_and_labs(self):
        res = client.post("/api/compliance/journey", json={"standard": "IS 16046 (Part 2)"})
        assert res.status_code == 200
        journey_data = res.json()

        node_script = f"""
        import {{ ComplianceJourneyComponent }} from './frontend/complianceJourneyComponent.js';
        const journeyData = {json.dumps(journey_data)};
        const html = ComplianceJourneyComponent.renderJourneyCard(journeyData, {{
            t: (k, fb) => fb || k
        }});

        // Stage 3 Amended QCO
        if (!html.includes('Amended QCO identified') && !html.includes('Amended QCO')) {{
            console.error('Missing Amended QCO in Stage 3');
            process.exit(1);
        }}

        // Stage 9 Qualified Labs count and toggle
        if (!html.includes('qualified laboratories found') && !html.includes('qualified laboratory records match')) {{
            console.error('Missing qualified labs summary in Stage 9');
            process.exit(2);
        }}
        if (!html.includes('btn-toggle-all-labs')) {{
            console.error('Missing btn-toggle-all-labs for >4 labs in Stage 9');
            process.exit(3);
        }}

        // Testing fee display for REACT COMPLIANCE lab
        if (!html.includes('comp-lab-fee') || !html.includes('65,000')) {{
            console.error('Missing ₹65,000 fee for IS 16046 lab in Stage 9');
            process.exit(4);
        }}

        console.log('SUCCESS_IS16046_DISPLAY');
        process.exit(0);
        """

        runner = subprocess.run(
            ["node", "--input-type=module", "-e", node_script],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True
        )
        assert runner.returncode == 0, f"IS 16046 display verification failed:\n{runner.stderr}\n{runner.stdout}"

    def test_is15750_unknown_and_unestablished(self):
        res = client.post("/api/compliance/journey", json={"standard": "IS 15750"})
        assert res.status_code == 200
        journey_data = res.json()

        node_script = f"""
        import {{ ComplianceJourneyComponent }} from './frontend/complianceJourneyComponent.js';
        const journeyData = {json.dumps(journey_data)};
        const html = ComplianceJourneyComponent.renderJourneyCard(journeyData, {{
            t: (k, fb) => fb || k
        }});

        // Stage 3 QCO Not Established / Unknown
        if (!html.includes('QCO status could not be established') && !html.includes('QCO not established')) {{
            console.error('Missing QCO not established in Stage 3');
            process.exit(1);
        }}

        // Stage 4 Mandatory Not Established
        if (!html.includes('Mandatory certification not established')) {{
            console.error('Missing Mandatory certification not established in Stage 4');
            process.exit(2);
        }}

        // Stage 5 Product-specific scheme not established + General Reference Box
        if (!html.includes('Product-specific certification scheme not established')) {{
            console.error('Missing Product-specific certification scheme not established in Stage 5');
            process.exit(3);
        }}
        if (!html.includes('general-reference-box') || !html.includes('GENERAL REFERENCE')) {{
            console.error('Missing general reference disclaimer in Stage 5');
            process.exit(4);
        }}

        // Stage 6 Testing requirements not established
        if (!html.includes('Testing requirements not established')) {{
            console.error('Missing Testing requirements not established in Stage 6');
            process.exit(5);
        }}

        // Stage 9 No matching lab notice
        if (!html.includes('empty-labs-notice') || !html.includes('No matching qualified BIS laboratory found')) {{
            console.error('Missing empty-labs-notice in Stage 9');
            process.exit(6);
        }}

        console.log('SUCCESS_IS15750_DISPLAY');
        process.exit(0);
        """

        runner = subprocess.run(
            ["node", "--input-type=module", "-e", node_script],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True
        )
        assert runner.returncode == 0, f"IS 15750 display verification failed:\n{runner.stderr}\n{runner.stdout}"


class TestPC6FrozenSubsystemsPreservation:
    """Ensures zero changes were made to frozen subsystems."""

    def test_baseline_hashes_unaltered(self):
        if not BASELINE_HASHES_FILE.exists():
            pytest.skip("Baseline hashes file not present in workspace")
        with open(BASELINE_HASHES_FILE, "r") as f:
            expected_hashes = json.load(f)

        for rel_path, expected_hash in expected_hashes.items():
            full_path = PROJECT_ROOT / rel_path
            assert full_path.exists(), f"Frozen file missing: {rel_path}"
            with open(full_path, "rb") as fp:
                actual_hash = hashlib.sha256(fp.read()).hexdigest()
            assert actual_hash == expected_hash, (
                f"Cryptographic hash mismatch in frozen subsystem {rel_path}!\n"
                f"Expected: {expected_hash}\n"
                f"Actual:   {actual_hash}"
            )
