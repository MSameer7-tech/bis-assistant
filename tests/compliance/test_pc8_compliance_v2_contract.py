import pytest
from pydantic import ValidationError
from ai.compliance.journey_v2_models import (
    ComplianceJourneyV2Response,
    ComplianceStage,
    ProductIdentificationStage,
    ApplicableStandardsStage,
    RegulatoryStatusStage,
    MandatoryCertificationStage,
    CertificationSchemeStage,
    ComplianceTestingStage,
    InspectionStage,
    SamplingStage,
    LaboratoriesStage,
    CertificationProcessStage,
    AssessmentStage
)

def test_compliance_stage_base():
    """Test that the base compliance stage enforces the mandatory answer field."""
    # Should raise error without answer
    with pytest.raises(ValidationError):
        ComplianceStage()
        
    # Should pass with minimal fields
    stage = ComplianceStage(answer="General information goes here.")
    assert stage.answer == "General information goes here."
    assert stage.key_information == []
    assert stage.evidence_ids == []

def test_compliance_journey_v2_valid():
    """Test that a fully formed ComplianceJourneyV2Response validates correctly."""
    data = {
        "product_identification": {
            "answer": "This is a product.",
            "product_name": "Timber Doors"
        },
        "applicable_standards": {
            "answer": "Standard IS 2202 applies.",
            "standards": ["IS 2202"]
        },
        "regulatory_status": {
            "answer": "Regulated by QCO.",
            "regulatory_orders": ["QCO 2023"]
        },
        "mandatory_certification": {
            "answer": "Yes, it is mandatory.",
            "is_mandatory": True
        },
        "certification_scheme": {
            "answer": "Scheme I applies.",
            "scheme_name": "Scheme I"
        },
        "testing": {
            "answer": "Test in a lab."
        },
        "inspection": {
            "answer": "Factory inspection required."
        },
        "sampling": {
            "answer": "Sample size is 5."
        },
        "laboratories": {
            "answer": "Use BIS approved labs."
        },
        "certification_process": {
            "answer": "Apply online."
        },
        "assessment": {
            "answer": "Fully assessed."
        },
        "next_steps": [
            "Prepare documents.",
            "Apply online."
        ]
    }
    
    response = ComplianceJourneyV2Response(**data)
    assert response.product_identification.product_name == "Timber Doors"
    assert response.applicable_standards.standards == ["IS 2202"]
    assert len(response.next_steps) == 2
    assert response.testing.key_information == []
    assert response.testing.answer == "Test in a lab."

def test_compliance_journey_v2_missing_stage():
    """Test that the top-level contract requires all stages."""
    data = {
        "product_identification": {
            "answer": "This is a product."
        }
        # Missing all other stages
    }
    with pytest.raises(ValidationError):
        ComplianceJourneyV2Response(**data)
