import pytest
from backend.compliance_rag_synthesizer import get_compliance_rag_synthesizer
from ai.compliance.journey_models import ComplianceJourneyRequest

class TestStage5Regression:
    def test_stage5_unknown_scheme_preserves_qco(self):
        """IS 4985 has QCO but no scheme. Should report scheme UNKNOWN and preserve QCO info."""
        synthesizer = get_compliance_rag_synthesizer()
        req = ComplianceJourneyRequest(standard="IS 4985")
        journey = synthesizer.process_journey(req)
        
        # QCO Stage 3 should be confirmed
        assert journey["regulatory_status"]["qco_status"] == "QCO_APPLIES"
        
        # Mandatory Certification Stage 4 should be confirmed
        assert journey["mandatory_certification"]["status"] == "MANDATORY_CERTIFICATION_CONFIRMED"
        
        # Scheme Stage 5 should be UNKNOWN but Groq should NOT invent a scheme
        scheme = journey["certification_scheme"]
        assert scheme["status"] == "CERTIFICATION_SCHEME_UNKNOWN"
        assert scheme["synthesis"]["primary_answer"] == "Product-specific certification scheme not established from available BIS evidence"
        
        gen_info = scheme["synthesis"].get("general_information", "")
        # Should NOT select Scheme I or CRS
        assert "select" not in gen_info.lower() and "therefore scheme" not in gen_info.lower()
        
    def test_stage5_unknown_scheme_is_15750(self):
        """IS 15750 has no QCO and no scheme."""
        synthesizer = get_compliance_rag_synthesizer()
        req = ComplianceJourneyRequest(standard="IS 15750")
        journey = synthesizer.process_journey(req)
        
        # QCO Stage 3 should be unknown
        assert journey["regulatory_status"]["qco_status"] == "QCO_STATUS_UNKNOWN"
        
        # Scheme Stage 5 should be UNKNOWN
        scheme = journey["certification_scheme"]
        assert scheme["status"] == "CERTIFICATION_SCHEME_UNKNOWN"
