from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ConsumerServiceCategory(str, Enum):
    VERIFICATION = "VERIFICATION"
    COMPLAINT_REDRESSAL = "COMPLAINT_REDRESSAL"
    STANDARDS_ACCESS = "STANDARDS_ACCESS"
    LICENCE_SEARCH = "LICENCE_SEARCH"
    COMPENSATION_CLAIM = "COMPENSATION_CLAIM"
    CONSUMER_AWARENESS = "CONSUMER_AWARENESS"


class ServiceChannel(str, Enum):
    BIS_CARE_APP = "BIS_CARE_APP"
    MANAKONLINE_PORTAL = "MANAKONLINE_PORTAL"
    NATIONAL_CONSUMER_HELPLINE = "NATIONAL_CONSUMER_HELPLINE"
    BRANCH_OFFICE = "BRANCH_OFFICE"
    ECOMPLAINT_PORTAL = "ECOMPLAINT_PORTAL"


class ConsumerServiceRecord(BaseModel):
    service_id: str
    service_name: str
    category: ConsumerServiceCategory
    channel: ServiceChannel
    description: str
    target_mark: Optional[str] = None
    input_parameters: List[str] = Field(default_factory=list)
    verification_output: List[str] = Field(default_factory=list)
    complaint_types: List[str] = Field(default_factory=list)
    resolution_tat_days: int = 15
    escalation_levels: List[str] = Field(default_factory=list)
    statutory_provisions: List[str] = Field(default_factory=list)
    penalty_clause: Optional[str] = None
    consumer_rights: List[str] = Field(default_factory=list)
    evidence_backed: bool = True


@dataclass
class ConsumerRecord:
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
    information_type: Optional[str] = None # COMPLAINT_MECHANISM, VERIFICATION, AWARENESS, FAQ, CONTACT
    procedure_step: Optional[str] = None
    eligibility: Optional[str] = None
    required_document: Optional[str] = None
    fee: Optional[float] = None
    validity: Optional[str] = None
    official_portal: Optional[str] = None
    verification_method: Optional[str] = None
