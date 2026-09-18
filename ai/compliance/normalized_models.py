"""
Phase PC-2: Compliance Data Normalization & Provenance Models.

Strict schemas enforcing:
- Universal Provenance Contract across all normalized records.
- Deterministic PC-1 lineage (source_record_id).
- Preservation of source verification states (SOURCE_VERIFIED / SOURCE_UNVERIFIED).
- Dual standard representation (standard_original & standard_normalized) without edition loss.
- Separation of SCHEME_DEFINITION and SCHEME_APPLICABILITY.
- Preservation of explicit null / UNKNOWN values without synthetic inference.
"""

from enum import Enum
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field


class SourceVerificationState(str, Enum):
    """Authoritative source verification state matching PC-1."""
    SOURCE_VERIFIED = "SOURCE_VERIFIED"
    SOURCE_UNVERIFIED = "SOURCE_UNVERIFIED"


class RecordType(str, Enum):
    """Normalized record categories."""
    QCO_REGISTRY_RECORD = "QCO_REGISTRY_RECORD"
    PRODUCT_STANDARD_MAP_RECORD = "PRODUCT_STANDARD_MAP_RECORD"
    SCHEME_DEFINITION = "SCHEME_DEFINITION"
    SCHEME_APPLICABILITY = "SCHEME_APPLICABILITY"
    TESTING_REQUIREMENT = "TESTING_REQUIREMENT"
    PRODUCT_MANUAL_RECORD = "PRODUCT_MANUAL_RECORD"
    CERTIFICATION_PROCEDURE_RECORD = "CERTIFICATION_PROCEDURE_RECORD"
    DOCUMENT_REGISTRY_RECORD = "DOCUMENT_REGISTRY_RECORD"
    CONFLICT_RECORD = "CONFLICT_RECORD"
    DUPLICATE_REFERENCE = "DUPLICATE_REFERENCE"


class ConflictType(str, Enum):
    """Deterministic conflict classifications."""
    DUPLICATE_IDENTIFIER = "DUPLICATE_IDENTIFIER"
    DUPLICATE_REFERENCE = "DUPLICATE_REFERENCE"
    CONFLICTING_EFFECTIVE_DATES = "CONFLICTING_EFFECTIVE_DATES"
    CONFLICTING_STATUS = "CONFLICTING_STATUS"
    CONFLICTING_STANDARD_REPRESENTATIONS = "CONFLICTING_STANDARD_REPRESENTATIONS"
    CONFLICTING_MANUAL_VERSIONS = "CONFLICTING_MANUAL_VERSIONS"
    CONFLICTING_SCHEME_RELATIONSHIPS = "CONFLICTING_SCHEME_RELATIONSHIPS"
    CONFLICTING_TESTING_REQUIREMENTS = "CONFLICTING_TESTING_REQUIREMENTS"


class UniversalProvenance(BaseModel):
    """Universal Provenance Contract embedded or attached to every normalized record."""
    source_url: Optional[str] = None
    source_document: Optional[str] = None
    source_hash: Optional[str] = None
    source_location: Optional[str] = None
    retrieved_at: Optional[str] = None


class StandardReference(BaseModel):
    """Dual standard representation preserving original edition string and canonical identifier."""
    standard_original: str
    standard_normalized: str


class NormalizedQcoRecord(BaseModel):
    """Normalized Quality Control Order record."""
    record_id: str
    record_type: RecordType = RecordType.QCO_REGISTRY_RECORD
    source_record_id: str
    qco_id: str
    notification_number: Optional[str] = None
    title: str
    issuing_authority: Optional[str] = None
    publication_date: Optional[str] = None
    effective_date: Optional[str] = None
    referenced_products: List[str] = Field(default_factory=list)
    referenced_standards: List[StandardReference] = Field(default_factory=list)
    scheme_reference: Optional[str] = None
    exemptions: List[str] = Field(default_factory=list)
    amendment_reference: Optional[str] = None
    status: str = "UNKNOWN"
    source_verification_state: SourceVerificationState
    provenance: UniversalProvenance

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class NormalizedProductStandardMap(BaseModel):
    """Normalized Product -> Standard mapping record with PC-1 lineage."""
    record_id: str
    record_type: RecordType = RecordType.PRODUCT_STANDARD_MAP_RECORD
    source_record_id: str
    product_original: str
    standard_original: str
    standard_normalized: str
    relationship_type: str
    is_mandatory: Optional[bool] = None
    qco_reference: Optional[str] = None
    source_verification_state: SourceVerificationState
    source_url: Optional[str] = None
    source_document: Optional[str] = None
    source_location: Optional[str] = None
    source_hash: Optional[str] = None
    retrieved_at: Optional[str] = None
    provenance: UniversalProvenance

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class NormalizedSchemeRecord(BaseModel):
    """Normalized Certification Scheme definition or explicit applicability record."""
    record_id: str
    record_type: RecordType  # SCHEME_DEFINITION or SCHEME_APPLICABILITY
    source_record_id: str
    scheme_id: str
    scheme_name: str
    statutory_basis: Optional[str] = None
    source_description: Optional[str] = None
    # For applicability records (when explicitly present in raw source):
    applicable_standard: Optional[StandardReference] = None
    applicable_product: Optional[str] = None
    applicability_basis: Optional[str] = None
    source_verification_state: SourceVerificationState
    provenance: UniversalProvenance

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class NormalizedTestingRequirement(BaseModel):
    """Normalized testing requirement / SIT clause schedule."""
    record_id: str
    record_type: RecordType = RecordType.TESTING_REQUIREMENT
    source_record_id: str
    standard_original: str
    standard_normalized: str
    product: Optional[str] = None
    test_name: str
    test_method: Optional[str] = None
    frequency: Optional[str] = None
    sample_size: Optional[str] = None
    sampling_method: Optional[str] = None
    requirement_text: Optional[str] = None
    record_requirement: Optional[str] = None
    is_mandatory: Optional[bool] = None
    source_verification_state: SourceVerificationState
    source_location: Optional[str] = None
    provenance: UniversalProvenance

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class NormalizedProductManual(BaseModel):
    """Normalized Product Manual record."""
    record_id: str
    record_type: RecordType = RecordType.PRODUCT_MANUAL_RECORD
    source_record_id: str
    manual_id: str
    standard_original: str
    standard_normalized: str
    product: str
    title: str
    version: Optional[str] = None
    version_date: Optional[str] = None
    scope: Optional[str] = None
    sampling: Optional[str] = None
    tests: Optional[Union[str, List[str]]] = None
    equipment: Optional[str] = None
    grouping: Optional[str] = None
    marking: Optional[str] = None
    sit_reference: Optional[str] = None
    source_verification_state: SourceVerificationState
    source_url: Optional[str] = None
    source_document: Optional[str] = None
    source_hash: Optional[str] = None
    source_location: Optional[str] = None
    retrieved_at: Optional[str] = None
    provenance: UniversalProvenance

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class NormalizedCertificationProcedure(BaseModel):
    """Normalized certification procedure guideline."""
    record_id: str
    record_type: RecordType = RecordType.CERTIFICATION_PROCEDURE_RECORD
    source_record_id: str
    procedure_id: str
    procedure_type: str  # NORMAL, SIMPLIFIED, CRS, FMCS, UNKNOWN
    scheme_id: str
    stage_name: str
    title: str
    description: str
    stages: List[str] = Field(default_factory=list)
    documents: List[str] = Field(default_factory=list)
    inspection: Optional[str] = None
    sampling: Optional[str] = None
    fees: Optional[str] = None
    timelines: Optional[str] = None
    source_verification_state: SourceVerificationState
    source_location: Optional[str] = None
    provenance: UniversalProvenance

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class NormalizedDocumentEntry(BaseModel):
    """Normalized document artifact registry entry."""
    record_id: str
    record_type: RecordType = RecordType.DOCUMENT_REGISTRY_RECORD
    document_id: str
    domain: str
    filename: str
    relative_path: str
    sha256: str
    file_size_bytes: int
    source_url: Optional[str] = None
    retrieved_at: Optional[str] = None
    source_verification_state: SourceVerificationState
    referencing_record_ids: List[str] = Field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class ComplianceConflictRecord(BaseModel):
    """Logged conflict or duplicate reference across compliance sources."""
    conflict_id: str
    conflict_type: str  # e.g. CONFLICTING_EFFECTIVE_DATES, DUPLICATE_REFERENCE, etc.
    affected_record_ids: List[str]
    entity_reference: str
    conflicting_values: Dict[str, Any]
    provenance: Dict[str, Any]
    resolution_policy: str = "UNRESOLVED_DISCLOSED"

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()
