"""
backend/compliance_context_builder.py
Sub-phase C: Compliance Context Assembly & Single-Synthesis Pipeline Orchestrator.

Connects:
1. Production NLU / Context Resolution (analyze_query_context, slot extraction, conversational anaphora).
2. Authoritative Deterministic PC-5 Orchestration (ComplianceJourneyOrchestrator).
3. Stage-Specific Phase 12.E Targeted RAG Retrieval (query_production_rag for Stages 2, 3, 4, 5, 6, 7, 8, 10).
4. Stage 9 F3 LIMS Laboratory Facilities.
5. Deterministic Context Assembly & Progressive Chaining into GroqComplianceInput.
6. Exactly ONE Call to ComplianceJourneyV2Synthesizer.synthesize().
7. Execution Telemetry (nlu_ms, pc5_ms, rag_ms, context_build_ms, groq_ms, total_ms).
"""

import time
import re
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

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
    get_nlu_clarification_engine,
    ComplianceNLUClarificationEngine,
)
from scripts.phase12_f2_orchestrator import (
    analyze_query_context,
    resolve_conversational_context,
    extract_product_from_query,
    GroqClient,
)
from scripts.phase12_e_production_rag import query_production_rag
from backend.compliance_rag_synthesizer import QCOAuthoritativeIndex
from backend.compliance_journey_v2_synthesizer import (
    GroqComplianceInput,
    ComplianceJourneyV2Synthesizer,
    ComplianceJourneyV2Response,
)

logger = logging.getLogger("compliance_context_builder")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(asctime)s - %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Stage-specific query templates for targeted Phase 12.E RAG retrieval
STAGE_RAG_TEMPLATES = {
    2: "{std} Indian Standard specification title scope application",
    3: "{std} Quality Control Order notification effective date Gazette order",
    4: "{std} mandatory certification statutory order Gazette requirement",
    5: "{std} certification scheme Scheme I ISI Mark CRS applicability",
    6: "{std} scheme of inspection testing test parameters frequency SIT methods",
    7: "{std} factory inspection routine frequency test register SIT",
    8: "{std} sampling lot size sample quantity scale of sampling",
    10: "{std} certification procedure conformity assessment application",
}


def package_evidence_item(ev: Dict[str, Any], stage_name: str, standard: Optional[str] = None) -> Dict[str, Any]:
    """Packages a single RAG retrieval unit preserving IDs and provenance for the Evidence Drawer."""
    unit_id = ev.get("retrieval_unit_id") or ev.get("source_record_id") or ev.get("id") or "ev_unknown"
    return {
        "retrieval_unit_id": str(unit_id),
        "source_record_id": str(ev.get("source_record_id") or unit_id),
        "source_title": ev.get("source_title") or ev.get("heading") or "BIS Canonical Document",
        "standard": ev.get("standard") or standard,
        "clause": ev.get("clause"),
        "page_number": ev.get("page_number") or ev.get("page"),
        "source_url": ev.get("source_url") or ev.get("url"),
        "text": (ev.get("text") or ev.get("text_preview") or "").strip(),
        "relevant_passage": (ev.get("text") or ev.get("text_preview") or "").strip(),
        "provenance": ev.get("provenance") or {},
        "evidence_hash": ev.get("evidence_hash") or ev.get("hash"),
        "stage": stage_name,
    }


class ComplianceContextBuilder:
    """
    Assembles real compliance context from NLU, PC-5, Phase 12.E RAG, and F3 LIMS
    into GroqComplianceInput and coordinates the single-call synthesis.
    """

    def __init__(
        self,
        orchestrator: Optional[ComplianceJourneyOrchestrator] = None,
        synthesizer: Optional[ComplianceJourneyV2Synthesizer] = None,
        groq_client: Optional[GroqClient] = None,
        data_root: Optional[Path] = None,
    ):
        self.root_dir = data_root or PROJECT_ROOT
        self.orchestrator = orchestrator or get_compliance_orchestrator()
        self.nlu_engine = get_nlu_clarification_engine()
        self.qco_index = QCOAuthoritativeIndex(self.root_dir)
        self._groq_client = groq_client
        self._synthesizer = synthesizer
        self._rag_cache: Dict[str, Dict[str, Any]] = {}
        self._last_pc5_response: Optional[ComplianceJourneyResponse] = None

    @property
    def synthesizer(self) -> ComplianceJourneyV2Synthesizer:
        if self._synthesizer is None:
            self._synthesizer = ComplianceJourneyV2Synthesizer(groq_client=self._groq_client)
        return self._synthesizer

    def _execute_rag(self, query_text: str) -> List[Dict[str, Any]]:
        """Executes targeted Phase 12.E RAG retrieval with caching and error containment."""
        clean_q = query_text.strip()
        if not clean_q:
            return []
        if clean_q in self._rag_cache:
            return self._rag_cache[clean_q].get("evidence", [])
        try:
            rag_res = query_production_rag(clean_q)
            self._rag_cache[clean_q] = rag_res
            return rag_res.get("evidence", [])
        except Exception as e:
            logger.warning(f"RAG retrieval failed for '{clean_q}': {e}")
            return []

    def build_compliance_input(
        self,
        query: str,
        product: Optional[str] = None,
        standard: Optional[str] = None,
        location: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[GroqComplianceInput, Dict[str, Any]]:
        """
        Builds the complete GroqComplianceInput using real data from:
        - NLU / Conversational context resolution
        - PC-5 ComplianceJourneyOrchestrator (deterministic authority)
        - Targeted Phase 12.E RAG retrieval per stage
        - F3 LIMS laboratory facilities
        """
        timings: Dict[str, float] = {}
        total_start = time.time()

        # -------------------------------------------------------------------
        # STEP 1: NLU & Context Resolution
        # -------------------------------------------------------------------
        nlu_start = time.time()
        raw_query = (query or "").strip()

        # Conversational anaphora resolution
        normalized_history = []
        if conversation_history:
            for item in conversation_history:
                if isinstance(item, dict):
                    c = dict(item)
                    if "content" in c and "text" not in c:
                        c["text"] = c["content"]
                    normalized_history.append(c)
                else:
                    normalized_history.append(item)

        resolved_q, res_std, res_prod, was_resolved = resolve_conversational_context(
            raw_query, conversation_history=normalized_history
        )
        effective_query = resolved_q or raw_query

        # Rich context analysis (intents, roles, entities, standards)
        query_ctx = analyze_query_context(
            effective_query,
            conversation_history=normalized_history
        )

        # Slot extraction for product attributes
        slots = self.nlu_engine.extract_slots(effective_query)

        # Explicit input takes highest precedence, then resolved context, then extracted
        extracted_stds = query_ctx.get("is_numbers", [])
        resolved_standard = standard or (extracted_stds[0] if extracted_stds else None) or res_std or slots.standard
        resolved_product = product or query_ctx.get("product") or res_prod or slots.product

        # If anaphora was resolved but product was not explicitly captured, look back in history
        if was_resolved and (not resolved_product or resolved_product.lower() in ["them", "it", "this", "these"]) and normalized_history:
            for prev in reversed(normalized_history):
                prev_text = prev.get("text") or prev.get("content") or ""
                p_cand = extract_product_from_query(prev_text)
                if p_cand:
                    resolved_product = p_cand
                    break

        resolved_location = location or query_ctx.get("entities", {}).get("location") or slots.location
        detected_intent = query_ctx.get("intent") or "COMPLIANCE_REQUIREMENT"
        user_role = query_ctx.get("user_role")

        # Product attributes dictionary
        product_attributes: Dict[str, Any] = {}
        if slots.material:
            product_attributes["material"] = slots.material
        if slots.application:
            product_attributes["application"] = slots.application
        if user_role:
            product_attributes["user_role"] = user_role
        if was_resolved:
            product_attributes["conversational_context_resolved"] = True

        timings["nlu_ms"] = round((time.time() - nlu_start) * 1000, 2)

        # -------------------------------------------------------------------
        # STEP 2: PC-5 Deterministic Journey Execution
        # -------------------------------------------------------------------
        pc5_start = time.time()
        pc5_req = ComplianceJourneyRequest(
            product=resolved_product,
            standard=resolved_standard,
            location=resolved_location,
            query=effective_query,
        )
        pc5_response: ComplianceJourneyResponse = self.orchestrator.build_journey(pc5_req)
        self._last_pc5_response = pc5_response

        # Reconcile final resolved product and standard from PC-5
        final_standard = (
            resolved_standard
            or pc5_response.applicable_standards.primary_standard
            or (pc5_response.applicable_standards.standards[0].standard_number if pc5_response.applicable_standards.standards else None)
        )
        final_product = (
            pc5_response.product.resolved_product_name
            or pc5_response.product.input_product
            or resolved_product
        )

        # Assemble deterministic results dictionary from PC-5
        is_mandatory = pc5_response.mandatory_certification.is_mandatory
        qco_status = pc5_response.regulatory_status.qco_status
        cert_scheme = (
            pc5_response.certification_scheme.applicable_scheme_code
            or (pc5_response.certification_scheme.status if "UNKNOWN" not in pc5_response.certification_scheme.status else None)
        )

        det_results: Dict[str, Any] = {
            "is_mandatory": is_mandatory,
            "certification_scheme": cert_scheme,
            "qco_status": qco_status,
            "standards": [s.standard_number for s in pc5_response.applicable_standards.standards] if pc5_response.applicable_standards.standards else ([final_standard] if final_standard else []),
            "stage_3": {
                "status": qco_status,
                "notification_numbers": pc5_response.regulatory_status.notification_numbers,
                "effective_date": pc5_response.regulatory_status.effective_date,
                "associated_qco_ids": pc5_response.regulatory_status.associated_qco_ids,
            },
            "stage_4": {
                "is_mandatory": is_mandatory,
                "status": pc5_response.mandatory_certification.status,
            },
            "stage_5": {
                "certification_scheme": cert_scheme,
                "scheme_code": pc5_response.certification_scheme.applicable_scheme_code,
                "status": pc5_response.certification_scheme.status,
            },
            "stage_6": {
                "total_tests": pc5_response.testing.total_tests,
                "testing_requirements": [
                    {
                        "test_name": t.test_name,
                        "test_method": t.test_method,
                        "test_clause": t.test_clause,
                        "frequency": t.frequency,
                    }
                    for t in pc5_response.testing.testing_requirements
                ],
            },
            "stage_7": {
                "total_requirements": pc5_response.inspection.total_requirements,
                "inspection_requirements": [
                    {
                        "inspection_reference": i.inspection_reference,
                        "frequency": i.frequency,
                        "test_register": i.test_register,
                    }
                    for i in pc5_response.inspection.inspection_requirements
                ],
            },
            "stage_8": {
                "total_requirements": pc5_response.sampling.total_requirements,
                "sampling_requirements": [
                    {"sampling_reference": s.sampling_reference, "sample_size": s.sample_size, "lot_definition": s.lot_definition}
                    for s in pc5_response.sampling.sampling_requirements
                ],
            },
            "stage_10": {
                "total_steps": len(pc5_response.certification_process.procedure_steps),
                "procedure_steps": [s.description for s in pc5_response.certification_process.procedure_steps],
            },
        }

        # QCO Authoritative Data (from Normalized Gazette Registry)
        qco_info = None
        if final_standard:
            qco_info = self.qco_index.get_qco_info_for_standard(final_standard)
        if not qco_info and pc5_response.regulatory_status.associated_qco_ids:
            qco_info = {
                "qco_status": qco_status,
                "associated_qco_ids": pc5_response.regulatory_status.associated_qco_ids,
                "notification_numbers": pc5_response.regulatory_status.notification_numbers,
                "effective_date": pc5_response.regulatory_status.effective_date,
            }

        timings["pc5_ms"] = round((time.time() - pc5_start) * 1000, 2)

        # -------------------------------------------------------------------
        # STEP 3: Stage-Specific RAG Retrieval
        # -------------------------------------------------------------------
        rag_start = time.time()
        stage_timings: Dict[str, float] = {}
        target_term = final_standard or final_product or "Bureau of Indian Standards compliance"

        stage_rag_results: Dict[int, List[Dict[str, Any]]] = {}
        for s_num, template in STAGE_RAG_TEMPLATES.items():
            s_t0 = time.time()
            rag_query = template.format(std=target_term)
            raw_ev = self._execute_rag(rag_query)
            stage_rag_results[s_num] = raw_ev
            stage_timings[f"stage_{s_num}_rag_ms"] = round((time.time() - s_t0) * 1000, 2)

        # Package evidence per stage preserving provenance & drawer compatibility
        rag_evidence_stage2 = [package_evidence_item(e, "Applicable Standards", final_standard) for e in stage_rag_results[2]]
        cert_evidence_stage5 = [package_evidence_item(e, "Certification Scheme", final_standard) for e in stage_rag_results[5]]
        testing_evidence_stage6 = [package_evidence_item(e, "Required Testing", final_standard) for e in stage_rag_results[6]]
        inspection_evidence_stage7 = [package_evidence_item(e, "Factory Inspection", final_standard) for e in stage_rag_results[7]]
        sampling_evidence_stage8 = [package_evidence_item(e, "Sampling Requirements", final_standard) for e in stage_rag_results[8]]
        process_evidence_stage10 = [package_evidence_item(e, "Certification Process", final_standard) for e in stage_rag_results[10]]

        timings["rag_ms"] = round((time.time() - rag_start) * 1000, 2)

        # -------------------------------------------------------------------
        # STEP 4: Stage 9 F3 Laboratories
        # -------------------------------------------------------------------
        f3_laboratories: List[Dict[str, Any]] = []
        for lab in pc5_response.laboratories.qualified_laboratories:
            addr = lab.address if isinstance(lab.address, dict) else {}
            f3_laboratories.append({
                "laboratory_name": lab.laboratory_name,
                "public_lab_code": lab.public_lab_code,
                "id": lab.public_lab_code,
                "category": lab.category,
                "city": addr.get("city", ""),
                "state": addr.get("state", ""),
                "address": addr,
                "capability_evidence": lab.capability_evidence if isinstance(lab.capability_evidence, dict) else {},
            })

        # -------------------------------------------------------------------
        # STEP 5: Assemble GroqComplianceInput
        # -------------------------------------------------------------------
        ctx_start = time.time()
        standards_list = det_results.get("standards", [])

        compliance_input = GroqComplianceInput(
            user_question=raw_query,
            intent=detected_intent,
            product=final_product,
            product_attributes=product_attributes,
            location=resolved_location,
            standards=standards_list,
            deterministic_results=det_results,
            rag_evidence=rag_evidence_stage2,
            qco_evidence=qco_info,
            certification_evidence=cert_evidence_stage5,
            testing_evidence=testing_evidence_stage6,
            inspection_evidence=inspection_evidence_stage7,
            sampling_evidence=sampling_evidence_stage8,
            certification_process_evidence=process_evidence_stage10,
            conversation_history=conversation_history,
            f3_laboratories=f3_laboratories,
        )

        timings["context_build_ms"] = round((time.time() - ctx_start) * 1000, 2)
        timings["total_ms"] = round((time.time() - total_start) * 1000, 2)

        meta: Dict[str, Any] = {
            "timings": timings,
            "rag_stage_timings": stage_timings,
            "stage_evidence_counts": {
                "stage_2_standards": len(rag_evidence_stage2),
                "stage_3_4_qco": len(qco_info.get("notification_numbers", [])) if qco_info else 0,
                "stage_5_scheme": len(cert_evidence_stage5),
                "stage_6_testing": len(testing_evidence_stage6),
                "stage_7_inspection": len(inspection_evidence_stage7),
                "stage_8_sampling": len(sampling_evidence_stage8),
                "stage_9_laboratories": len(f3_laboratories),
                "stage_10_process": len(process_evidence_stage10),
            },
            "resolved_product": final_product,
            "resolved_standard": final_standard,
            "intent": detected_intent,
            "pc5_status": pc5_response.status.value,
        }

        return compliance_input, meta

    def execute_compliance_journey(
        self,
        query: str,
        product: Optional[str] = None,
        standard: Optional[str] = None,
        location: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[ComplianceJourneyV2Response, Dict[str, Any]]:
        """
        Executes the end-to-end compliance journey:
        Context Assembly -> Single-Call Groq Synthesis -> Structured V2 Response.
        """
        pipeline_t0 = time.time()

        # 1. Assemble real compliance input
        input_data, meta = self.build_compliance_input(
            query=query,
            product=product,
            standard=standard,
            location=location,
            conversation_history=conversation_history,
        )

        # 2. Invoke Groq synthesis EXACTLY ONCE
        groq_t0 = time.time()
        v2_response = self.synthesizer.synthesize(input_data)
        groq_ms = round((time.time() - groq_t0) * 1000, 2)

        # 3. Finalize execution telemetry
        total_pipeline_ms = round((time.time() - pipeline_t0) * 1000, 2)
        telemetry = dict(meta["timings"])
        telemetry["groq_ms"] = groq_ms
        telemetry["total_ms"] = total_pipeline_ms

        response_meta: Dict[str, Any] = {
            "nlu_ms": telemetry.get("nlu_ms", 0.0),
            "pc5_ms": telemetry.get("pc5_ms", 0.0),
            "rag_ms": telemetry.get("rag_ms", 0.0),
            "context_build_ms": telemetry.get("context_build_ms", 0.0),
            "groq_ms": groq_ms,
            "total_ms": total_pipeline_ms,
            "synthesis_call_count": self.synthesizer.last_trace.get("call_count", 1),
            "stage_evidence_counts": meta["stage_evidence_counts"],
            "rag_stage_timings": meta["rag_stage_timings"],
            "resolved_product": meta["resolved_product"],
            "resolved_standard": meta["resolved_standard"],
            "intent": meta["intent"],
            "fallback_used": self.synthesizer.last_trace.get("fallback_used", False),
            "fallback_reason": self.synthesizer.last_trace.get("fallback_reason"),
            "correctness_report": self.synthesizer.last_trace.get("correctness_report", {}),
            "pc5_journey": self._last_pc5_response.model_dump() if self._last_pc5_response else {},
        }

        return v2_response, response_meta
