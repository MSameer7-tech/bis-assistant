"""
Tests for Phase F3 Step 4A: Laboratory Matching Engine Data Models.

Verifies:
1. Deterministic validation and creation of LabMatchingRequest
2. Strict isolation between public_lab_code and internal_id
3. Invariant preservation of authoritative BIS original_address
4. External geographic metadata isolation (defaults to None, strictly separate)
5. Enums (MatchStatus, ScopeCompleteness, MatchReason) and serialization/deserialization
"""

import pytest
from ai.lims.models import LabCategory
from ai.lims.matching_models import (
    MatchStatus,
    ScopeCompleteness,
    MatchReason,
    LabMatchingRequest,
    LabCandidateMatch,
    LabMatchingResult,
)


def test_valid_request_creation_and_validation():
    req = LabMatchingRequest(standard="IS 8978")
    is_valid, err = req.validate()
    assert is_valid is True
    assert err is None
    assert req.standard == "IS 8978"
    assert req.part is None
    assert req.clauses == []
    assert req.require_complete_scope is False


def test_invalid_empty_standard_rejection():
    # Empty string
    req_empty = LabMatchingRequest(standard="")
    is_valid, err = req_empty.validate()
    assert is_valid is False
    assert "MISSING_STANDARD" in err

    # Whitespace only
    req_ws = LabMatchingRequest(standard="   ")
    is_valid, err = req_ws.validate()
    assert is_valid is False
    assert "MISSING_STANDARD" in err

    # Too short
    req_short = LabMatchingRequest(standard="I")
    is_valid, err = req_short.validate()
    assert is_valid is False
    assert "INVALID_STANDARD" in err


def test_request_optional_filters_and_serialization():
    req = LabMatchingRequest(
        standard="IS 8978",
        part="Part 1",
        year="2020",
        clauses=["Clause 5.1", "Clause 6.2"],
        test_requirements=["High Voltage Test", "Leakage Current"],
        state="Delhi",
        district="New Delhi",
        city="Delhi",
        category=LabCategory.BIS_OWNED,
        require_complete_scope=True,
    )
    is_valid, err = req.validate()
    assert is_valid is True

    # Test serialization to dict
    d = req.to_dict()
    assert d["standard"] == "IS 8978"
    assert d["part"] == "Part 1"
    assert d["year"] == "2020"
    assert len(d["clauses"]) == 2
    assert d["category"] == "BIS_OWNED"
    assert d["require_complete_scope"] is True

    # Test deserialization from dict
    restored = LabMatchingRequest.from_dict(d)
    assert restored.standard == req.standard
    assert restored.part == req.part
    assert restored.category == LabCategory.BIS_OWNED
    assert restored.clauses == req.clauses
    assert restored.require_complete_scope is True


def test_lab_candidate_match_identity_separation_and_invariants():
    """
    Verifies that public_lab_code and internal_id are strictly separated,
    and external_geographic_metadata defaults to None.
    """
    candidate = LabCandidateMatch(
        laboratory_identity="Northern Regional Office Laboratory",
        public_lab_code="8102006",
        internal_id=15,
        category=LabCategory.BIS_OWNED,
        original_address="Plot No. 4-A, Sahibabad Industrial Area, Ghaziabad, UP 201010",
        state="Uttar Pradesh",
        district="Ghaziabad",
        city="Sahibabad",
        pincode="201010",
        matching_standard="IS 8978",
        matching_scope_id="SCOPE_8102006_IS8978",
        scope_completeness=ScopeCompleteness.COMPLETE_SCOPE,
        matched_clauses=["5.1", "5.2", "6.1"],
        unmatched_requested_clauses=[],
        excluded_clauses=[],
        reasons=[MatchReason.EXACT_STANDARD_SCOPE, MatchReason.CLAUSE_REQUIREMENTS_MATCHED],
        explanation="Laboratory has verified active complete scope for IS 8978 covering all requested clauses.",
        base_testing_fee=15000.0,
        currency="INR",
        provenance_url="https://lims.bis.gov.in/home/bis_labs/view_scope/15",
        provenance_sha256="abc123hash",
        match_score=1.0,
        rank=1,
    )

    # Invariants verification
    assert candidate.public_lab_code == "8102006"
    assert candidate.internal_id == 15
    assert candidate.public_lab_code != str(candidate.internal_id)
    assert "Sahibabad Industrial Area" in candidate.original_address

    # In Step 4A, external geographic metadata MUST be None by default
    assert candidate.external_geographic_metadata is None

    # Serialization test
    d = candidate.to_dict()
    assert d["public_lab_code"] == "8102006"
    assert d["internal_id"] == 15
    assert d["category"] == "BIS_OWNED"
    assert d["scope_completeness"] == "COMPLETE_SCOPE"
    assert d["reasons"] == ["EXACT_STANDARD_SCOPE", "CLAUSE_REQUIREMENTS_MATCHED"]
    assert d["external_geographic_metadata"] is None


def test_matching_result_container():
    req = LabMatchingRequest(standard="IS 8978", state="Delhi")
    res = LabMatchingResult(
        request=req,
        status=MatchStatus.EXACT_MATCH,
        candidates=[],
        total_candidates=0,
        catalog_statistics={"total_labs": 24, "total_scopes": 149},
        provenance={"catalog_source": "data/catalog/phase_f3_lims/catalog_manifest.json"}
    )

    assert res.status == MatchStatus.EXACT_MATCH
    assert res.total_candidates == 0
    assert "total_labs" in res.catalog_statistics
    assert res.execution_timestamp is not None

    d = res.to_dict()
    assert d["status"] == "EXACT_MATCH"
    assert d["request"]["standard"] == "IS 8978"
    assert d["catalog_statistics"]["total_labs"] == 24


def test_external_geographic_metadata_isolation():
    """
    Verifies that when external geographic metadata is provided (in future steps),
    it is isolated in external_geographic_metadata without altering original_address.
    """
    candidate = LabCandidateMatch(
        laboratory_identity="Test Lab",
        public_lab_code="9999999",
        internal_id=99,
        category=LabCategory.BIS_RECOGNIZED,
        original_address="Statutory BIS Address 123, Okhla, New Delhi",
        external_geographic_metadata={
            "provider": "geoapify",
            "latitude": 28.5355,
            "longitude": 77.2732,
            "confidence": 0.95,
        }
    )

    # Statutory address is strictly preserved
    assert candidate.original_address == "Statutory BIS Address 123, Okhla, New Delhi"
    assert candidate.external_geographic_metadata["provider"] == "geoapify"
    assert candidate.external_geographic_metadata["latitude"] == 28.5355
