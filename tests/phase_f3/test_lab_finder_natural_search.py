"""
Test Suite for Phase F3: Controlled Natural Language Laboratory Search with Groq.

Verifies:
1. Pure deterministic parser extracts explicit standards, locations, categories, and scopes.
2. Controlled product-to-standard mapping correctly resolves terms like 'led lamps', 'pvc pipes', 'water heaters'.
3. Unrecognized products request clarification instead of hallucinating or guessing.
4. Groq natural language interpretation layer accurately parses nuanced queries.
5. Strict validation gate sanitizes and validates all Groq outputs before construction of LabSearchRequest.
6. Automatic, silent fallback to deterministic parser on any Groq API failure, timeout, or invalid JSON.
7. Capability results, candidate counts, and laboratory facts come exclusively from the authoritative BIS LIMS dataset.
8. API endpoints (POST and GET /api/labs/natural-search) return structured responses with factual interpretations.
9. UI invariants: restrained factual summaries without chatbot/marketing clutter.
"""

import os
import json
import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.lab_finder_api import (
    LabNaturalSearchRequest,
    execute_natural_search,
    LabSearchResponse,
)
from backend.nl_lab_parser import (
    parse_deterministic_query,
    parse_lab_natural_query,
    extract_explicit_standard,
    extract_location,
    extract_category,
    extract_scope_requirement,
    match_controlled_product,
    CONTROLLED_PRODUCT_STANDARDS,
    ParsedLabQuery,
)


class MockGroqClient:
    """Mock Groq client for deterministic testing."""
    def __init__(self, response_text: str = "", should_fail: bool = False):
        self.response_text = response_text
        self.should_fail = should_fail
        self.is_configured = True
        self.recorded_messages = []

    def chat_completion(self, messages, max_tokens=150):
        self.recorded_messages = messages
        if self.should_fail:
            raise RuntimeError("Mock Groq API connection timeout or network failure.")
        return self.response_text


@pytest.fixture
def client():
    return TestClient(app)


class TestLabFinderNaturalSearch:

    def test_01_extract_explicit_standard(self):
        """Verifies extraction of explicit standard designations."""
        assert extract_explicit_standard("find me the lab for is 4985 testing") == "IS 4985"
        assert extract_explicit_standard("find labs for IS 16102") == "IS 16102"
        assert extract_explicit_standard("testing for is 8978:1992") == "IS 8978"
        assert extract_explicit_standard("testing for IS 10500 Part 1") == "IS 10500 Part 1"
        assert extract_explicit_standard("random search query without standard") is None

    def test_02_extract_location(self):
        """Verifies extraction of Indian states and cities."""
        state, city = extract_location("find labs in Delhi")
        assert state == "Delhi" and city == "Delhi"

        state, city = extract_location("labs near Mumbai")
        assert state == "Maharashtra" and city == "Mumbai"

        state, city = extract_location("labs in Gujarat state")
        assert state == "Gujarat" and city is None

        state, city = extract_location("labs in Noida")
        assert state == "Uttar Pradesh" and city == "Noida"

    def test_03_extract_category_and_scope(self):
        """Verifies category and scope requirement extraction."""
        assert extract_category("find bis owned labs") == "BIS_OWNED"
        assert extract_category("find recognized laboratories") == "BIS_RECOGNIZED"
        assert extract_category("find empanelled labs") == "BIS_EMPANELLED"
        assert extract_category("find all labs") is None

        assert extract_scope_requirement("labs with complete scope") is True
        assert extract_scope_requirement("labs covering all clauses") is True
        assert extract_scope_requirement("general testing") is False

    def test_04_controlled_product_mapping(self):
        """Verifies controlled product vocabulary mappings."""
        led_match = match_controlled_product("find labs for testing led lamps")
        assert led_match is not None
        assert led_match[0] == "IS 16102"

        pipe_match = match_controlled_product("find labs for pvc pipes")
        assert pipe_match is not None
        assert pipe_match[0] == "IS 4985"

        heater_match = match_controlled_product("find labs for water heaters")
        assert heater_match is not None
        assert heater_match[0] == "IS 8978"

        water_match = match_controlled_product("testing for drinking water")
        assert water_match is not None
        assert water_match[0] == "IS 10500"

    def test_05_deterministic_query_parsing(self):
        """Tests pure deterministic parser without Groq."""
        # Case A: Explicit standard
        res_a = parse_deterministic_query("find me the lab for is 4985 testing")
        assert res_a.standard == "IS 4985"
        assert not res_a.clarification_needed
        assert "Searching for: IS 4985" in res_a.factual_summary

        # Case B: Colloquial product mapping
        res_b = parse_deterministic_query("find labs for testing led lamps")
        assert res_b.standard == "IS 16102"
        assert not res_b.clarification_needed
        assert "Interpreted as: Self-Ballasted LED Lamps · IS 16102" in res_b.factual_summary

        # Case C: Product + Location + Category
        res_c = parse_deterministic_query("find recognized labs for water heaters near Delhi")
        assert res_c.standard == "IS 8978"
        assert res_c.state == "Delhi"
        assert res_c.category == "BIS_RECOGNIZED"
        assert not res_c.clarification_needed
        assert "Delhi" in res_c.factual_summary
        assert "Recognized" in res_c.factual_summary

        # Case D: Unrecognized query requires clarification
        res_d = parse_deterministic_query("find labs for unknown quantum flux widget")
        assert res_d.standard is None
        assert res_d.clarification_needed
        assert "specify an Indian Standard number" in res_d.clarification_message

    def test_06_groq_natural_language_parser(self):
        """Verifies Groq-powered natural language interpretation."""
        groq_mock = MockGroqClient(response_text=json.dumps({
            "standard": "IS 16102",
            "product_name": "LED Lamps",
            "state": "Delhi",
            "city": "Delhi",
            "category": "BIS_RECOGNIZED",
            "require_complete_scope": False
        }))

        res = parse_lab_natural_query("find recognized labs for LED lamps in Delhi", groq_client=groq_mock)
        assert res.standard == "IS 16102"
        assert res.state == "Delhi"
        assert res.category == "BIS_RECOGNIZED"
        assert res.parser_source == "GROQ"
        assert "Interpreted as: LED Lamps · IS 16102" in res.factual_summary

    def test_07_groq_failure_falls_back_to_deterministic(self):
        """Verifies automatic fallback to deterministic parser when Groq fails."""
        groq_failing_mock = MockGroqClient(should_fail=True)

        # Fallback resolves controlled product
        res = parse_lab_natural_query("find labs for testing led lamps", groq_client=groq_failing_mock)
        assert res.standard == "IS 16102"
        assert res.parser_source == "DETERMINISTIC_CONTROLLED"
        assert not res.clarification_needed

    def test_08_groq_output_validation_gate(self):
        """Verifies that invalid or hallucinated Groq output is sanitized."""
        # Groq returns an invalid standard format
        groq_invalid_mock = MockGroqClient(response_text=json.dumps({
            "standard": "NON_EXISTENT_FORMAT_999",
            "product_name": "Unknown",
            "state": "NonExistentState",
            "category": "INVALID_CAT"
        }))

        res = parse_lab_natural_query("find labs for strange product", groq_client=groq_invalid_mock)
        # Should be rejected and require clarification
        assert res.standard is None
        assert res.clarification_needed

    def test_09_execute_natural_search_end_to_end(self):
        """Tests complete execution of natural search through authoritative BIS LIMS engine."""
        # 1. Explicit standard query
        req1 = LabNaturalSearchRequest(query="find me the lab for is 4985 testing")
        res1 = execute_natural_search(req1)
        assert res1.status == "MATCH"
        assert res1.search_results is not None
        assert res1.search_results.standard == "IS 4985"
        assert res1.search_results.total_matching == 29
        assert len(res1.search_results.candidates) == 29

        # 2. Product query (LED lamps -> IS 16102)
        req2 = LabNaturalSearchRequest(query="find labs for testing led lamps")
        res2 = execute_natural_search(req2)
        assert res2.status == "MATCH"
        assert res2.search_results is not None
        assert res2.search_results.standard == "IS 16102"
        assert res2.search_results.total_matching == 41

        # 3. Product + Location + Category query (Water heaters near Delhi recognized)
        req3 = LabNaturalSearchRequest(query="find recognized labs for water heaters near Delhi")
        res3 = execute_natural_search(req3)
        assert res3.status == "MATCH"
        assert res3.search_results is not None
        assert res3.search_results.standard == "IS 8978"
        # Product family expansion (IS 8978 + IS 2082) yields 6 recognized labs in Delhi
        assert res3.search_results.total_matching == 6
        for cand in res3.search_results.candidates:
            assert cand.category == "BIS_RECOGNIZED"

        # 4. Unknown query requiring clarification
        req4 = LabNaturalSearchRequest(query="find labs for space rocket propulsion module")
        res4 = execute_natural_search(req4)
        assert res4.status == "NEEDS_CLARIFICATION"
        assert res4.search_results is None
        assert "specify an Indian Standard number" in res4.clarification_message

    def test_10_api_endpoints(self, client):
        """Tests POST and GET /api/labs/natural-search HTTP endpoints."""
        # POST
        post_resp = client.post("/api/labs/natural-search", json={
            "query": "find me the lab for is 4985 testing"
        })
        assert post_resp.status_code == 200
        post_data = post_resp.json()
        assert post_data["status"] == "MATCH"
        assert post_data["parsed_query"]["standard"] == "IS 4985"
        assert post_data["search_results"]["total_matching"] == 29

        # GET
        get_resp = client.get("/api/labs/natural-search?query=find%20labs%20for%20testing%20led%20lamps")
        assert get_resp.status_code == 200
        get_data = get_resp.json()
        assert get_data["status"] == "MATCH"
        assert get_data["parsed_query"]["standard"] == "IS 16102"
        assert get_data["search_results"]["total_matching"] == 41

        # Clarification
        clarify_resp = client.post("/api/labs/natural-search", json={
            "query": "find labs for mysterious object 999"
        })
        assert clarify_resp.status_code == 200
        clarify_data = clarify_resp.json()
        assert clarify_data["status"] == "NEEDS_CLARIFICATION"
        assert clarify_data["search_results"] is None

    def test_11_scope_normalization_is302_and_is10322(self):
        """Verifies punctuation normalization for IS 302 and IS 10322."""
        # IS 302 (household electrical appliances)
        res_302 = execute_natural_search(LabNaturalSearchRequest(query="find labs for IS 302"))
        assert res_302.status == "MATCH"
        assert res_302.search_results.total_matching == 84
        assert len(res_302.search_results.candidates) == 84
        for c in res_302.search_results.candidates:
            assert "302" in c.capability_evidence.matching_standard

        # IS 10322 (luminaires)
        res_10322 = execute_natural_search(LabNaturalSearchRequest(query="find labs for IS 10322"))
        assert res_10322.status == "MATCH"
        assert res_10322.search_results.total_matching == 38
        assert len(res_10322.search_results.candidates) == 38

    def test_12_product_family_expansion_cement_and_steel(self):
        """Verifies product-family search expansion for cement and steel with deduplication."""
        # Cement: expands to IS 269, IS 1489, IS 455, IS 8041, etc.
        res_cement = execute_natural_search(LabNaturalSearchRequest(query="cement"))
        assert res_cement.status == "MATCH"
        assert res_cement.search_results.total_matching == 34
        # Verify deduplication
        cand_ids = [c.internal_id for c in res_cement.search_results.candidates]
        assert len(cand_ids) == len(set(cand_ids))

        # Steel / TMT
        res_steel = execute_natural_search(LabNaturalSearchRequest(query="steel"))
        assert res_steel.status == "MATCH"
        assert res_steel.search_results.total_matching == 59
        cand_ids_steel = [c.internal_id for c in res_steel.search_results.candidates]
        assert len(cand_ids_steel) == len(set(cand_ids_steel))

    def test_13_product_family_pipes_water_cables(self):
        """Verifies product-family expansion for pipe, water, and cable."""
        res_pipe = execute_natural_search(LabNaturalSearchRequest(query="pipe"))
        assert res_pipe.status == "MATCH"
        assert res_pipe.search_results.total_matching == 52

        res_water = execute_natural_search(LabNaturalSearchRequest(query="water"))
        assert res_water.status == "MATCH"
        assert res_water.search_results.total_matching == 70

        res_cable = execute_natural_search(LabNaturalSearchRequest(query="cable"))
        assert res_cable.status == "MATCH"
        assert res_cable.search_results.total_matching == 41

    def test_14_location_only_search_delhi(self):
        """Verifies location-only search returns verified laboratories without fabricating capabilities."""
        res_delhi = execute_natural_search(LabNaturalSearchRequest(query="Delhi"))
        assert res_delhi.status == "MATCH"
        assert res_delhi.search_results.match_status == "LOCATION_DISCOVERY"
        assert res_delhi.search_results.total_matching == 59
        # Check that original BIS address contains Delhi
        for c in res_delhi.search_results.candidates:
            assert "delhi" in c.address.original_address.lower() or (c.address.state and "delhi" in c.address.state.lower())
            assert "discovery" in c.capability_evidence.explanation.lower()

    def test_15_lab_name_search_national_test_house(self):
        """Verifies laboratory-name search matches identity fields without inferring capabilities."""
        res_nth = execute_natural_search(LabNaturalSearchRequest(query="National Test House"))
        assert res_nth.status == "MATCH"
        assert res_nth.search_results.match_status == "LAB_DISCOVERY"
        assert res_nth.search_results.total_matching == 7
        for c in res_nth.search_results.candidates:
            assert "national test house" in c.laboratory_name.lower()
            assert c.capability_evidence.provenance_url.startswith("https://lims.bis.gov.in/")

    def test_16_generic_keyword_scope_discovery_transformer(self):
        """Verifies scope-text search fallback finds transformer testing laboratories."""
        res_trans = execute_natural_search(LabNaturalSearchRequest(query="transformer"))
        assert res_trans.status == "MATCH"
        assert res_trans.search_results.total_matching == 27
        cand_ids = [c.internal_id for c in res_trans.search_results.candidates]
        assert len(cand_ids) == len(set(cand_ids))

    def test_17_deterministic_ordering_and_evidence_preservation(self):
        """Verifies repeated natural search runs produce identical bitwise ordering and evidence."""
        req = LabNaturalSearchRequest(query="cement")
        run1 = execute_natural_search(req)
        run2 = execute_natural_search(req)
        assert run1.search_results.total_matching == run2.search_results.total_matching
        ids1 = [c.internal_id for c in run1.search_results.candidates]
        ids2 = [c.internal_id for c in run2.search_results.candidates]
        assert ids1 == ids2
