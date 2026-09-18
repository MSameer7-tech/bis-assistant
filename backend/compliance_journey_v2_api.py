"""
backend/compliance_journey_v2_api.py
Sub-phase E: Thin V2 API Adapter.

Calls ComplianceContextBuilder.execute_compliance_journey() EXACTLY ONCE per request,
then merges the V2 Groq-synthesized response with the already-computed PC-5 deterministic
journey into a single frontend response.

Responsibilities:
1. Receive the compliance journey request.
2. Execute the full V2 pipeline (NLU → PC-5 → RAG → F3 → Groq → D validation) ONCE.
3. Merge PC-5 deterministic data + V2 answers into one response dict.
4. Return the merged response for the frontend.

Does NOT:
- Perform regulatory reasoning
- Execute PC-5 a second time
- Execute Groq a second time
- Modify frozen compliance engines
"""

import logging
from typing import Dict, Any, Optional, List

from pydantic import BaseModel, Field

from backend.compliance_context_builder import ComplianceContextBuilder

logger = logging.getLogger("compliance_journey_v2_api")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(asctime)s - %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Request model (extends the frozen ComplianceJourneyRequest fields with
# conversation_history, without modifying the frozen ai/compliance/journey_models.py)
# ---------------------------------------------------------------------------

class V2ComplianceJourneyRequest(BaseModel):
    """Extended request model for the V2 compliance journey endpoint."""
    product: Optional[str] = None
    standard: Optional[str] = None
    location: Optional[str] = None
    query: Optional[str] = None
    conversation_history: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Optional conversation history for anaphora resolution."
    )


# ---------------------------------------------------------------------------
# Singleton Context Builder
# ---------------------------------------------------------------------------

_global_context_builder: Optional[ComplianceContextBuilder] = None


def get_compliance_context_builder() -> ComplianceContextBuilder:
    """Lazy singleton getter for the ComplianceContextBuilder."""
    global _global_context_builder
    if _global_context_builder is None:
        _global_context_builder = ComplianceContextBuilder()
    return _global_context_builder


# ---------------------------------------------------------------------------
# V2 Journey Response Builder
# ---------------------------------------------------------------------------

def build_v2_journey_response(
    query: Optional[str] = None,
    product: Optional[str] = None,
    standard: Optional[str] = None,
    location: Optional[str] = None,
    conversation_history: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Executes the full V2 compliance journey pipeline EXACTLY ONCE and returns
    a merged response containing:

    1. PC-5 deterministic journey fields (product, standards, regulatory status,
       mandatory certification, scheme, testing, inspection, sampling, laboratories,
       certification process, provenance, warnings, limitations)
    2. compliance_answer_v2: Groq-synthesized V2 response with 10 natural-language
       stage answers, assessment, and next_steps
    3. _response_meta: Internal telemetry (not rendered in frontend)

    The PC-5 result is the SAME one already computed inside the C-layer.
    No second PC-5 execution. No second Groq synthesis call.
    """
    builder = get_compliance_context_builder()

    # Build the effective query from available inputs
    effective_query = query or product or standard or "Compliance inquiry"

    # Execute the full V2 pipeline exactly once
    v2_response, meta = builder.execute_compliance_journey(
        query=effective_query,
        product=product,
        standard=standard,
        location=location,
        conversation_history=conversation_history,
    )

    # Extract the already-computed PC-5 journey from metadata (computed in C-layer)
    pc5_journey = meta.pop("pc5_journey", {})

    # Separate internal telemetry from user-facing response
    response_meta = {
        "nlu_ms": meta.get("nlu_ms", 0.0),
        "pc5_ms": meta.get("pc5_ms", 0.0),
        "rag_ms": meta.get("rag_ms", 0.0),
        "groq_ms": meta.get("groq_ms", 0.0),
        "total_ms": meta.get("total_ms", 0.0),
        "synthesis_call_count": meta.get("synthesis_call_count", 1),
        "fallback_used": meta.get("fallback_used", False),
        "fallback_reason": meta.get("fallback_reason"),
        "correctness_report": meta.get("correctness_report", {}),
        "resolved_product": meta.get("resolved_product"),
        "resolved_standard": meta.get("resolved_standard"),
        "intent": meta.get("intent"),
    }

    # Build merged response: PC-5 deterministic data + V2 answers
    response: Dict[str, Any] = dict(pc5_journey)
    response["compliance_answer_v2"] = v2_response.model_dump()
    response["_response_meta"] = response_meta

    logger.info(
        f"V2 journey built: product={meta.get('resolved_product')}, "
        f"standard={meta.get('resolved_standard')}, "
        f"fallback={meta.get('fallback_used', False)}, "
        f"total_ms={meta.get('total_ms', 0)}"
    )

    return response
