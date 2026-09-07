from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any


class AHCStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CANCELLED = "CANCELLED"


class MetalType(str, Enum):
    GOLD = "GOLD"
    SILVER = "SILVER"


import re
from pydantic import BaseModel


@dataclass
class GoldPurityFineness:
    karat: str
    fineness_ppt: int
    description: str


class HallmarkRecord(BaseModel):
    ahc_id: str
    ahc_name: str
    recognition_number: str
    status: AHCStatus
    address: str
    city: str
    district: str
    state: str
    pincode: str
    is_mandatory_district: bool
    metals_handled: List[MetalType]
    standards_covered: List[str]
    testing_methods: List[str]
    huid_supported: bool
    daily_capacity_pieces: int
    valid_from: str
    valid_until: str
    evidence_backed: bool

    @staticmethod
    def validate_huid(huid: Optional[str]) -> bool:
        if not huid or not isinstance(huid, str):
            return False
        clean = huid.strip()
        if len(clean) != 6:
            return False
        return bool(re.match(r"^[A-Za-z0-9]{6}$", clean))



@dataclass
class HallmarkingRecord:
    record_id: str
    record_type: str
    title: str
    content: str
    source_url: str
    source_type: str  # HTML, PDF, API
    issuing_authority: str  # BIS
    authority_level: str  # SUPPORTING_GUIDANCE, PROCEDURAL, STATUTORY
    retrieved_at: str
    source_sha256: str
    parent_source_url: Optional[str] = None
    access_status: str = "ACQUIRED" # ACQUIRED, FAILED, WAF_BLOCKED, SESSION_REQUIRED, ACCESS_RESTRICTED
    extraction_status: str = "SUCCESS" # SUCCESS, FAILED
    record_status: str = "ACTIVE"
    
    # Domain Specific fields
    information_type: Optional[str] = None # HUID, JEWELLER_REGISTRATION, AHC, FEES
    procedure_step: Optional[str] = None
    eligibility: Optional[str] = None
    required_document: Optional[str] = None
    fee: Optional[float] = None
    validity: Optional[str] = None
    official_portal: Optional[str] = None
    verification_method: Optional[str] = None
