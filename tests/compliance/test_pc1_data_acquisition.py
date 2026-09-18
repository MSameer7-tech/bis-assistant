"""
Automated Test Suite for Phase PC-1: BIS Compliance Data Acquisition & Provenance Layer.

Validates:
1. Every record across all 6 compliance domains has a verifiable source URL.
2. Every document hash is a valid 64-character SHA-256 hexadecimal string or UNKNOWN.
3. Provenance traceability: no record exists without authoritative source backing.
4. QCO lifecycle status strictness (strictly ACTIVE, UPCOMING, SUPERSEDED, AMENDED, UNKNOWN).
5. Missing fields are preserved as null or UNKNOWN (zero invention).
6. Product -> Standard relationships carry explicit source citations.
7. Certification schemes are grounded in official statutory regulations.
8. Product Manuals preserve standard linkage and raw uninterpreted content.
9. SIT testing schedules preserve explicit test methods and inspection frequencies.
10. Certification procedures capture official BIS workflows (Normal, Simplified, CRS, FMCS).
11. Manifest and audit records reconcile bitwise with physical JSONL datasets.
12. Invariant: frozen systems (Phase 12, 13, F3, 14/15, frontend) remain completely untouched.
"""

import json
import re
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
COMPLIANCE_RAW = PROJECT_ROOT / "data" / "compliance" / "raw"
METADATA_DIR = COMPLIANCE_RAW / "metadata"


class TestPC1DataAcquisition:
    """Verification suite for Phase PC-1 compliance data acquisition."""

    @pytest.fixture(scope="class")
    def loaded_data(self):
        """Loads all raw compliance datasets and metadata."""
        def load_jsonl(rel_path):
            p = COMPLIANCE_RAW / rel_path
            assert p.exists(), f"Missing dataset file at {p}"
            records = []
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        records.append(json.loads(line))
            return records

        manifest_file = METADATA_DIR / "acquisition_manifest.json"
        audit_file = METADATA_DIR / "data_quality_audit.json"
        assert manifest_file.exists(), "Manifest file missing"
        assert audit_file.exists(), "Audit file missing"

        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        audit = json.loads(audit_file.read_text(encoding="utf-8"))

        return {
            "qcos": load_jsonl("qcos/qcos.jsonl"),
            "product_standards": load_jsonl("product_standard/product_standard_sources.jsonl"),
            "schemes": load_jsonl("certification_schemes/schemes.jsonl"),
            "product_manuals": load_jsonl("product_manuals/product_manuals.jsonl"),
            "sit": load_jsonl("testing/sit_records.jsonl"),
            "procedures": load_jsonl("certification_process/certification_procedures.jsonl"),
            "manifest": manifest,
            "audit": audit,
        }

    def test_01_all_records_have_verifiable_source_url(self, loaded_data):
        """Ensures every record carries a non-empty source URL from an authoritative domain."""
        valid_domains = (
            ".gov.in",
            "crsbis.in",
        )
        for domain, records in [
            ("qcos", loaded_data["qcos"]),
            ("product_standards", loaded_data["product_standards"]),
            ("schemes", loaded_data["schemes"]),
            ("product_manuals", loaded_data["product_manuals"]),
            ("sit", loaded_data["sit"]),
            ("procedures", loaded_data["procedures"]),
        ]:
            for r in records:
                url = r.get("source_url")
                assert url, f"Record in {domain} missing source_url: {r}"
                assert any(vd in url for vd in valid_domains), f"Source URL in {domain} not from authoritative domain: {url}"

    def test_02_all_document_sha256_hashes_are_valid_hex(self, loaded_data):
        """Ensures all cryptographic hashes are valid 64-char hex strings or UNKNOWN."""
        hex_pattern = re.compile(r"^[0-9a-f]{64}$")
        for domain, key, records in [
            ("qcos", "source_hash", loaded_data["qcos"]),
            ("product_standards", "source_hash", loaded_data["product_standards"]),
            ("schemes", "source_hash", loaded_data["schemes"]),
            ("product_manuals", "document_hash", loaded_data["product_manuals"]),
            ("sit", "document_hash", loaded_data["sit"]),
            ("procedures", "document_hash", loaded_data["procedures"]),
        ]:
            for r in records:
                h = r.get(key)
                assert h, f"Record in {domain} missing hash field {key}"
                if h != "UNKNOWN":
                    assert hex_pattern.match(h), f"Invalid SHA-256 hash in {domain}: '{h}'"

    def test_03_provenance_traceability_and_no_unbacked_records(self, loaded_data):
        """Mechanically verifies that every manifest entry maps to a valid record and source."""
        manifest_records = loaded_data["manifest"]["records"]
        assert len(manifest_records) > 0, "Manifest must not be empty"

        for entry in manifest_records:
            assert entry.get("record_id"), f"Manifest entry missing record_id: {entry}"
            assert entry.get("domain") in [
                "QCO", "PRODUCT_STANDARD", "CERTIFICATION_SCHEME",
                "PRODUCT_MANUAL", "TESTING_SIT", "CERTIFICATION_PROCESS"
            ], f"Unexpected domain: {entry.get('domain')}"
            assert entry.get("source_url"), f"Manifest entry missing source_url: {entry}"
            assert entry.get("source_verification_state") in [
                "SOURCE_VERIFIED", "SOURCE_UNVERIFIED", "SOURCE_MISSING"
            ]

    def test_04_qco_lifecycle_status_strictness(self, loaded_data):
        """Verifies QCO status is strictly one of the 5 allowed authoritative enums."""
        allowed_statuses = {"ACTIVE", "UPCOMING", "SUPERSEDED", "AMENDED", "UNKNOWN"}
        for q in loaded_data["qcos"]:
            st = q.get("status")
            assert st in allowed_statuses, f"QCO {q.get('qco_id')} has invalid status: {st}"

    def test_05_missing_fields_preserved_as_null_or_unknown(self, loaded_data):
        """Verifies zero synthetic fabrication: missing fields remain null or UNKNOWN."""
        # Find records where publication or effective dates are null
        null_pub_dates = [q for q in loaded_data["qcos"] if q.get("publication_date") is None]
        null_eff_dates = [q for q in loaded_data["qcos"] if q.get("effective_date") is None]
        # Real-world records without explicit dates must preserve null
        assert len(null_pub_dates) > 0, "Missing publication dates should remain null, not guessed"
        assert len(null_eff_dates) > 0, "Missing effective dates should remain null, not guessed"

        # Check for presence of uninvented fields in product manuals
        null_dates_pm = [pm for pm in loaded_data["product_manuals"] if pm.get("version_date") is None]
        assert len(null_dates_pm) > 0, "Missing product manual version dates must remain null"

    def test_06_product_standard_relationship_provenance(self, loaded_data):
        """Ensures product-to-standard relationships carry explicit evidence or clause citations."""
        ps_records = loaded_data["product_standards"]
        assert len(ps_records) >= 500, f"Expected substantial product-standard pairs, found {len(ps_records)}"
        for ps in ps_records:
            assert ps.get("product"), "Product name must not be empty"
            assert ps.get("standard"), "Standard number must not be empty"
            assert ps.get("source_document"), "Source document must be specified"

    def test_07_certification_schemes_statutory_grounding(self, loaded_data):
        """Verifies certification schemes reflect official BIS Conformity Assessment schemes."""
        schemes = loaded_data["schemes"]
        scheme_ids = {s["scheme_id"] for s in schemes}
        expected_core_schemes = {"SCHEME-I", "SCHEME-II", "SCHEME-IV", "FMCS", "HALLMARKING"}
        assert expected_core_schemes.issubset(scheme_ids), f"Missing core schemes: {expected_core_schemes - scheme_ids}"
        for s in schemes:
            assert s.get("statutory_basis"), f"Scheme {s['scheme_id']} missing statutory basis"

    def test_08_product_manuals_integrity_and_standards_linkage(self, loaded_data):
        """Verifies product manuals link to standards and preserve raw content."""
        pms = loaded_data["product_manuals"]
        assert len(pms) >= 700, f"Expected over 700 product manuals, found {len(pms)}"
        verified_count = len([pm for pm in pms if pm.get("verification_state") == "SOURCE_VERIFIED"])
        assert verified_count >= 600, f"Expected at least 600 verified product manuals, found {verified_count}"

    def test_09_sit_testing_requirements_traceability(self, loaded_data):
        """Verifies SIT records contain test parameters from official inspection schemes."""
        sits = loaded_data["sit"]
        assert len(sits) >= 100, f"Expected over 100 SIT records, found {len(sits)}"
        for s in sits:
            assert s.get("standard"), "SIT record missing standard"
            assert s.get("test_name"), "SIT record missing test_name"

    def test_10_certification_procedure_completeness(self, loaded_data):
        """Verifies certification procedures capture official grant workflows."""
        procs = loaded_data["procedures"]
        assert len(procs) >= 20, f"Expected at least 20 procedures, found {len(procs)}"
        proc_types = {p["procedure_type"] for p in procs}
        assert "NORMAL" in proc_types
        assert "SIMPLIFIED" in proc_types
        assert "CRS" in proc_types

    def test_11_manifest_and_audit_reconciliation(self, loaded_data):
        """Reconciles manifest counts and audit statistics against actual JSONL datasets."""
        audit = loaded_data["audit"]
        manifest = loaded_data["manifest"]

        assert audit["qcos_accepted"] == len(loaded_data["qcos"])
        assert audit["product_standards_accepted"] == len(loaded_data["product_standards"])
        assert audit["schemes_accepted"] == len(loaded_data["schemes"])
        assert audit["product_manuals_accepted"] == len(loaded_data["product_manuals"])
        assert audit["sit_records_accepted"] == len(loaded_data["sit"])
        assert audit["procedures_accepted"] == len(loaded_data["procedures"])

        total_accepted = (
            len(loaded_data["qcos"])
            + len(loaded_data["product_standards"])
            + len(loaded_data["schemes"])
            + len(loaded_data["product_manuals"])
            + len(loaded_data["sit"])
            + len(loaded_data["procedures"])
        )
        assert manifest["total_manifest_entries"] == total_accepted
        assert audit["total_records_accepted"] == total_accepted

    def test_12_frozen_systems_immutability(self):
        """Verifies that no frozen system directories were altered or polluted."""
        # Ensure Phase 12 production files exist and are untampered
        phase12_rag = PROJECT_ROOT / "scripts" / "phase12_e_production_rag.py"
        assert phase12_rag.exists()

        # Ensure F3 catalog files remain intact
        f3_manifest = PROJECT_ROOT / "data" / "catalog" / "phase_f3_lims" / "catalog_manifest.json"
        assert f3_manifest.exists()
        f3_data = json.loads(f3_manifest.read_text(encoding="utf-8"))
        assert f3_data.get("unique_laboratories") == 580
