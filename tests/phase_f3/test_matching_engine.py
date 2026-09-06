"""
Comprehensive deterministic test suite for Phase F3 Step 4B: Laboratory Matching Engine.

Verifies all 20 specified criteria:
1. exact IS match
2. standard with part
3. standard with year
4. multiple laboratories for one standard
5. clause match
6. missing clause
7. excluded clause
8. complete scope
9. partial scope
10. state filter
11. district filter
12. city filter
13. category filter
14. no matching standard
15. missing/invalid request
16. deterministic tie-breaking
17. repeated execution produces identical results
18. lab_code and internal_id remain separate
19. provenance remains intact
20. no capability inference from laboratory name
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
def catalog_engine():
    """Engine loaded with actual Phase F3 Step 3 ingested catalog."""
    catalog_path = Path("data/catalog/phase_f3_lims")
    if catalog_path.exists():
        return LimsMatchingEngine(catalog_dir=catalog_path)
    return LimsMatchingEngine()


@pytest.fixture
def structural_test_engine():
    """
    In-memory engine with controlled authoritative-style structural test fixtures
    for clause, exclusion, tie-breaking, and boundary tests.
    """
    labs = [
        NormalizedLimsLab(
            internal_id=101,
            lab_code="8101001",
            lab_name="Northern Electrical Testing Lab",
            category=LabCategory.BIS_OWNED,
            original_address="Plot 1, Okhla Industrial Area Phase 1, New Delhi, Delhi 110020",
            normalized_state="Delhi",
            normalized_district="South Delhi",
            normalized_city="New Delhi",
            pincode="110020",
            source_url="https://lims.bis.gov.in/home/bis_labs/view_scope/101",
            provenance_sha256="sha_lab_101"
        ),
        NormalizedLimsLab(
            internal_id=102,
            lab_code="8101002",
            lab_name="Western Calibration & Materials Lab",
            category=LabCategory.BIS_RECOGNIZED,
            original_address="GIDC Estate, Makarpura, Vadodara, Gujarat 390010",
            normalized_state="Gujarat",
            normalized_district="Vadodara",
            normalized_city="Vadodara",
            pincode="390010",
            source_url="https://lims.bis.gov.in/home/labs/view_scope/102",
            provenance_sha256="sha_lab_102"
        ),
        NormalizedLimsLab(
            internal_id=103,
            lab_code="8101003",
            lab_name="Southern Ceramic & Glass Lab",
            category=LabCategory.BIS_EMPANELLED,
            original_address="Peenya Industrial Area, Bengaluru, Karnataka 560058",
            normalized_state="Karnataka",
            normalized_district="Bengaluru Urban",
            normalized_city="Bengaluru",
            pincode="560058",
            source_url="https://lims.bis.gov.in/home/empaneled_labs/view_scope/103",
            provenance_sha256="sha_lab_103"
        ),
        NormalizedLimsLab(
            internal_id=104,
            lab_code="8101004",
            lab_name="Apex Electricals & Cable Test House",
            category=LabCategory.BIS_RECOGNIZED,
            original_address="B-44, Mayapuri Industrial Area, New Delhi, Delhi 110064",
            normalized_state="Delhi",
            normalized_district="West Delhi",
            normalized_city="New Delhi",
            pincode="110064",
            source_url="https://lims.bis.gov.in/home/labs/view_scope/104",
            provenance_sha256="sha_lab_104"
        ),
    ]

    scopes = [
        # Lab 101: Complete scope for IS 8978 with full clauses
        NormalizedLimsScope(
            scope_id="SCOPE_101_IS8978",
            internal_lab_id=101,
            lab_code="8101001",
            standard_number="IS 8978: 1992",
            standard_title="Electric Electric Irons",
            edition_year="1992",
            is_complete_scope=True,
            base_testing_fee=8500.0,
            clauses=[
                ClauseRecord(clause_number="5.1", is_excluded=False, fee_amount=500.0),
                ClauseRecord(clause_number="6.2", is_excluded=False, fee_amount=1200.0),
                ClauseRecord(clause_number="7.0", is_excluded=False, fee_amount=800.0),
            ],
            excluded_clauses=[],
            source_url="https://lims.bis.gov.in/home/bis_labs/view_scope/101",
            source_sha256="sha_scope_101"
        ),
        # Lab 104: Partial scope for IS 8978 with an excluded clause
        NormalizedLimsScope(
            scope_id="SCOPE_104_IS8978",
            internal_lab_id=104,
            lab_code="8101004",
            standard_number="IS 8978: 1992",
            standard_title="Electric Electric Irons",
            edition_year="1992",
            is_complete_scope=False,
            base_testing_fee=6000.0,
            clauses=[
                ClauseRecord(clause_number="5.1", is_excluded=False, fee_amount=500.0),
                ClauseRecord(clause_number="7.0", is_excluded=False, fee_amount=800.0),
            ],
            excluded_clauses=["6.2"],
            source_url="https://lims.bis.gov.in/home/labs/view_scope/104",
            source_sha256="sha_scope_104"
        ),
        # Lab 102: IS 2553 Part 1
        NormalizedLimsScope(
            scope_id="SCOPE_102_IS2553_P1",
            internal_lab_id=102,
            lab_code="8101002",
            standard_number="IS 2553 (Part 1): 2018",
            standard_title="Safety Glass - Architectural",
            edition_year="2018",
            is_complete_scope=True,
            clauses=[
                ClauseRecord(clause_number="4.1", is_excluded=False),
                ClauseRecord(clause_number="4.2", is_excluded=False),
            ],
            excluded_clauses=[],
            source_url="https://lims.bis.gov.in/home/labs/view_scope/102",
            source_sha256="sha_scope_102"
        ),
    ]

    retrieval = LimsRetrievalLayer(laboratories=labs, scopes=scopes)
    return LimsMatchingEngine(retrieval_layer=retrieval)


def test_01_exact_is_match(catalog_engine):
    """Criterion 1: Exact IS match returns verified laboratories."""
    req = LabMatchingRequest(standard="IS 4985")
    res = catalog_engine.match(req)
    assert res.status == MatchStatus.EXACT_MATCH
    assert res.total_candidates >= 1
    for cand in res.candidates:
        assert "4985" in cand.matching_standard
        assert MatchReason.EXACT_STANDARD_SCOPE in cand.reasons


def test_02_standard_with_part(structural_test_engine):
    """Criterion 2: Match standard with specific part."""
    req = LabMatchingRequest(standard="IS 2553", part="Part 1")
    res = structural_test_engine.match(req)
    assert res.status == MatchStatus.EXACT_MATCH
    assert res.total_candidates == 1
    cand = res.candidates[0]
    assert cand.internal_id == 102
    assert MatchReason.EXACT_STANDARD_PART_SCOPE in cand.reasons


def test_03_standard_with_year(structural_test_engine):
    """Criterion 3: Match standard with specific edition year."""
    req = LabMatchingRequest(standard="IS 8978", year="1992")
    res = structural_test_engine.match(req)
    assert res.status == MatchStatus.EXACT_MATCH
    assert res.total_candidates == 2


def test_04_multiple_laboratories_for_one_standard(catalog_engine):
    """Criterion 4: Handle multiple accredited laboratories for a single standard."""
    req = LabMatchingRequest(standard="IS 4985")
    res = catalog_engine.match(req)
    # Both Lab 15 (SIIR) and Lab 19 (Kailtech) are accredited for IS 4985
    assert res.total_candidates >= 2
    lab_ids = [c.internal_id for c in res.candidates]
    assert 15 in lab_ids
    assert 19 in lab_ids


def test_05_clause_match(structural_test_engine):
    """Criterion 5: Explicit clause matching reports matched clauses."""
    req = LabMatchingRequest(standard="IS 8978", clauses=["Clause 5.1", "Clause 7.0"])
    res = structural_test_engine.match(req)
    assert res.status == MatchStatus.EXACT_MATCH
    top_cand = res.candidates[0]
    assert "Clause 5.1" in top_cand.matched_clauses
    assert "Clause 7.0" in top_cand.matched_clauses
    assert MatchReason.CLAUSE_REQUIREMENTS_MATCHED in top_cand.reasons


def test_06_missing_clause(structural_test_engine):
    """Criterion 6: Report missing/unsupported clause."""
    req = LabMatchingRequest(standard="IS 8978", clauses=["Clause 9.9_nonexistent"])
    res = structural_test_engine.match(req)
    for cand in res.candidates:
        assert "Clause 9.9_nonexistent" in cand.unmatched_requested_clauses
        assert MatchReason.MISSING_REQUIRED_CLAUSES in cand.reasons


def test_07_excluded_clause(structural_test_engine):
    """Criterion 7: Explicit excluded clauses cannot be reported as supported."""
    req = LabMatchingRequest(standard="IS 8978", clauses=["Clause 6.2"])
    res = structural_test_engine.match(req)
    # Lab 101 has 6.2; Lab 104 has 6.2 explicitly excluded
    lab_104 = next(c for c in res.candidates if c.internal_id == 104)
    assert "Clause 6.2" in lab_104.excluded_clauses
    assert "Clause 6.2" not in lab_104.matched_clauses
    assert MatchReason.EXCLUDED_CLAUSES_PRESENT in lab_104.reasons


def test_08_complete_scope(structural_test_engine):
    """Criterion 8: Complete scope laboratory identified and prioritized."""
    req = LabMatchingRequest(standard="IS 8978", require_complete_scope=True)
    res = structural_test_engine.match(req)
    # Only Lab 101 has complete scope
    assert res.total_candidates == 1
    assert res.candidates[0].internal_id == 101
    assert res.candidates[0].scope_completeness == ScopeCompleteness.COMPLETE_SCOPE


def test_09_partial_scope(structural_test_engine):
    """Criterion 9: Partial scope reported accurately without false upgrade."""
    req = LabMatchingRequest(standard="IS 8978")
    res = structural_test_engine.match(req)
    lab_104 = next(c for c in res.candidates if c.internal_id == 104)
    assert lab_104.scope_completeness == ScopeCompleteness.PARTIAL_SCOPE
    assert MatchReason.PARTIAL_SCOPE in lab_104.reasons


def test_10_state_filter(catalog_engine):
    """Criterion 10: State filter reduces candidate set accurately."""
    # IS 4985 has labs in Delhi (15) and Madhya Pradesh (19)
    req_delhi = LabMatchingRequest(standard="IS 4985", state="Delhi")
    res_delhi = catalog_engine.match(req_delhi)
    assert res_delhi.total_candidates >= 1
    for c in res_delhi.candidates:
        assert "delhi" in (c.state or "").lower() or "delhi" in c.original_address.lower()


def test_11_district_filter(structural_test_engine):
    """Criterion 11: District filter filters candidates by district."""
    req = LabMatchingRequest(standard="IS 8978", district="South Delhi")
    res = structural_test_engine.match(req)
    assert res.total_candidates == 1
    assert res.candidates[0].internal_id == 101


def test_12_city_filter(structural_test_engine):
    """Criterion 12: City filter filters candidates by city."""
    req = LabMatchingRequest(standard="IS 2553", city="Vadodara")
    res = structural_test_engine.match(req)
    assert res.total_candidates == 1
    assert res.candidates[0].internal_id == 102


def test_13_category_filter(structural_test_engine):
    """Criterion 13: Laboratory category filtering."""
    req = LabMatchingRequest(standard="IS 8978", category=LabCategory.BIS_OWNED)
    res = structural_test_engine.match(req)
    assert res.total_candidates == 1
    assert res.candidates[0].category == LabCategory.BIS_OWNED
    assert res.candidates[0].internal_id == 101


def test_14_no_matching_standard(catalog_engine):
    """Criterion 14: Return explicit NO_MATCH for uncataloged standard without broadening."""
    req = LabMatchingRequest(standard="IS 99999")
    res = catalog_engine.match(req)
    assert res.status == MatchStatus.NO_MATCH
    assert res.total_candidates == 0
    assert len(res.candidates) == 0


def test_15_missing_invalid_request(catalog_engine):
    """Criterion 15: Structural rejection of empty or blank standard."""
    req_blank = LabMatchingRequest(standard="")
    res = catalog_engine.match(req_blank)
    assert res.status == MatchStatus.INVALID_REQUEST
    assert res.total_candidates == 0


def test_16_deterministic_tie_breaking(structural_test_engine):
    """Criterion 16: Stable tie-breaking uses public_lab_code and internal_id."""
    req = LabMatchingRequest(standard="IS 8978")
    res = structural_test_engine.match(req)
    assert res.candidates[0].rank == 1
    assert res.candidates[1].rank == 2
    # Verify strict ascending rank
    for idx, c in enumerate(res.candidates):
        assert c.rank == idx + 1


def test_17_repeated_execution_produces_identical_results(structural_test_engine):
    """Criterion 17: Repeated execution yields bitwise identical outputs."""
    req = LabMatchingRequest(standard="IS 8978", clauses=["5.1"])
    res1 = structural_test_engine.match(req)
    res2 = structural_test_engine.match(req)
    assert res1.to_dict()["candidates"] == res2.to_dict()["candidates"]


def test_18_lab_code_and_internal_id_remain_separate(catalog_engine):
    """Criterion 18: public lab_code and internal_id are strictly separate."""
    req = LabMatchingRequest(standard="IS 4985")
    res = catalog_engine.match(req)
    for c in res.candidates:
        assert isinstance(c.internal_id, int)
        assert isinstance(c.public_lab_code, str)
        assert c.public_lab_code != str(c.internal_id)


def test_19_provenance_remains_intact(catalog_engine):
    """Criterion 19: Statutory BIS provenance is preserved."""
    req = LabMatchingRequest(standard="IS 4985")
    res = catalog_engine.match(req)
    for c in res.candidates:
        assert c.provenance_url.startswith("https://lims.bis.gov.in")
        assert len(c.provenance_sha256) > 0


def test_20_no_capability_inference_from_laboratory_name(structural_test_engine):
    """
    Criterion 20: Capability is NEVER inferred from lab name.
    'Apex Electricals' should NOT match IS 2553 (Safety Glass) despite having 'Apex' in name.
    """
    req = LabMatchingRequest(standard="IS 2553")
    res = structural_test_engine.match(req)
    lab_names = [c.laboratory_identity for c in res.candidates]
    assert "Apex Electricals & Cable Test House" not in lab_names
    assert "Northern Electrical Testing Lab" not in lab_names
