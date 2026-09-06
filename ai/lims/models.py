"""
Phase F3 Step 3: Authoritative BIS LIMS Data Models.

Defines:
1. Category Enums (BIS_OWNED, BIS_RECOGNIZED, BIS_EMPANELLED)
2. Raw Layer Models (RawLimsLabRecord, RawLimsScopeRecord)
3. Normalized Search Layer Models (NormalizedLimsLab, NormalizedLimsScope, ClauseRecord)
4. Validation & Rejection Tracking Models (RejectedRecord)

Architectural Invariants:
- original_address is NEVER modified, overwritten, or substituted with geocoded values.
- Lab categories remain strictly segregated (no generic collapse).
- Internal database ID (internal_id) and public regulatory code (lab_code) are preserved separately.
- Scope and clause-level structures are preserved without flattening.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, List, Dict, Any


class LabCategory(str, Enum):
    BIS_OWNED = "BIS_OWNED"
    BIS_RECOGNIZED = "BIS_RECOGNIZED"
    BIS_EMPANELLED = "BIS_EMPANELLED"


@dataclass(frozen=True)
class TestingCharge:
    amount: float
    currency: str = "INR"
    tax_included: bool = False
    raw_value: str = ""
    charge_context: str = ""


@dataclass(frozen=True)
class ClauseRecord:
    clause_number: str
    is_excluded: bool
    fee_amount: Optional[float] = None
    effective_date: Optional[str] = None
    remark: Optional[str] = None
    raw_text: Optional[str] = None


@dataclass
class RawLimsLabRecord:
    raw_id: str
    internal_id: Optional[int]
    lab_code: Optional[str]
    lab_name: str
    category: str
    raw_address: str
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    validity_date: Optional[str] = None
    source_url: str = ""
    retrieved_at: str = ""
    raw_html_sha256: str = ""
    extraction_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RawLimsScopeRecord:
    raw_scope_id: str
    internal_lab_id: int
    raw_standard: str
    raw_product: Optional[str] = None
    raw_grade_type_size: Optional[str] = None
    raw_fee_text: Optional[str] = None
    raw_validity_date: Optional[str] = None
    raw_remark: Optional[str] = None
    raw_modal_html: Optional[str] = None
    source_url: str = ""
    source_sha256: str = ""
    retrieved_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class NormalizedLimsLab:
    internal_id: int
    lab_code: str
    lab_name: str
    category: LabCategory
    original_address: str
    normalized_state: Optional[str] = None
    normalized_district: Optional[str] = None
    normalized_city: Optional[str] = None
    pincode: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    recognition_status: str = "ACTIVE"
    validity_date: Optional[str] = None
    source_url: str = ""
    retrieved_at: str = ""
    provenance_sha256: str = ""
    scope_status: str = "SCOPE_AVAILABLE"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value if isinstance(self.category, LabCategory) else self.category
        return d


@dataclass
class NormalizedLimsScope:
    scope_id: str
    internal_lab_id: int
    lab_code: str
    standard_number: str
    standard_title: Optional[str] = None
    edition_year: Optional[str] = None
    product: Optional[str] = None
    grade_type_size: Optional[str] = None
    base_testing_fee: Optional[float] = None
    currency: str = "INR"
    is_complete_scope: bool = True
    clauses: List[ClauseRecord] = field(default_factory=list)
    excluded_clauses: List[str] = field(default_factory=list)
    validity_date: Optional[str] = None
    remark: Optional[str] = None
    source_url: str = ""
    source_sha256: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["clauses"] = [asdict(c) for c in self.clauses]
        return d


@dataclass
class RejectedRecord:
    record_type: str  # "LABORATORY" | "SCOPE"
    raw_identifier: str
    rejection_reason: str
    raw_data: Dict[str, Any]
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
