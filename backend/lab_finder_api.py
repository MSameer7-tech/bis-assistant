"""
Phase F3 Step 7: Lab Finder Backend Search API.

Composes:
  Authoritative BIS LIMS Matching Engine
  → Qualified Laboratory Candidates
  → Frozen Geographic Cache
  → Step 6 Distance & Geographic Ranking Engine
  → Structured API Response

Invariants & Architectural Guarantees:
1. Separation of Concerns: Capability matching happens FIRST via LimsMatchingEngine.
   Geographic proximity NEVER creates or qualifies candidates.
2. Statutory Authority: BIS testing scope remains the sole normative authority.
   External geographic data is strictly supplementary metadata.
3. Zero External Calls: Pure offline execution using frozen disk catalog and cache.
4. ZERO_RESULTS Integrity: Labs without valid geocoding retain null coordinates and null distance.
   Zero coordinate fabrication or interpolation.
5. Empty-Scope Exclusion: Empty-scope labs (39 in catalog) never match capability.
6. Deterministic Ordering: 100% reproducible results across repeated calls.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ai.lims.matching_models import (
    LabMatchingRequest,
    MatchStatus,
    ScopeCompleteness,
    MatchReason,
    LabCandidateMatch,
)
from ai.lims.matching_engine import LimsMatchingEngine
from ai.lims.models import LabCategory
from ai.geo.distance import validate_coordinates
from ai.geo.ranking import GeographicRankingEngine, GeographicDistanceMetadata
from backend.nl_lab_parser import ParsedLabQuery, parse_lab_natural_query


# ---------------------------------------------------------------------------
# Pydantic Schemas for Lab Finder Search API
# ---------------------------------------------------------------------------

class LabSearchRequest(BaseModel):
    """
    Search request for BIS Laboratory Finder API.
    """
    standard: str = Field(
        ...,
        description="Mandatory Indian Standard designation (e.g., 'IS 4985', 'IS 8978:1992')."
    )
    part: Optional[str] = Field(
        None,
        description="Optional standard part number (e.g., '1', 'Part 2')."
    )
    year: Optional[str] = Field(
        None,
        description="Optional standard edition year (e.g., '2021', '1992')."
    )
    clauses: List[str] = Field(
        default_factory=list,
        description="Optional list of specific test clauses required (e.g., ['5.1', '6.2'])."
    )
    test_requirements: List[str] = Field(
        default_factory=list,
        description="Optional list of test parameter requirements."
    )
    state: Optional[str] = Field(
        None,
        description="Optional state filter (case-insensitive substring match against BIS address)."
    )
    district: Optional[str] = Field(
        None,
        description="Optional district filter."
    )
    city: Optional[str] = Field(
        None,
        description="Optional city filter."
    )
    latitude: Optional[float] = Field(
        None,
        description="Optional user reference latitude in [-90.0, 90.0] for proximity ranking."
    )
    longitude: Optional[float] = Field(
        None,
        description="Optional user reference longitude in [-180.0, 180.0] for proximity ranking."
    )
    max_distance_km: Optional[float] = Field(
        None,
        description="Optional maximum distance radius in km. Requires latitude and longitude."
    )
    category: Optional[str] = Field(
        None,
        description="Optional laboratory category filter: 'BIS_OWNED', 'BIS_RECOGNIZED', or 'BIS_EMPANELLED'."
    )
    require_complete_scope: bool = Field(
        False,
        description="If True, only laboratories with complete (non-partial) scope are returned."
    )
    limit: Optional[int] = Field(
        None,
        description="Optional maximum number of candidates to return (must be >= 1)."
    )


class LabAddressResponse(BaseModel):
    """
    Authoritative BIS laboratory address information.
    """
    original_address: str
    state: Optional[str] = None
    district: Optional[str] = None
    city: Optional[str] = None
    pincode: Optional[str] = None


class CapabilityEvidenceResponse(BaseModel):
    """
    Normative BIS testing capability evidence.
    """
    matching_standard: str
    matching_scope_id: str
    scope_completeness: str
    matched_clauses: List[str] = Field(default_factory=list)
    unmatched_requested_clauses: List[str] = Field(default_factory=list)
    excluded_clauses: List[str] = Field(default_factory=list)
    match_reasons: List[str] = Field(default_factory=list)
    explanation: str
    match_score: float
    base_testing_fee: Optional[float] = None
    clause_fee_total: Optional[float] = None
    currency: str = "INR"
    provenance_url: str
    provenance_sha256: str


class GeographicMetadataResponse(BaseModel):
    """
    Supplementary geographic metadata and proximity calculation.
    Explicitly decoupled from normative BIS capability.
    """
    has_coordinates: bool
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    distance_km: Optional[float] = None
    geocoding_status: str
    formatted_address: Optional[str] = None
    place_id: Optional[str] = None
    confidence: Optional[float] = None
    match_type: Optional[str] = None
    provider: str = "GEOAPIFY"
    authority_disclaimer: str = (
        "Geographic distance is supplementary spatial metadata. "
        "It does not constitute normative evidence of BIS recognition, "
        "laboratory capability, or testing scope."
    )


class LaboratoryCandidateResponse(BaseModel):
    """
    Structured laboratory candidate returned in search results.
    """
    rank: int
    internal_id: int
    public_lab_code: str
    laboratory_name: str
    category: str
    address: LabAddressResponse
    capability_evidence: CapabilityEvidenceResponse
    geographic_metadata: GeographicMetadataResponse


class QueryCriteriaResponse(BaseModel):
    """
    Echo of the search criteria applied to the request.
    """
    standard: str
    part: Optional[str] = None
    year: Optional[str] = None
    clauses: List[str] = Field(default_factory=list)
    test_requirements: List[str] = Field(default_factory=list)
    state: Optional[str] = None
    district: Optional[str] = None
    city: Optional[str] = None
    user_coordinates: Optional[Dict[str, float]] = None
    max_distance_km: Optional[float] = None
    category: Optional[str] = None
    require_complete_scope: bool = False
    limit: Optional[int] = None


class LabSearchResponse(BaseModel):
    """
    Unified API response for laboratory searches.
    """
    status: str = Field(..., description="High-level status: 'MATCH', 'NO_MATCH', or 'INVALID_REQUEST'")
    match_status: str = Field(..., description="Granular BIS match status: 'EXACT_MATCH', 'PARTIAL_MATCH', or 'NO_MATCH'")
    standard: str
    total_matching: int
    returned_candidates: int
    query_criteria: QueryCriteriaResponse
    candidates: List[LaboratoryCandidateResponse]
    provenance: Dict[str, Any]
    disclaimer: str = (
        "Authoritative BIS LIMS testing capability strictly governs qualification. "
        "External geographic metadata provides proximity ranking only."
    )
    executed_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class LabNaturalSearchRequest(BaseModel):
    """
    Search request for Natural-Language BIS Laboratory Finder API.
    Interpreted via Groq / controlled deterministic terminology before execution.
    """
    query: str = Field(
        ...,
        description="Natural language laboratory search query (e.g., 'find labs for testing LED lamps near Delhi')."
    )
    latitude: Optional[float] = Field(
        None,
        description="Optional user reference latitude in [-90.0, 90.0] for proximity ranking."
    )
    longitude: Optional[float] = Field(
        None,
        description="Optional user reference longitude in [-180.0, 180.0] for proximity ranking."
    )
    max_distance_km: Optional[float] = Field(
        None,
        description="Optional maximum distance radius in km."
    )
    category: Optional[str] = Field(
        None,
        description="Optional laboratory category override: 'BIS_OWNED', 'BIS_RECOGNIZED', or 'BIS_EMPANELLED'."
    )
    require_complete_scope: Optional[bool] = Field(
        None,
        description="Optional override for complete (non-partial) scope requirement."
    )
    limit: Optional[int] = Field(
        None,
        description="Optional maximum number of laboratory candidates to return."
    )


class LabNaturalSearchResponse(BaseModel):
    """
    Unified response for Natural-Language Laboratory Search.
    Factual interpretation is decoupled from authoritative BIS LIMS search results.
    """
    status: str = Field(..., description="'MATCH', 'NO_MATCH', or 'NEEDS_CLARIFICATION'")
    parsed_query: ParsedLabQuery
    search_results: Optional[LabSearchResponse] = None
    clarification_message: Optional[str] = None


# ---------------------------------------------------------------------------
# Engine Singletons & Service Function
# ---------------------------------------------------------------------------

_matching_engine: Optional[LimsMatchingEngine] = None
_ranking_engine: Optional[GeographicRankingEngine] = None


def get_matching_engine() -> LimsMatchingEngine:
    global _matching_engine
    if _matching_engine is None:
        _matching_engine = LimsMatchingEngine()
    return _matching_engine


def get_ranking_engine() -> GeographicRankingEngine:
    global _ranking_engine
    if _ranking_engine is None:
        _ranking_engine = GeographicRankingEngine()
    return _ranking_engine


def validate_search_request(req: LabSearchRequest) -> None:
    """
    Validates search request parameters against architectural invariants.
    Raises HTTPException(status_code=400) on invalid input.
    """
    # 1. Standard requirement
    if not req.standard or not req.standard.strip():
        raise HTTPException(
            status_code=400,
            detail={
                "status": "INVALID_REQUEST",
                "error": "Standard number must be provided."
            }
        )
    if len(req.standard.strip()) < 2:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "INVALID_REQUEST",
                "error": "Standard number is too short."
            }
        )

    # 2. Coordinates validation
    has_lat = req.latitude is not None
    has_lon = req.longitude is not None
    if has_lat != has_lon:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "INVALID_REQUEST",
                "error": "Both latitude and longitude must be provided for coordinate-based proximity ranking."
            }
        )

    if has_lat and has_lon:
        if not validate_coordinates(req.latitude, req.longitude):
            raise HTTPException(
                status_code=400,
                detail={
                    "status": "INVALID_REQUEST",
                    "error": f"Invalid coordinates: latitude ({req.latitude}) must be in [-90, 90] and longitude ({req.longitude}) in [-180, 180]."
                }
            )

    # 3. max_distance_km validation
    if req.max_distance_km is not None:
        if not (has_lat and has_lon):
            raise HTTPException(
                status_code=400,
                detail={
                    "status": "INVALID_REQUEST",
                    "error": "max_distance_km requires reference latitude and longitude."
                }
            )
        if req.max_distance_km <= 0:
            raise HTTPException(
                status_code=400,
                detail={
                    "status": "INVALID_REQUEST",
                    "error": "max_distance_km must be greater than zero."
                }
            )

    # 4. Limit validation
    if req.limit is not None and req.limit <= 0:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "INVALID_REQUEST",
                "error": "limit must be greater than zero."
            }
        )

    # 5. Category validation
    if req.category:
        valid_cats = {c.value for c in LabCategory}
        cat_clean = req.category.strip().upper()
        if cat_clean not in valid_cats:
            raise HTTPException(
                status_code=400,
                detail={
                    "status": "INVALID_REQUEST",
                    "error": f"Invalid laboratory category: '{req.category}'. Allowed categories: {sorted(list(valid_cats))}."
                }
            )


def execute_search(
    req: LabSearchRequest,
    matching_engine: Optional[LimsMatchingEngine] = None,
    ranking_engine: Optional[GeographicRankingEngine] = None
) -> LabSearchResponse:
    """
    Core search orchestration:
    1. Validate request parameters.
    2. Execute capability matching via LimsMatchingEngine (capability-first).
    3. If matched candidates exist, apply geographic ranking & distance calculation.
    4. Apply result limiting if requested.
    5. Package and return structured LabSearchResponse.
    """
    validate_search_request(req)

    matcher = matching_engine or get_matching_engine()
    ranker = ranking_engine or get_ranking_engine()

    # Parse Category enum if provided
    cat_enum: Optional[LabCategory] = None
    if req.category:
        cat_enum = LabCategory(req.category.strip().upper())

    # -----------------------------------------------------------------------
    # Step 1: Capability Matching (BIS LIMS is sole capability authority)
    # -----------------------------------------------------------------------
    matching_req = LabMatchingRequest(
        standard=req.standard,
        part=req.part,
        year=req.year,
        clauses=req.clauses,
        test_requirements=req.test_requirements,
        state=req.state,
        district=req.district,
        city=req.city,
        category=cat_enum,
        require_complete_scope=req.require_complete_scope
    )

    matching_res = matcher.match(matching_req)

    # Prepare user coordinates dict for echoing
    user_coords = None
    if req.latitude is not None and req.longitude is not None:
        user_coords = {"latitude": req.latitude, "longitude": req.longitude}

    query_criteria = QueryCriteriaResponse(
        standard=req.standard,
        part=req.part,
        year=req.year,
        clauses=req.clauses,
        test_requirements=req.test_requirements,
        state=req.state,
        district=req.district,
        city=req.city,
        user_coordinates=user_coords,
        max_distance_km=req.max_distance_km,
        category=req.category,
        require_complete_scope=req.require_complete_scope,
        limit=req.limit
    )

    # If matching failed structurally
    if matching_res.status == MatchStatus.INVALID_REQUEST:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "INVALID_REQUEST",
                "error": matching_res.provenance.get("error", "Invalid standard request.")
            }
        )

    # If no candidates matched BIS capability
    if matching_res.status == MatchStatus.NO_MATCH or not matching_res.candidates:
        return LabSearchResponse(
            status="NO_MATCH",
            match_status=matching_res.status.value,
            standard=req.standard,
            total_matching=0,
            returned_candidates=0,
            query_criteria=query_criteria,
            candidates=[],
            provenance={
                "bis_lims_matching": matching_res.provenance,
                "geographic_ranking": None
            }
        )

    # -----------------------------------------------------------------------
    # Step 2: Geographic Ranking & Proximity Attachment
    # -----------------------------------------------------------------------
    ranked_candidates = ranker.rank_candidates(
        candidates=matching_res.candidates,
        user_lat=req.latitude,
        user_lon=req.longitude,
        max_distance_km=req.max_distance_km
    )

    total_matching = len(ranked_candidates)

    # If max_distance_km filtered all candidates out
    if total_matching == 0:
        return LabSearchResponse(
            status="NO_MATCH",
            match_status=matching_res.status.value,
            standard=req.standard,
            total_matching=0,
            returned_candidates=0,
            query_criteria=query_criteria,
            candidates=[],
            provenance={
                "bis_lims_matching": matching_res.provenance,
                "geographic_ranking": {
                    "user_coordinates": user_coords,
                    "max_distance_km": req.max_distance_km,
                    "filtered_out_all": True
                }
            }
        )

    # Apply limit
    returned_candidates = ranked_candidates
    if req.limit is not None and req.limit > 0:
        returned_candidates = ranked_candidates[:req.limit]

    # -----------------------------------------------------------------------
    # Step 3: Serialize Candidates
    # -----------------------------------------------------------------------
    serialized_candidates = [_serialize_candidate(cand) for cand in returned_candidates]

    ranking_provenance = {
        "user_coordinates": user_coords,
        "ranked_candidate_count": total_matching,
        "returned_candidate_count": len(serialized_candidates),
        "max_distance_km_filter": req.max_distance_km,
        "ranking_engine": "Phase F3 Step 6 Deterministic Haversine Ranking",
        "authority_disclaimer": (
            "Geographic ranking is strictly a proximity ordering of already-qualified "
            "BIS laboratories. Proximity does not alter testing capability or statutory scope."
        )
    }

    return LabSearchResponse(
        status="MATCH",
        match_status=matching_res.status.value,
        standard=req.standard,
        total_matching=total_matching,
        returned_candidates=len(serialized_candidates),
        query_criteria=query_criteria,
        candidates=serialized_candidates,
        provenance={
            "bis_lims_matching": matching_res.provenance,
            "geographic_ranking": ranking_provenance
        }
    )


def _serialize_candidate(cand: LabCandidateMatch) -> LaboratoryCandidateResponse:
    """Serializes an internal LabCandidateMatch into the canonical API response model."""
    geo = cand.external_geographic_metadata or {}
    cat_val = cand.category.value if isinstance(cand.category, LabCategory) else str(cand.category)
    scope_comp_val = (
        cand.scope_completeness.value
        if isinstance(cand.scope_completeness, ScopeCompleteness)
        else str(cand.scope_completeness)
    )
    reasons_val = [
        r.value if isinstance(r, MatchReason) else str(r)
        for r in cand.reasons
    ]

    return LaboratoryCandidateResponse(
        rank=cand.rank,
        internal_id=cand.internal_id,
        public_lab_code=cand.public_lab_code,
        laboratory_name=cand.laboratory_identity,
        category=cat_val,
        address=LabAddressResponse(
            original_address=cand.original_address,
            state=cand.state,
            district=cand.district,
            city=cand.city,
            pincode=cand.pincode
        ),
        capability_evidence=CapabilityEvidenceResponse(
            matching_standard=cand.matching_standard,
            matching_scope_id=cand.matching_scope_id,
            scope_completeness=scope_comp_val,
            matched_clauses=cand.matched_clauses,
            unmatched_requested_clauses=cand.unmatched_requested_clauses,
            excluded_clauses=cand.excluded_clauses,
            match_reasons=reasons_val,
            explanation=cand.explanation,
            match_score=cand.match_score,
            base_testing_fee=cand.base_testing_fee,
            clause_fee_total=cand.clause_fee_total,
            currency=cand.currency,
            provenance_url=cand.provenance_url,
            provenance_sha256=cand.provenance_sha256
        ),
        geographic_metadata=GeographicMetadataResponse(
            has_coordinates=bool(geo.get("has_coordinates", False)),
            latitude=geo.get("laboratory_latitude"),
            longitude=geo.get("laboratory_longitude"),
            distance_km=geo.get("distance_km"),
            geocoding_status=geo.get("geocoding_status", "UNKNOWN"),
            formatted_address=geo.get("formatted_address"),
            place_id=geo.get("place_id"),
            confidence=geo.get("confidence"),
            match_type=geo.get("match_type"),
            provider=geo.get("provider", "GEOAPIFY"),
            authority_disclaimer=geo.get(
                "authority_disclaimer",
                "Geographic distance is supplementary spatial metadata. "
                "It does not constitute normative evidence of BIS recognition, "
                "laboratory capability, or testing scope."
            )
        )
    )


def execute_natural_search(
    req: LabNaturalSearchRequest,
    matching_engine: Optional[LimsMatchingEngine] = None,
    ranking_engine: Optional[GeographicRankingEngine] = None,
    groq_client: Optional[Any] = None
) -> LabNaturalSearchResponse:
    """
    Orchestrates a natural-language laboratory search:
    1. Interprets query via Groq / controlled deterministic parser.
    2. Supports product-family expansion across multiple Indian Standards.
    3. Supports location-only and laboratory-name discovery without fabricating capabilities.
    4. Falls back to verified scope text discovery for unrecognized product keywords.
    5. Deduplicates candidates by internal_id and preserves strongest verified evidence.
    6. Preserves deterministic Haversine ranking when coordinates/anchors are provided.
    """
    parsed = parse_lab_natural_query(req.query, groq_client=groq_client)

    matcher = matching_engine or get_matching_engine()
    ranker = ranking_engine or get_ranking_engine()

    effective_category = req.category or parsed.category
    effective_scope = req.require_complete_scope if req.require_complete_scope is not None else parsed.require_complete_scope
    cat_enum: Optional[LabCategory] = None
    if effective_category:
        cat_enum = LabCategory(effective_category.strip().upper())

    user_coords = None
    if req.latitude is not None and req.longitude is not None:
        user_coords = {"latitude": req.latitude, "longitude": req.longitude}

    # Determine standards to search
    standards_to_search = list(parsed.standards)
    if not standards_to_search and parsed.standard:
        standards_to_search = [parsed.standard]

    # If no standards yet, check generic scope-text fallback before giving up
    if not standards_to_search and not parsed.state and not parsed.city and not parsed.lab_name:
        text_scopes = matcher.retrieval_layer.search_scopes_by_text(req.query)
        if text_scopes:
            from ai.lims.retrieval_layer import LimsRetrievalLayer
            discovered = list(dict.fromkeys(
                LimsRetrievalLayer._normalize_std_key(s.standard_number)
                for s in text_scopes if s.standard_number
            ))
            if discovered:
                standards_to_search = discovered
                parsed.clarification_needed = False
                if not parsed.factual_summary:
                    parsed.factual_summary = f"Discovered verified testing scopes for: {req.query}"

    # Scenario 1: Standards exist (Single standard or Product-family expanded standards)
    if standards_to_search:
        merged_by_id: Dict[int, LabCandidateMatch] = {}
        matched_standards: Set[str] = set()

        for std in standards_to_search:
            m_req = LabMatchingRequest(
                standard=std,
                state=parsed.state,
                city=parsed.city,
                category=cat_enum,
                require_complete_scope=effective_scope
            )
            m_res = matcher.match(m_req)
            if m_res.status in (MatchStatus.EXACT_MATCH, MatchStatus.PARTIAL_MATCH) and m_res.candidates:
                matched_standards.add(std)
                for cand in m_res.candidates:
                    if cand.internal_id not in merged_by_id:
                        merged_by_id[cand.internal_id] = cand
                    else:
                        # Preserve strongest verified capability evidence
                        existing = merged_by_id[cand.internal_id]
                        if cand.match_score > existing.match_score:
                            merged_by_id[cand.internal_id] = cand

        raw_candidates = list(merged_by_id.values())
        # Deterministic sorting: match_score desc, then internal_id asc
        raw_candidates.sort(key=lambda c: (-c.match_score, c.internal_id))

        ranked_candidates = ranker.rank_candidates(
            candidates=raw_candidates,
            user_lat=req.latitude,
            user_lon=req.longitude,
            max_distance_km=req.max_distance_km
        )

        total_matching = len(ranked_candidates)
        returned_candidates = ranked_candidates
        if req.limit is not None and req.limit > 0:
            returned_candidates = ranked_candidates[:req.limit]

        serialized = [_serialize_candidate(c) for c in returned_candidates]
        primary_std = parsed.standard or (standards_to_search[0] if standards_to_search else req.query)

        query_criteria = QueryCriteriaResponse(
            standard=primary_std,
            state=parsed.state,
            city=parsed.city,
            latitude=req.latitude,
            longitude=req.longitude,
            max_distance_km=req.max_distance_km,
            category=effective_category,
            require_complete_scope=effective_scope,
            limit=req.limit
        )

        ranking_provenance = {
            "user_coordinates": user_coords,
            "ranked_candidate_count": total_matching,
            "returned_candidate_count": len(serialized),
            "max_distance_km_filter": req.max_distance_km,
            "ranking_engine": "Phase F3 Step 6 Deterministic Haversine Ranking",
            "authority_disclaimer": (
                "Geographic ranking is strictly a proximity ordering of already-qualified "
                "BIS laboratories. Proximity does not alter testing capability or statutory scope."
            )
        }

        search_res = LabSearchResponse(
            status="MATCH" if total_matching > 0 else "NO_MATCH",
            match_status="EXACT_MATCH" if total_matching > 0 else "NO_MATCH",
            standard=primary_std,
            total_matching=total_matching,
            returned_candidates=len(serialized),
            query_criteria=query_criteria,
            candidates=serialized,
            provenance={
                "bis_lims_matching": {
                    "standards_evaluated": standards_to_search,
                    "matched_standards": list(matched_standards),
                    "total_evaluated_standards": len(standards_to_search)
                },
                "geographic_ranking": ranking_provenance
            }
        )

        return LabNaturalSearchResponse(
            status=search_res.status,
            parsed_query=parsed,
            search_results=search_res
        )

    # Scenario 2: Location-only or Laboratory-name discovery (No specific standard required)
    target_lab_name = parsed.lab_name
    if not target_lab_name and not (parsed.state or parsed.city):
        target_lab_name = req.query.strip()

    discovered_labs = matcher.retrieval_layer.search_laboratories(
        name=target_lab_name,
        state=parsed.state,
        city=parsed.city,
        category=cat_enum,
        limit=580
    )

    if discovered_labs:
        discovery_candidates: List[LabCandidateMatch] = []
        for lab in discovered_labs:
            scopes = matcher.retrieval_layer.get_scope_for_laboratory(lab.internal_id)
            if scopes:
                primary_scope = scopes[0]
                matching_std = primary_scope.standard_number
                scope_id = primary_scope.scope_id
                scope_comp = ScopeCompleteness.COMPLETE_SCOPE if primary_scope.is_complete_scope else ScopeCompleteness.PARTIAL_SCOPE
                expl = (
                    f"Accredited BIS laboratory ({lab.category.value if isinstance(lab.category, LabCategory) else lab.category}). "
                    f"Statutory testing scope on record (e.g. {primary_scope.standard_number}). "
                    f"Location/Identity discovery result; capability determined strictly by statutory LIMS scope."
                )
                score = 1.0
            else:
                matching_std = "NO_SCOPES_CATALOGED"
                scope_id = f"NO_SCOPE_{lab.internal_id}"
                scope_comp = ScopeCompleteness.UNKNOWN
                expl = (
                    f"Accredited BIS laboratory ({lab.category.value if isinstance(lab.category, LabCategory) else lab.category}). "
                    f"Empty testing scope in BIS directory."
                )
                score = 0.5

            reasons_list = [MatchReason.LOCATION_FILTER_MATCH] if (parsed.state or parsed.city) else ([MatchReason.EXACT_STANDARD_SCOPE] if scopes else [])

            cand = LabCandidateMatch(
                internal_id=lab.internal_id,
                public_lab_code=lab.lab_code,
                laboratory_identity=lab.lab_name,
                category=lab.category if isinstance(lab.category, LabCategory) else LabCategory(lab.category),
                original_address=lab.original_address,
                state=lab.normalized_state,
                district=lab.normalized_district,
                city=lab.normalized_city,
                pincode=lab.pincode,
                matching_standard=matching_std,
                matching_scope_id=scope_id,
                scope_completeness=scope_comp,
                matched_clauses=[],
                unmatched_requested_clauses=[],
                excluded_clauses=[],
                reasons=reasons_list,
                explanation=expl,
                match_score=score,
                base_testing_fee=None,
                clause_fee_total=None,
                currency="INR",
                provenance_url=lab.source_url,
                provenance_sha256=lab.provenance_sha256
            )
            discovery_candidates.append(cand)

        # Deterministic sort
        discovery_candidates.sort(key=lambda c: (-c.match_score, c.internal_id))

        ranked_candidates = ranker.rank_candidates(
            candidates=discovery_candidates,
            user_lat=req.latitude,
            user_lon=req.longitude,
            max_distance_km=req.max_distance_km
        )

        total_matching = len(ranked_candidates)
        returned_candidates = ranked_candidates
        if req.limit is not None and req.limit > 0:
            returned_candidates = ranked_candidates[:req.limit]

        serialized = [_serialize_candidate(c) for c in returned_candidates]

        discovery_label = (
            f"Location: {parsed.city or parsed.state}"
            if (parsed.city or parsed.state)
            else f"Laboratory: {target_lab_name}"
        )

        query_criteria = QueryCriteriaResponse(
            standard=discovery_label,
            state=parsed.state,
            city=parsed.city,
            latitude=req.latitude,
            longitude=req.longitude,
            max_distance_km=req.max_distance_km,
            category=effective_category,
            require_complete_scope=effective_scope,
            limit=req.limit
        )

        ranking_provenance = {
            "user_coordinates": user_coords,
            "ranked_candidate_count": total_matching,
            "returned_candidate_count": len(serialized),
            "max_distance_km_filter": req.max_distance_km,
            "ranking_engine": "Phase F3 Step 6 Deterministic Haversine Ranking",
            "authority_disclaimer": (
                "Geographic discovery identifies accredited BIS laboratories matching location or identity criteria. "
                "Proximity does not establish testing capability."
            )
        }

        search_res = LabSearchResponse(
            status="MATCH" if total_matching > 0 else "NO_MATCH",
            match_status="LOCATION_DISCOVERY" if (parsed.state or parsed.city) else "LAB_DISCOVERY",
            standard=discovery_label,
            total_matching=total_matching,
            returned_candidates=len(serialized),
            query_criteria=query_criteria,
            candidates=serialized,
            provenance={
                "bis_lims_matching": {
                    "discovery_type": "LOCATION" if (parsed.state or parsed.city) else "LAB_NAME",
                    "total_discovered": len(discovered_labs)
                },
                "geographic_ranking": ranking_provenance
            }
        )

        return LabNaturalSearchResponse(
            status=search_res.status,
            parsed_query=parsed,
            search_results=search_res
        )

    # Scenario 3: Unrecognized query requires clarification
    return LabNaturalSearchResponse(
        status="NEEDS_CLARIFICATION",
        parsed_query=parsed,
        search_results=None,
        clarification_message=parsed.clarification_message or (
            "Please specify an Indian Standard number (e.g. IS 4985), product, laboratory name, "
            "or location to find accredited testing laboratories."
        )
    )


# ---------------------------------------------------------------------------
# FastAPI Router Definition
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/labs", tags=["BIS Laboratory Finder"])


@router.post("/search", response_model=LabSearchResponse)
async def search_labs_post(req: LabSearchRequest) -> LabSearchResponse:
    """
    Searches for BIS laboratories capable of testing against a given Indian Standard.
    Capability matching is evaluated first; proximity ranking is applied to qualified labs.
    """
    return execute_search(req)


@router.get("/search", response_model=LabSearchResponse)
async def search_labs_get(
    standard: str = Query(..., description="Mandatory Indian Standard (e.g. 'IS 4985')"),
    part: Optional[str] = Query(None, description="Standard part"),
    year: Optional[str] = Query(None, description="Standard year"),
    clauses: Optional[List[str]] = Query(None, description="Requested test clauses"),
    test_requirements: Optional[List[str]] = Query(None, description="Test requirements"),
    state: Optional[str] = Query(None, description="State filter"),
    district: Optional[str] = Query(None, description="District filter"),
    city: Optional[str] = Query(None, description="City filter"),
    latitude: Optional[float] = Query(None, description="User reference latitude"),
    longitude: Optional[float] = Query(None, description="User reference longitude"),
    max_distance_km: Optional[float] = Query(None, description="Max radius in km"),
    category: Optional[str] = Query(None, description="Category filter"),
    require_complete_scope: bool = Query(False, description="Require complete scope"),
    limit: Optional[int] = Query(None, description="Max results")
) -> LabSearchResponse:
    """
    GET endpoint for searching BIS laboratories by standard and optional geographic proximity.
    """
    req = LabSearchRequest(
        standard=standard,
        part=part,
        year=year,
        clauses=clauses or [],
        test_requirements=test_requirements or [],
        state=state,
        district=district,
        city=city,
        latitude=latitude,
        longitude=longitude,
        max_distance_km=max_distance_km,
        category=category,
        require_complete_scope=require_complete_scope,
        limit=limit
    )
    return execute_search(req)


@router.post("/natural-search", response_model=LabNaturalSearchResponse)
async def search_labs_natural_post(req: LabNaturalSearchRequest) -> LabNaturalSearchResponse:
    """
    POST endpoint for natural-language laboratory search.
    Interprets query via Groq / controlled terminology, then executes authoritative BIS LIMS search.
    """
    return execute_natural_search(req)


@router.get("/natural-search", response_model=LabNaturalSearchResponse)
async def search_labs_natural_get(
    query: str = Query(..., description="Natural language laboratory search query"),
    latitude: Optional[float] = Query(None, description="User reference latitude"),
    longitude: Optional[float] = Query(None, description="User reference longitude"),
    max_distance_km: Optional[float] = Query(None, description="Max radius in km"),
    category: Optional[str] = Query(None, description="Category filter override"),
    require_complete_scope: Optional[bool] = Query(None, description="Require complete scope override"),
    limit: Optional[int] = Query(None, description="Max results")
) -> LabNaturalSearchResponse:
    """
    GET endpoint for natural-language laboratory search.
    """
    req = LabNaturalSearchRequest(
        query=query,
        latitude=latitude,
        longitude=longitude,
        max_distance_km=max_distance_km,
        category=category,
        require_complete_scope=require_complete_scope,
        limit=limit
    )
    return execute_natural_search(req)

