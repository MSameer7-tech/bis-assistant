"""
Phase PC-4: Certification Process & Composite Testing-Process Data Models.

Strict schemas enforcing:
- Independent multi-dimensional evaluation:
  - testing_status (CONFIRMED / PARTIAL / UNKNOWN)
  - inspection_status (CONFIRMED / PARTIAL / UNKNOWN)
  - sampling_status (CONFIRMED / PARTIAL / UNKNOWN)
  - certification_process_status (CONFIRMED / PARTIAL / UNKNOWN)
- Preservation of frozen PC-3 regulatory states (MANDATORY_CERTIFICATION_CONFIRMED, etc.).
- Preservation of generic procedure definitions without automatic product stamping.
- Complete provenance linkage to PC-2 normalized evidence.
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from ai.compliance.relationship_models import RelationshipProvenance
from ai.compliance.testing_models import (
    TestingRequirementStatus,
    InspectionRequirementStatus,
    SamplingRequirementStatus,
)


class CertificationProcessStatus(str, Enum):
    """Authoritative certification process status for a Product -> Standard pair."""
    CERTIFICATION_PROCESS_CONFIRMED = "CERTIFICATION_PROCESS_CONFIRMED"
    CERTIFICATION_PROCESS_PARTIAL = "CERTIFICATION_PROCESS_PARTIAL"
    CERTIFICATION_PROCESS_UNKNOWN = "CERTIFICATION_PROCESS_UNKNOWN"


class CertificationProcedureRecord(BaseModel):
    """Authoritative certification procedure reference record from PC-2."""
    relationship_id: str
    relationship_type: str = "CERTIFICATION_PROCEDURE_DEFINITION"
    procedure_id: str
    scheme_id: str
    procedure_type: str
    stage_name: str
    title: str
    description: str
    stages: List[str] = Field(default_factory=list)
    documents: List[str] = Field(default_factory=list)
    inspection: Optional[str] = None
    sampling: Optional[str] = None
    fees: Optional[str] = None
    timelines: Optional[str] = None
    source_record_id: str
    source_document: Optional[str] = None
    source_url: Optional[str] = None
    source_location: Optional[str] = None
    source_verification_state: str
    evidence_hash: Optional[str] = None
    conflict_ids: List[str] = Field(default_factory=list)
    provenance: RelationshipProvenance

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class TestingProcessRelationshipRecord(BaseModel):
    """Unified composite relationship record extending PC-3 with testing and process dimensions."""
    __test__ = False
    relationship_id: str
    compliance_relationship_id: str
    product_identifier: str
    product_name: str
    standard_normalized: str
    standard_original: str
    testing_status: TestingRequirementStatus
    inspection_status: InspectionRequirementStatus
    sampling_status: SamplingRequirementStatus
    certification_process_status: CertificationProcessStatus
    associated_testing_ids: List[str] = Field(default_factory=list)
    associated_inspection_ids: List[str] = Field(default_factory=list)
    associated_sampling_ids: List[str] = Field(default_factory=list)
    associated_procedure_ids: List[str] = Field(default_factory=list)
    product_manual_count: int = 0
    product_manual_ids: List[str] = Field(default_factory=list)
    product_manual_status: str
    qco_status: str
    mandatory_certification_status: str
    scheme_applicability_status: str
    conflict_ids: List[str] = Field(default_factory=list)
    source_verification_state: str
    provenance: RelationshipProvenance

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()
