from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

class ComplianceStage(BaseModel):
    """Base model for all compliance stages in the new contract."""
    title: Optional[str] = Field(None, description="Human-readable title of the stage.")
    answer: str = Field(..., description="The primary user-facing natural language response constructed by Groq.")
    key_information: List[str] = Field(default_factory=list, description="Structured key information items.")
    evidence_ids: List[str] = Field(default_factory=list, description="List of authoritative evidence IDs to preserve the Evidence Drawer functionality.")

# 1. Product Identification
class ProductIdentificationStage(ComplianceStage):
    product_name: Optional[str] = None
    product_category: Optional[str] = None

# 2. Applicable Standards
class ApplicableStandardsStage(ComplianceStage):
    standards: List[str] = Field(default_factory=list)

# 3. Regulatory Status
class RegulatoryStatusStage(ComplianceStage):
    regulatory_orders: List[str] = Field(default_factory=list)

# 4. Mandatory Certification
class MandatoryCertificationStage(ComplianceStage):
    is_mandatory: Optional[bool] = None

# 5. Certification Scheme
class CertificationSchemeStage(ComplianceStage):
    scheme_type: Optional[str] = None
    scheme_name: Optional[str] = None

# 6. Testing
class ComplianceTestingStage(ComplianceStage):
    test_methods: List[str] = Field(default_factory=list)

# 7. Inspection
class InspectionStage(ComplianceStage):
    inspection_requirements: List[str] = Field(default_factory=list)

# 8. Sampling
class SamplingStage(ComplianceStage):
    sampling_guidelines: List[str] = Field(default_factory=list)

# 9. Laboratories
class LaboratoriesStage(ComplianceStage):
    recognized_labs: List[str] = Field(default_factory=list)

# 10. Certification Process
class CertificationProcessStage(ComplianceStage):
    process_steps: List[str] = Field(default_factory=list)

# 11. Assessment
class AssessmentStage(ComplianceStage):
    assessment_summary: Optional[str] = None

# Top-level Response Contract
class ComplianceJourneyV2Response(BaseModel):
    """
    The new top-level structured response contract for the Product Compliance Journey.
    """
    product_identification: ProductIdentificationStage
    applicable_standards: ApplicableStandardsStage
    regulatory_status: RegulatoryStatusStage
    mandatory_certification: MandatoryCertificationStage
    certification_scheme: CertificationSchemeStage
    testing: ComplianceTestingStage
    inspection: InspectionStage
    sampling: SamplingStage
    laboratories: LaboratoriesStage
    certification_process: CertificationProcessStage
    assessment: AssessmentStage
    next_steps: List[str] = Field(
        default_factory=list,
        description="A simple list of natural-language next steps for the user."
    )

    def to_structured_dict(self) -> Dict[str, Any]:
        """
        Returns the clean Section 19 dictionary representation with all 10 stages,
        assessment, and next_steps.
        """
        stages_map = {
            "product_identification": self.product_identification,
            "applicable_standards": self.applicable_standards,
            "regulatory_status": self.regulatory_status,
            "mandatory_certification": self.mandatory_certification,
            "certification_scheme": self.certification_scheme,
            "testing": self.testing,
            "inspection": self.inspection,
            "sampling": self.sampling,
            "laboratories": self.laboratories,
            "certification_process": self.certification_process,
            "assessment": self.assessment,
        }
        res: Dict[str, Any] = {}
        for key, stg in stages_map.items():
            res[key] = {
                "title": stg.title,
                "answer": stg.answer,
                "key_information": list(stg.key_information or []),
                "evidence_ids": list(stg.evidence_ids or [])
            }
        res["next_steps"] = list(self.next_steps or [])
        return res

