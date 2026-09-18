"""
Phase PC-5: Product Compliance Journey API Router.

FastAPI Router with prefix /api/compliance exposing:
- POST /api/compliance/journey: Full deterministic product compliance journey
- GET /api/compliance/health: Health check and dataset accounting
- GET /api/compliance/metadata: PC-3/PC-4/F3 integration metadata & SHA-256 hashes
"""

from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends

from ai.compliance.journey_models import (
    ComplianceJourneyRequest,
    ComplianceJourneyResponse,
    JourneyStatus,
)
from ai.compliance.journey_orchestrator import (
    get_compliance_orchestrator,
    ComplianceJourneyOrchestrator,
)
from ai.compliance.nlu_clarification import (
    ComplianceClarificationRequest,
    ComplianceClarificationResponse,
    get_nlu_clarification_engine,
    ComplianceNLUClarificationEngine,
    ClarificationState,
    QuerySlots,
    RefinedRequest,
)

router = APIRouter(prefix="/api/compliance", tags=["Product Compliance Journey"])


@router.post("/clarify", response_model=ComplianceClarificationResponse)
async def clarify_compliance_query(
    req: ComplianceClarificationRequest,
    engine: ComplianceNLUClarificationEngine = Depends(get_nlu_clarification_engine)
) -> ComplianceClarificationResponse:
    """
    Evaluates natural language compliance query for clarity, ambiguity, or incompleteness.
    Provides grounded candidates and adaptive questions without making regulatory decisions.
    """
    try:
        return engine.analyze_clarification(req)
    except Exception as e:
        # Graceful fallback: Treat as CLEAR with original input so PC-5 handles deterministically
        return ComplianceClarificationResponse(
            state=ClarificationState.CLEAR,
            slots=QuerySlots(raw_query=req.query or "", product=req.product, standard=req.standard, location=req.location),
            refined_request=RefinedRequest(product=req.product, standard=req.standard, location=req.location, query=req.query),
            resolved_standard=req.standard,
            resolved_product=req.product,
            message=f"NLU fallback to direct resolution: {str(e)}"
        )


@router.post("/journey", response_model=ComplianceJourneyResponse)
async def get_product_compliance_journey(
    req: ComplianceJourneyRequest,
    orchestrator: ComplianceJourneyOrchestrator = Depends(get_compliance_orchestrator)
) -> ComplianceJourneyResponse:
    """
    Builds the authoritative Product Compliance Journey combining PC-3, PC-4, and F3.
    Deterministic, provenance-preserving, and non-collapsing.
    """
    try:
        response = orchestrator.build_journey(req)
        return response
    except Exception as e:
        # Fallback safeguard: Never return an unhandled raw crash
        query_echo = {
            "product": req.product,
            "standard": req.standard,
            "location": req.location,
            "query": req.query
        }
        return orchestrator._build_empty_or_invalid_journey(
            JourneyStatus.INVALID_REQUEST,
            query_echo,
            f"An internal error occurred during journey orchestration: {str(e)}"
        )


@router.get("/health")
async def get_compliance_health(
    orchestrator: ComplianceJourneyOrchestrator = Depends(get_compliance_orchestrator)
) -> Dict[str, Any]:
    """
    Returns the health status and dataset record counts of the Product Compliance Journey engine.
    """
    return {
        "status": "healthy",
        "service": "bis-product-compliance-journey",
        "version": "PC-5.0",
        "phase": "PC-5",
        "engine": "ComplianceJourneyOrchestrator",
        "loaded_dataset_counts": orchestrator.loaded_counts,
        "f3_lims_integration": "ACTIVE",
        "zero_llm_guarantee": True,
        "non_collapsing_stages": 10
    }


@router.get("/metadata")
async def get_compliance_metadata(
    orchestrator: ComplianceJourneyOrchestrator = Depends(get_compliance_orchestrator)
) -> Dict[str, Any]:
    """
    Exposes frozen PC-3 and PC-4 metadata, SHA-256 hashes, and invariant declarations.
    """
    return {
        "phase": "PC-5",
        "version": "PC-5.0",
        "pc3_metadata": {
            "manifest_version": orchestrator.pc3_manifest.get("manifest_version", "PC-3.0"),
            "input_hashes": orchestrator.pc3_manifest.get("input_hashes", {}),
            "artifact_hashes": orchestrator.pc3_manifest.get("artifact_hashes", {}),
            "relationship_counts": orchestrator.pc3_manifest.get("relationship_counts", {}),
        },
        "pc4_metadata": {
            "manifest_version": orchestrator.pc4_manifest.get("manifest_version", "PC-4.0"),
            "artifact_hashes": orchestrator.pc4_manifest.get("artifact_hashes", {}),
            "relationship_counts": orchestrator.pc4_manifest.get("relationship_counts", {}),
            "zero_invention_guarantees": orchestrator.pc4_manifest.get("zero_invention_guarantees", {}),
        },
        "f3_integration": {
            "authority": "Bureau of Indian Standards Laboratory Information Management System (LIMS)",
            "interface": "execute_search",
            "capability_precedes_proximity": True,
            "external_api_calls": False
        },
        "invariants": [
            "Standard != mandatory certification",
            "Testing evidence != mandatory certification",
            "Missing evidence != negative evidence",
            "Zero LLM / Groq regulatory decisions",
            "Generic Scheme I procedures are never promoted to product-specific",
            "Certification scheme applicability remains UNKNOWN (0/665 confirmed)",
            "Unresolved conflicts preserved as UNRESOLVED_DISCLOSED"
        ]
    }
