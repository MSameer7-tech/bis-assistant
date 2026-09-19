"""
Phase PC-8 V2: Groq Compliance Answer Synthesis & Safety Guard Layer.

Implements the user-facing natural language answer synthesis for the Product Compliance Journey,
conforming to the Phase 1 ComplianceJourneyV2Response contract.

Key Architectural Guarantees:
1. Groq (openai/gpt-oss-120b) writes concise, natural-language answers and structures information.
2. Groq is NOT the regulatory decision maker:
   - Mandatory certification status and QCO applicability are strictly locked to authoritative data.
   - QCO notification numbers, effective dates, clauses, testing frequencies, sample quantities,
     certification schemes, laboratories, and citations cannot be hallucinated.
3. Stage 9 (Laboratories) is 100% locked to F3 LIMS data; Groq does not generate laboratories.
4. Technical status labels (UNKNOWN, GROUNDED, HYBRID, LLM_FALLBACK, RAG, PC-3, PC-4, PC-5,
   evidence corpus, deterministic baseline, retrieval status) are purged from all user-facing fields.
5. If evidence is missing, Groq provides general explanation without phrasing it as a verified BIS requirement.
6. Robust deterministic fallback ensures zero failure rate when Groq is unavailable or rate-limited.
"""

import os
import re
import json
import time
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from pathlib import Path

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
    AssessmentStage,
)
from scripts.phase12_f2_orchestrator import GroqClient
from backend.compliance_correctness_engine import ComplianceCorrectnessEngine

logger = logging.getLogger("compliance_journey_v2_synthesizer")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(asctime)s - %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

DEFAULT_V2_MODEL = "openai/gpt-oss-120b"

# Technical jargon regex patterns that must NEVER leak into the user-facing UI
FORBIDDEN_INTERNAL_TERMS = [
    r'\bUNKNOWN\b',
    r'\bNOT_ESTABLISHED\b',
    r'\bGROUNDED\b',
    r'\bHYBRID\b',
    r'\bLLM_FALLBACK\b',
    r'\bRAG\b',
    r'\bPC-[1-9]\b',
    r'\bPC5\b',
    r'\bPC4\b',
    r'\bPC3\b',
    r'\bPC2\b',
    r'\bPC1\b',
    r'\bevidence corpus\b',
    r'\bdeterministic baseline\b',
    r'\bretrieval status\b',
    r'\bGENERAL INFORMATION:?\s*',
]


# ---------------------------------------------------------------------------
# Input Data Structure for Synthesis
# ---------------------------------------------------------------------------

@dataclass
class GroqComplianceInput:
    """
    Standardized container for all context fed to the Groq synthesis engine.
    """
    user_question: str
    intent: Optional[str] = None
    product: Optional[str] = None
    product_attributes: Optional[Dict[str, Any]] = None
    location: Optional[str] = None
    standards: List[str] = field(default_factory=list)
    deterministic_results: Dict[str, Any] = field(default_factory=dict)
    rag_evidence: List[Dict[str, Any]] = field(default_factory=list)
    qco_evidence: Optional[Dict[str, Any]] = None
    certification_evidence: List[Dict[str, Any]] = field(default_factory=list)
    testing_evidence: List[Dict[str, Any]] = field(default_factory=list)
    inspection_evidence: List[Dict[str, Any]] = field(default_factory=list)
    sampling_evidence: List[Dict[str, Any]] = field(default_factory=list)
    certification_process_evidence: List[Dict[str, Any]] = field(default_factory=list)
    conversation_history: Optional[List[Dict[str, Any]]] = None
    f3_laboratories: List[Dict[str, Any]] = field(default_factory=list)

    def get_all_evidence_ids(self) -> List[str]:
        ids = set()
        for ev in (
            self.rag_evidence +
            self.certification_evidence +
            self.testing_evidence +
            self.inspection_evidence +
            self.sampling_evidence +
            self.certification_process_evidence
        ):
            ev_id = ev.get("source_record_id") or ev.get("retrieval_unit_id")
            if ev_id:
                ids.add(str(ev_id))
        for lab in self.f3_laboratories:
            lab_id = lab.get("id") or lab.get("public_lab_code") or lab.get("laboratory_id")
            if lab_id:
                ids.add(str(lab_id))
        if self.qco_evidence:
            for qid in self.qco_evidence.get("associated_qco_ids", []):
                if qid:
                    ids.add(str(qid))
        return list(ids)


# ---------------------------------------------------------------------------
# Safety & Grounding Validation Layer
# ---------------------------------------------------------------------------

class ComplianceSafetyValidator:
    """
    Enforces absolute regulatory locking and purges internal engine jargon.
    """

    @staticmethod
    def sanitize_text(text: Optional[str]) -> str:
        """Removes internal technical labels from user-facing text and normalizes unicode."""
        if not text:
            return ""
        cleaned = text
        # Normalize non-breaking spaces, zero-width spaces, and non-breaking hyphens
        cleaned = cleaned.replace('\u202f', ' ').replace('\xa0', ' ').replace('\u2011', '-').replace('\u2010', '-')
        for pat in FORBIDDEN_INTERNAL_TERMS:
            cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE)
        # Normalize whitespace
        cleaned = re.sub(r'[ \t]+', ' ', cleaned)
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip()
        return cleaned

    @classmethod
    def deduplicate_key_information(
        cls,
        items: List[str],
        answer: str,
        structured_terms: Optional[List[str]] = None
    ) -> List[str]:
        """
        Deduplicates key_information items:
        - Purges internal labels and cleans text.
        - Suppresses items whose core fact or value is already expressed in the stage answer.
        - Suppresses items that merely duplicate structured detail terms (e.g. test methods or lab names).
        - Enforces uniqueness across items.
        """
        if not items:
            return []

        norm_ans = (answer or "").lower()
        clean_ans = re.sub(r'[*_`#]', '', norm_ans)
        clean_struct = [t.lower().strip() for t in (structured_terms or []) if t]

        seen = set()
        deduped = []

        for raw in items:
            clean = cls.sanitize_text(raw)
            clean = re.sub(r'[*_`#]', '', clean).strip()
            if not clean:
                continue

            clean_lower = clean.lower()
            if clean_lower in seen:
                continue
            seen.add(clean_lower)

            # If item has "Label: Value", extract value
            if ":" in clean:
                parts = clean.split(":", 1)
                val = parts[1].strip().lower()
            else:
                val = clean_lower

            # If value is already stated in the primary answer (minimum 3 chars)
            if len(val) >= 3 and (val in clean_ans or val in norm_ans):
                continue

            # If full item is in the primary answer (minimum 4 chars)
            if len(clean_lower) >= 4 and (clean_lower in clean_ans or clean_lower in norm_ans):
                continue

            # If item simply repeats a structured detail term
            if any(term in val for term in clean_struct if len(term) >= 4):
                continue

            deduped.append(clean)

        return deduped

    @classmethod
    def validate_and_guard(
        cls,
        raw_dict: Dict[str, Any],
        input_data: GroqComplianceInput
    ) -> ComplianceJourneyV2Response:
        """
        Validates the raw dict against deterministic boundaries and constructs
        a valid ComplianceJourneyV2Response.
        """
        valid_ev_ids = set(input_data.get_all_evidence_ids())
        det = input_data.deterministic_results

        # 1. Product Identification
        raw_prod = raw_dict.get("product_identification", {})
        prod_ans = cls.sanitize_text(raw_prod.get("answer") or "")
        if not prod_ans:
            prod_name = input_data.product or (input_data.standards[0] if input_data.standards else "specified product")
            prod_ans = f"Product identified for compliance evaluation: {prod_name}."
        prod_key_info = cls.deduplicate_key_information(
            raw_prod.get("key_information", []),
            prod_ans,
            [input_data.product] if input_data.product else []
        )

        prod_stage = ProductIdentificationStage(
            title=cls.sanitize_text(raw_prod.get("title") or "Product Identification"),
            answer=prod_ans,
            key_information=prod_key_info,
            evidence_ids=[eid for eid in raw_prod.get("evidence_ids", []) if eid in valid_ev_ids],
            product_name=input_data.product or raw_prod.get("product_name"),
            product_category=raw_prod.get("product_category")
        )

        # 2. Applicable Standards
        raw_std = raw_dict.get("applicable_standards", {})
        std_ans = cls.sanitize_text(raw_std.get("answer") or "")
        det_standards = input_data.standards or det.get("standards", [])
        has_std_ev = bool(input_data.rag_evidence or input_data.qco_evidence or det.get("standards"))

        # If standard is unverified/absent from RAG & QCO, ensure answer does not claim it is verified
        if not has_std_ev and det_standards:
            if not std_ans or not any(w in std_ans.lower() for w in ["could not be confirmed", "not identified", "unverified", "no specific", "no indian standard", "could not be verified"]):
                std_ans = f"The standard {', '.join(det_standards)} could not be confirmed from available BIS records."
        elif not std_ans:
            if det_standards:
                std_ans = f"The primary applicable standard identified is {', '.join(det_standards)}."
            else:
                std_ans = "No specific Indian Standard could be confirmed from available BIS records."

        std_ev_ids = [eid for eid in raw_std.get("evidence_ids", []) if eid in valid_ev_ids]
        if not std_ev_ids and input_data.standards and has_std_ev:
            for ev in input_data.rag_evidence:
                if any(s in str(ev) for s in input_data.standards):
                    eid = ev.get("source_record_id") or ev.get("retrieval_unit_id")
                    if eid:
                        std_ev_ids.append(str(eid))

        std_key_info = cls.deduplicate_key_information(
            raw_std.get("key_information", []),
            std_ans,
            det_standards
        )

        applicable_standards_stage = ApplicableStandardsStage(
            title=cls.sanitize_text(raw_std.get("title") or "Applicable Indian Standards"),
            answer=std_ans,
            key_information=std_key_info,
            evidence_ids=list(set(std_ev_ids)),
            standards=det_standards or raw_std.get("standards", [])
        )

        # 3. Regulatory Status (QCO Locking)
        raw_reg = raw_dict.get("regulatory_status", {})
        qco_info = input_data.qco_evidence or {}
        det_qco_status = det.get("qco_status", "")
        qco_title = qco_info.get("qco_title")
        notifs = qco_info.get("notification_numbers", [])
        is_qco_conflict = "CONFLICT" in str(det_qco_status).upper() or "CONFLICT" in str(det.get("stage_3", {}).get("status", "")).upper()

        reg_ans = cls.sanitize_text(raw_reg.get("answer") or "")
        reg_orders = []

        if is_qco_conflict:
            reg_ans = "Available BIS Gazette records contain conflicting regulatory notifications for this standard. Statutory status remains under conservative regulatory review."
            if qco_title:
                reg_orders.append(qco_title)
        elif qco_title or notifs:
            reg_orders.append(qco_title or f"Quality Control Order for {', '.join(input_data.standards)}")
            # Ensure answer does not contradict confirmed QCO
            if not reg_ans or "not confirmed" in reg_ans.lower() or "no qco" in reg_ans.lower():
                notif_str = f" under notification {', '.join(notifs)}" if notifs else ""
                reg_ans = f"This product is governed by the {reg_orders[0]}{notif_str} issued under the BIS Act."
            # Strip any hallucinated notification numbers from the answer
            found_notifs = re.findall(r'\bS\.?O\.?\s*\d+\s*\([A-Z]\)', reg_ans, re.IGNORECASE)
            for fn in found_notifs:
                if not any(fn.lower() in n.lower() or n.lower() in fn.lower() for n in notifs):
                    reg_ans = reg_ans.replace(fn, "").replace("()", "").strip()
        else:
            reg_ans = "No active Quality Control Order was identified in published BIS Gazette records for this standard."
            reg_orders = []

        reg_ev_ids = [eid for eid in raw_reg.get("evidence_ids", []) if eid in valid_ev_ids]
        if qco_info and qco_info.get("associated_qco_ids"):
            reg_ev_ids.extend([str(qid) for qid in qco_info.get("associated_qco_ids")])

        reg_key_info = cls.deduplicate_key_information(
            raw_reg.get("key_information", []),
            reg_ans,
            reg_orders
        )

        regulatory_status_stage = RegulatoryStatusStage(
            title=cls.sanitize_text(raw_reg.get("title") or "QCO / Regulatory Status"),
            answer=reg_ans,
            key_information=reg_key_info,
            evidence_ids=list(set(reg_ev_ids)),
            regulatory_orders=reg_orders
        )

        # 4. Mandatory Certification (Strict Authority Lock)
        raw_mand = raw_dict.get("mandatory_certification", {})
        det_is_mandatory = det.get("is_mandatory")
        if det_is_mandatory is None:
            stage_4 = det.get("stage_4", {})
            if "is_mandatory" in stage_4:
                det_is_mandatory = stage_4.get("is_mandatory")
            elif qco_title or notifs:
                det_is_mandatory = True

        mand_ans = cls.sanitize_text(raw_mand.get("answer") or "")
        if det_is_mandatory is True:
            locked_is_mandatory = True
            if not mand_ans or any(w in mand_ans.lower() for w in ["voluntary", "optional", "not mandatory", "not established"]):
                order_name = qco_title or "the notified Quality Control Order"
                mand_ans = f"BIS certification is mandatory under {order_name}. Conformity assessment is a statutory prerequisite prior to manufacturing, importing, stocking, or selling in India."
        elif det_is_mandatory is False:
            locked_is_mandatory = False
            mand_ans = "Mandatory certification has not been established under published Quality Control Orders."
        else:
            locked_is_mandatory = None
            if not mand_ans or "not been established" in mand_ans.lower():
                mand_ans = "Mandatory certification status depends on applicable ministerial Quality Control Orders."

        mand_key_info = cls.deduplicate_key_information(
            raw_mand.get("key_information", []),
            mand_ans
        )

        mandatory_certification_stage = MandatoryCertificationStage(
            title=cls.sanitize_text(raw_mand.get("title") or "Mandatory Certification"),
            answer=mand_ans,
            key_information=mand_key_info,
            evidence_ids=[eid for eid in raw_mand.get("evidence_ids", []) if eid in valid_ev_ids],
            is_mandatory=locked_is_mandatory
        )

        # 5. Certification Scheme (Prevent Scheme Guessing)
        raw_scheme = raw_dict.get("certification_scheme", {})
        det_scheme = det.get("certification_scheme") or det.get("stage_5", {}).get("certification_scheme")
        scheme_ans = cls.sanitize_text(raw_scheme.get("answer") or "")
        reg_title = qco_title or ""
        is_cro = "compulsory registration" in reg_title.lower() or "cro" in reg_title.lower()

        if det_scheme:
            scheme_name = det_scheme
            scheme_type = det.get("scheme_type") or "Product Certification Scheme"
            if not scheme_ans:
                scheme_ans = f"Certification is governed under {det_scheme}."
        elif is_cro:
            scheme_name = "Compulsory Registration Scheme (CRS) / Scheme-II"
            scheme_type = "Compulsory Registration Scheme"
            if not scheme_ans or "could not be confirmed" in scheme_ans.lower():
                std_lbl = input_data.standards[0] if input_data.standards else "This product"
                scheme_ans = f"{std_lbl} products covered by the applicable regulatory framework require registration under the Compulsory Registration Scheme (CRS), as supported by the available BIS regulatory evidence."
        else:
            scheme_name = None
            scheme_type = None
            target_std = input_data.standards[0] if input_data.standards else ""
            q_text = f"{target_std} {getattr(input_data, 'user_question', '') or ''} {getattr(input_data, 'product', '') or ''}".lower()
            is_electronics = any(w in q_text for w in ["16046", "battery", "laptop", "mobile", "electronic", "it equipment"])
            if is_electronics:
                scheme_ans = "Operates under Scheme-II (Compulsory Registration Scheme / CRS) for electronics and IT goods under BIS regulations. The specific scheme could not be confirmed from available BIS records."
            else:
                scheme_ans = "Operates under Scheme-I (ISI Mark Scheme) under the BIS (Conformity Assessment) Regulations, 2018 for product licensing. The specific scheme could not be confirmed from available BIS records."

        scheme_key_info = cls.deduplicate_key_information(
            raw_scheme.get("key_information", []),
            scheme_ans,
            [scheme_name] if scheme_name else []
        )

        certification_scheme_stage = CertificationSchemeStage(
            title=cls.sanitize_text(raw_scheme.get("title") or "Certification Scheme"),
            answer=scheme_ans,
            key_information=scheme_key_info,
            evidence_ids=[eid for eid in raw_scheme.get("evidence_ids", []) if eid in valid_ev_ids],
            scheme_type=scheme_type,
            scheme_name=scheme_name
        )

        # 6. Testing (Validate Clauses & Parameters)
        raw_test = raw_dict.get("testing", {})
        test_ans = cls.sanitize_text(raw_test.get("answer") or "")
        verified_tests = det.get("testing_requirements", []) or det.get("stage_6", {}).get("testing_requirements", [])
        test_methods = [t.get("test_name") for t in verified_tests if isinstance(t, dict) and t.get("test_name")]

        all_test_ev_text = " ".join([
            ev.get("text") or ev.get("source_title") or "" for ev in (input_data.testing_evidence + input_data.rag_evidence)
        ])

        test_clauses_in_ans = re.findall(r'\bClause\s*(\d+(?:\.\d+)*)\b', test_ans, re.IGNORECASE)
        for cl in test_clauses_in_ans:
            if cl not in all_test_ev_text:
                test_ans = test_ans.replace(f"Clause {cl}", "applicable standard clauses")

        if not test_methods and not input_data.testing_evidence:
            test_ans = "Product-specific laboratory testing parameters could not be confirmed from the available BIS records for this standard."
            test_methods = []
        elif not test_ans:
            if test_methods:
                bullets = "\n".join([f"- **{t}**" for t in test_methods[:6]])
                test_ans = f"Testing must conform to the Scheme of Inspection and Testing (SIT), covering key parameters:\n{bullets}"
            else:
                test_ans = "Product-specific laboratory testing parameters could not be confirmed from the available BIS records for this standard."

        test_key_info = cls.deduplicate_key_information(
            raw_test.get("key_information", []),
            test_ans,
            test_methods
        )

        testing_stage = ComplianceTestingStage(
            title=cls.sanitize_text(raw_test.get("title") or "Required Testing"),
            answer=test_ans,
            key_information=test_key_info,
            evidence_ids=[eid for eid in raw_test.get("evidence_ids", []) if eid in valid_ev_ids],
            test_methods=test_methods or raw_test.get("test_methods", [])
        )

        # 7. Inspection Requirements
        raw_insp = raw_dict.get("inspection", {})
        insp_ans = cls.sanitize_text(raw_insp.get("answer") or "")
        total_insp = det.get("stage_7", {}).get("total_requirements", 0)

        if is_cro:
            insp_ans = "Under the Compulsory Registration Scheme (CRS), pre-certification factory inspection is not required; conformity is established through accredited laboratory test reports."
            insp_key_info = ["CRS is a test-report registration scheme without routine pre-license factory audit"]
        elif total_insp == 0 and not input_data.inspection_evidence:
            insp_ans = "Product-specific factory inspection requirements could not be confirmed from the available BIS records."
            insp_key_info = ["Product-specific inspection schedule is not established in available BIS evidence"]
        elif not insp_ans:
            insp_ans = "Manufacturers must maintain adequate testing equipment and continuous quality control registers conforming to the Scheme of Inspection and Testing (SIT)."
            insp_key_info = raw_insp.get("key_information", [])
        else:
            insp_key_info = raw_insp.get("key_information", [])

        insp_key_info = cls.deduplicate_key_information(
            insp_key_info,
            insp_ans
        )

        inspection_stage = InspectionStage(
            title=cls.sanitize_text(raw_insp.get("title") or "Factory Inspection"),
            answer=insp_ans,
            key_information=insp_key_info,
            evidence_ids=[eid for eid in raw_insp.get("evidence_ids", []) if eid in valid_ev_ids],
            inspection_requirements=raw_insp.get("inspection_requirements", [])
        )

        # 8. Sampling Requirements
        raw_samp = raw_dict.get("sampling", {})
        samp_ans = cls.sanitize_text(raw_samp.get("answer") or "")
        total_samp = det.get("stage_8", {}).get("total_requirements", 0)

        if re.search(r'\b(?:5\s*%|five units|minimum of \d+|1 sample per day)\b', samp_ans, re.IGNORECASE) and not input_data.sampling_evidence:
            samp_ans = "Product-specific sampling requirements could not be confirmed from the available BIS records."

        if total_samp == 0 and not input_data.sampling_evidence:
            samp_ans = "Product-specific sampling requirements could not be confirmed from the available BIS records."
            samp_key_info = ["Product-specific sampling protocol is not established in available BIS evidence"]
        elif not samp_ans:
            samp_ans = "Sampling must be carried out on representative production lots in accordance with the statistical sampling criteria defined in the Indian Standard."
            samp_key_info = raw_samp.get("key_information", [])
        else:
            samp_key_info = raw_samp.get("key_information", [])

        samp_key_info = cls.deduplicate_key_information(
            samp_key_info,
            samp_ans
        )

        sampling_stage = SamplingStage(
            title=cls.sanitize_text(raw_samp.get("title") or "Lot & Control Unit Sampling"),
            answer=samp_ans,
            key_information=samp_key_info,
            evidence_ids=[eid for eid in raw_samp.get("evidence_ids", []) if eid in valid_ev_ids],
            sampling_guidelines=raw_samp.get("sampling_guidelines", [])
        )

        # 9. Laboratories (100% Locked to F3 LIMS Output)
        raw_labs = raw_dict.get("laboratories", {})
        f3_labs = input_data.f3_laboratories
        recognized_lab_names = []
        lab_ev_ids = []

        for lab in f3_labs:
            name = lab.get("laboratory_name") or lab.get("name")
            if name:
                recognized_lab_names.append(name)
            lid = lab.get("id") or lab.get("public_lab_code") or lab.get("laboratory_id")
            if lid:
                lab_ev_ids.append(str(lid))

        if recognized_lab_names:
            lab_ans = f"Identified {len(recognized_lab_names)} BIS-recognized laboratory facility(ies) qualified for testing according to the specified standard."
        else:
            lab_ans = "No BIS-recognized testing laboratories were identified in the LIMS directory for the specified standard and location."

        raw_lab_ki = raw_labs.get("key_information", [])
        if not raw_lab_ki and recognized_lab_names:
            raw_lab_ki = [f"Recognized Testing Facilities: {len(recognized_lab_names)} found in BIS LIMS"]

        lab_key_info = cls.deduplicate_key_information(
            raw_lab_ki,
            lab_ans,
            recognized_lab_names
        )

        laboratories_stage = LaboratoriesStage(
            title=cls.sanitize_text(raw_labs.get("title") or "Qualified BIS Laboratories"),
            answer=lab_ans,
            key_information=lab_key_info,
            evidence_ids=lab_ev_ids,
            recognized_labs=recognized_lab_names
        )

        # 10. Certification Process
        raw_proc = raw_dict.get("certification_process", {})
        proc_ans = cls.sanitize_text(raw_proc.get("answer") or "")
        if not proc_ans:
            proc_ans = (
                "The standard BIS certification workflow involves:\n"
                "1. Submission of online application via Manakonline portal\n"
                "2. Setup of in-house testing facilities per SIT\n"
                "3. Factory inspection and sample drawing by BIS officers\n"
                "4. Independent laboratory test verification\n"
                "5. Grant of Licence (GoL)"
            )
        elif "application" not in proc_ans.lower() and "manakonline" not in proc_ans.lower():
            proc_ans += " Formal application is submitted online through the BIS Manakonline portal."

        proc_key_info = cls.deduplicate_key_information(
            raw_proc.get("key_information", []),
            proc_ans
        )

        certification_process_stage = CertificationProcessStage(
            title=cls.sanitize_text(raw_proc.get("title") or "Certification Process"),
            answer=proc_ans,
            key_information=proc_key_info,
            evidence_ids=[eid for eid in raw_proc.get("evidence_ids", []) if eid in valid_ev_ids],
            process_steps=raw_proc.get("process_steps", [
                "1. Application submission on Manakonline",
                "2. Implementation of Scheme of Inspection & Testing",
                "3. BIS Factory Audit & Sampling",
                "4. Independent Lab Testing",
                "5. Grant of Licence (GoL)"
            ])
        )

        # 11. Assessment Summary
        raw_assess = raw_dict.get("assessment", {})
        assess_ans = cls.sanitize_text(raw_assess.get("answer") or "")

        if not assess_ans:
            prod_name = input_data.product or (input_data.standards[0] if input_data.standards else "specified product")
            is_mand = det.get("is_mandatory")
            if is_mand is True:
                assess_ans = f"BIS certification is mandatory for {prod_name} under the applicable regulatory order."
            elif is_mand is False:
                assess_ans = f"Mandatory certification is not currently notified for {prod_name} under published Quality Control Orders."
            else:
                assess_ans = f"Compliance evaluation for {prod_name}: Refer to applicable Indian Standards and published regulatory notifications."

        assess_key_info = cls.deduplicate_key_information(
            raw_assess.get("key_information", []),
            assess_ans
        )

        assessment_stage = AssessmentStage(
            title=cls.sanitize_text(raw_assess.get("title") or "Assessment"),
            answer=assess_ans,
            key_information=assess_key_info,
            evidence_ids=[eid for eid in raw_assess.get("evidence_ids", []) if eid in valid_ev_ids],
            assessment_summary=assess_ans
        )

        # 12. Next Steps
        raw_steps = raw_dict.get("next_steps", [])
        cleaned_steps = [cls.sanitize_text(s) for s in raw_steps if cls.sanitize_text(s)]
        if not cleaned_steps:
            cleaned_steps = [
                "Review the latest version of the applicable Indian Standard.",
                "Verify statutory Quality Control Order timelines on the official BIS portal.",
                "Ensure factory manufacturing equipment and test facilities meet SIT specifications.",
                "Engage a BIS-recognized laboratory for initial prototype testing if required."
            ]

        return ComplianceJourneyV2Response(
            product_identification=prod_stage,
            applicable_standards=applicable_standards_stage,
            regulatory_status=regulatory_status_stage,
            mandatory_certification=mandatory_certification_stage,
            certification_scheme=certification_scheme_stage,
            testing=testing_stage,
            inspection=inspection_stage,
            sampling=sampling_stage,
            laboratories=laboratories_stage,
            certification_process=certification_process_stage,
            assessment=assessment_stage,
            next_steps=cleaned_steps
        )


# ---------------------------------------------------------------------------
# Defensive JSON Recovery Helper
# ---------------------------------------------------------------------------

def extract_json_payload(raw_text: str) -> Optional[Dict[str, Any]]:
    """
    Defensive recovery mechanism for extracting JSON payloads from malformed,
    fenced, or preamble-wrapped model responses.
    """
    if not raw_text or not raw_text.strip():
        return None

    cleaned = raw_text.strip()

    # 1. Strip markdown code blocks if present
    if "```" in cleaned:
        fence_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', cleaned, re.DOTALL | re.IGNORECASE)
        if fence_match:
            candidate = fence_match.group(1).strip()
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass

    # 2. Try direct parse
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    # 3. Locate outermost JSON object boundaries { ... }
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        json_slice = cleaned[first_brace:last_brace + 1].strip()
        try:
            parsed = json.loads(json_slice)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            # 4. Clean trailing commas before closing braces/brackets
            fixed = re.sub(r',\s*([}\]])', r'\1', json_slice)
            try:
                parsed = json.loads(fixed)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass

    return None


# ---------------------------------------------------------------------------
# Main V2 Synthesizer Service
# ---------------------------------------------------------------------------

class ComplianceJourneyV2Synthesizer:
    """
    Orchestrates the Groq synthesis prompt and safety validation for the
    redesigned Compliance Journey response contract.
    """

    def __init__(
        self,
        groq_client: Optional[GroqClient] = None,
        model: str = DEFAULT_V2_MODEL,
        max_tokens: int = 3500,
        temperature: float = 0.0,
        enable_correctness_guarding: bool = True
    ):
        self._groq_client = groq_client
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.enable_correctness_guarding = enable_correctness_guarding
        self.validator = ComplianceSafetyValidator()
        self.last_trace: Dict[str, Any] = {}

    @property
    def groq_client(self) -> GroqClient:
        if self._groq_client is None:
            self._groq_client = GroqClient(model=self.model)
        return self._groq_client

    def build_prompt(self, input_data: GroqComplianceInput) -> List[Dict[str, str]]:
        """
        Constructs the structured prompt treating the 10 stages as separate logical questions.
        Adheres to:
        - 4-tier evidence hierarchy (Correction 1)
        - Progressive stage context chaining (Section 20)
        - Ten logical questions verbatim (Section 2)
        - Anti-hallucination boundaries on precise regulatory facts (Correction 1C)
        - Constructive contextual guidance over 'evidence not established' (Correction 1D)
        - User-facing terminology restriction without banning prompt-internal context (Correction 2)
        - Stage 9 F3 laboratory invariant (Section 15)
        - Structured 10-stage JSON response schema (Section 19)
        """
        system_msg = (
            "You are the Product Compliance Journey Answer Generation Engine for the Bureau of Indian Standards (BIS) assistant.\n\n"
            "Your objective is to generate clear, accurate, natural-language compliance answers across 10 logical stages, an overall assessment, and actionable next steps in ONE single structured JSON response.\n\n"
            "EVIDENCE HIERARCHY & REGULATORY ACCURACY RULES:\n"
            "1. Primary Basis: If authoritative BIS/RAG evidence is supplied in the context, use it as the primary factual basis.\n"
            "2. General Knowledge: If the requested information is absent from the supplied evidence, use your general knowledge of Indian Standards, engineering practices, and BIS conformity assessment to provide a useful, natural answer.\n"
            "3. Precise Regulatory Truth Boundaries (Never Fabricate):\n"
            "   For precise current regulatory facts, you must NEVER invent or guess:\n"
            "   - Quality Control Order (QCO) names\n"
            "   - Gazette notification numbers (e.g., S.O. numbers)\n"
            "   - Statutory effective dates\n"
            "   - Exact BIS scheme numbers\n"
            "   - Statutory legal provisions\n"
            "   - Exact BIS fee amounts\n"
            "   - Exact test clauses or section numbers not in evidence\n"
            "   - Exact testing frequencies\n"
            "   - Exact lot/sample quantities\n"
            "   - BIS laboratory names\n"
            "4. Useful Contextual Guidance over 'Evidence Not Established':\n"
            "   If a precise regulatory fact cannot be reliably confirmed, provide useful, constructive contextual guidance rather than fabricating a specific fact.\n"
            "   Do NOT repeatedly say 'evidence not established' or 'could not be confirmed from available BIS records'. Give the user the most helpful, practical guidance possible based on standard industry and regulatory practice.\n"
            "5. Stage 9 (Laboratories) Invariant:\n"
            "   You must NOT generate, invent, or rerank testing laboratories. The backend deterministically injects authoritative BIS-recognized laboratories from the LIMS directory. You may write a natural introductory sentence acknowledging the recognized laboratory facilities.\n"
            "6. Adaptive Answer Length & Content Structure:\n"
            "   Structure text semantically according to the nature of each stage so it is immediately scannable and readable:\n"
            "   - Stage 1 (Product Identification): Concise 1-2 sentence identification of the product and primary scope without methodology narration.\n"
            "   - Stage 2 (Applicable Indian Standards): Direct standard identification (1 sentence; bullet list if multiple standards apply).\n"
            "   - Stage 3 (QCO / Regulatory Status): Clear regulatory conclusion first, followed by compact bullet points for regulatory facts (Order title, notification, effective date; or conflict summary).\n"
            "   - Stage 4 (Mandatory Certification): Direct conclusion first ('BIS certification is mandatory under [Order].' or 'Mandatory certification has not been established under published Quality Control Orders.'), followed by 1-sentence regulatory basis.\n"
            "   - Stage 5 (Certification Scheme): 1-2 sentence statement of applicable scheme (e.g., Scheme-I ISI Mark, Scheme-II CRS, or unestablished).\n"
            "   - Stage 6 (Required Testing): 1-sentence testing framework introduction, followed by a clean bullet list of required tests when multiple tests exist (e.g. '- **Test Name**: clause/scope'). Summarize frequencies/SIT at the end. Do NOT produce a dense, unreadable paragraph.\n"
            "   - Stage 7 (Factory Inspection): Clear statement on whether factory inspection applies (e.g. not required for CRS; factory audit & SIT registers required for Scheme-I), with bullets for specific controls if established.\n"
            "   - Stage 8 (Sampling Requirements): Structured bullets for lot/sample requirements if established in evidence; otherwise concise unconfirmed statement without guessing numbers.\n"
            "   - Stage 9 (Laboratories): Single concise introductory sentence acknowledging the recognized laboratory facilities. Do NOT list or invent any laboratory names.\n"
            "   - Stage 10 (Certification Process): Numbered step-by-step sequence (1., 2., 3., etc.) for the conformity workflow.\n"
            "   - Assessment: This acts as the conversational chat response. Direct answer first. Use bullets for multiple facts. NEVER collapse multiple standards into one paragraph; always separate them. DO NOT write giant paragraphs.\n"
            "   - Next Steps: Numbered action items (1., 2., 3., etc.) for practical follow-up.\n"
            "7. User-Facing Terminology Restriction:\n"
            "   The generated user-facing text (answer, key_information, assessment, next_steps) must NEVER expose internal architecture jargon: do NOT use 'PC-3', 'PC-4', 'PC-5', 'RAG', 'UNKNOWN', 'GROUNDED', 'HYBRID', 'LLM_FALLBACK', 'retrieval status', 'evidence corpus', or 'EVIDENCE NOT ESTABLISHED'. Write in professional, natural language.\n"
            "8. Comprehensive 10-Stage Coverage (Even for Definition / Lookup Queries):\n"
            "   Even if the user query is concise (e.g., standard code like 'IS 374') or the classified intent is DEFINITION, LOOKUP, or PRODUCT_LOOKUP, you MUST generate a comprehensive, authoritative, fully-developed answer across ALL 10 stages of the compliance journey. The definition of the standard belongs in Stage 2 (and Stage 1 for product context), but Stages 3-10 (QCO, Mandatory status, Scheme, Testing, Inspection, Sampling, Labs, Process) MUST still be thoroughly generated using the supplied context and evidence. Do not omit, truncate, or leave any stage empty.\n"
            "9. Three Levels of Content (Zero Repetition):\n"
            "   - Level 1: 'answer' provides the primary conclusion and stage-appropriate structured explanation.\n"
            "   - Level 2: 'key_information' provides 1-3 compact supplemental chips containing ONLY new, additional facts (e.g. gazette notification number, implementation date). NEVER repeat facts, words, or values already present in 'answer'. If no additional facts exist, provide an empty list [].\n"
            "   - Level 3: 'details' (structured cards for tests, candidate standards, and qualified labs are rendered automatically by the UI). Never duplicate entire tables in 'answer'.\n"
            "10. CONVERSATIONAL ASSESSMENT FORMATTING (CRITICAL):\n"
            "   The 'assessment' acts as the main conversational chat response. It must be polished, readable, and strictly adhere to these formatting rules:\n"
            "   - Direct Answer First: Start with the actual answer immediately (e.g., 'IS 4985:2021 covers unplasticized PVC...'). Do NOT start with 'IS 4985:2021 is an Indian Standard that specifies...' followed by a huge paragraph.\n"
            "   - Bullets for Multiple Facts: If the answer contains 3 or more distinct facts (or clauses), use bullets. Do not combine separate clauses into one paragraph.\n"
            "   - Multiple Standards: When referencing multiple Indian Standards, ALWAYS separate them into a bulleted list explaining what each standard contributes. Never place multiple standards in one giant paragraph.\n"
            "   - Standard/Definition Questions: Prefer a short 1-2 sentence answer, then a bulleted 'It covers' list.\n"
            "   - Technical Questions: Use compact tables or grouped bullets (Parameter, Test, Method, Clause, Frequency) rather than paragraphs.\n"
            "   - Certification Questions: Structure as 'Answer' (one direct conclusion) -> 'Why' (bullets for QCO/standard) -> 'Process' (numbered steps). Do not mix conclusion and process.\n"
            "   - QCO/Regulatory Questions: 'Regulatory status' (1 sentence) -> 'QCO details' (bullets for QCO, Notification, Date, Standard). Explain conflicts briefly. Do not bury regulatory conclusions in prose.\n"
            "   - Testing Questions: Bulleted list of tests. Only provide frequency/laboratory if useful. Do not repeat test info in prose below the list.\n"
            "   - Laboratory Questions: Structured numbered list (Name, Location, Status, Scope). Only use provided F3 data. Do not invent labs.\n"
            "   - Process/How-to Questions: Use concise numbered steps.\n"
            "   - Comparison Questions: Use a Markdown table.\n"
            "   - Answer Length: Decide based on the query. 1-3 sentences for simple questions. Do not make a simple question unnecessarily long, and do not compress complex answers into one paragraph.\n"
            "   - Remove Repetition: Do not repeat facts across the opening sentence, bullet lists, key information, and footers. State it once.\n"
            "   - Semantic Markdown: Use **bold**, *italic*, bullets, numbered lists, and short headings. Do NOT output raw HTML. Do not use excessive bolding, emojis, or long horizontal separators."
        )

        # Build context summary
        qco = input_data.qco_evidence or {}
        det = input_data.deterministic_results

        controlled_contexts = ComplianceCorrectnessEngine.build_stage_controlled_contexts(input_data)
        stages_ctx_lines = []
        for s_num in range(1, 11):
            s_ctx = controlled_contexts[s_num]
            stages_ctx_lines.append(
                f"Stage {s_num} ({s_ctx.stage_name}):\n"
                f"  Authoritative Facts: {s_ctx.authoritative_facts or ['None']}\n"
                f"  Missing Facts: {s_ctx.missing_facts or ['None']}\n"
                f"  General Guidance Allowed: {s_ctx.general_guidance_allowed}"
            )

        evidence_summary = []
        for ev in input_data.rag_evidence[:8]:
            eid = ev.get("source_record_id") or ev.get("retrieval_unit_id") or "ev"
            title = ev.get("source_title") or ev.get("heading") or "Official Record"
            text = (ev.get("text") or ev.get("text_preview") or "").strip()
            if text:
                evidence_summary.append(f"[{eid}] {title}: {text[:350]}")

        f3_labs_summary = []
        for lab in input_data.f3_laboratories:
            name = lab.get("laboratory_name") or lab.get("name")
            code = lab.get("public_lab_code") or lab.get("id") or ""
            city = lab.get("city") or (lab.get("address", {}).get("city") if isinstance(lab.get("address"), dict) else "")
            f3_labs_summary.append(f"{name} ({code}) - {city}")

        # Progressive Context Chaining (Section 20)
        prod_label = input_data.product or (input_data.standards[0] if input_data.standards else "the specified product")
        stds_label = ", ".join(input_data.standards) if input_data.standards else "Under identification"
        qco_label = qco.get("qco_title") or ("Notified QCO" if det.get("is_mandatory") is True else "Under regulatory review")
        mand_label = "Mandatory under QCO" if det.get("is_mandatory") is True else ("Voluntary / Unconfirmed" if det.get("is_mandatory") is False else "Under regulatory review")
        scheme_label = det.get("certification_scheme") or "Per applicable BIS regulatory route"

        progressive_context = (
            f"PROGRESSIVE STAGE CONTEXT:\n"
            f"- Stage 1 context: Product = {prod_label}\n"
            f"- Stage 2 context: Product = {prod_label}, Standards = {stds_label}\n"
            f"- Stage 3 context: Product = {prod_label}, Standard = {stds_label}, Regulatory Order = {qco_label}\n"
            f"- Stage 4 context: Product = {prod_label}, Standard = {stds_label}, Order = {qco_label}, Mandatory Certification = {mand_label}\n"
            f"- Stage 5 context: Product = {prod_label}, Standard = {stds_label}, Order = {qco_label}, Mandatory = {mand_label}, Route/Scheme = {scheme_label}\n"
            f"- Stage 6 context: Product = {prod_label}, Standard = {stds_label}, Scheme = {scheme_label}\n"
            f"- Stage 7 context: Product = {prod_label}, Standard = {stds_label}, Factory Inspection Routine per SIT\n"
            f"- Stage 8 context: Product = {prod_label}, Standard = {stds_label}, Sampling Guidelines per SIT\n"
            f"- Stage 9 context: Product = {prod_label}, Standard = {stds_label}, Qualified Laboratories = {len(input_data.f3_laboratories)} facilities found in LIMS\n"
            f"- Stage 10 context: Product = {prod_label}, Standard = {stds_label}, Route/Scheme = {scheme_label}"
        )

        conv_ctx = ""
        if input_data.conversation_history:
            history_lines = []
            for msg in input_data.conversation_history[-4:]:
                r = msg.get("role", "user")
                c = msg.get("content", "")
                if c:
                    history_lines.append(f"{r.upper()}: {c[:150]}")
            if history_lines:
                conv_ctx = f"PREVIOUS CONVERSATIONAL CONTEXT:\n" + "\n".join(history_lines) + "\n\n"

        user_content = f"""USER QUESTION: {input_data.user_question}
DETECTED INTENT: {input_data.intent or 'General Compliance Evaluation'}
IDENTIFIED PRODUCT: {input_data.product or 'Not explicitly specified'}
PRODUCT ATTRIBUTES: {json.dumps(input_data.product_attributes or {}) if input_data.product_attributes else 'None'}
LOCATION: {input_data.location or 'All India'}
IDENTIFIED STANDARD(S): {', '.join(input_data.standards) if input_data.standards else 'Not explicitly specified'}

{conv_ctx}DETERMINISTIC COMPLIANCE BASELINE:
- QCO Title: {qco.get('qco_title') or 'None confirmed'}
- Notification Numbers: {', '.join(qco.get('notification_numbers', [])) or 'None'}
- Effective Date: {qco.get('effective_date') or 'Not specified'}
- Mandatory Status: {det.get('is_mandatory')}
- Verified Scheme: {det.get('certification_scheme') or 'Not established in BIS records'}

{progressive_context}

EVIDENCE-FIRST STAGE CONTEXTS (Adhere strictly to these factual boundaries):
{chr(10).join(stages_ctx_lines)}

SUPPLIED F3 AUTHORITATIVE LABORATORIES (Do not invent others):
{chr(10).join(f3_labs_summary) if f3_labs_summary else 'No matching recognized laboratories in LIMS'}

RETRIEVED BIS EVIDENCE:
{chr(10).join(evidence_summary) if evidence_summary else 'No authoritative text chunks retrieved'}

TEN LOGICAL STAGE QUESTIONS TO ANSWER:
STAGE 1 (Product Identification):
"Identify the product and its primary application/scope in 1-2 concise sentences without methodology narration."

STAGE 2 (Applicable Indian Standards):
"Which Indian Standard(s) apply? State the primary standard concisely, or provide a bulleted list if multiple apply."

STAGE 3 (QCO / Regulatory Status):
"What QCO or regulatory order applies? State the regulatory status first, followed by compact bulleted facts (order, notification, effective date; or conflict summary)."

STAGE 4 (Mandatory Certification):
"Is BIS certification mandatory? State the requirement directly in the first sentence, followed by the regulatory basis."

STAGE 5 (Certification Scheme):
"Which BIS certification scheme applies? State the specific scheme concisely (e.g. Scheme-I, Scheme-II/CRS, or unestablished)."

STAGE 6 (Required Testing):
"What testing is required? Provide a 1-sentence SIT introduction, followed by a structured bullet list of specific tests. Summarize frequency/SIT briefly. Do not dump a single dense paragraph."

STAGE 7 (Factory Inspection):
"What factory inspection applies? State clearly if required or not, followed by key quality control points in bullets if in evidence."

STAGE 8 (Lot & Control Unit Sampling):
"What sampling requirements apply? Provide structured bullets for lot/sample rules if in evidence; otherwise state unconfirmed without guessing numbers."

STAGE 9 (Qualified BIS Laboratories):
"Acknowledge the recognized testing facilities matching the standard in a single introductory sentence (do not list laboratory names)."

STAGE 10 (Certification Process):
"What is the step-by-step certification workflow? Provide a numbered sequence (1., 2., 3.) of procedural steps."

ASSESSMENT:
"Answer the user's original question directly in the first sentence, followed by a structured summary."

NEXT STEPS:
"Provide numbered practical next actions (1., 2., 3.)."

OUTPUT FORMAT: Return STRICT JSON matching:
{{
  "product_identification": {{"title": "Product Identification", "answer": "...", "key_information": [...], "evidence_ids": [...]}},
  "applicable_standards": {{"title": "Applicable Indian Standards", "answer": "...", "key_information": [...], "evidence_ids": [...]}},
  "regulatory_status": {{"title": "QCO / Regulatory Status", "answer": "...", "key_information": [...], "evidence_ids": [...]}},
  "mandatory_certification": {{"title": "Mandatory Certification", "answer": "...", "key_information": [...], "evidence_ids": [...]}},
  "certification_scheme": {{"title": "Certification Scheme", "answer": "...", "key_information": [...], "evidence_ids": [...]}},
  "testing": {{"title": "Required Testing", "answer": "...", "key_information": [...], "evidence_ids": [...]}},
  "inspection": {{"title": "Factory Inspection", "answer": "...", "key_information": [...], "evidence_ids": [...]}},
  "sampling": {{"title": "Lot & Control Unit Sampling", "answer": "...", "key_information": [...], "evidence_ids": [...]}},
  "laboratories": {{"title": "Qualified BIS Laboratories", "answer": "...", "key_information": [...], "evidence_ids": [...]}},
  "certification_process": {{"title": "Certification Process", "answer": "...", "key_information": [...], "evidence_ids": [...]}},
  "assessment": {{"title": "Assessment", "answer": "...", "key_information": [...], "evidence_ids": [...]}},
  "next_steps": ["...", "..."]
}}"""

        return [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_content}
        ]

    def _deterministic_fallback(
        self,
        input_data: GroqComplianceInput,
        reason: str,
        trace_info: Optional[Dict[str, Any]] = None
    ) -> ComplianceJourneyV2Response:
        """
        Safe deterministic fallback when Groq is unavailable, rate-limited,
        times out, or returns an unparseable response.
        Preserves available deterministic input facts without inventing detailed answers.
        """
        if trace_info is None:
            trace_info = getattr(self, "last_trace", {}) or {}
        trace_info["fallback_used"] = True
        trace_info["fallback_reason"] = reason
        self.last_trace = trace_info
        logger.info(f"Using deterministic V2 fallback (reason: {reason}).")
        resp = self.validator.validate_and_guard({}, input_data)
        # Sub-phase D: Deep semantic correctness validation, dynamic fidelity, authority locks
        if self.enable_correctness_guarding:
            resp, quality_scores, contradictions = ComplianceCorrectnessEngine.enforce_semantic_consistency(
                v2_response=resp,
                input_data=input_data
            )
            trace_info["correctness_report"] = ComplianceCorrectnessEngine.build_correctness_report(
                quality_scores=quality_scores,
                contradictions_detected=contradictions
            )
        self.last_trace = trace_info
        return resp

    def synthesize(self, input_data: GroqComplianceInput) -> ComplianceJourneyV2Response:
        """
        Executes one-call ten-question synthesis with Groq, passes through SafetyValidator,
        and gracefully falls back deterministically if Groq fails or is unconfigured.

        Sub-phase B & D guarantees:
        - Exactly ONE Groq request per journey.
        - Preferred flow: direct JSON -> schema validation -> response parsing -> invariant validation.
        - Defensive recovery via extract_json_payload for malformed responses.
        - Deterministic fallback on 429, timeout, network error, or invalid output.
        - Stage 9 F3 laboratory invariant strictly enforced.
        - Internal technical jargon purged from all user-facing fields.
        - Trace telemetry recorded in self.last_trace.
        - Deep semantic correctness validation, dynamic fidelity, and authority locks (Sub-phase D).
        """
        trace_info: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "groq_invoked": False,
            "call_count": 0,
            "fallback_used": False,
            "fallback_reason": None,
            "json_recovery_used": False,
        }
        self.last_trace = trace_info

        if not self.groq_client.is_configured:
            logger.info("GroqClient not configured; using deterministic V2 fallback.")
            return self._deterministic_fallback(input_data, reason="GROQ_NOT_CONFIGURED", trace_info=trace_info)

        messages = self.build_prompt(input_data)
        trace_info["groq_invoked"] = True
        trace_info["call_count"] = 1

        try:
            start_time = time.time()
            raw_response = self.groq_client.chat_completion(
                messages,
                max_tokens=self.max_tokens,
                trace_info=trace_info
            )
            trace_info["latency_sec"] = round(time.time() - start_time, 3)

            if not raw_response or not raw_response.strip():
                logger.warning("Groq returned empty response; falling back to deterministic V2.")
                return self._deterministic_fallback(input_data, reason="EMPTY_RESPONSE", trace_info=trace_info)

            # Preferred flow (Correction 1):
            # Groq structured JSON response -> schema validation -> response parsing -> invariant validation
            # Do NOT rely on free-form JSON extraction as the primary mechanism.
            parsed = None
            raw_trimmed = raw_response.strip()

            candidate = raw_trimmed
            if candidate.startswith("```json") and candidate.endswith("```"):
                candidate = candidate[7:-3].strip()
            elif candidate.startswith("```") and candidate.endswith("```"):
                candidate = candidate[3:-3].strip()

            try:
                direct = json.loads(candidate)
                if isinstance(direct, dict):
                    parsed = direct
            except Exception:
                pass

            # extract_json_payload() remains as a defensive recovery mechanism for malformed/non-structured responses
            if parsed is None:
                logger.info("Direct JSON parse failed; executing defensive recovery extraction.")
                parsed = extract_json_payload(raw_response)
                if parsed is not None:
                    trace_info["json_recovery_used"] = True

            if not isinstance(parsed, dict):
                logger.warning("Groq did not return a valid JSON object; falling back to deterministic V2.")
                return self._deterministic_fallback(input_data, reason="MALFORMED_JSON", trace_info=trace_info)

            # Response parsing & shape validation & invariant enforcement
            resp = self.validator.validate_and_guard(parsed, input_data)
            # Sub-phase D: Deep semantic correctness validation, dynamic fidelity, authority locks
            if self.enable_correctness_guarding:
                resp, quality_scores, contradictions = ComplianceCorrectnessEngine.enforce_semantic_consistency(
                    v2_response=resp,
                    input_data=input_data
                )
                trace_info["correctness_report"] = ComplianceCorrectnessEngine.build_correctness_report(
                    quality_scores=quality_scores,
                    contradictions_detected=contradictions
                )
            self.last_trace = trace_info
            return resp

        except Exception as e:
            err_str = str(e)
            logger.warning(f"Groq synthesis failed ({err_str}); falling back to deterministic V2.")
            reason = "RATE_LIMITED_429" if ("429" in err_str or "RATE_LIMITED" in err_str) else f"EXCEPTION_{type(e).__name__}"
            return self._deterministic_fallback(input_data, reason=reason, trace_info=trace_info)

