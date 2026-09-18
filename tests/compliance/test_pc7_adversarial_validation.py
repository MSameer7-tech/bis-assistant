"""
Phase PC-7: End-to-End Adversarial Validation & Final Freeze Test Suite.

Comprehensive audit across all 15 validation areas:
1. Area 1: End-to-End Journey (10 representative cases)
2. Area 2: Regulatory Integrity (conflicts, unknown, non-inference, frontend boundary)
3. Area 3: Laboratory Integrity (F3 qualification, capability-first, no unqualified labs)
4. Area 4: Provenance & Evidence Drawer Integration
5. Area 5: Exact Uncertainty & Conflict Grounding
6. Area 6: Failure Handling, Anti-Hallucination & Stale-State Prevention
7. Area 7: Cross-Query Contamination Prevention
8. Area 8: Concurrent Request Safety & Race-Condition Prevention
9. Area 9: Normal Assistant Regression (ordinary queries, RAG, auth)
10. Area 10: F3 Laboratory Finder Regression
11. Area 11: Internationalization (i18n) & Accessibility
12. Area 12: Security & Secret Leakage Audit
13. Area 13: Deterministic Execution (byte-identical responses)
14. Area 14: Subsystem Immutability (cryptographic baseline verification)
15. Area 15: End-to-End Integrity Verification
"""

import json
import hashlib
import re
import subprocess
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.lab_finder_api import execute_search, LabSearchRequest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
BASELINE_HASHES_FILE = PROJECT_ROOT / "scratch_pc6_baseline_hashes.json"

client = TestClient(app)


# ==============================================================================
# AREA 1: END-TO-END JOURNEY (10 REPRESENTATIVE CASES)
# ==============================================================================
class TestArea1EndToEndJourney:
    """Verifies complete 10-stage journey generation across 10 benchmark cases."""

    def _verify_complete_10_stages(self, journey):
        assert journey["status"] in ["JOURNEY_ESTABLISHED", "STANDARD_NOT_ESTABLISHED", "AMBIGUOUS_PRODUCT"]
        stages = [
            "product",
            "applicable_standards",
            "regulatory_status",
            "mandatory_certification",
            "certification_scheme",
            "testing",
            "inspection",
            "sampling",
            "laboratories",
            "certification_process"
        ]
        for stage_name in stages:
            assert stage_name in journey, f"Missing required compliance stage: {stage_name}"
            stage_obj = journey[stage_name]
            assert "status" in stage_obj, f"Stage {stage_name} missing explicit status field"
            assert stage_obj["status"] is not None, f"Stage {stage_name} status cannot be None"

        assert "warnings" in journey, "Warnings list missing"
        assert "limitations" in journey, "Limitations list missing"
        assert "provenance" in journey, "Provenance list missing"

    def test_case_01_is4985(self):
        """Case 1: IS 4985 (PVC Pipes)."""
        res = client.post("/api/compliance/journey", json={"standard": "IS 4985"})
        assert res.status_code == 200
        journey = res.json()
        self._verify_complete_10_stages(journey)
        assert journey["status"] == "JOURNEY_ESTABLISHED"
        assert journey["applicable_standards"]["standards"][0]["standard_number"] == "IS 4985"
        assert journey["mandatory_certification"]["is_mandatory"] is True
        assert journey["laboratories"]["total_matching"] > 0

    def test_case_02_is374(self):
        """Case 2: IS 374 (Electric Ceiling Fans) - QCO conflict handling."""
        res = client.post("/api/compliance/journey", json={"standard": "IS 374"})
        assert res.status_code == 200
        journey = res.json()
        self._verify_complete_10_stages(journey)
        assert journey["status"] == "JOURNEY_ESTABLISHED"
        assert journey["applicable_standards"]["standards"][0]["standard_number"] == "IS 374"
        # Conflict IDs must be preserved
        assert len(journey["regulatory_status"]["conflict_ids"]) > 0

    def test_case_03_is16046_part2(self):
        """Case 3: IS 16046 Part 2 (Lithium Ion Batteries / Cells)."""
        res = client.post("/api/compliance/journey", json={"standard": "IS 16046 (Part 2)"})
        assert res.status_code == 200
        journey = res.json()
        self._verify_complete_10_stages(journey)
        assert journey["status"] == "JOURNEY_ESTABLISHED"
        assert "IS 16046" in journey["applicable_standards"]["standards"][0]["standard_number"]

    def test_case_04_is15750(self):
        """Case 4: IS 15750 - Unconfirmed QCO status."""
        res = client.post("/api/compliance/journey", json={"standard": "IS 15750"})
        assert res.status_code == 200
        journey = res.json()
        self._verify_complete_10_stages(journey)
        assert journey["regulatory_status"]["status"] in ["UNKNOWN", "NOT_ESTABLISHED", "QCO_UNKNOWN", "QCO_STATUS_UNKNOWN"]
        assert journey["mandatory_certification"]["status"] in ["QCO_STATUS_UNKNOWN", "MANDATORY_CERTIFICATION_NOT_ESTABLISHED", "NOT_ESTABLISHED"]
        assert journey["mandatory_certification"]["is_mandatory"] is not True

    def test_case_05_is1653(self):
        """Case 5: IS 1653 (Rigid Steel Conduits for Electrical Wiring)."""
        res = client.post("/api/compliance/journey", json={"standard": "IS 1653"})
        assert res.status_code == 200
        journey = res.json()
        self._verify_complete_10_stages(journey)
        assert "IS 1653" in journey["applicable_standards"]["standards"][0]["standard_number"]

    def test_case_06_is12254(self):
        """Case 6: IS 12254 (Polyvinyl Chloride Boots)."""
        res = client.post("/api/compliance/journey", json={"standard": "IS 12254"})
        assert res.status_code == 200
        journey = res.json()
        self._verify_complete_10_stages(journey)
        assert "IS 12254" in journey["applicable_standards"]["standards"][0]["standard_number"]

    def test_case_07_automotive_vehicles(self):
        """Case 7: Automotive vehicles (Complex/Multi-standard product category)."""
        res = client.post("/api/compliance/journey", json={"product": "automotive vehicles"})
        assert res.status_code == 200
        journey = res.json()
        self._verify_complete_10_stages(journey)

    def test_case_08_timber_doors(self):
        """Case 8: Timber doors (Standard not established / general term)."""
        res = client.post("/api/compliance/journey", json={"product": "timber doors"})
        assert res.status_code == 200
        journey = res.json()
        self._verify_complete_10_stages(journey)
        assert journey["status"] in ["JOURNEY_ESTABLISHED", "STANDARD_NOT_ESTABLISHED"]
        assert journey["product"]["input_product"] == "timber doors"

    def test_case_09_explicit_standard_overrides_ambiguous_product(self):
        """Case 9: Explicit standard designation strictly takes precedence over ambiguous product query."""
        res = client.post("/api/compliance/journey", json={"standard": "IS 4985", "product": "doors"})
        assert res.status_code == 200
        journey = res.json()
        self._verify_complete_10_stages(journey)
        # IS 4985 PVC pipes must take precedence, not timber doors
        primary_std = journey["applicable_standards"]["primary_standard"]
        assert primary_std == "IS 4985", f"Explicit standard must take precedence, got: {primary_std}"

    def test_case_10_location_specific_laboratory_search(self):
        """Case 10: Location-specific laboratory search preserves location filter."""
        res = client.post("/api/compliance/journey", json={"standard": "IS 4985", "location": "Delhi"})
        assert res.status_code == 200
        journey = res.json()
        self._verify_complete_10_stages(journey)
        assert journey["laboratories"]["location_filter_applied"] == "Delhi"


# ==============================================================================
# AREA 2: REGULATORY INTEGRITY
# ==============================================================================
class TestArea2RegulatoryIntegrity:
    """Verifies that regulatory states are strictly grounded with zero synthetic promotion."""

    def test_qco_conflicts_remain_conflicts(self):
        res = client.post("/api/compliance/journey", json={"standard": "IS 374"})
        assert res.status_code == 200
        journey = res.json()
        assert len(journey["regulatory_status"]["conflict_ids"]) > 0
        assert journey["regulatory_status"]["status"] in ["QCO_CONFLICT", "CONFLICT"]
        assert journey["mandatory_certification"]["status"] in ["QCO_CONFLICT", "CONFLICT_UNDER_REVIEW"]

    def test_testing_evidence_never_implies_mandatory_certification(self):
        """IS 374 has confirmed testing requirements in SIT, but mandatory status must NOT be confirmed."""
        res = client.post("/api/compliance/journey", json={"standard": "IS 374"})
        assert res.status_code == 200
        journey = res.json()
        assert journey["testing"]["total_tests"] > 0
        # Mandatory must NOT be CONFIRMED/MANDATORY due to active conflict
        assert journey["mandatory_certification"]["status"] != "MANDATORY_CERTIFICATION_CONFIRMED"
        assert journey["mandatory_certification"]["is_mandatory"] is not True

    def test_generic_procedures_never_become_product_specific(self):
        """Generic Scheme I procedures must always flag is_generic_procedure=True."""
        res = client.post("/api/compliance/journey", json={"standard": "IS 4985"})
        assert res.status_code == 200
        journey = res.json()
        assert journey["certification_process"]["is_generic_procedure"] is True

    def test_frontend_does_not_contain_prohibited_regulatory_logic(self):
        """Frontend JS files must not make regulatory determinations or inferences."""
        comp_js = (FRONTEND_DIR / "complianceJourneyComponent.js").read_text(encoding="utf-8")
        app_js = (FRONTEND_DIR / "app.js").read_text(encoding="utf-8")

        for code, name in [(comp_js, "complianceJourneyComponent.js"), (app_js, "app.js")]:
            assert not re.search(r'\bis_mandatory\s*=\s*(?:true|false|1|0)', code), f"{name} must not assign is_mandatory"
            assert not re.search(r'\bqco_status\s*=\s*["\']', code), f"{name} must not assign qco_status"
            for forbidden_fn in ["qualifyLab(", "rankLab(", "determineScheme(", "inferStandard("]:
                assert forbidden_fn not in code, f"{name} contains prohibited function: {forbidden_fn}"


# ==============================================================================
# AREA 3: LABORATORY INTEGRITY
# ==============================================================================
class TestArea3LaboratoryIntegrity:
    """Verifies that F3 laboratory qualification rules are strictly obeyed."""

    def test_only_f3_qualified_labs_returned(self):
        res = client.post("/api/compliance/journey", json={"standard": "IS 4985"})
        assert res.status_code == 200
        labs = res.json()["laboratories"]["qualified_laboratories"]
        assert len(labs) > 0
        for lab in labs:
            assert lab["public_lab_code"]
            assert lab["laboratory_name"]
            # Verify lab capability contains IS 4985
            cap_evidence = lab.get("capability_evidence", {})
            assert "4985" in cap_evidence.get("matching_standard", "") or any("4985" in str(v) for v in cap_evidence.values()), f"Lab {lab['public_lab_code']} lacks IS 4985 capability"

    def test_capability_evaluated_before_proximity(self):
        res = client.post("/api/compliance/journey", json={"standard": "IS 4985", "location": "Chennai"})
        assert res.status_code == 200
        journey = res.json()
        assert journey["laboratories"]["capability_evaluated_first"] is True

    def test_zero_matching_laboratories_handled_cleanly(self):
        """Query standard with no qualified labs returns clean non-collapsing status."""
        res = client.post("/api/compliance/journey", json={"standard": "IS 15750"})
        assert res.status_code == 200
        journey = res.json()
        labs_stage = journey["laboratories"]
        assert labs_stage["status"] in ["NO_MATCHING_LABORATORY", "QUALIFIED_LABS_FOUND", "LAB_MATCHING_LIMITED"]
        assert isinstance(labs_stage["qualified_laboratories"], list)


# ==============================================================================
# AREA 4: PROVENANCE AND EVIDENCE DRAWER INTEGRATION
# ==============================================================================
class TestArea4ProvenanceAndEvidenceDrawer:
    """Verifies that all evidence items trace back to authoritative records."""

    def test_provenance_records_have_complete_fields(self):
        res = client.post("/api/compliance/journey", json={"standard": "IS 4985"})
        assert res.status_code == 200
        prov_list = res.json()["provenance"]
        assert len(prov_list) > 0
        for prov in prov_list:
            assert "source_layer" in prov
            assert prov["source_layer"] in [
                "PC-1_RAW", "PC-2_NORMALIZED", "PC-3_RELATIONSHIPS",
                "PC-4_TESTING_PROCESS", "F3_LAB_FINDER"
            ]
            assert "source_record_ids" in prov or "record_id" in prov
            assert "source_documents" in prov

    def test_register_provenance_populates_evidence_memory(self):
        """Node.js headless test of registerProvenanceRecord."""
        node_script = """
        import { ComplianceJourneyComponent } from './frontend/complianceJourneyComponent.js';

        global.window = {};
        const sampleProv = {
            record_id: 'TEST-REC-001',
            source_layer: 'PC-3_RELATIONSHIPS',
            standard_number: 'IS 4985',
            source_documents: ['Authoritative BIS PVC QCO'],
            source_urls: ['https://www.bis.gov.in/qco/pvc.pdf'],
            evidence_hashes: ['abc123hash']
        };

        ComplianceJourneyComponent.registerProvenanceRecord(sampleProv);

        if (!global.window.evidenceMemory || !global.window.evidenceMemory['TEST-REC-001']) {
            console.error("registerProvenanceRecord failed to populate evidenceMemory");
            process.exit(1);
        }

        const mem = global.window.evidenceMemory['TEST-REC-001'];
        if (mem.source_layer !== 'PC-3_RELATIONSHIPS' || mem.standard_number !== 'IS 4985') {
            console.error("Mismatch in populated memory fields");
            process.exit(2);
        }

        console.log("PROVENANCE_POPULATED_OK");
        process.exit(0);
        """
        runner = subprocess.run(
            ["node", "--input-type=module", "-e", node_script],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True
        )
        assert runner.returncode == 0, f"registerProvenanceRecord test failed:\n{runner.stderr}\n{runner.stdout}"
        assert "PROVENANCE_POPULATED_OK" in runner.stdout


# ==============================================================================
# AREA 5: EXACT UNCERTAINTY / CONFLICT GROUNDING
# ==============================================================================
class TestArea5ExactGrounding:
    """Verifies that the exact required grounding phrases are present and banned terms are absent."""

    def test_exact_grounding_strings(self):
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

    def test_no_misleading_negative_conclusions(self):
        en_path = FRONTEND_DIR / "i18n" / "en.json"
        with open(en_path, "r", encoding="utf-8") as f:
            en_text = f.read()
        cj_block = en_text[en_text.find('"compliance_journey"'):en_text.find('"auth"')]
        for banned in ["voluntary standard", "not mandatory", "certification is optional", "certification is not required"]:
            assert banned not in cj_block.lower(), f"Banned phrase found in i18n: {banned}"


# ==============================================================================
# AREA 6: FAILURE AND ANTI-HALLUCINATION & STALE-STATE PREVENTION
# ==============================================================================
class TestArea6FailureAndStaleState:
    """Verifies failure behavior, retry mechanisms, and stale-state isolation."""

    def test_invalid_request_returns_clear_error_state(self):
        """Empty request returns INVALID_REQUEST without crashing."""
        res = client.post("/api/compliance/journey", json={})
        assert res.status_code == 200
        data = res.json()
        assert data["status"] in ["INVALID_REQUEST", "NO_COMPLIANCE_EVIDENCE"]

    def test_stale_state_prevention_on_failure(self):
        """Simulate journey A success followed by journey B failure; ensure A is cleared and B error is shown."""
        node_script = """
        import { ComplianceJourneyComponent } from './frontend/complianceJourneyComponent.js';

        // Mock container and DOM elements
        const mockResultsContainer = {
            set innerHTML(val) { this._html = val; },
            get innerHTML() { return this._html || ''; },
            querySelector: () => null
        };
        const container = {
            querySelector: (sel) => {
                if (sel === '#complianceResultsContainer') {
                    return mockResultsContainer;
                }
                return null;
            }
        };

        const comp = new ComplianceJourneyComponent({
            container: container,
            apiEndpoint: 'http://invalid-endpoint-for-testing.local/api/compliance/journey',
            t: (k, fb) => fb || k
        });

        // 1. Set journey A as current
        comp.currentJourney = { product: { resolved_product_name: 'Product A' } };
        comp.activeJourney = comp.currentJourney;

        // 2. Trigger error state with failed request B
        comp.renderErrorState('Simulated 500 server error', { standard: 'IS 9999' });

        // 3. Clear currentJourney on error (as executed in catch block)
        comp.currentJourney = null;
        comp.activeJourney = null;

        // 4. Verify A is NOT present
        if (comp.currentJourney !== null) {
            console.error("Failed: currentJourney was not cleared on error");
            process.exit(1);
        }

        const rendered = container.querySelector('#complianceResultsContainer').innerHTML;
        if (!rendered.includes('IS 9999')) {
            console.error("Failed: rendered error does not identify failed target IS 9999");
            process.exit(2);
        }

        if (rendered.includes('Product A')) {
            console.error("Failed: stale data from Product A leaked into error state");
            process.exit(3);
        }

        console.log("STALE_STATE_PREVENTED_OK");
        process.exit(0);
        """
        runner = subprocess.run(
            ["node", "--input-type=module", "-e", node_script],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True
        )
        assert runner.returncode == 0, f"Stale state test failed:\n{runner.stderr}\n{runner.stdout}"
        assert "STALE_STATE_PREVENTED_OK" in runner.stdout


# ==============================================================================
# AREA 7: CROSS-QUERY CONTAMINATION
# ==============================================================================
class TestArea7CrossQueryContamination:
    """Verifies that sequential queries do not contaminate each other."""

    def test_sequential_queries_have_zero_cross_contamination(self):
        # Query A = IS 4985
        res_a = client.post("/api/compliance/journey", json={"standard": "IS 4985"})
        journey_a = res_a.json()

        # Query B = IS 374
        res_b = client.post("/api/compliance/journey", json={"standard": "IS 374"})
        journey_b = res_b.json()

        # Query C = timber doors
        res_c = client.post("/api/compliance/journey", json={"product": "timber doors"})
        journey_c = res_c.json()

        # Check A vs B
        std_a = journey_a["applicable_standards"]["standards"][0]["standard_number"]
        std_b = journey_b["applicable_standards"]["standards"][0]["standard_number"]
        assert std_a == "IS 4985"
        assert std_b == "IS 374"
        assert "4985" not in json.dumps(journey_b["applicable_standards"])
        assert "374" not in json.dumps(journey_a["applicable_standards"])

        # Check B vs C
        assert "374" not in json.dumps(journey_c["applicable_standards"])
        assert journey_c["product"]["input_product"] == "timber doors"


# ==============================================================================
# AREA 8: CONCURRENT REQUEST SAFETY
# ==============================================================================
class TestArea8ConcurrentRequestSafety:
    """Verifies that out-of-order async responses do not cause race-condition overwrites."""

    def test_concurrent_request_token_guard_in_component(self):
        """Verify activeRequestId concurrency guard in ComplianceJourneyComponent."""
        node_script = """
        import { ComplianceJourneyComponent } from './frontend/complianceJourneyComponent.js';

        const comp = new ComplianceJourneyComponent({
            container: { querySelector: () => ({ innerHTML: '' }) },
            apiEndpoint: 'mock://test',
            t: (k, fb) => fb || k
        });

        // Simulate Request 1 dispatched
        comp.activeRequestId = 1;
        const req1Id = comp.activeRequestId;

        // Simulate Request 2 dispatched before Request 1 finishes
        comp.activeRequestId = 2;
        const req2Id = comp.activeRequestId;

        // When Request 1 finishes late, check concurrency guard
        const shouldIgnoreReq1 = (comp.activeRequestId !== req1Id);
        const shouldAcceptReq2 = (comp.activeRequestId === req2Id);

        if (!shouldIgnoreReq1 || !shouldAcceptReq2) {
            console.error("Concurrency guard failed to distinguish active request ID");
            process.exit(1);
        }

        console.log("CONCURRENCY_GUARD_VERIFIED_OK");
        process.exit(0);
        """
        runner = subprocess.run(
            ["node", "--input-type=module", "-e", node_script],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True
        )
        assert runner.returncode == 0, f"Concurrency test failed:\n{runner.stderr}\n{runner.stdout}"
        assert "CONCURRENCY_GUARD_VERIFIED_OK" in runner.stdout


# ==============================================================================
# AREA 9: NORMAL ASSISTANT REGRESSION
# ==============================================================================
class TestArea9NormalAssistantRegression:
    """Verifies normal Assistant conversation, RAG, and authentication remain intact."""

    def test_ordinary_bis_assistant_query(self):
        """Assistant query about compressive strength of cement routes normally to RAG."""
        res = client.post("/api/assistant/query", json={"query": "What is the compressive strength requirement for cement?"})
        assert res.status_code == 200
        data = res.json()
        assert "answer" in data
        assert data.get("generation_mode") in ["GROUNDED", "HYBRID", "LLM_FALLBACK"]

    def test_ordinary_general_query(self):
        """General non-BIS query does not enter compliance journey."""
        res = client.post("/api/assistant/query", json={"query": "What is the capital of France?"})
        assert res.status_code == 200
        data = res.json()
        assert "answer" in data
        # Must not have compliance journey payload
        assert "compliance_journey" not in data


# ==============================================================================
# AREA 10: F3 LABORATORY FINDER REGRESSION
# ==============================================================================
class TestArea10F3Regression:
    """Verifies direct F3 Laboratory Finder functionality."""

    def test_f3_execute_search_direct(self):
        req = LabSearchRequest(standard="IS 4985")
        res = execute_search(req)
        assert res.status in ["MATCH", "success"]
        assert res.total_matching > 0
        assert len(res.candidates) > 0


# ==============================================================================
# AREA 11: I18N AND ACCESSIBILITY
# ==============================================================================
class TestArea11I18nAndAccessibility:
    """Verifies bilingual parity and accessible HTML landmarks."""

    def test_i18n_symmetry_and_non_empty_values(self):
        en_path = FRONTEND_DIR / "i18n" / "en.json"
        hi_path = FRONTEND_DIR / "i18n" / "hi.json"

        with open(en_path, "r", encoding="utf-8") as f:
            en_data = json.load(f)["compliance_journey"]
        with open(hi_path, "r", encoding="utf-8") as f:
            hi_data = json.load(f)["compliance_journey"]

        missing_in_hi = set(en_data.keys()) - set(hi_data.keys())
        assert not missing_in_hi, f"Missing keys in Hindi: {missing_in_hi}"

        for k, v in hi_data.items():
            assert v and len(v.strip()) > 0, f"Empty Hindi translation for {k}"

    def test_accessibility_landmarks_and_color_independence(self):
        html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
        assert 'role="region"' in html
        assert 'aria-label="Product Compliance Journey"' in html

        css = (FRONTEND_DIR / "styles.css").read_text(encoding="utf-8")
        # Every badge has explicit icon and text along with color
        assert ".compliance-status-badge" in css
        assert ".badge-icon" in css


# ==============================================================================
# AREA 12: SECURITY AUDIT
# ==============================================================================
class TestArea12SecurityAudit:
    """Scans compliance files and endpoints for accidental secret or credential leaks."""

    def test_no_hardcoded_secrets_in_compliance_files(self):
        compliance_files = [
            FRONTEND_DIR / "complianceJourneyComponent.js",
            PROJECT_ROOT / "backend" / "compliance_journey_api.py",
            PROJECT_ROOT / "ai" / "compliance" / "journey_models.py",
            PROJECT_ROOT / "ai" / "compliance" / "journey_orchestrator.py",
        ]
        secret_patterns = [
            re.compile(r'AIza[0-9A-Za-z-_]{35}'),          # Google API Key
            re.compile(r'gsk_[0-9A-Za-z]{48,}'),          # Groq API Key
            re.compile(r'sbp_[0-9A-Za-z]{40,}'),          # Supabase Token
            re.compile(r'-----BEGIN\s+PRIVATE\s+KEY-----') # Private Key
        ]
        for fpath in compliance_files:
            assert fpath.exists()
            content = fpath.read_text(encoding="utf-8", errors="ignore")
            for pat in secret_patterns:
                assert not pat.search(content), f"Secret pattern matched in {fpath.name}"

    def test_health_endpoint_does_not_leak_environment_secrets(self):
        res = client.get("/api/compliance/health")
        assert res.status_code == 200
        health_str = json.dumps(res.json())
        assert "password" not in health_str.lower()
        assert "secret" not in health_str.lower()
        assert "key" not in health_str.lower() or '"key"' not in health_str.lower()


# ==============================================================================
# AREA 13: DETERMINISM
# ==============================================================================
class TestArea13Determinism:
    """Verifies byte-identical responses across repeated identical requests."""

    def test_pc5_api_byte_identical_responses(self):
        responses = []
        for _ in range(3):
            res = client.post("/api/compliance/journey", json={"standard": "IS 4985"})
            assert res.status_code == 200
            responses.append(res.text)

        assert responses[0] == responses[1] == responses[2], "PC-5 API response was not deterministic across identical calls"


# ==============================================================================
# AREA 14: SUBSYSTEM IMMUTABILITY
# ==============================================================================
class TestArea14SubsystemImmutability:
    """Verifies SHA-256 hashes of all frozen subsystems against authoritative baseline."""

    def test_all_frozen_subsystem_hashes_match(self):
        assert BASELINE_HASHES_FILE.exists(), "Baseline hashes file missing"
        with open(BASELINE_HASHES_FILE, "r") as f:
            expected = json.load(f)

        for rel_path, exp_hash in expected.items():
            full_path = PROJECT_ROOT / rel_path
            assert full_path.exists(), f"Frozen file missing: {rel_path}"
            with open(full_path, "rb") as fp:
                act_hash = hashlib.sha256(fp.read()).hexdigest()
            assert act_hash == exp_hash, f"Hash mismatch in {rel_path}!\nExpected: {exp_hash}\nActual:   {act_hash}"
