from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class LicenceStatus(str, Enum):
    OPERATIVE = "OPERATIVE"
    EXPIRED = "EXPIRED"
    SUSPENDED = "SUSPENDED"
    CANCELLED = "CANCELLED"


class LicenceRecord(BaseModel):
    # Registry fields
    cml_number: Optional[str] = None
    standard_number: Optional[str] = None
    product_name: Optional[str] = None
    licensee_name: Optional[str] = None
    factory_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    scheme_code: Optional[str] = "SCHEME-I"
    status: Optional[LicenceStatus] = LicenceStatus.OPERATIVE
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    brand_names: List[str] = Field(default_factory=list)
    varieties_covered: List[str] = Field(default_factory=list)
    is_foreign_manufacturer: bool = False
    evidence_backed: bool = True

    # Acquisition / Document fields
    record_id: Optional[str] = None
    record_type: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    source_url: Optional[str] = None
    source_type: Optional[str] = None  # HTML, PDF, API
    issuing_authority: Optional[str] = "BIS"
    authority_level: Optional[str] = "SUPPORTING_GUIDANCE"
    retrieved_at: Optional[str] = None
    source_sha256: Optional[str] = None
    parent_source_url: Optional[str] = None
    access_status: str = "ACQUIRED"
    extraction_status: str = "SUCCESS"
    record_status: str = "ACTIVE"
    information_type: Optional[str] = None
    procedure_step: Optional[str] = None
    eligibility: Optional[str] = None
    required_document: Optional[str] = None
    fee: Optional[float] = None
    validity: Optional[str] = None
    official_portal: Optional[str] = None
    verification_method: Optional[str] = None

