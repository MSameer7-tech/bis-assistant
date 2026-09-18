"""
Phase PC-5: Product Compliance Journey Response Models.

Defines strict Pydantic schemas for the end-to-end Compliance Journey API:
- Request: ComplianceJourneyRequest (flexible product/standard/location/query inputs)
- JourneyStatus, ProductResolutionStatus, StandardResolutionStatus, LaboratoryStageStatus enums
- 10 distinct compliance stages (Product, Standards, Regulatory, Mandatory, Scheme,
  Testing, Inspection, Sampling, Laboratories, Certification Process)
- Cross-cutting aggregated provenance and warnings/limitations
- Complete non-collapsing response structure preserving UNKNOWN / NOT_ESTABLISHED / NO_MATCHING_LABORATORY
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from ai.compliance.relationship_models import RelationshipProvenance


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class JourneyStatus(str, Enum):
    """High-level status of the compliance journey."""
    JOURNEY_ESTABLISHED = "JOURNEY_ESTABLISHED"
    AMBIGUOUS_PRODUCT = "AMBIGUOUS_PRODUCT"
    STANDARD_NOT_ESTABLISHED = "STANDARD_NOT_ESTABLISHED"
    NO_COMPLIANCE_EVIDENCE = "NO_COMPLIANCE_EVIDENCE"
    INVALID_REQUEST = "INVALID_REQUEST"


class ProductResolutionStatus(str, Enum):
    """Resolution status for user product query."""
    PRODUCT_IDENTIFIED = "PRODUCT_IDENTIFIED"
    AMBIGUOUS_PRODUCT = "AMBIGUOUS_PRODUCT"
    PRODUCT_NOT_ESTABLISHED = "PRODUCT_NOT_ESTABLISHED"


class StandardResolutionStatus(str, Enum):
    """Resolution status for applicable Indian Standards."""
    STANDARDS_IDENTIFIED = "STANDARDS_IDENTIFIED"
    STANDARD_NOT_ESTABLISHED = "STANDARD_NOT_ESTABLISHED"


class LaboratoryStageStatus(str, Enum):
    """Qualification status for BIS laboratories."""
    QUALIFIED_LABS_FOUND = "QUALIFIED_LABS_FOUND"
    NO_MATCHING_LABORATORY = "NO_MATCHING_LABORATORY"
    LAB_MATCHING_LIMITED = "LAB_MATCHING_LIMITED"
    LAB_MATCHING_UNAVAILABLE = "LAB_MATCHING_UNAVAILABLE"


# ---------------------------------------------------------------------------
# Request Model
# ---------------------------------------------------------------------------

class ComplianceJourneyRequest(BaseModel):
    """
    Search request for the Product Compliance Journey API.
    All fields are optional, but at least one must contain usable input.
    """
    product: Optional[str] = Field(
        None,
        description="Product name or description (e.g., 'ceiling fan', 'timber doors', 'PVC pipes')."
    )
    standard: Optional[str] = Field(
        None,
        description="Explicit Indian Standard designation (e.g., 'IS 4985', 'IS 374'). Highest precedence."
    )
    location: Optional[str] = Field(
        None,
        description="Optional location (city or state, e.g., 'Delhi', 'Maharashtra') for laboratory proximity ranking."
    )
    query: Optional[str] = Field(
        None,
        description="General natural language query from manufacturer or importer."
    )


# ---------------------------------------------------------------------------
# Stage Sub-Models
# ---------------------------------------------------------------------------

class ProductCandidate(BaseModel):
    """Candidate product when resolution is ambiguous."""
    product_name: str
    product_identifier: Optional[str] = None
    standard_number: Optional[str] = None
    confidence: float = 1.0


class ProductStage(BaseModel):
    """Stage 1: Product Identification & Mapping."""
    status: ProductResolutionStatus
    input_product: Optional[str] = None
    resolved_product_name: Optional[str] = None
    product_identifier: Optional[str] = None
    candidates: List[ProductCandidate] = Field(default_factory=list)
    provenance: Optional[RelationshipProvenance] = None


class StandardDetailRecord(BaseModel):
    """Details of an applicable Indian Standard."""
    standard_number: str
    standard_title: Optional[str] = None
    relationship_nature: Optional[str] = None
    source_document: Optional[str] = None
    evidence_hash: Optional[str] = None
    provenance: Optional[RelationshipProvenance] = None


class StandardsStage(BaseModel):
    """Stage 2: Applicable Indian Standards."""
    status: StandardResolutionStatus
    primary_standard: Optional[str] = None
    standards: List[StandardDetailRecord] = Field(default_factory=list)
    provenance: Optional[RelationshipProvenance] = None


class RegulatoryStage(BaseModel):
    """Stage 3: QCO / Regulatory Status (from PC-3)."""
    status: str
    qco_status: str
    notification_numbers: List[str] = Field(default_factory=list)
    effective_date: Optional[str] = None
    associated_qco_ids: List[str] = Field(default_factory=list)
    conflict_ids: List[str] = Field(default_factory=list)
    explanation: str
    provenance: Optional[RelationshipProvenance] = None


class MandatoryStage(BaseModel):
    """Stage 4: Mandatory Certification Status (from PC-3)."""
    status: str
    is_mandatory: Optional[bool] = None
    explanation: str
    provenance: Optional[RelationshipProvenance] = None


class SchemeStage(BaseModel):
    """Stage 5: Certification Scheme Applicability (from PC-3)."""
    status: str = "CERTIFICATION_SCHEME_UNKNOWN"
    applicable_scheme_code: Optional[str] = None
    applicability_basis: str = "NO_AUTHORITATIVE_APPLICABILITY_RECORD_IN_CORPUS"
    explanation: str
    provenance: Optional[RelationshipProvenance] = None


class TestingItemRecord(BaseModel):
    """Individual required test parameter (from PC-4)."""
    __test__ = False
    test_name: str
    test_method: Optional[str] = None
    test_clause: Optional[str] = None
    test_parameter: Optional[str] = None
    frequency: Optional[str] = None
    sampling_reference: Optional[str] = None
    source_document: Optional[str] = None
    source_url: Optional[str] = None
    evidence_hash: Optional[str] = None


class TestingStage(BaseModel):
    """Stage 6: Required Testing Requirements (from PC-4)."""
    __test__ = False
    status: str
    total_tests: int = 0
    testing_requirements: List[TestingItemRecord] = Field(default_factory=list)
    explanation: str
    provenance: Optional[RelationshipProvenance] = None


class InspectionItemRecord(BaseModel):
    """Individual factory inspection requirement (from PC-4)."""
    inspection_reference: str
    test_register: Optional[str] = None
    frequency: Optional[str] = None
    source_document: Optional[str] = None
    evidence_hash: Optional[str] = None


class InspectionStage(BaseModel):
    """Stage 7: Factory & Routine Inspection Requirements (from PC-4)."""
    status: str
    total_requirements: int = 0
    inspection_requirements: List[InspectionItemRecord] = Field(default_factory=list)
    explanation: str
    provenance: Optional[RelationshipProvenance] = None


class SamplingItemRecord(BaseModel):
    """Individual sampling requirement (from PC-4)."""
    sampling_reference: str
    sample_size: Optional[str] = None
    lot_definition: Optional[str] = None
    source_document: Optional[str] = None
    evidence_hash: Optional[str] = None


class SamplingStage(BaseModel):
    """Stage 8: Lot & Control Unit Sampling Requirements (from PC-4)."""
    status: str
    total_requirements: int = 0
    sampling_requirements: List[SamplingItemRecord] = Field(default_factory=list)
    explanation: str
    provenance: Optional[RelationshipProvenance] = None


class LaboratoryItemRecord(BaseModel):
    """Qualified laboratory candidate (from F3)."""
    public_lab_code: str
    laboratory_name: str
    category: str
    address: Dict[str, Any] = Field(default_factory=dict)
    capability_evidence: Dict[str, Any] = Field(default_factory=dict)
    geographic_metadata: Dict[str, Any] = Field(default_factory=dict)


class LaboratoriesStage(BaseModel):
    """Stage 9: Qualified BIS Testing Laboratories (from F3)."""
    status: LaboratoryStageStatus
    total_matching: int = 0
    returned_count: int = 0
    qualified_laboratories: List[LaboratoryItemRecord] = Field(default_factory=list)
    capability_evaluated_first: bool = True
    location_filter_applied: Optional[str] = None
    explanation: str
    provenance: Optional[RelationshipProvenance] = None


class ProcessStepRecord(BaseModel):
    """Individual certification process stage step."""
    step_number: int
    title: str
    description: str
    is_generic: bool = True


class CertificationProcessStage(BaseModel):
    """Stage 10: Certification Process Requirements (from PC-4)."""
    status: str
    is_generic_procedure: bool = True
    procedure_steps: List[ProcessStepRecord] = Field(default_factory=list)
    explanation: str
    provenance: Optional[RelationshipProvenance] = None


# ---------------------------------------------------------------------------
# Unified Top-Level Journey Response
# ---------------------------------------------------------------------------

class ComplianceJourneyResponse(BaseModel):
    """
    Unified, structured, versioned response for the Product Compliance Journey.
    Contains all 10 distinct compliance stages, complete provenance, and explicit caveats.
    """
    journey_version: str = "PC-5.0"
    status: JourneyStatus
    query_echo: Dict[str, Any] = Field(default_factory=dict)

    # 10 Compliance Stages
    product: ProductStage
    applicable_standards: StandardsStage
    regulatory_status: RegulatoryStage
    mandatory_certification: MandatoryStage
    certification_scheme: SchemeStage
    testing: TestingStage
    inspection: InspectionStage
    sampling: SamplingStage
    laboratories: LaboratoriesStage
    certification_process: CertificationProcessStage

    # Cross-cutting sections
    provenance: List[RelationshipProvenance] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
