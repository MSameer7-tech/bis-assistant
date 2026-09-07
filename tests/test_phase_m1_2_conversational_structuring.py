import pytest
import re
import json
from scripts.phase12_f2_orchestrator import (
    orchestrate_assistant_query,
    clean_standard_title_and_category,
    group_evidence_by_standard,
    strip_unverified_disclaimers,
    classify_evidence_unit,
    resolve_standard_identity,
    is_standard_relevant_to_product,
    synthesize_multi_standard_answer,
    analyze_query_context,
    KNOWN_CANONICAL_STANDARDS
)
from scripts.phase12_e_production_rag import query_production_rag


def test_water_heater_query_excludes_is_369():
    """Test 1: 'tell me about water heater certifications' must exclude IS 369."""
    res = orchestrate_assistant_query("tell me about water heater certifications")
    assert res["status"] in ("SUFFICIENT", "PARTIAL")
    answer = res["answer"]
    assert "IS 369" not in answer, f"IS 369 found in answer:\n{answer}"


def test_water_heater_query_excludes_room_heater():
    """Test 2: 'tell me about water heater certifications' must not mention room heaters."""
    res = orchestrate_assistant_query("tell me about water heater certifications")
    answer = res["answer"].lower()
    assert "room heater" not in answer
    assert "direct acting" not in answer
    assert "space heater" not in answer


def test_relevant_water_heater_standards_remain():
    """Test 3: Relevant water heater standards (IS 15558, IS 368, IS 8978) must remain."""
    res = orchestrate_assistant_query("tell me about water heater certifications")
    answer = res["answer"]
    assert "IS 15558" in answer
    assert "IS 368" in answer
    assert "IS 8978" in answer


def test_laboratory_names_never_become_standard_titles():
    """Test 4: Lab names like 'Conformity Testing Labs' must never be promoted to standard titles."""
    res = orchestrate_assistant_query("tell me about water heater certifications")
    answer = res["answer"]
    assert "Conformity Testing Labs Pvt Ltd | IS 8978" not in answer
    assert not re.search(r"###\s*Conformity Testing Labs", answer)
    assert not re.search(r"\*\*Conformity Testing Labs.*?—", answer)
    # But laboratory availability should mention the lab cleanly
    assert "Conformity Testing Labs" in answer


def test_is_4985_product_manual_never_official_title():
    """Test 5: Product Manual title must not be used as official standard title for IS 4985."""
    res = orchestrate_assistant_query("tell me about IS 4985")
    assert res["status"] == "SUFFICIENT"
    answer = res["answer"]
    assert "BIS Product Manual for IS 4985 ()" not in answer
    assert "Official Title: BIS Product Manual" not in answer
    assert not re.search(r"Official Title:\s*Product Manual", answer, re.IGNORECASE)
    assert "Unplasticized Polyvinyl Chloride" in answer or "uPVC" in answer


def test_is_4985_hydrostatic_test_never_official_title():
    """Test 6: Test parameters (e.g. Hydrostatic Pressure Test) must never be shown as standard title."""
    res = orchestrate_assistant_query("what are the requirements of IS 4985?")
    assert res["status"] == "SUFFICIENT"
    answer = res["answer"]
    assert not re.search(r"Official Title:.*Hydrostatic", answer, re.IGNORECASE)
    assert not re.search(r"\bIS 4985.*?—\s*\*Hydrostatic", answer, re.IGNORECASE)
    # Hydrostatic should appear under testing requirements
    assert "### Key Testing Requirements" in answer
    assert "Hydrostatic" in answer


def test_is_16102_certification_marking_never_official_title():
    """Test 7: BIS Certification Marking must never be shown as official standard title."""
    res = orchestrate_assistant_query("tell me about LED lamp certification")
    assert res["status"] == "SUFFICIENT"
    answer = res["answer"]
    assert "BIS Certification Marking" not in answer
    assert not re.search(r"Official Title:.*BIS Certification Marking", answer, re.IGNORECASE)


def test_is_16102_general_never_official_title():
    """Test 8: Generic clause words like 'General' or 'Scope' must never be standard titles."""
    res = orchestrate_assistant_query("tell me about LED lamp certification")
    assert res["status"] == "SUFFICIENT"
    answer = res["answer"]
    assert not re.search(r"Official Title:\s*General\b", answer, re.IGNORECASE)
    assert not re.search(r"\bIS 16102.*?—\s*\*General\*", answer)


def test_testing_parameters_never_standard_titles():
    """Test 9: Specific unit test verifying testing parameters are classified as TESTING, not titles."""
    test_unit = {
        "record_id": "ev_reg_evid-test-01",
        "authority_tier": "TIER_2_TESTING",
        "standard_title": "Hydrostatic Pressure Test at 27 deg C",
        "heading": "Clause 8.1 Hydrostatic Requirements",
        "text": "The pipe shall withstand hydrostatic pressure test without failure."
    }
    assert classify_evidence_unit(test_unit) == "TESTING"
    identity = resolve_standard_identity("IS 4985", [test_unit])
    assert identity["official_standard_title"] is None
    assert any("Hydrostatic Pressure" in p for p in identity["test_parameters"])


def test_catalog_mappings_never_establish_certification_requirements():
    """Test 10: Catalog metadata units must not trigger Scheme - I mandatory assertions."""
    catalog_unit = {
        "record_id": "ev_rel_mapping_01",
        "authority_tier": "TIER_3_CATALOG",
        "standard_title": "Product Mapping: Water Heater -> IS 8978",
        "text": "Product Mapping: Instantaneous Water Heater -> IS 8978. Licence CM/L-12345."
    }
    assert classify_evidence_unit(catalog_unit) == "CATALOG_METADATA"
    ans = synthesize_multi_standard_answer("water heater", {"IS 8978": [catalog_unit]}, "en")
    assert "Mandatory BIS certification under Scheme – I" not in ans


def test_lims_fees_never_establish_certification_mandates():
    """Test 11: LIMS Fee units alone must not assert Scheme - I mandatory certification."""
    fee_unit = {
        "record_id": "ev_lims_fee_99",
        "fee_amount": 22000,
        "text": "Displayed testing charge excluding taxes: ₹22000"
    }
    assert classify_evidence_unit(fee_unit) == "LIMS_FEE"
    ans = synthesize_multi_standard_answer("water heater", {"IS 8978": [fee_unit]}, "en")
    assert "Mandatory BIS certification under Scheme – I" not in ans


def test_is_8978_remains_partial():
    """Test 12: IS 8978 has no normative text in corpus and must have None official title."""
    lims_scope_unit = {
        "record_id": "ev_lims_scope_42",
        "authority_tier": "TIER_3_LIMS_LAB",
        "standard_title": "Conformity Testing Labs Pvt Ltd | IS 8978 : 1992 | Electric Instantaneous Water Heaters",
        "text": "Direct BIS LIMS scope record for IS 8978 : 1992"
    }
    assert classify_evidence_unit(lims_scope_unit) == "LIMS_SCOPE"
    identity = resolve_standard_identity("IS 8978", [lims_scope_unit])
    assert identity["official_standard_title"] is None
    assert identity["revision_year"] == "1992"
    assert identity["product_category"] == "Electric Instantaneous Water Heaters"


def test_hindi_follows_same_filtering():
    """Test 13: Hindi query must apply the exact same relevance and identity filtering."""
    res = orchestrate_assistant_query("वॉटर हीटर प्रमाणन के बारे में बताएं", target_language="hi")
    assert res["status"] in ("SUFFICIENT", "PARTIAL")
    answer = res["answer"]
    assert "IS 369" not in answer
    assert "रूम हीटर" not in answer
    assert "IS 15558" in answer
    assert "IS 368" in answer
    assert "IS 8978" in answer
    assert "### एलपीजी इंस्टेंटेनियस घरेलू वॉटर हीटर" in answer
    assert "### इलेक्ट्रिक इंस्टेंटेनियस वॉटर हीटर" in answer
    assert "### इलेक्ट्रिक इमर्शन वॉटर हीटर" in answer


def test_english_follows_same_filtering():
    """Test 14: English query must apply the exact same relevance and identity filtering."""
    res = orchestrate_assistant_query("tell me about water heater certifications", target_language="en")
    assert res["status"] in ("SUFFICIENT", "PARTIAL")
    answer = res["answer"]
    assert "IS 369" not in answer
    assert "room heater" not in answer.lower()
    assert "IS 15558" in answer
    assert "IS 368" in answer
    assert "IS 8978" in answer
    assert "### LPG Instantaneous Domestic Water Heaters" in answer
    assert "### Electric Instantaneous Water Heaters" in answer
    assert "### Electric Immersion Water Heaters" in answer


def test_evidence_array_remains_byte_equivalent():
    """Test 15: The evidence array returned to frontend must remain byte-equivalent to Phase 13 output."""
    query = "tell me about water heater certifications"
    ctx = analyze_query_context(query)
    raw_rag = query_production_rag(ctx.get("search_intent") or query)
    orch_res = orchestrate_assistant_query(query)
    raw_ev = raw_rag.get("evidence", [])
    orch_ev = orch_res.get("rag", {}).get("evidence", [])
    assert len(raw_ev) == len(orch_ev)
    assert json.dumps(raw_ev, sort_keys=True) == json.dumps(orch_ev, sort_keys=True)


def test_conversational_structure_intact():
    """Test 16: Conversational structure (intro, clean headers, bullets, next-steps) intact."""
    res = orchestrate_assistant_query("tell me about water heater certifications")
    answer = res["answer"]
    # Intro sentence
    assert "BIS certification requirements for" in answer
    # Headers
    assert "###" in answer
    # Bullet points
    assert "- **" in answer
    # Next step
    assert "Which standard applies to your product?" in answer
    # No debug text
    forbidden_debug_patterns = [
        r"Authoritative BIS records identify",
        r"Authoritative BIS operational and regulatory records provide",
        r"Authoritative BIS Retrieval Results",
        r"Laboratory identifier:\s*\d+",
        r"\bretrieved units\b",
        r"Authority Tier:\s*TIER_",
        r"Evidence Depth:",
    ]
    for pattern in forbidden_debug_patterns:
        assert not re.search(pattern, answer, re.IGNORECASE)
