"""
Phase PC-3: Compliance Relationship Engine Data Models.

Strict schemas enforcing:
- Multi-dimensional compliance status without boolean collapsing.
- Non-negotiable compliance invariants:
  1. Standard != Mandatory Certification (MANDATORY_CERTIFICATION_NOT_ESTABLISHED).
  2. Missing Evidence != Negative Evidence (Never assume 'NO').
  3. Amended QCO Safety (Preserve uncertainty unless operative status established).
  4. Scheme Applicability Safety (Strictly SCHEME_APPLICABILITY_UNKNOWN unless authoritative).
  5. Unresolved Conflict Preservation (Mark CONFLICT / UNRESOLVED_DISCLOSED).
- Deterministic Universal Provenance Contract linking back to PC-1 and PC-2.
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class QcoRelationshipStatus(str, Enum):
    """Authoritative standard-to-QCO relationship status."""
    QCO_APPLIES = "QCO_APPLIES"
    QCO_AMENDED = "QCO_AMENDED"
    QCO_STATUS_UNKNOWN = "QCO_STATUS_UNKNOWN"
    QCO_CONFLICT = "QCO_CONFLICT"
    QCO_NOT_ESTABLISHED = "QCO_NOT_ESTABLISHED"


class MandatoryCertificationStatus(str, Enum):
    """Authoritative statutory certification requirement status."""
    MANDATORY_CERTIFICATION_CONFIRMED = "MANDATORY_CERTIFICATION_CONFIRMED"
    MANDATORY_CERTIFICATION_NOT_ESTABLISHED = "MANDATORY_CERTIFICATION_NOT_ESTABLISHED"
    QCO_STATUS_UNKNOWN = "QCO_STATUS_UNKNOWN"
    QCO_CONFLICT = "QCO_CONFLICT"


class SchemeApplicabilityStatus(str, Enum):
    """Authoritative certification scheme applicability status."""
    CERTIFICATION_SCHEME_CONFIRMED = "CERTIFICATION_SCHEME_CONFIRMED"
    CERTIFICATION_SCHEME_UNKNOWN = "CERTIFICATION_SCHEME_UNKNOWN"


class ProductManualRelationshipStatus(str, Enum):
    """Product Manual availability and conflict status."""
    PRODUCT_MANUAL_AVAILABLE = "PRODUCT_MANUAL_AVAILABLE"
    PRODUCT_MANUAL_CONFLICT = "PRODUCT_MANUAL_CONFLICT"
    PRODUCT_MANUAL_NOT_FOUND = "PRODUCT_MANUAL_NOT_FOUND"


class RelationshipProvenance(BaseModel):
    """Universal provenance contract attached to every relationship record."""
    source_layer: str = "PC-2_NORMALIZED"
    source_record_ids: List[str] = Field(default_factory=list)
    source_documents: List[str] = Field(default_factory=list)
    source_urls: List[str] = Field(default_factory=list)
    source_locations: List[str] = Field(default_factory=list)
    evidence_hashes: List[str] = Field(default_factory=list)
    source_verification_state: str
    conflict_ids: List[str] = Field(default_factory=list)


class ProductStandardRelationshipRecord(BaseModel):
    """Deterministic Product -> Indian Standard relationship record."""
    relationship_id: str
    relationship_type: str = "PRODUCT_TO_STANDARD"
    product_identifier: str
    product_name: str
    standard_number: str  # standard_normalized
    standard_original: str
    standard_title: str = "UNKNOWN"
    relationship_nature: str
    is_mandatory_raw: Optional[bool] = None
    source_record_id: str
    source_document: str
    source_url: str
    source_location: Optional[str] = None
    source_verification_state: str
    evidence_hash: str
    provenance: RelationshipProvenance
    status: str = "STANDARD_IDENTIFIED"

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class StandardQcoRelationshipRecord(BaseModel):
    """Deterministic Standard -> QCO regulatory link record."""
    relationship_id: str
    relationship_type: str = "STANDARD_TO_QCO"
    standard_normalized: str
    standard_original: str
    qco_relationship_status: QcoRelationshipStatus
    associated_qco_ids: List[str] = Field(default_factory=list)
    notification_numbers: List[str] = Field(default_factory=list)
    conflict_ids: List[str] = Field(default_factory=list)
    source_record_ids: List[str] = Field(default_factory=list)
    source_verification_state: str
    provenance: RelationshipProvenance

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class QcoRequirementRelationshipRecord(BaseModel):
    """Authoritative QCO -> Regulatory Requirement record."""
    relationship_id: str
    relationship_type: str = "QCO_TO_REQUIREMENT"
    qco_id: str
    notification_number: Optional[str] = None
    notification_title: str
    issuing_authority: Optional[str] = None
    affected_standards: List[str] = Field(default_factory=list)
    affected_products: List[str] = Field(default_factory=list)
    commencement_date: Optional[str] = None
    regulatory_status: str
    is_mandatory_established: bool = False
    mandatory_status: MandatoryCertificationStatus
    exemptions: List[str] = Field(default_factory=list)
    amendments: List[str] = Field(default_factory=list)
    unresolved_conflict: bool = False
    conflict_ids: List[str] = Field(default_factory=list)
    source_record_id: str
    source_document: Optional[str] = None
    source_url: Optional[str] = None
    source_location: Optional[str] = None
    source_verification_state: str
    evidence_hash: Optional[str] = None
    provenance: RelationshipProvenance

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class CertificationSchemeRelationshipRecord(BaseModel):
    """Standard / Product -> Certification Scheme relationship record."""
    relationship_id: str
    relationship_type: str = "STANDARD_PRODUCT_TO_SCHEME"
    product_identifier: Optional[str] = None
    product_name: Optional[str] = None
    standard_normalized: str
    standard_original: str
    scheme_applicability_status: SchemeApplicabilityStatus = SchemeApplicabilityStatus.CERTIFICATION_SCHEME_UNKNOWN
    scheme_id: Optional[str] = None
    scheme_name: Optional[str] = None
    applicability_basis: str = "NO_AUTHORITATIVE_APPLICABILITY_RECORD_IN_CORPUS"
    source_verification_state: str
    provenance: RelationshipProvenance

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class CompositeComplianceRelationshipRecord(BaseModel):
    """Unified composite compliance relationship linking all 5 dimensions."""
    compliance_relationship_id: str
    product_identifier: str
    product_name: str
    standard_normalized: str
    standard_original: str
    product_standard_status: str = "STANDARD_IDENTIFIED"
    qco_status: QcoRelationshipStatus
    mandatory_certification_status: MandatoryCertificationStatus
    scheme_applicability_status: SchemeApplicabilityStatus
    product_manual_status: ProductManualRelationshipStatus
    associated_qco_ids: List[str] = Field(default_factory=list)
    notification_numbers: List[str] = Field(default_factory=list)
    effective_date: Optional[str] = None
    product_manual_count: int = 0
    conflict_ids: List[str] = Field(default_factory=list)
    source_verification_state: str
    provenance: RelationshipProvenance

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()
