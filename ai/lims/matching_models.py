"""
Phase F3 Step 4A: Laboratory Matching Engine Data Models.

Defines deterministic data structures representing:
1. Laboratory Matching Request (standard, part, year, clauses, location, category)
2. Match Status, Reason, and Scope Completeness Enums
3. Structured Candidate Match Record (capability-first, strictly separating
   authoritative BIS attributes from external geographic metadata)
4. Unified Matching Result Container

Invariants:
- public lab_code and internal_id are strictly separated.
- original_address is preserved verbatim and never overwritten.
- external_geographic_metadata is explicitly separated and remains None in Step 4A.
- No fuzzy guessing or silent coercion of missing values into positive matches.
- Zero external language models or external geocoding dependencies.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone

from ai.lims.models import LabCategory


class MatchStatus(str, Enum):
    EXACT_MATCH = "EXACT_MATCH"
    PARTIAL_MATCH = "PARTIAL_MATCH"
    NO_MATCH = "NO_MATCH"
    INVALID_REQUEST = "INVALID_REQUEST"


class ScopeCompleteness(str, Enum):
    COMPLETE_SCOPE = "COMPLETE_SCOPE"
    PARTIAL_SCOPE = "PARTIAL_SCOPE"
    UNKNOWN = "UNKNOWN"


class MatchReason(str, Enum):
    EXACT_STANDARD_SCOPE = "EXACT_STANDARD_SCOPE"
    EXACT_STANDARD_PART_SCOPE = "EXACT_STANDARD_PART_SCOPE"
    CLAUSE_REQUIREMENTS_MATCHED = "CLAUSE_REQUIREMENTS_MATCHED"
    PARTIAL_SCOPE = "PARTIAL_SCOPE"
    LOCATION_FILTER_MATCH = "LOCATION_FILTER_MATCH"
    EXCLUDED_CLAUSES_PRESENT = "EXCLUDED_CLAUSES_PRESENT"
    MISSING_REQUIRED_CLAUSES = "MISSING_REQUIRED_CLAUSES"
    NO_MATCHING_STANDARD = "NO_MATCHING_STANDARD"
    LOCATION_FILTER_MISMATCH = "LOCATION_FILTER_MISMATCH"
    CATEGORY_FILTER_MISMATCH = "CATEGORY_FILTER_MISMATCH"


@dataclass
class LabMatchingRequest:
    """
    Deterministic request input for the Laboratory Matching Engine.
    """
    standard: str
    part: Optional[str] = None
    year: Optional[str] = None
    clauses: List[str] = field(default_factory=list)
    test_requirements: List[str] = field(default_factory=list)
    state: Optional[str] = None
    district: Optional[str] = None
    city: Optional[str] = None
    category: Optional[LabCategory] = None
    require_complete_scope: bool = False

    def validate(self) -> Tuple[bool, Optional[str]]:
        """Validates that request has required normative standard."""
        if not self.standard or not self.standard.strip():
            return False, "MISSING_STANDARD: Standard number must be provided."
        clean_std = self.standard.strip().upper()
        if len(clean_std) < 2:
            return False, "INVALID_STANDARD: Standard number is too short."
        return True, None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if self.category:
            d["category"] = self.category.value if isinstance(self.category, LabCategory) else self.category
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LabMatchingRequest":
        cat = data.get("category")
        if cat and not isinstance(cat, LabCategory):
            cat = LabCategory(cat)
        return cls(
            standard=data.get("standard", ""),
            part=data.get("part"),
            year=data.get("year"),
            clauses=data.get("clauses", []) or [],
            test_requirements=data.get("test_requirements", []) or [],
            state=data.get("state"),
            district=data.get("district"),
            city=data.get("city"),
            category=cat,
            require_complete_scope=bool(data.get("require_complete_scope", False))
        )


@dataclass
class LabCandidateMatch:
    """
    Authoritative candidate match resulting from deterministic scope evaluation.
    Preserves strict separation between statutory BIS attributes and optional
    external geographic metadata.
    """
    laboratory_identity: str
    public_lab_code: str
    internal_id: int
    category: LabCategory
    original_address: str
    state: Optional[str] = None
    district: Optional[str] = None
    city: Optional[str] = None
    pincode: Optional[str] = None
    matching_standard: str = ""
    matching_scope_id: str = ""
    scope_completeness: ScopeCompleteness = ScopeCompleteness.UNKNOWN
    matched_clauses: List[str] = field(default_factory=list)
    unmatched_requested_clauses: List[str] = field(default_factory=list)
    excluded_clauses: List[str] = field(default_factory=list)
    reasons: List[MatchReason] = field(default_factory=list)
    explanation: str = ""
    base_testing_fee: Optional[float] = None
    clause_fee_total: Optional[float] = None
    currency: str = "INR"
    provenance_url: str = ""
    provenance_sha256: str = ""
    match_score: float = 0.0
    rank: int = 0
    # Strictly marked as external metadata (NOT authoritative BIS data, remains None in 4A)
    external_geographic_metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value if isinstance(self.category, LabCategory) else self.category
        d["scope_completeness"] = self.scope_completeness.value if isinstance(self.scope_completeness, ScopeCompleteness) else self.scope_completeness
        d["reasons"] = [r.value if isinstance(r, MatchReason) else r for r in self.reasons]
        return d


@dataclass
class LabMatchingResult:
    """
    Container for matching engine output.
    """
    request: LabMatchingRequest
    status: MatchStatus
    candidates: List[LabCandidateMatch] = field(default_factory=list)
    total_candidates: int = 0
    execution_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    catalog_statistics: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request": self.request.to_dict(),
            "status": self.status.value,
            "candidates": [c.to_dict() for c in self.candidates],
            "total_candidates": self.total_candidates,
            "execution_timestamp": self.execution_timestamp,
            "catalog_statistics": self.catalog_statistics,
            "provenance": self.provenance
        }
