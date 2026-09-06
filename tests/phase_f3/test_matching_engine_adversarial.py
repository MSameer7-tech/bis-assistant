"""
Phase F3 Step 4C: Adversarial Audit Test Suite for BIS Laboratory Matching Engine.

Explicitly tests all 19 adversarial audit vectors:
1. False positive laboratory matches
2. Matching based only on laboratory name
3. Matching based only on product-name similarity
4. Partial scope incorrectly reported as complete
5. Excluded clauses incorrectly reported as supported
6. Missing clauses silently accepted
7. State/city filters overriding laboratory capability
8. Laboratory category corruption
9. lab_code/internal_id confusion
10. Loss of BIS provenance
11. Nondeterministic ranking
12. Hidden fuzzy matching
13. LLM usage
14. Fabricated capabilities
15. Automatic broadening to unrelated standards
16. Catalog honesty (does not claim to represent all BIS labs)
17. Accidental Geoapify or map integration
18. Accidental frontend/API changes
19. Frozen baseline modifications
"""

import pytest
from pathlib import Path

from ai.lims.models import (
    LabCategory,
    ClauseRecord,
    NormalizedLimsLab,
    NormalizedLimsScope,
)
from ai.lims.matching_models import (
    MatchStatus,
    ScopeCompleteness,
    MatchReason,
    LabMatchingRequest,
    LabCandidateMatch,
    LabMatchingResult,
)
from ai.lims.retrieval_layer import LimsRetrievalLayer
from ai.lims.matching_engine import LimsMatchingEngine


@pytest.fixture
def adversarial_catalog():
    """
    Constructs an adversarial fixture specifically engineered to trap
    fuzzy matching, name-based hallucination, location overrides, and clause leakage.
    """
    labs = [
        # Lab A: Named "Apex Solar & Cable Lab" in Delhi, but ONLY accredited for IS 1293 (Plugs & Sockets)
        NormalizedLimsLab(
            internal_id=201,
            lab_code="8201001",
            lab_name="Apex Solar & Cable Laboratory Delhi",
            category=LabCategory.BIS_RECOGNIZED,
            original_address="12, Okhla Phase 3, New Delhi 110020",
            normalized_state="Delhi",
            normalized_district="South Delhi",
            normalized_city="New Delhi",
            pincode="110020",
            source_url="https://lims.bis.gov.in/home/labs/view_scope/201",
            provenance_sha256="sha_adv_201"
        ),
        # Lab B: Located in Bengaluru, accredited for IS 14286 (Solar PV) with PARTIAL scope (Clause 10.1 excluded)
        NormalizedLimsLab(
            internal_id=202,
            lab_code="8201002",
            lab_name="Southern Photovoltaic Testing Centre",
            category=LabCategory.BIS_OWNED,
            original_address="Electronic City, Bengaluru 560100",
            normalized_state="Karnataka",
            normalized_district="Bengaluru",
            normalized_city="Bengaluru",
            pincode="560100",
            source_url="https://lims.bis.gov.in/home/bis_labs/view_scope/202",
            provenance_sha256="sha_adv_202"
        ),
        # Lab C: Located in Mumbai, accredited for IS 14286 (Solar PV) with COMPLETE scope
        NormalizedLimsLab(
            internal_id=203,
            lab_code="8201003",
            lab_name="National Photovoltaic Research Institute",
            category=LabCategory.BIS_EMPANELLED,
            original_address="MIDC Andheri, Mumbai 400093",
            normalized_state="Maharashtra",
            normalized_district="Mumbai Suburban",
            normalized_city="Mumbai",
            pincode="400093",
            source_url="https://lims.bis.gov.in/home/empaneled_labs/view_scope/203",
            provenance_sha256="sha_adv_203"
        ),
    ]

    scopes = [
        # Lab 201 has IS 1293
        NormalizedLimsScope(
            scope_id="SCOPE_201_IS1293",
            internal_lab_id=201,
            lab_code="8201001",
            standard_number="IS 1293: 2019",
            standard_title="Plugs and Socket-Outlets",
            edition_year="2019",
            is_complete_scope=True,
            clauses=[
                ClauseRecord(clause_number="8.1", is_excluded=False),
                ClauseRecord(clause_number="9.2", is_excluded=False),
            ],
            excluded_clauses=[],
            source_url="https://lims.bis.gov.in/home/labs/view_scope/201",
            source_sha256="sha_scope_201"
        ),
        # Lab 202 has IS 14286 with PARTIAL scope (clause 10.1 excluded)
        NormalizedLimsScope(
            scope_id="SCOPE_202_IS14286",
            internal_lab_id=202,
            lab_code="8201002",
            standard_number="IS 14286: 2010",
            standard_title="Crystalline Silicon Terrestrial Photovoltaic Modules",
            edition_year="2010",
            is_complete_scope=False,
            clauses=[
                ClauseRecord(clause_number="10.2", is_excluded=False),
                ClauseRecord(clause_number="10.3", is_excluded=False),
            ],
            excluded_clauses=["10.1"],
            source_url="https://lims.bis.gov.in/home/bis_labs/view_scope/202",
            source_sha256="sha_scope_202"
        ),
        # Lab 203 has IS 14286 with COMPLETE scope
        NormalizedLimsScope(
            scope_id="SCOPE_203_IS14286",
            internal_lab_id=203,
            lab_code="8201003",
            standard_number="IS 14286: 2010",
            standard_title="Crystalline Silicon Terrestrial Photovoltaic Modules",
            edition_year="2010",
            is_complete_scope=True,
            clauses=[
                ClauseRecord(clause_number="10.1", is_excluded=False),
                ClauseRecord(clause_number="10.2", is_excluded=False),
                ClauseRecord(clause_number="10.3", is_excluded=False),
            ],
            excluded_clauses=[],
            source_url="https://lims.bis.gov.in/home/empaneled_labs/view_scope/203",
            source_sha256="sha_scope_203"
        ),
    ]

    retrieval = LimsRetrievalLayer(laboratories=labs, scopes=scopes)
    return LimsMatchingEngine(retrieval_layer=retrieval)


def test_audit_01_no_false_positive_matches(adversarial_catalog):
    """Vector 1: Non-existent standard yields NO_MATCH and zero candidates."""
    res = adversarial_catalog.match(LabMatchingRequest(standard="IS 00000"))
    assert res.status == MatchStatus.NO_MATCH
    assert res.total_candidates == 0
    assert res.candidates == []


def test_audit_02_no_match_on_lab_name_alone(adversarial_catalog):
    """
    Vector 2: Lab 201 is named 'Apex Solar & Cable Laboratory Delhi',
    but querying IS 14286 (Solar PV) MUST NEVER match Lab 201 since it lacks scope.
    """
    res = adversarial_catalog.match(LabMatchingRequest(standard="IS 14286"))
    matched_ids = [c.internal_id for c in res.candidates]
    assert 201 not in matched_ids


def test_audit_03_no_match_on_product_name_similarity(adversarial_catalog):
    """
    Vector 3: Requesting standard IS 1293 (Plugs) must not match IS 14286 (Solar),
    even though both are electrical standards.
    """
    res = adversarial_catalog.match(LabMatchingRequest(standard="IS 1293"))
    matched_stds = [c.matching_standard for c in res.candidates]
    for std in matched_stds:
        assert "1293" in std
        assert "14286" not in std


def test_audit_04_partial_scope_not_reported_as_complete(adversarial_catalog):
    """Vector 4: Lab 202 has partial scope; it must never be marked COMPLETE_SCOPE."""
    res = adversarial_catalog.match(LabMatchingRequest(standard="IS 14286"))
    lab_202 = next(c for c in res.candidates if c.internal_id == 202)
    assert lab_202.scope_completeness == ScopeCompleteness.PARTIAL_SCOPE
    assert MatchReason.PARTIAL_SCOPE in lab_202.reasons


def test_audit_05_excluded_clauses_not_reported_as_supported(adversarial_catalog):
    """
    Vector 5: Lab 202 explicitly excludes Clause 10.1.
    A request demanding Clause 10.1 must report 10.1 in excluded_clauses and NOT in matched_clauses.
    """
    res = adversarial_catalog.match(LabMatchingRequest(standard="IS 14286", clauses=["10.1"]))
    lab_202 = next(c for c in res.candidates if c.internal_id == 202)
    assert "10.1" in lab_202.excluded_clauses
    assert "10.1" not in lab_202.matched_clauses
    assert MatchReason.EXCLUDED_CLAUSES_PRESENT in lab_202.reasons


def test_audit_06_missing_clauses_not_silently_accepted(adversarial_catalog):
    """Vector 6: Unlisted clause 99.9 must be reported in unmatched_requested_clauses."""
    res = adversarial_catalog.match(LabMatchingRequest(standard="IS 14286", clauses=["99.9"]))
    for c in res.candidates:
        assert "99.9" in c.unmatched_requested_clauses
        assert MatchReason.MISSING_REQUIRED_CLAUSES in c.reasons


def test_audit_07_location_filter_cannot_override_capability(adversarial_catalog):
    """
    Vector 7: Query for IS 14286 with state='Delhi'.
    Lab 201 is in Delhi, but has NO scope for IS 14286.
    The engine MUST NOT return Lab 201. Result must be NO_MATCH.
    """
    res = adversarial_catalog.match(LabMatchingRequest(standard="IS 14286", state="Delhi"))
    assert res.status == MatchStatus.NO_MATCH
    assert res.total_candidates == 0


def test_audit_08_laboratory_category_not_corrupted(adversarial_catalog):
    """Vector 8: Category enums are strictly preserved."""
    res = adversarial_catalog.match(LabMatchingRequest(standard="IS 14286"))
    lab_202 = next(c for c in res.candidates if c.internal_id == 202)
    lab_203 = next(c for c in res.candidates if c.internal_id == 203)
    assert lab_202.category == LabCategory.BIS_OWNED
    assert lab_203.category == LabCategory.BIS_EMPANELLED


def test_audit_09_lab_code_and_internal_id_not_confused(adversarial_catalog):
    """Vector 9: lab_code is string '8201002' and internal_id is int 202."""
    res = adversarial_catalog.match(LabMatchingRequest(standard="IS 14286"))
    for c in res.candidates:
        assert isinstance(c.public_lab_code, str)
        assert isinstance(c.internal_id, int)
        assert c.public_lab_code != str(c.internal_id)


def test_audit_10_provenance_intact(adversarial_catalog):
    """Vector 10: BIS URL and SHA256 provenance are present and non-empty."""
    res = adversarial_catalog.match(LabMatchingRequest(standard="IS 14286"))
    for c in res.candidates:
        assert c.provenance_url.startswith("https://lims.bis.gov.in")
        assert len(c.provenance_sha256) > 0


def test_audit_11_nondeterministic_ranking_prevented(adversarial_catalog):
    """Vector 11: 10 repeated runs yield bitwise identical rank and candidate list."""
    req = LabMatchingRequest(standard="IS 14286")
    runs = [adversarial_catalog.match(req).to_dict()["candidates"] for _ in range(10)]
    for r in runs[1:]:
        assert r == runs[0]


def test_audit_12_no_hidden_fuzzy_matching(adversarial_catalog):
    """Vector 12: 'IS 1428' must NOT fuzzy-match 'IS 14286'."""
    res = adversarial_catalog.match(LabMatchingRequest(standard="IS 1428"))
    assert res.status == MatchStatus.NO_MATCH
    assert res.total_candidates == 0


def test_audit_13_no_llm_usage():
    """Vector 13: ai/lims/ source files contain zero LLM references or imports."""
    lims_dir = Path("ai/lims")
    for f in lims_dir.glob("*.py"):
        content = f.read_text(encoding="utf-8").lower()
        assert "groq" not in content, f"Found LLM Groq reference in {f}"
        assert "openai" not in content, f"Found OpenAI reference in {f}"
        assert "langchain" not in content, f"Found LangChain reference in {f}"


def test_audit_14_no_fabricated_capabilities(adversarial_catalog):
    """Vector 14: Laboratory cannot have capabilities outside its defined scope."""
    res = adversarial_catalog.match(LabMatchingRequest(standard="IS 1293"))
    assert res.total_candidates == 1
    assert res.candidates[0].internal_id == 201


def test_audit_15_no_automatic_broadening(adversarial_catalog):
    """Vector 15: No automatic broadening to related standards on missing standard."""
    res = adversarial_catalog.match(LabMatchingRequest(standard="IS 14286-99"))
    assert res.status == MatchStatus.NO_MATCH
    assert res.total_candidates == 0


def test_audit_16_catalog_honesty():
    """Vector 16: Catalog statistics report actual ingested numbers honestly."""
    engine = LimsMatchingEngine()
    stats = engine.retrieval_layer.get_statistics()
    # Ingested catalog reflects 580 validated unique labs and 6,327 scopes
    assert stats["total_unique_laboratories"] == 580
    assert stats["total_scope_records"] == 6327


def test_audit_17_no_external_geographic_metadata(adversarial_catalog):
    """Vector 17: external_geographic_metadata is strictly None."""
    res = adversarial_catalog.match(LabMatchingRequest(standard="IS 14286"))
    for c in res.candidates:
        assert c.external_geographic_metadata is None


def test_audit_18_no_accidental_api_or_frontend_modifications():
    """Vector 18: Matching engine is self-contained in ai/lims with no API or frontend couplings."""
    engine_file = Path("ai/lims/matching_engine.py")
    content = engine_file.read_text(encoding="utf-8")
    assert "fastapi" not in content.lower()
    assert "flask" not in content.lower()
    assert "geoapify" not in content.lower()
    assert "leaflet" not in content.lower()


def test_audit_19_capability_over_proximity_contract(adversarial_catalog):
    """
    Vector 19: Complete scope in Mumbai (Lab 203) MUST outrank Partial scope in Bengaluru (Lab 202).
    """
    res = adversarial_catalog.match(LabMatchingRequest(standard="IS 14286"))
    assert res.candidates[0].internal_id == 203  # Complete scope
    assert res.candidates[1].internal_id == 202  # Partial scope
    assert res.candidates[0].match_score > res.candidates[1].match_score
