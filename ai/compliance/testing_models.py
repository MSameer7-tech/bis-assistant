"""
Phase PC-4: Testing, Inspection, and Sampling Relationship Data Models.

Strict schemas enforcing:
- Authoritative testing requirements with clause-level provenance.
- Clear separation between testing, inspection, and sampling dimensions.
- Explicit status tracking:
  - TestingRequirementStatus (CONFIRMED / PARTIAL / UNKNOWN)
  - InspectionRequirementStatus (CONFIRMED / PARTIAL / UNKNOWN)
  - SamplingRequirementStatus (CONFIRMED / PARTIAL / UNKNOWN)
- Universal Provenance Contract tracing to PC-2 normalized records.
- Zero synthetic invention of test methods, clauses, frequencies, or sample sizes.
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from ai.compliance.relationship_models import RelationshipProvenance


class TestingRequirementStatus(str, Enum):
    """Authoritative testing requirement status for a Product -> Standard pair."""
    __test__ = False
    TESTING_REQUIREMENTS_CONFIRMED = "TESTING_REQUIREMENTS_CONFIRMED"
    TESTING_REQUIREMENTS_PARTIAL = "TESTING_REQUIREMENTS_PARTIAL"
    TESTING_REQUIREMENTS_UNKNOWN = "TESTING_REQUIREMENTS_UNKNOWN"


class InspectionRequirementStatus(str, Enum):
    """Authoritative inspection requirement status for a Product -> Standard pair."""
    INSPECTION_REQUIREMENTS_CONFIRMED = "INSPECTION_REQUIREMENTS_CONFIRMED"
    INSPECTION_REQUIREMENTS_PARTIAL = "INSPECTION_REQUIREMENTS_PARTIAL"
    INSPECTION_REQUIREMENTS_UNKNOWN = "INSPECTION_REQUIREMENTS_UNKNOWN"


class SamplingRequirementStatus(str, Enum):
    """Authoritative sampling requirement status for a Product -> Standard pair."""
    SAMPLING_REQUIREMENTS_CONFIRMED = "SAMPLING_REQUIREMENTS_CONFIRMED"
    SAMPLING_REQUIREMENTS_PARTIAL = "SAMPLING_REQUIREMENTS_PARTIAL"
    SAMPLING_REQUIREMENTS_UNKNOWN = "SAMPLING_REQUIREMENTS_UNKNOWN"


class TestingRequirementRelationshipRecord(BaseModel):
    """Granular authoritative test requirement relationship."""
    __test__ = False
    relationship_id: str
    relationship_type: str = "TESTING_REQUIREMENT"
    standard_normalized: str
    standard_original: str
    standard_title: Optional[str] = None
    product_identifier: Optional[str] = None
    product_name: Optional[str] = None
    associated_products: List[str] = Field(default_factory=list)
    test_name: str
    test_method: Optional[str] = None
    test_clause: Optional[str] = None
    test_parameter: Optional[str] = None
    frequency: Optional[str] = None
    mandatory_status: Optional[str] = None
    sampling_reference: Optional[str] = None
    inspection_reference: Optional[str] = None
    product_manual_reference: Optional[str] = None
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


class InspectionRequirementRelationshipRecord(BaseModel):
    """Granular authoritative factory/in-house inspection requirement relationship."""
    relationship_id: str
    relationship_type: str = "INSPECTION_REQUIREMENT"
    standard_normalized: str
    standard_original: str
    associated_products: List[str] = Field(default_factory=list)
    inspection_activity: str
    inspection_scope: str = "IN_HOUSE_FACTORY_INSPECTION"
    test_register_requirement: Optional[str] = None
    calibration_check_requirement: Optional[str] = None
    frequency: Optional[str] = None
    clause: Optional[str] = None
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


class SamplingRequirementRelationshipRecord(BaseModel):
    """Granular authoritative lot sampling criteria relationship."""
    relationship_id: str
    relationship_type: str = "SAMPLING_REQUIREMENT"
    standard_normalized: str
    standard_original: str
    associated_products: List[str] = Field(default_factory=list)
    sample_size: Optional[str] = None
    sampling_method: Optional[str] = None
    lot_definition: Optional[str] = None
    frequency: Optional[str] = None
    clause: Optional[str] = None
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
