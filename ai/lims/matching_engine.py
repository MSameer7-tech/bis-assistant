"""
Phase F3 Step 4B: Deterministic BIS Laboratory Matching Engine.

Evaluates laboratory testing capabilities strictly based on authoritative
BIS LIMS catalog evidence.

Principles:
1. Capability strictly supersedes geographic proximity.
2. Exact Indian Standard match using normalized representations.
3. Clause-level capability verification (never assume an unlisted clause is supported).
4. Strict separation between public_lab_code and internal_id.
5. Preserves statutory BIS provenance.
6. Deterministic scoring and stable tie-breaking.
7. Zero LLM, zero vector similarity, zero external geocoding calls.
"""

from pathlib import Path
from typing import List, Dict, Optional, Union, Any, Set, Tuple
from datetime import datetime, timezone
import re

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
from ai.acquisition.lims_scope.scope_parser import normalize_standard


class LimsMatchingEngine:
    """
    Deterministic capability-first Laboratory Matching Engine.
    Operates on the authoritative normalized BIS LIMS catalog.
    """

    def __init__(self, retrieval_layer: Optional[LimsRetrievalLayer] = None, catalog_dir: Optional[Path] = None):
        if retrieval_layer is not None:
            self.retrieval_layer = retrieval_layer
        elif catalog_dir is not None:
            self.retrieval_layer = LimsRetrievalLayer.load_from_catalog(catalog_dir)
        else:
            default_path = Path("data/catalog/phase_f3_lims")
            if default_path.exists():
                self.retrieval_layer = LimsRetrievalLayer.load_from_catalog(default_path)
            else:
                self.retrieval_layer = LimsRetrievalLayer()

    @staticmethod
    def _clean_clause_id(clause_text: str) -> str:
        """
        Normalizes clause strings for deterministic comparison.
        E.g. 'Clause 5.1' -> '5.1', 'cl. 6' -> '6'
        """
        c = clause_text.strip().lower()
        c = re.sub(r'^(?:clause|cl\.?)\s*', '', c, flags=re.IGNORECASE)
        return c.strip()

    def match(self, request: LabMatchingRequest) -> LabMatchingResult:
        """
        Evaluates a LabMatchingRequest deterministically against the catalog.
        """
        # Step 1: Structural Request Validation
        is_valid, err_msg = request.validate()
        if not is_valid:
            return LabMatchingResult(
                request=request,
                status=MatchStatus.INVALID_REQUEST,
                candidates=[],
                total_candidates=0,
                catalog_statistics=self.retrieval_layer.get_statistics(),
                provenance={"error": err_msg or "INVALID_REQUEST"}
            )

        # Step 2: Normalize requested standard
        norm_std_key = LimsRetrievalLayer._normalize_std_key(request.standard)
        base_req_std, req_part, _, req_year = normalize_standard(request.standard)
        
        # If part or year are explicitly specified in the request object, they override string parsing
        effective_part = request.part if request.part is not None else req_part
        effective_year = request.year if request.year is not None else req_year

        # Step 3: Query retrieval layer for scopes matching standard
        matching_scopes: List[NormalizedLimsScope] = self.retrieval_layer._scopes_by_standard.get(norm_std_key, [])

        if not matching_scopes:
            return LabMatchingResult(
                request=request,
                status=MatchStatus.NO_MATCH,
                candidates=[],
                total_candidates=0,
                catalog_statistics=self.retrieval_layer.get_statistics(),
                provenance={"search_standard": norm_std_key, "match_type": "NO_SCOPE_ASSOCIATION"}
            )

        # Step 4: Evaluate candidate laboratories
        candidates_by_lab_id: Dict[int, LabCandidateMatch] = {}

        for scope in matching_scopes:
            lab = self.retrieval_layer.get_laboratory_by_id(scope.internal_lab_id)
            if not lab:
                continue

            # Standard Part Filter (if requested)
            if effective_part:
                clean_req_part = str(effective_part).strip().lower()
                clean_req_part = re.sub(r'^(?:part\s*)', '', clean_req_part).strip()
                scope_base, scope_part, _, _ = normalize_standard(scope.standard_number)
                clean_scope_part = str(scope_part or "").strip().lower()
                clean_scope_part = re.sub(r'^(?:part\s*)', '', clean_scope_part).strip()
                if clean_req_part and clean_scope_part and clean_req_part != clean_scope_part:
                    continue

            # Standard Year / Edition Filter (if requested)
            if effective_year:
                clean_req_year = str(effective_year).strip()
                scope_year = scope.edition_year or ""
                if not scope_year:
                    _, _, _, parsed_scope_year = normalize_standard(scope.standard_number)
                    scope_year = parsed_scope_year or ""
                if clean_req_year and scope_year and clean_req_year != scope_year:
                    continue

            # Category Filter (if requested)
            if request.category is not None:
                req_cat = request.category if isinstance(request.category, LabCategory) else LabCategory(request.category)
                if lab.category != req_cat:
                    continue

            # Location Filter: State (if requested)
            if request.state:
                state_query = request.state.strip().lower()
                lab_state = (lab.normalized_state or "").lower()
                lab_addr = lab.original_address.lower()
                if state_query not in lab_state and state_query not in lab_addr:
                    continue

            # Location Filter: District (if requested)
            if request.district:
                dist_query = request.district.strip().lower()
                lab_dist = (lab.normalized_district or "").lower()
                lab_addr = lab.original_address.lower()
                if dist_query not in lab_dist and dist_query not in lab_addr:
                    continue

            # Location Filter: City (if requested)
            if request.city:
                city_query = request.city.strip().lower()
                lab_city = (lab.normalized_city or "").lower()
                lab_addr = lab.original_address.lower()
                if city_query not in lab_city and city_query not in lab_addr:
                    continue

            # Scope Completeness Evaluation
            has_explicit_exclusions = bool(scope.excluded_clauses)
            scope_is_complete = bool(scope.is_complete_scope) and not has_explicit_exclusions
            completeness = ScopeCompleteness.COMPLETE_SCOPE if scope_is_complete else ScopeCompleteness.PARTIAL_SCOPE

            if request.require_complete_scope and completeness != ScopeCompleteness.COMPLETE_SCOPE:
                continue

            # Clause-level Evaluation
            matched_clauses: List[str] = []
            unmatched_clauses: List[str] = []
            excluded_clauses: List[str] = []
            reasons: List[MatchReason] = [MatchReason.EXACT_STANDARD_SCOPE]

            if effective_part:
                reasons.append(MatchReason.EXACT_STANDARD_PART_SCOPE)

            if completeness == ScopeCompleteness.PARTIAL_SCOPE:
                reasons.append(MatchReason.PARTIAL_SCOPE)

            # Available clauses in laboratory scope
            available_clauses_map: Dict[str, ClauseRecord] = {}
            for c in scope.clauses:
                clean_c = self._clean_clause_id(c.clause_number)
                available_clauses_map[clean_c] = c

            clean_excluded_set = {self._clean_clause_id(ec) for ec in scope.excluded_clauses}

            clause_fee_total = 0.0
            has_clause_fee = False

            if request.clauses:
                for req_c in request.clauses:
                    clean_req_c = self._clean_clause_id(req_c)
                    if clean_req_c in clean_excluded_set:
                        excluded_clauses.append(req_c)
                    elif clean_req_c in available_clauses_map:
                        rec = available_clauses_map[clean_req_c]
                        if rec.is_excluded:
                            excluded_clauses.append(req_c)
                        else:
                            matched_clauses.append(req_c)
                            if rec.fee_amount is not None:
                                clause_fee_total += rec.fee_amount
                                has_clause_fee = True
                    else:
                        unmatched_clauses.append(req_c)

                if matched_clauses and not unmatched_clauses and not excluded_clauses:
                    reasons.append(MatchReason.CLAUSE_REQUIREMENTS_MATCHED)
                if unmatched_clauses:
                    reasons.append(MatchReason.MISSING_REQUIRED_CLAUSES)
                if excluded_clauses:
                    reasons.append(MatchReason.EXCLUDED_CLAUSES_PRESENT)

            if request.state or request.district or request.city:
                reasons.append(MatchReason.LOCATION_FILTER_MATCH)

            # Capability-First Deterministic Scoring
            # Base exact standard capability: 100.0
            match_score = 100.0

            # Completeness bonus
            if completeness == ScopeCompleteness.COMPLETE_SCOPE:
                match_score += 20.0
            else:
                match_score += 5.0

            # Clause coverage score
            if request.clauses:
                coverage_ratio = len(matched_clauses) / max(len(request.clauses), 1)
                match_score += (coverage_ratio * 30.0)
                # Penalty for excluded or missing requested clauses
                if excluded_clauses:
                    match_score -= (len(excluded_clauses) * 15.0)
                if unmatched_clauses:
                    match_score -= (len(unmatched_clauses) * 10.0)
            else:
                match_score += 15.0

            # Location filter match minor bonus (capability strictly precedes location)
            if request.state or request.district or request.city:
                match_score += 2.0

            # Explanation construction strictly from BIS facts
            parts_expl = [f"Explicit BIS LIMS scope match for {scope.standard_number}"]
            if completeness == ScopeCompleteness.COMPLETE_SCOPE:
                parts_expl.append("with verified complete testing scope.")
            else:
                parts_expl.append("with partial testing scope.")
            if request.clauses:
                parts_expl.append(f"Matched {len(matched_clauses)}/{len(request.clauses)} requested clauses.")
                if excluded_clauses:
                    parts_expl.append(f"Excluded clauses: {', '.join(excluded_clauses)}.")
                if unmatched_clauses:
                    parts_expl.append(f"Unmatched clauses: {', '.join(unmatched_clauses)}.")

            explanation = " ".join(parts_expl)

            candidate = LabCandidateMatch(
                laboratory_identity=lab.lab_name,
                public_lab_code=lab.lab_code,
                internal_id=lab.internal_id,
                category=lab.category,
                original_address=lab.original_address,
                state=lab.normalized_state,
                district=lab.normalized_district,
                city=lab.normalized_city,
                pincode=lab.pincode,
                matching_standard=scope.standard_number,
                matching_scope_id=scope.scope_id,
                scope_completeness=completeness,
                matched_clauses=matched_clauses,
                unmatched_requested_clauses=unmatched_clauses,
                excluded_clauses=excluded_clauses,
                reasons=reasons,
                explanation=explanation,
                base_testing_fee=scope.base_testing_fee,
                clause_fee_total=clause_fee_total if has_clause_fee else None,
                currency=scope.currency,
                provenance_url=scope.source_url or lab.source_url,
                provenance_sha256=scope.source_sha256 or lab.provenance_sha256,
                match_score=round(match_score, 2),
                rank=0,
                external_geographic_metadata=None
            )

            # Deduplication per laboratory: keep best match score for the requested standard
            existing = candidates_by_lab_id.get(lab.internal_id)
            if existing is None or candidate.match_score > existing.match_score:
                candidates_by_lab_id[lab.internal_id] = candidate

        candidates = list(candidates_by_lab_id.values())

        if not candidates:
            return LabMatchingResult(
                request=request,
                status=MatchStatus.NO_MATCH,
                candidates=[],
                total_candidates=0,
                catalog_statistics=self.retrieval_layer.get_statistics(),
                provenance={"search_standard": norm_std_key, "filter_exhausted": True}
            )

        # Deterministic Ranking:
        # Primary: match_score (descending)
        # Secondary: matched_clauses count (descending)
        # Tie-breaker 1: public_lab_code (ascending string)
        # Tie-breaker 2: internal_id (ascending int)
        candidates.sort(
            key=lambda c: (-c.match_score, -len(c.matched_clauses), c.public_lab_code, c.internal_id)
        )

        for idx, cand in enumerate(candidates, start=1):
            cand.rank = idx

        # Determine overall match status
        has_complete = any(
            c.scope_completeness == ScopeCompleteness.COMPLETE_SCOPE and not c.unmatched_requested_clauses
            for c in candidates
        )
        overall_status = MatchStatus.EXACT_MATCH if has_complete else MatchStatus.PARTIAL_MATCH

        return LabMatchingResult(
            request=request,
            status=overall_status,
            candidates=candidates,
            total_candidates=len(candidates),
            catalog_statistics=self.retrieval_layer.get_statistics(),
            provenance={
                "search_standard": norm_std_key,
                "engine": "LimsMatchingEngine",
                "authority": "Bureau of Indian Standards (BIS LIMS)",
                "catalog_source": "data/catalog/phase_f3_lims"
            }
        )
