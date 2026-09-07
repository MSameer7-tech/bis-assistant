"""
Phase F3 Step 6: Deterministic Geographic Ranking Engine.

Ranks already-qualified BIS laboratory candidates based on geographic proximity
using existing cached coordinates and exact Haversine distance calculations.

Architectural Invariants:
1. Separation of Concerns: Geographic data NEVER qualifies, creates, or validates a candidate.
   BIS testing scope remains the sole normative authority on laboratory capabilities.
2. Zero Network Calls: Uses exclusively the frozen geographic cache on disk. Zero calls to
   Geoapify, Google Maps, OpenStreetMap, or external APIs.
3. Zero Coordinate Fabrication: Missing or ZERO_RESULTS coordinates remain strictly None,
   with distance_km set to None and explicitly represented.
4. Determinism: Ranking order is 100% deterministic, with stable laboratory internal_id
   as the final tie-breaker.
5. Immutability: Statutory laboratory identity, category, address, scope evidence, and provenance
   remain completely unchanged.
"""

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass, asdict, field

from ai.geo.distance import (
    haversine_distance_km,
    safe_haversine_distance_km,
    validate_coordinates,
)
from ai.geo.cache import LabGeographicCache
from ai.lims.matching_models import (
    LabCandidateMatch,
    LabMatchingResult,
    ScopeCompleteness,
)
from ai.lims.models import LabCategory


@dataclass
class GeographicDistanceMetadata:
    """
    Structured geographic metadata attached to a candidate match.
    Strictly supplementary to statutory BIS capabilities.
    """
    user_latitude: Optional[float]
    user_longitude: Optional[float]
    laboratory_latitude: Optional[float] = None
    laboratory_longitude: Optional[float] = None
    distance_km: Optional[float] = None
    distance_km_raw: Optional[float] = None
    has_coordinates: bool = False
    geocoding_status: str = "UNKNOWN"
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
    ranked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class GeographicRankingEngine:
    """
    Ranks already-qualified BIS laboratory candidates geographically.
    Operates strictly as a post-qualification ordering layer.
    """

    def __init__(self, cache: Optional[LabGeographicCache] = None):
        self.cache = cache or LabGeographicCache()

    def attach_distance(
        self,
        candidate: LabCandidateMatch,
        user_lat: Optional[float] = None,
        user_lon: Optional[float] = None
    ) -> LabCandidateMatch:
        """
        Attaches geographic distance and spatial metadata to a single candidate.
        Does NOT alter candidate capability evaluation.
        """
        has_user_coords = (user_lat is not None and user_lon is not None)
        if has_user_coords and not validate_coordinates(user_lat, user_lon):
            # Invalid user coordinates: cannot calculate distance
            candidate.external_geographic_metadata = GeographicDistanceMetadata(
                user_latitude=user_lat,
                user_longitude=user_lon,
                has_coordinates=False,
                geocoding_status="INVALID_USER_COORDINATES"
            ).to_dict()
            return candidate

        internal_id = candidate.internal_id
        original_address = candidate.original_address

        # Check cache for laboratory coordinates
        geo_meta = self.cache.get_for_laboratory(internal_id, original_address)

        if geo_meta is None:
            # Cache miss or stale address
            is_stale = self.cache.is_stale(internal_id, original_address)
            status = "STALE_ADDRESS" if is_stale else "MISSING_CACHE_RECORD"
            candidate.external_geographic_metadata = GeographicDistanceMetadata(
                user_latitude=user_lat,
                user_longitude=user_lon,
                has_coordinates=False,
                geocoding_status=status
            ).to_dict()
            return candidate

        # Laboratory found in cache
        if geo_meta.status == "SUCCESS" and geo_meta.has_valid_coordinates():
            if has_user_coords:
                dist = haversine_distance_km(
                    user_lat, user_lon, geo_meta.latitude, geo_meta.longitude
                )
                dist_rounded = round(dist, 2)
                dist_raw = dist
                status = "SUCCESS"
            else:
                dist_rounded = None
                dist_raw = None
                status = "SUCCESS_NO_USER_LOCATION"

            candidate.external_geographic_metadata = GeographicDistanceMetadata(
                user_latitude=user_lat,
                user_longitude=user_lon,
                laboratory_latitude=geo_meta.latitude,
                laboratory_longitude=geo_meta.longitude,
                distance_km=dist_rounded,
                distance_km_raw=dist_raw,
                has_coordinates=True,
                geocoding_status=status,
                formatted_address=geo_meta.formatted_address,
                place_id=geo_meta.place_id,
                confidence=geo_meta.confidence,
                match_type=geo_meta.match_type
            ).to_dict()
        else:
            # Zero results, failure status, or null coordinates
            candidate.external_geographic_metadata = GeographicDistanceMetadata(
                user_latitude=user_lat,
                user_longitude=user_lon,
                laboratory_latitude=None,
                laboratory_longitude=None,
                distance_km=None,
                distance_km_raw=None,
                has_coordinates=False,
                geocoding_status=geo_meta.status,
                formatted_address=geo_meta.formatted_address,
                place_id=geo_meta.place_id,
                confidence=geo_meta.confidence,
                match_type=geo_meta.match_type
            ).to_dict()

        return candidate

    def rank_candidates(
        self,
        candidates: List[LabCandidateMatch],
        user_lat: Optional[float] = None,
        user_lon: Optional[float] = None,
        max_distance_km: Optional[float] = None
    ) -> List[LabCandidateMatch]:
        """
        Ranks already-qualified candidates by geographic proximity.

        Ordering Rules:
        1. When user coordinates are provided:
           a. Candidates with valid coordinates precede candidates without coordinates.
           b. Candidates with coordinates are sorted by distance_km ascending.
        2. Deterministic tie-breaking for equal distance or missing user coordinates:
           a. Scope completeness (COMPLETE_SCOPE before PARTIAL_SCOPE)
           b. Match score (descending)
           c. Lab category (BIS_OWNED -> BIS_RECOGNIZED -> BIS_EMPANELLED)
           d. Laboratory internal_id (ascending) - guarantees bitwise deterministic ordering.
        """
        if not candidates:
            return []

        # Step 1: Attach distance metadata to all candidates
        enriched_candidates = [
            self.attach_distance(cand, user_lat, user_lon)
            for cand in candidates
        ]

        # Step 2: Optional max distance filtering (if requested)
        if max_distance_km is not None and max_distance_km > 0:
            filtered = []
            for cand in enriched_candidates:
                geo = cand.external_geographic_metadata or {}
                dist = geo.get("distance_km_raw")
                if dist is not None and dist <= max_distance_km:
                    filtered.append(cand)
            enriched_candidates = filtered

        # Step 3: Deterministic Sort
        def sort_key(cand: LabCandidateMatch) -> Tuple:
            geo = cand.external_geographic_metadata or {}
            has_coords = geo.get("has_coordinates", False)
            raw_dist = geo.get("distance_km_raw")

            # 1. Coordinate availability flag (0 = has coords, 1 = no coords)
            coord_flag = 0 if has_coords else 1

            # 2. Distance (float or inf)
            dist_val = raw_dist if (has_coords and raw_dist is not None) else float("inf")

            # 3. Scope completeness (COMPLETE_SCOPE = 0, PARTIAL_SCOPE = 1, UNKNOWN = 2)
            if cand.scope_completeness == ScopeCompleteness.COMPLETE_SCOPE:
                comp_score = 0
            elif cand.scope_completeness == ScopeCompleteness.PARTIAL_SCOPE:
                comp_score = 1
            else:
                comp_score = 2

            # 4. Match score (negated for descending order)
            score_neg = -cand.match_score

            # 5. Category preference
            if cand.category == LabCategory.BIS_OWNED:
                cat_score = 0
            elif cand.category == LabCategory.BIS_RECOGNIZED:
                cat_score = 1
            else:
                cat_score = 2

            # 6. Final tie-breaker: stable laboratory internal_id ascending
            id_tie = cand.internal_id

            return (coord_flag, dist_val, comp_score, score_neg, cat_score, id_tie)

        ranked = sorted(enriched_candidates, key=sort_key)

        # Step 4: Update rank property (1-indexed)
        for idx, cand in enumerate(ranked, start=1):
            cand.rank = idx

        return ranked

    def rank_matching_result(
        self,
        result: LabMatchingResult,
        user_lat: Optional[float] = None,
        user_lon: Optional[float] = None,
        max_distance_km: Optional[float] = None
    ) -> LabMatchingResult:
        """
        Convenience method to rank an entire LabMatchingResult container.
        Updates candidates in-place with geographic metadata and ranking.
        """
        ranked_candidates = self.rank_candidates(
            candidates=result.candidates,
            user_lat=user_lat,
            user_lon=user_lon,
            max_distance_km=max_distance_km
        )

        result.candidates = ranked_candidates
        result.total_candidates = len(ranked_candidates)

        # Record geographic ranking provenance
        result.provenance["geographic_ranking"] = {
            "user_coordinates": {"latitude": user_lat, "longitude": user_lon} if (user_lat is not None and user_lon is not None) else None,
            "ranked_candidate_count": len(ranked_candidates),
            "max_distance_km_filter": max_distance_km,
            "ranking_engine": "Phase F3 Step 6 Deterministic Haversine Ranking",
            "authority_disclaimer": (
                "Geographic ranking is strictly a proximity ordering of already-qualified "
                "BIS laboratories. Proximity does not alter testing capability or statutory scope."
            )
        }

        return result
