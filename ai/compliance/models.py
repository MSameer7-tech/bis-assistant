"""
Phase PC-1: BIS Compliance Data Acquisition & Provenance Layer Models.

Strict schemas for raw, verifiable BIS compliance evidence across:
- QCOs
- Product-Standard relationships
- Certification Schemes
- Product Manuals
- Testing / SIT specifications
- Certification Process procedures

Invariants:
- Zero invention: Missing values default to None, "UNKNOWN", or "NOT_FOUND".
- Strict provenance: Every record carries source_url, source_document, sha256, and retrieved_at.
- Status integrity: Status is strictly classified as ACTIVE, UPCOMING, SUPERSEDED, AMENDED, or UNKNOWN.
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class SourceVerificationState(str, Enum):
    """Authoritative source verification categorization."""
    SOURCE_VERIFIED = "SOURCE_VERIFIED"
    SOURCE_UNVERIFIED = "SOURCE_UNVERIFIED"
    SOURCE_MISSING = "SOURCE_MISSING"


class QcoLifecycleStatus(str, Enum):
    """Authoritative lifecycle status of Quality Control Orders."""
    ACTIVE = "ACTIVE"
    UPCOMING = "UPCOMING"
    SUPERSEDED = "SUPERSEDED"
    AMENDED = "AMENDED"
    UNKNOWN = "UNKNOWN"


class ParserStatus(str, Enum):
    """Processing and extraction state of raw document artifacts."""
    PARSED = "PARSED"
    RAW_ARCHIVED = "RAW_ARCHIVED"
    EXTRACTION_PENDING = "EXTRACTION_PENDING"
    PARSE_FAILED = "PARSE_FAILED"


class QcoRawRecord(BaseModel):
    """Raw authoritative Quality Control Order (QCO) evidence record."""
    qco_id: str
    notification_number: Optional[str] = None
    title: str
    issuing_authority: Optional[str] = None
    publication_date: Optional[str] = None
    effective_date: Optional[str] = None
    referenced_standards: List[str] = Field(default_factory=list)
    referenced_products: List[str] = Field(default_factory=list)
    scheme_reference: Optional[str] = None
    exemptions: List[str] = Field(default_factory=list)
    amendments: List[str] = Field(default_factory=list)
    source_url: str
    source_document: str
    source_hash: str
    retrieved_at: str
    verification_state: SourceVerificationState = SourceVerificationState.SOURCE_VERIFIED
    status: QcoLifecycleStatus = QcoLifecycleStatus.UNKNOWN
    raw_text_snippet: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class ProductStandardRawRecord(BaseModel):
    """Explicit BIS-published relationship between a product and Indian Standard."""
    product: str
    standard: str
    relationship_type: str = "UNKNOWN"
    is_mandatory: Optional[bool] = None
    qco_reference: Optional[str] = None
    source_url: str
    source_document: str
    page_clause: Optional[str] = None
    source_hash: str
    retrieved_at: str
    verification_state: SourceVerificationState = SourceVerificationState.SOURCE_VERIFIED

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class CertificationSchemeRawRecord(BaseModel):
    """Authoritative certification scheme definition and statutory basis."""
    scheme_id: str
    scheme_name: str
    statutory_basis: str
    source_description: str
    source_url: str
    source_document: str
    source_hash: str
    retrieved_at: str
    verification_state: SourceVerificationState = SourceVerificationState.SOURCE_VERIFIED

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class ProductManualRawRecord(BaseModel):
    """Raw archived BIS Product Manual specification."""
    manual_id: str
    title: str
    standard: str
    product: str
    version_date: Optional[str] = None
    source_url: str
    source_document: str
    document_hash: str
    retrieved_at: str
    parser_status: ParserStatus = ParserStatus.RAW_ARCHIVED
    raw_content: Dict[str, Any] = Field(default_factory=dict)
    verification_state: SourceVerificationState = SourceVerificationState.SOURCE_VERIFIED

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class SitRawRecord(BaseModel):
    """Authoritative Scheme of Inspection and Testing (SIT) clause schedule."""
    document_id: str
    sit_id: str
    standard: str
    product: Optional[str] = None
    test_name: str
    test_method: Optional[str] = None
    frequency: Optional[str] = None
    sample_size: Optional[str] = None
    sampling_method: Optional[str] = None
    requirement: Optional[str] = None
    record_requirement: Optional[str] = None
    source_document: str
    source_url: str
    source_location: Optional[str] = None
    document_hash: str
    retrieved_at: str
    verification_state: SourceVerificationState = SourceVerificationState.SOURCE_VERIFIED

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class CertificationProcessRawRecord(BaseModel):
    """Official BIS certification procedure guidelines and required documentation."""
    procedure_id: str
    procedure_type: str
    scheme_id: str
    stage_name: str
    title: str
    description: str
    required_documents: List[str] = Field(default_factory=list)
    inspection_details: Optional[str] = None
    sampling_procedure: Optional[str] = None
    timelines_days: Optional[str] = None
    fees_structure: Optional[str] = None
    source_url: str
    source_document: str
    document_hash: str
    retrieved_at: str
    verification_state: SourceVerificationState = SourceVerificationState.SOURCE_VERIFIED

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class AcquisitionManifestEntry(BaseModel):
    """Manifest record tracking cryptographic provenance for acquired artifacts."""
    record_id: str
    domain: str
    source_url: str
    source_document: str
    sha256: str
    retrieved_at: str
    source_verification_state: SourceVerificationState
    parser_status: ParserStatus

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()
