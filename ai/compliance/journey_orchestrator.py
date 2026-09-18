"""
Phase PC-5: Product Compliance Journey Orchestrator.

Combines:
1. Frozen PC-3: Product -> Standard -> QCO -> Mandatory Certification -> Certification Scheme relationships
2. Frozen PC-4: Testing -> Inspection -> Sampling -> Certification Process relationships
3. Frozen F3: BIS Laboratory Finder (via execute_search approved Python interface)

Guarantees:
- 100% Deterministic execution: Zero LLM / Groq calls for regulatory decisions.
- Non-collapsing complete 10-stage journey with full provenance.
- Standard precedence: Explicit Indian Standard designation takes precedence over ambiguous product keywords.
- Capability-first laboratory qualification: F3 capability precedes proximity ranking.
- Subsystem immutability: Zero modification of PC-1/2/3/4 datasets or F3 catalog.
"""

import os
import re
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Set

from ai.compliance.relationship_models import RelationshipProvenance
from ai.compliance.journey_models import (
    ComplianceJourneyRequest,
    ComplianceJourneyResponse,
    JourneyStatus,
    ProductResolutionStatus,
    StandardResolutionStatus,
    LaboratoryStageStatus,
    ProductStage,
    ProductCandidate,
    StandardsStage,
    StandardDetailRecord,
    RegulatoryStage,
    MandatoryStage,
    SchemeStage,
    TestingStage,
    TestingItemRecord,
    InspectionStage,
    InspectionItemRecord,
    SamplingStage,
    SamplingItemRecord,
    LaboratoriesStage,
    LaboratoryItemRecord,
    CertificationProcessStage,
    ProcessStepRecord,
)

logger = logging.getLogger(__name__)

# Default project root resolution
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _clean_str(val: Optional[str]) -> str:
    """Normalize string by stripping and lowercasing."""
    return (val or "").strip().lower()


def _canonical_key(val: str) -> str:
    """Removes non-alphanumeric characters for robust key lookup."""
    return re.sub(r'[^a-zA-Z0-9]', '', val).lower()


class ComplianceJourneyOrchestrator:
    """
    In-memory indexed orchestration engine for the Product Compliance Journey.
    Reads strictly from frozen PC-3, PC-4, and PC-2 datasets.
    """

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or PROJECT_ROOT
        self.data_dir = self.base_dir / "data" / "compliance"
        
        # In-memory indices
        self.tp_by_standard: Dict[str, List[Dict[str, Any]]] = {}
        self.tp_by_product: Dict[str, List[Dict[str, Any]]] = {}
        self.standard_key_map: Dict[str, str] = {}
        self.product_name_map: Dict[str, List[Dict[str, Any]]] = {}
        
        self.testing_reqs_by_standard: Dict[str, List[Dict[str, Any]]] = {}
        self.inspection_reqs_by_standard: Dict[str, List[Dict[str, Any]]] = {}
        self.sampling_reqs_by_standard: Dict[str, List[Dict[str, Any]]] = {}
        self.scheme_reqs_by_standard: Dict[str, List[Dict[str, Any]]] = {}
        self.generic_process_steps: List[ProcessStepRecord] = []
        
        # Manifests and dataset counts
        self.pc3_manifest: Dict[str, Any] = {}
        self.pc4_manifest: Dict[str, Any] = {}
        self.loaded_counts: Dict[str, int] = {}
        
        self._load_datasets()

    def _load_datasets(self):
        """Loads and indexes frozen datasets without modification."""
        tp_path = self.data_dir / "testing_process" / "testing_process_relationships.jsonl"
        ps_path = self.data_dir / "relationships" / "product_standard_relationships.jsonl"
        tr_path = self.data_dir / "testing_process" / "testing_requirement_relationships.jsonl"
        ir_path = self.data_dir / "testing_process" / "inspection_requirement_relationships.jsonl"
        sr_path = self.data_dir / "testing_process" / "sampling_requirement_relationships.jsonl"
        cp_path = self.data_dir / "normalized" / "certification_process.jsonl"
        csr_path = self.data_dir / "relationships" / "certification_scheme_relationships.jsonl"

        # 1. Testing Process Relationships (Composite)
        tp_count = 0
        if tp_path.exists():
            with open(tp_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    rec = json.loads(line)
                    std_norm = rec.get("standard_normalized")
                    prod_name = rec.get("product_name")
                    
                    if std_norm:
                        self.tp_by_standard.setdefault(std_norm, []).append(rec)
                        self.standard_key_map[_canonical_key(std_norm)] = std_norm
                        # Also register without part/sec for base lookup
                        base_std = std_norm.split("(")[0].strip()
                        self.standard_key_map[_canonical_key(base_std)] = std_norm
                        
                    if prod_name:
                        p_clean = _clean_str(prod_name)
                        self.tp_by_product.setdefault(p_clean, []).append(rec)
                    tp_count += 1
        self.loaded_counts["testing_process_relationships"] = tp_count

        # 2. Product-Standard Relationships
        ps_count = 0
        if ps_path.exists():
            with open(ps_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    rec = json.loads(line)
                    prod_name = rec.get("product_name")
                    if prod_name:
                        p_clean = _clean_str(prod_name)
                        self.product_name_map.setdefault(p_clean, []).append(rec)
                    ps_count += 1
        self.loaded_counts["product_standard_relationships"] = ps_count

        # 3. Testing Requirements
        tr_count = 0
        if tr_path.exists():
            with open(tr_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    rec = json.loads(line)
                    std_norm = rec.get("standard_normalized")
                    if std_norm:
                        self.testing_reqs_by_standard.setdefault(std_norm, []).append(rec)
                    tr_count += 1
        self.loaded_counts["testing_requirement_relationships"] = tr_count

        # 4. Inspection Requirements
        ir_count = 0
        if ir_path.exists():
            with open(ir_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    rec = json.loads(line)
                    std_norm = rec.get("standard_normalized")
                    if std_norm:
                        self.inspection_reqs_by_standard.setdefault(std_norm, []).append(rec)
                    ir_count += 1
        self.loaded_counts["inspection_requirement_relationships"] = ir_count

        # 5. Sampling Requirements
        sr_count = 0
        if sr_path.exists():
            with open(sr_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    rec = json.loads(line)
                    std_norm = rec.get("standard_normalized")
                    if std_norm:
                        self.sampling_reqs_by_standard.setdefault(std_norm, []).append(rec)
                    sr_count += 1
        self.loaded_counts["sampling_requirement_relationships"] = sr_count

        # 6. Certification Scheme Relationships
        csr_count = 0
        if csr_path.exists():
            with open(csr_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    rec = json.loads(line)
                    std_norm = rec.get("standard_normalized")
                    if std_norm:
                        self.scheme_reqs_by_standard.setdefault(std_norm, []).append(rec)
                    csr_count += 1
        self.loaded_counts["certification_scheme_relationships"] = csr_count

        # 7. Generic Certification Process Steps
        cp_count = 0
        if cp_path.exists():
            with open(cp_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    rec = json.loads(line)
                    # Extract sample stages if Scheme I
                    if rec.get("scheme_id") == "NORM-SCHEME-0001":
                        stages = rec.get("stages", [])
                        for idx, stg in enumerate(stages, 1):
                            self.generic_process_steps.append(ProcessStepRecord(
                                step_number=idx,
                                title=stg.get("stage_name", f"Step {idx}"),
                                description=stg.get("description", "BIS Scheme I Procedural Guideline"),
                                is_generic=True
                            ))
                        break
                    cp_count += 1
        self.loaded_counts["certification_procedures"] = cp_count

        # Default fallback generic steps if none parsed
        if not self.generic_process_steps:
            self.generic_process_steps = [
                ProcessStepRecord(step_number=1, title="Application Submission", description="Submit Form-V application via Manakonline with manufacturing details and test equipment.", is_generic=True),
                ProcessStepRecord(step_number=2, title="Factory Preliminary Audit", description="BIS technical auditor inspects production plant, quality controls, and in-house testing facility.", is_generic=True),
                ProcessStepRecord(step_number=3, title="Sample Drawing & Independent Testing", description="Auditor draws production samples for testing in BIS-recognized laboratory.", is_generic=True),
                ProcessStepRecord(step_number=4, title="Grant of Licence (GoL)", description="Upon satisfactory test reports and audit scrutiny, BIS grants certification licence and Standard Mark.", is_generic=True),
            ]

        # 7. Manifests
        pc3_m_path = self.data_dir / "relationships" / "metadata" / "relationship_manifest.json"
        if pc3_m_path.exists():
            with open(pc3_m_path, "r", encoding="utf-8") as f:
                self.pc3_manifest = json.load(f)

        pc4_m_path = self.data_dir / "testing_process" / "metadata" / "testing_process_manifest.json"
        if pc4_m_path.exists():
            with open(pc4_m_path, "r", encoding="utf-8") as f:
                self.pc4_manifest = json.load(f)

    def extract_explicit_standard(self, text: Optional[str]) -> Optional[str]:
        """
        Deterministically extracts an explicit Indian Standard designation from text.
        Matches formats like 'IS 4985', 'IS 374', 'IS 16046 (Part 2)', 'IS 16046:Part 2'.
        """
        if not text:
            return None
        clean_text = text.strip()
        
        # Direct key lookup first
        canon = _canonical_key(clean_text)
        if canon in self.standard_key_map:
            return self.standard_key_map[canon]

        # Regex search for Indian Standard pattern
        pattern = r'\b(?:IS|is)\s*(?:[/:]?\s*[A-Za-z]+)*\s*[:\-\s]*(\d{2,6})(?:\s*(?:Part|part|Pt|pt)\s*(\d+)(?:\s*(?:Sec|sec|Section)\s*(\d+))?)?(?:\s*[:\-]\s*(\d{4}))?'
        match = re.search(pattern, clean_text)
        if match:
            num = match.group(1)
            part = match.group(2)
            sec = match.group(3)
            
            # Construct candidate lookup strings
            candidates = []
            if part and sec:
                candidates.append(f"is{num}part{part}sec{sec}")
            if part:
                candidates.append(f"is{num}part{part}")
            candidates.append(f"is{num}")
            
            for c in candidates:
                if c in self.standard_key_map:
                    return self.standard_key_map[c]
            
            # Fallback formatted string if not found in catalog
            if part and sec:
                return f"IS {num} (PART {part}/SEC {sec})"
            elif part:
                return f"IS {num} (PART {part})"
            return f"IS {num}"

        return None

    def strip_conversational_phrases(self, text: Optional[str]) -> str:
        """Strips common conversational introductory clauses."""
        if not text:
            return ""
        s = text.strip()
        prefixes = [
            r"^i\s+manufacture\s+",
            r"^we\s+manufacture\s+",
            r"^i\s+produce\s+",
            r"^we\s+produce\s+",
            r"^i\s+make\s+",
            r"^we\s+make\s+",
            r"^my\s+product\s+is\s+(?:a|an)?\s*",
            r"^our\s+product\s+is\s+(?:a|an)?\s*",
            r"^producer\s+of\s+",
            r"^manufacturer\s+of\s+",
            r"^supplier\s+of\s+",
            r"^maker\s+of\s+",
            r"^importer\s+of\s+",
            r"^exporter\s+of\s+",
            r"^what\s+are\s+the\s+compliance\s+requirements\s+for\s+",
            r"^compliance\s+journey\s+for\s+",
            r"^bis\s+certification\s+for\s+",
        ]
        for p in prefixes:
            s = re.sub(p, "", s, flags=re.IGNORECASE).strip()
        return s

    def resolve_product(self, product_phrase: str) -> Tuple[ProductResolutionStatus, Optional[str], Optional[str], List[ProductCandidate], List[str]]:
        """
        Deterministically matches a product phrase against the compliance universe.
        Returns (status, resolved_name, product_id, candidates, applicable_standards).
        """
        clean_p = _clean_str(product_phrase)
        if not clean_p:
            return (ProductResolutionStatus.PRODUCT_NOT_ESTABLISHED, None, None, [], [])

        # 1. Exact match in testing_process index
        if clean_p in self.tp_by_product:
            records = self.tp_by_product[clean_p]
            first_rec = records[0]
            stds = list(dict.fromkeys(r["standard_normalized"] for r in records if r.get("standard_normalized")))
            candidates = [
                ProductCandidate(
                    product_name=r["product_name"],
                    product_identifier=r.get("product_identifier"),
                    standard_number=r.get("standard_normalized"),
                    confidence=1.0
                ) for r in records
            ]
            return (
                ProductResolutionStatus.PRODUCT_IDENTIFIED,
                first_rec["product_name"],
                first_rec.get("product_identifier"),
                candidates,
                stds
            )

        # 2. Singular / Plural variation
        variants = []
        if clean_p.endswith("s"):
            variants.append(clean_p[:-1])
        else:
            variants.append(clean_p + "s")
            
        for var in variants:
            if var in self.tp_by_product:
                records = self.tp_by_product[var]
                first_rec = records[0]
                stds = list(dict.fromkeys(r["standard_normalized"] for r in records if r.get("standard_normalized")))
                candidates = [
                    ProductCandidate(
                        product_name=r["product_name"],
                        product_identifier=r.get("product_identifier"),
                        standard_number=r.get("standard_normalized"),
                        confidence=0.95
                    ) for r in records
                ]
                return (
                    ProductResolutionStatus.PRODUCT_IDENTIFIED,
                    first_rec["product_name"],
                    first_rec.get("product_identifier"),
                    candidates,
                    stds
                )

        def _stem(w: str) -> str:
            w = w.lower()
            if w.endswith('s') and not w.endswith('ss') and len(w) > 3:
                return w[:-1]
            return w

        # 3. Substring / Token matching
        matching_products: Dict[str, List[Dict[str, Any]]] = {}
        for p_name, records in self.tp_by_product.items():
            if clean_p in p_name or p_name in clean_p:
                matching_products[p_name] = records

        # If no substring match, check word-boundary overlap with stemming and synonyms
        if not matching_products:
            raw_tokens = set(re.findall(r'\w+', clean_p))
            stopwords = {"i", "we", "the", "and", "or", "for", "a", "an", "of", "in", "to", "is"}
            tokens = {_stem(t) for t in raw_tokens if t not in stopwords}

            has_pvc = any(t in tokens for t in ["pvc", "upvc", "polyvinyl"])
            has_pipe = any(t in tokens for t in ["pipe", "piping", "tube"])

            if tokens:
                for p_name, records in self.tp_by_product.items():
                    p_raw = set(re.findall(r'\w+', p_name))
                    p_tokens = {_stem(t) for t in p_raw}

                    if has_pvc and has_pipe:
                        if ("pipe" in p_tokens or "pipes" in p_raw) and any(x in p_name for x in ["pvc", "upvc", "polyvinyl chloride"]):
                            matching_products[p_name] = records
                    elif tokens.issubset(p_tokens) or p_tokens.issubset(tokens):
                        matching_products[p_name] = records

        if not matching_products:
            return (ProductResolutionStatus.PRODUCT_NOT_ESTABLISHED, None, None, [], [])

        # Check standard diversity across matching products
        distinct_standards: Set[str] = set()
        all_candidates: List[ProductCandidate] = []
        for p_name, recs in matching_products.items():
            for r in recs:
                std = r.get("standard_normalized")
                if std:
                    distinct_standards.add(std)
                all_candidates.append(ProductCandidate(
                    product_name=r["product_name"],
                    product_identifier=r.get("product_identifier"),
                    standard_number=std,
                    confidence=0.8
                ))

        # If matching multiple distinct standards without an unambiguous winner, it is ambiguous
        if len(distinct_standards) > 1 or len(matching_products) > 1:
            # Special case: check if all matching products belong to the exact same family (e.g. 'ceiling fan' and 'electric ceiling fan' both -> IS 374)
            if len(distinct_standards) == 1:
                first_rec = list(matching_products.values())[0][0]
                return (
                    ProductResolutionStatus.PRODUCT_IDENTIFIED,
                    first_rec["product_name"],
                    first_rec.get("product_identifier"),
                    all_candidates,
                    list(distinct_standards)
                )
            # Distinct standards -> AMBIGUOUS_PRODUCT
            return (
                ProductResolutionStatus.AMBIGUOUS_PRODUCT,
                None,
                None,
                all_candidates,
                sorted(list(distinct_standards))
            )

        # Exactly 1 product matched
        single_p_name = list(matching_products.keys())[0]
        records = matching_products[single_p_name]
        first_rec = records[0]
        stds = list(dict.fromkeys(r["standard_normalized"] for r in records if r.get("standard_normalized")))
        return (
            ProductResolutionStatus.PRODUCT_IDENTIFIED,
            first_rec["product_name"],
            first_rec.get("product_identifier"),
            all_candidates,
            stds
        )

    def _get_f3_laboratories(self, standard: str, location: Optional[str]) -> Tuple[LaboratoryStageStatus, int, List[LaboratoryItemRecord], str]:
        """
        Queries the authoritative F3 Lab Finder engine via execute_search.
        Capability qualification happens strictly before proximity ranking.
        """
        try:
            from backend.lab_finder_api import execute_search, LabSearchRequest
            from backend.nl_lab_parser import extract_location

            loc_state = None
            loc_city = None
            if location:
                loc_state, loc_city = extract_location(location)

            search_req = LabSearchRequest(
                standard=standard,
                state=loc_state,
                city=loc_city
            )

            lab_resp = execute_search(search_req)

            if lab_resp.status == "NO_MATCH" or lab_resp.total_matching == 0:
                loc_note = f" in {location}" if location else ""
                explanation = f"No BIS-recognized laboratory was found with verified testing capability for standard {standard}{loc_note} in the current catalog."
                return (LaboratoryStageStatus.NO_MATCHING_LABORATORY, 0, [], explanation)

            candidates: List[LaboratoryItemRecord] = []
            for c in lab_resp.candidates:
                candidates.append(LaboratoryItemRecord(
                    public_lab_code=c.public_lab_code,
                    laboratory_name=c.laboratory_name,
                    category=c.category,
                    address=c.address.model_dump(),
                    capability_evidence=c.capability_evidence.model_dump(),
                    geographic_metadata=c.geographic_metadata.model_dump()
                ))

            loc_note = f" (filtered by {location})" if location else ""
            explanation = f"Found {lab_resp.total_matching} BIS-recognized testing laboratories qualified to test according to {standard}{loc_note}."
            return (LaboratoryStageStatus.QUALIFIED_LABS_FOUND, lab_resp.total_matching, candidates, explanation)

        except Exception as e:
            logger.warning(f"F3 laboratory lookup error for {standard}: {e}")
            explanation = f"BIS Laboratory Finder query could not complete: {e}"
            return (LaboratoryStageStatus.LAB_MATCHING_UNAVAILABLE, 0, [], explanation)

    def build_journey(self, req: ComplianceJourneyRequest) -> ComplianceJourneyResponse:
        """
        Executes the end-to-end Product Compliance Journey orchestration.
        Never collapses unknown into false; returns full 10-stage structured response.
        """
        query_echo = {
            "product": req.product,
            "standard": req.standard,
            "location": req.location,
            "query": req.query
        }

        # -------------------------------------------------------------------
        # Step 0: Input Validation
        # -------------------------------------------------------------------
        has_product = bool(req.product and req.product.strip())
        has_standard = bool(req.standard and req.standard.strip())
        has_query = bool(req.query and req.query.strip())
        has_location = bool(req.location and req.location.strip())

        if not (has_product or has_standard or has_query):
            return self._build_empty_or_invalid_journey(
                JourneyStatus.INVALID_REQUEST,
                query_echo,
                "Request does not contain usable product, standard, or query input."
            )

        # -------------------------------------------------------------------
        # Step 1: Standard & Product Resolution
        # Standard takes strict precedence if explicit
        # -------------------------------------------------------------------
        explicit_std = self.extract_explicit_standard(req.standard)
        if not explicit_std and req.query:
            explicit_std = self.extract_explicit_standard(req.query)

        resolved_product_name = None
        product_id = None
        product_status = ProductResolutionStatus.PRODUCT_NOT_ESTABLISHED
        product_candidates: List[ProductCandidate] = []
        applicable_standards: List[str] = []

        # Determine effective product input
        raw_product_text = req.product or req.query or ""
        cleaned_product_text = self.strip_conversational_phrases(raw_product_text)

        if explicit_std:
            # Explicit standard takes PRECEDENCE over ambiguous product text
            primary_std = explicit_std
            applicable_standards = [primary_std]
            
            # Check if this standard exists in our compliance universe
            std_records = self.tp_by_standard.get(primary_std, [])
            if std_records:
                first_rec = std_records[0]
                resolved_product_name = first_rec["product_name"]
                product_id = first_rec.get("product_identifier")
                product_status = ProductResolutionStatus.PRODUCT_IDENTIFIED
            else:
                # Standard specified by user but not in PC-3/PC-4 testing index
                resolved_product_name = cleaned_product_text or "Specified Standard Product"
                product_status = ProductResolutionStatus.PRODUCT_IDENTIFIED

        else:
            # Product-driven resolution
            p_stat, p_name, p_id, p_cands, p_stds = self.resolve_product(cleaned_product_text)
            product_status = p_stat
            resolved_product_name = p_name
            product_id = p_id
            product_candidates = p_cands
            applicable_standards = p_stds

            if product_status == ProductResolutionStatus.AMBIGUOUS_PRODUCT:
                return self._build_ambiguous_journey(
                    query_echo,
                    cleaned_product_text,
                    product_candidates,
                    applicable_standards,
                    req.location
                )

            if product_status == ProductResolutionStatus.PRODUCT_NOT_ESTABLISHED or not applicable_standards:
                return self._build_empty_or_invalid_journey(
                    JourneyStatus.STANDARD_NOT_ESTABLISHED,
                    query_echo,
                    f"Applicable Indian Standard not established from available BIS evidence for '{cleaned_product_text}'."
                )

            primary_std = applicable_standards[0]

        # -------------------------------------------------------------------
        # Step 2: Assemble Stages using PC-3 and PC-4 Evidence
        # -------------------------------------------------------------------
        comp_records = self.tp_by_standard.get(primary_std, [])
        comp_rec = comp_records[0] if comp_records else None

        # Stage 1: Product Stage
        product_stage = ProductStage(
            status=product_status,
            input_product=cleaned_product_text or req.product,
            resolved_product_name=resolved_product_name,
            product_identifier=product_id,
            candidates=product_candidates,
            provenance=RelationshipProvenance(**comp_rec["provenance"]) if (comp_rec and comp_rec.get("provenance")) else None
        )

        # Stage 2: Standards Stage
        standard_details: List[StandardDetailRecord] = []
        for std in applicable_standards:
            s_recs = self.tp_by_standard.get(std, [])
            s_rec = s_recs[0] if s_recs else None
            src_docs = s_rec.get("provenance", {}).get("source_documents", []) if s_rec else []
            ev_hashes = s_rec.get("provenance", {}).get("evidence_hashes", []) if s_rec else []
            detail = StandardDetailRecord(
                standard_number=std,
                standard_title=s_rec.get("standard_original") if s_rec else None,
                relationship_nature="APPLIES_TO_PRODUCT",
                source_document=src_docs[0] if src_docs else None,
                evidence_hash=ev_hashes[0] if ev_hashes else None,
                provenance=RelationshipProvenance(**s_rec["provenance"]) if (s_rec and s_rec.get("provenance")) else None
            )
            standard_details.append(detail)

        standards_stage = StandardsStage(
            status=StandardResolutionStatus.STANDARDS_IDENTIFIED,
            primary_standard=primary_std,
            standards=standard_details,
            provenance=standard_details[0].provenance if standard_details else None
        )

        # Stage 3: Regulatory Stage (from PC-3)
        if comp_rec:
            qco_stat = comp_rec.get("qco_status", "QCO_NOT_ESTABLISHED")
            notif_nums = comp_rec.get("notification_numbers", [])
            eff_date = comp_rec.get("effective_date")
            conf_ids = comp_rec.get("conflict_ids", [])
            qco_ids = comp_rec.get("associated_qco_ids", [])
            
            if qco_stat == "QCO_CONFLICT":
                reg_expl = "Regulatory Quality Control Order (QCO) status has unresolved conflicts between gazette notifications and is disclosed without silent resolution."
            elif qco_stat == "QCO_APPLIES":
                reg_expl = f"Standard {primary_std} is governed by an active, in-force Quality Control Order."
            elif qco_stat == "QCO_AMENDED":
                reg_expl = f"Standard {primary_std} is governed by an amended Quality Control Order."
            elif qco_stat == "QCO_STATUS_UNKNOWN":
                reg_expl = f"Regulatory QCO order exists for {primary_std}, but its operative status is unverified in available records."
            else:
                reg_expl = f"No authoritative Quality Control Order (QCO) is established in the current BIS corpus for standard {primary_std}."
        else:
            qco_stat = "QCO_NOT_ESTABLISHED"
            notif_nums = []
            eff_date = None
            conf_ids = []
            qco_ids = []
            reg_expl = f"No authoritative QCO established for standard {primary_std}."

        regulatory_stage = RegulatoryStage(
            status=qco_stat,
            qco_status=qco_stat,
            notification_numbers=notif_nums,
            effective_date=eff_date,
            associated_qco_ids=qco_ids,
            conflict_ids=conf_ids,
            explanation=reg_expl,
            provenance=RelationshipProvenance(**comp_rec["provenance"]) if (comp_rec and comp_rec.get("provenance")) else None
        )

        # Stage 4: Mandatory Certification Stage (from PC-3)
        if comp_rec:
            mand_stat = comp_rec.get("mandatory_certification_status", "MANDATORY_CERTIFICATION_NOT_ESTABLISHED")
            if mand_stat == "MANDATORY_CERTIFICATION_CONFIRMED":
                is_mand = True
                mand_expl = "Statutory BIS certification is mandatory under an active or in-force Quality Control Order (QCO)."
            elif mand_stat == "MANDATORY_CERTIFICATION_NOT_ESTABLISHED":
                is_mand = False
                mand_expl = "Mandatory certification is not established from available BIS evidence. (Note: absence of QCO does not definitively prove voluntary status)."
            elif mand_stat == "QCO_CONFLICT":
                is_mand = None
                mand_expl = "Mandatory certification status is indeterminate due to conflicting regulatory orders in the authoritative corpus (QCO_CONFLICT)."
            else:
                is_mand = None
                mand_expl = "Mandatory certification requirement is unknown because QCO operative status cannot be verified from available evidence."
        else:
            mand_stat = "MANDATORY_CERTIFICATION_NOT_ESTABLISHED"
            is_mand = False
            mand_expl = "Mandatory certification not established from available evidence."

        mandatory_stage = MandatoryStage(
            status=mand_stat,
            is_mandatory=is_mand,
            explanation=mand_expl,
            provenance=RelationshipProvenance(**comp_rec["provenance"]) if (comp_rec and comp_rec.get("provenance")) else None
        )

        # Stage 5: Certification Scheme Stage (from PC-3)
        raw_csr_items = self.scheme_reqs_by_standard.get(primary_std, [])
        # Find the best specific match
        best_csr = None
        for csr in raw_csr_items:
            if csr.get("product_identifier") and req.product and req.product.lower() in csr.get("product_identifier", "").lower():
                best_csr = csr
                break
        if not best_csr and raw_csr_items:
            best_csr = raw_csr_items[0]

        if best_csr and best_csr.get("scheme_applicability_status") != "CERTIFICATION_SCHEME_UNKNOWN":
            scheme_stage = SchemeStage(
                status=best_csr.get("scheme_applicability_status", "CERTIFICATION_SCHEME_CONFIRMED"),
                applicable_scheme_code=best_csr.get("scheme_id") or best_csr.get("scheme_name"),
                applicability_basis=best_csr.get("applicability_basis", "AUTHORITATIVE_CORPUS"),
                explanation=f"Certification scheme applicability is explicitly established in BIS records as {best_csr.get('scheme_name')}.",
                provenance=RelationshipProvenance(**best_csr["provenance"]) if best_csr.get("provenance") else None
            )
        else:
            scheme_stage = SchemeStage(
                status="CERTIFICATION_SCHEME_UNKNOWN",
                applicable_scheme_code=None,
                applicability_basis="NO_AUTHORITATIVE_APPLICABILITY_RECORD_IN_CORPUS",
                explanation="The current authoritative BIS corpus defines statutory schemes, but does not establish a confirmed product-specific scheme relationship for this product.",
                provenance=RelationshipProvenance(**comp_rec["provenance"]) if (comp_rec and comp_rec.get("provenance")) else None
            )

        # Stage 6: Testing Stage (from PC-4)
        testing_stat = comp_rec.get("testing_status", "TESTING_REQUIREMENTS_UNKNOWN") if comp_rec else "TESTING_REQUIREMENTS_UNKNOWN"
        raw_tr_items = self.testing_reqs_by_standard.get(primary_std, [])
        testing_items: List[TestingItemRecord] = []
        for tr in raw_tr_items:
            testing_items.append(TestingItemRecord(
                test_name=tr.get("test_name", "Required Test"),
                test_method=tr.get("test_method"),
                test_clause=tr.get("test_clause"),
                test_parameter=tr.get("test_parameter"),
                frequency=tr.get("frequency"),
                sampling_reference=tr.get("sampling_reference"),
                source_document=tr.get("source_document"),
                source_url=tr.get("source_url"),
                evidence_hash=tr.get("evidence_hash")
            ))

        if testing_stat == "TESTING_REQUIREMENTS_CONFIRMED":
            test_expl = f"Testing requirements and Scheme of Inspection and Testing (SIT) specifications are confirmed ({len(testing_items)} parameters)."
        elif testing_stat == "TESTING_REQUIREMENTS_PARTIAL":
            test_expl = f"Testing requirements are partially established from official BIS Product Manual guidelines ({len(testing_items)} parameters)."
        else:
            test_expl = "Testing requirements are not established from available BIS evidence (no normalized SIT or Product Manual available)."

        testing_stage = TestingStage(
            status=testing_stat,
            total_tests=len(testing_items),
            testing_requirements=testing_items,
            explanation=test_expl,
            provenance=RelationshipProvenance(**comp_rec["provenance"]) if (comp_rec and comp_rec.get("provenance")) else None
        )

        # Stage 7: Inspection Stage (from PC-4)
        insp_stat = comp_rec.get("inspection_status", "INSPECTION_REQUIREMENTS_UNKNOWN") if comp_rec else "INSPECTION_REQUIREMENTS_UNKNOWN"
        raw_ir_items = self.inspection_reqs_by_standard.get(primary_std, [])
        inspection_items: List[InspectionItemRecord] = []
        for ir in raw_ir_items:
            inspection_items.append(InspectionItemRecord(
                inspection_reference=ir.get("inspection_reference", "Routine Quality Inspection"),
                test_register=ir.get("test_register"),
                frequency=ir.get("frequency"),
                source_document=ir.get("source_document"),
                evidence_hash=ir.get("evidence_hash")
            ))

        if insp_stat == "INSPECTION_REQUIREMENTS_CONFIRMED":
            insp_expl = "Factory inspection and quality control routines are confirmed from BIS Scheme of Inspection and Testing."
        elif insp_stat == "INSPECTION_REQUIREMENTS_PARTIAL":
            insp_expl = "Factory inspection guidelines are partially outlined in the official BIS Product Manual."
        else:
            insp_expl = "Inspection requirements are not established from available BIS evidence."

        inspection_stage = InspectionStage(
            status=insp_stat,
            total_requirements=len(inspection_items),
            inspection_requirements=inspection_items,
            explanation=insp_expl,
            provenance=RelationshipProvenance(**comp_rec["provenance"]) if (comp_rec and comp_rec.get("provenance")) else None
        )

        # Stage 8: Sampling Stage (from PC-4)
        samp_stat = comp_rec.get("sampling_status", "SAMPLING_REQUIREMENTS_UNKNOWN") if comp_rec else "SAMPLING_REQUIREMENTS_UNKNOWN"
        raw_sr_items = self.sampling_reqs_by_standard.get(primary_std, [])
        sampling_items: List[SamplingItemRecord] = []
        for sr in raw_sr_items:
            sampling_items.append(SamplingItemRecord(
                sampling_reference=sr.get("sampling_reference", "Batch Sampling"),
                sample_size=sr.get("sample_size"),
                lot_definition=sr.get("lot_definition"),
                source_document=sr.get("source_document"),
                evidence_hash=sr.get("evidence_hash")
            ))

        if samp_stat == "SAMPLING_REQUIREMENTS_CONFIRMED":
            samp_expl = "Lot definition and control unit sample size requirements are confirmed from SIT specifications."
        elif samp_stat == "SAMPLING_REQUIREMENTS_PARTIAL":
            samp_expl = "General sampling principles are partially established from official BIS Product Manual."
        else:
            samp_expl = "Sampling requirements are not established from available BIS evidence."

        sampling_stage = SamplingStage(
            status=samp_stat,
            total_requirements=len(sampling_items),
            sampling_requirements=sampling_items,
            explanation=samp_expl,
            provenance=RelationshipProvenance(**comp_rec["provenance"]) if (comp_rec and comp_rec.get("provenance")) else None
        )

        # Stage 9: Laboratories Stage (from F3)
        lab_stat, lab_total, lab_candidates, lab_expl = self._get_f3_laboratories(primary_std, req.location)
        
        # Check limited condition
        if testing_stat == "TESTING_REQUIREMENTS_UNKNOWN" and lab_stat == LaboratoryStageStatus.QUALIFIED_LABS_FOUND:
            lab_stat = LaboratoryStageStatus.LAB_MATCHING_LIMITED
            lab_expl = f"Laboratories exist with scope for standard {primary_std}, but capability matching is limited because product testing requirements are unestablished in the authoritative compliance evidence."

        laboratories_stage = LaboratoriesStage(
            status=lab_stat,
            total_matching=lab_total,
            returned_count=len(lab_candidates),
            qualified_laboratories=lab_candidates,
            capability_evaluated_first=True,
            location_filter_applied=req.location,
            explanation=lab_expl,
            provenance=RelationshipProvenance(
                source_layer="F3_LAB_FINDER",
                source_record_ids=[c.public_lab_code for c in lab_candidates[:10]],
                source_documents=["BIS Laboratory Information Management System (LIMS)"],
                source_urls=["https://www.services.bis.gov.in/php/BIS_2.0/bisman/lab/"],
                source_locations=[],
                evidence_hashes=[],
                source_verification_state="SOURCE_VERIFIED",
                conflict_ids=[]
            ) if lab_candidates else None
        )

        # Stage 10: Certification Process Stage (from PC-4)
        proc_stat = comp_rec.get("certification_process_status", "CERTIFICATION_PROCESS_UNKNOWN") if comp_rec else "CERTIFICATION_PROCESS_UNKNOWN"
        proc_steps = self.generic_process_steps if proc_stat == "CERTIFICATION_PROCESS_PARTIAL" else []
        if proc_stat == "CERTIFICATION_PROCESS_PARTIAL":
            proc_expl = "General Scheme I certification steps are available as reference material. Product-specific certification procedures remain unconfirmed."
        else:
            proc_expl = "Certification process requirements are not established from available BIS evidence."

        process_stage = CertificationProcessStage(
            status=proc_stat,
            is_generic_procedure=True,
            procedure_steps=proc_steps,
            explanation=proc_expl,
            provenance=RelationshipProvenance(**comp_rec["provenance"]) if (comp_rec and comp_rec.get("provenance")) else None
        )

        # -------------------------------------------------------------------
        # Cross-cutting: Provenance & Warnings
        # -------------------------------------------------------------------
        all_provenance: List[RelationshipProvenance] = []
        for stg_prov in [
            product_stage.provenance,
            standards_stage.provenance,
            regulatory_stage.provenance,
            mandatory_stage.provenance,
            scheme_stage.provenance,
            testing_stage.provenance,
            inspection_stage.provenance,
            sampling_stage.provenance,
            laboratories_stage.provenance,
            process_stage.provenance
        ]:
            if stg_prov and stg_prov not in all_provenance:
                all_provenance.append(stg_prov)

        warnings: List[str] = [
            "Indian Standard existence does not establish statutory mandatory certification.",
            "Product-specific certification scheme applicability is unestablished in current BIS authoritative evidence (CERTIFICATION_SCHEME_UNKNOWN).",
            "Generic Scheme I procedures are reference material and do not represent confirmed product-specific certification steps."
        ]

        if qco_stat == "QCO_CONFLICT":
            warnings.append("Regulatory QCO status has unresolved conflicts between published notifications (QCO_CONFLICT).")
        elif qco_stat == "QCO_STATUS_UNKNOWN":
            warnings.append("Regulatory QCO status is unverified in authoritative records (QCO_STATUS_UNKNOWN).")

        limitations: List[str] = []
        if testing_stat == "TESTING_REQUIREMENTS_UNKNOWN":
            limitations.append("Authoritative testing specifications (SIT or Product Manual) are absent for this standard.")
        if lab_stat == LaboratoryStageStatus.NO_MATCHING_LABORATORY:
            limitations.append(f"No BIS-recognized laboratory currently possesses verified testing capability for {primary_std}.")

        return ComplianceJourneyResponse(
            journey_version="PC-5.0",
            status=JourneyStatus.JOURNEY_ESTABLISHED,
            query_echo=query_echo,
            product=product_stage,
            applicable_standards=standards_stage,
            regulatory_status=regulatory_stage,
            mandatory_certification=mandatory_stage,
            certification_scheme=scheme_stage,
            testing=testing_stage,
            inspection=inspection_stage,
            sampling=sampling_stage,
            laboratories=laboratories_stage,
            certification_process=process_stage,
            provenance=all_provenance,
            warnings=warnings,
            limitations=limitations
        )

    def _build_ambiguous_journey(
        self,
        query_echo: Dict[str, Any],
        product_query: str,
        candidates: List[ProductCandidate],
        distinct_standards: List[str],
        location: Optional[str]
    ) -> ComplianceJourneyResponse:
        """Constructs an explicit non-collapsing response when product identification is ambiguous."""
        product_stage = ProductStage(
            status=ProductResolutionStatus.AMBIGUOUS_PRODUCT,
            input_product=product_query,
            resolved_product_name=None,
            product_identifier=None,
            candidates=candidates,
            provenance=None
        )

        standards_details = [
            StandardDetailRecord(
                standard_number=std,
                standard_title=None,
                relationship_nature="CANDIDATE_STANDARD",
                source_document=None,
                evidence_hash=None,
                provenance=None
            ) for std in distinct_standards
        ]

        standards_stage = StandardsStage(
            status=StandardResolutionStatus.STANDARD_NOT_ESTABLISHED,
            primary_standard=None,
            standards=standards_details,
            provenance=None
        )

        regulatory_stage = RegulatoryStage(
            status="QCO_NOT_ESTABLISHED",
            qco_status="QCO_NOT_ESTABLISHED",
            notification_numbers=[],
            effective_date=None,
            associated_qco_ids=[],
            conflict_ids=[],
            explanation="Regulatory QCO status cannot be definitively established until product ambiguity is resolved.",
            provenance=None
        )

        mandatory_stage = MandatoryStage(
            status="MANDATORY_CERTIFICATION_NOT_ESTABLISHED",
            is_mandatory=None,
            explanation="Mandatory certification status depends on the specific standard selected from candidate matches.",
            provenance=None
        )

        scheme_stage = SchemeStage(
            status="CERTIFICATION_SCHEME_UNKNOWN",
            applicable_scheme_code=None,
            applicability_basis="NO_AUTHORITATIVE_APPLICABILITY_RECORD_IN_CORPUS",
            explanation="Certification scheme applicability remains unknown across candidate products.",
            provenance=None
        )

        testing_stage = TestingStage(
            status="TESTING_REQUIREMENTS_UNKNOWN",
            total_tests=0,
            testing_requirements=[],
            explanation="Testing requirements depend on candidate standard selection.",
            provenance=None
        )

        inspection_stage = InspectionStage(
            status="INSPECTION_REQUIREMENTS_UNKNOWN",
            total_requirements=0,
            inspection_requirements=[],
            explanation="Inspection requirements depend on candidate standard selection.",
            provenance=None
        )

        sampling_stage = SamplingStage(
            status="SAMPLING_REQUIREMENTS_UNKNOWN",
            total_requirements=0,
            sampling_requirements=[],
            explanation="Sampling requirements depend on candidate standard selection.",
            provenance=None
        )

        laboratories_stage = LaboratoriesStage(
            status=LaboratoryStageStatus.LAB_MATCHING_LIMITED,
            total_matching=0,
            returned_count=0,
            qualified_laboratories=[],
            capability_evaluated_first=True,
            location_filter_applied=location,
            explanation="Laboratory qualification requires selecting a specific candidate standard.",
            provenance=None
        )

        process_stage = CertificationProcessStage(
            status="CERTIFICATION_PROCESS_UNKNOWN",
            is_generic_procedure=True,
            procedure_steps=[],
            explanation="Certification process depends on candidate standard selection.",
            provenance=None
        )

        return ComplianceJourneyResponse(
            journey_version="PC-5.0",
            status=JourneyStatus.STANDARD_NOT_ESTABLISHED,
            query_echo=query_echo,
            product=product_stage,
            applicable_standards=standards_stage,
            regulatory_status=regulatory_stage,
            mandatory_certification=mandatory_stage,
            certification_scheme=scheme_stage,
            testing=testing_stage,
            inspection=inspection_stage,
            sampling=sampling_stage,
            laboratories=laboratories_stage,
            certification_process=process_stage,
            provenance=[],
            warnings=[
                f"Product query '{product_query}' matches {len(candidates)} candidate products across multiple Indian Standards.",
                "Please specify an explicit Indian Standard designation (e.g. IS 4985) or exact product name."
            ],
            limitations=[
                "Applicable Indian Standard could not be established from available BIS evidence.",
                "Candidate ambiguity prevents single-standard compliance resolution."
            ]
        )

    def _build_empty_or_invalid_journey(
        self,
        status: JourneyStatus,
        query_echo: Dict[str, Any],
        message: str
    ) -> ComplianceJourneyResponse:
        """Constructs a non-collapsing full structured journey response for unestablished or invalid queries."""
        p_stat = ProductResolutionStatus.PRODUCT_NOT_ESTABLISHED
        std_stat = StandardResolutionStatus.STANDARD_NOT_ESTABLISHED

        return ComplianceJourneyResponse(
            journey_version="PC-5.0",
            status=status,
            query_echo=query_echo,
            product=ProductStage(status=p_stat, input_product=query_echo.get("product") or query_echo.get("query")),
            applicable_standards=StandardsStage(status=std_stat, standards=[]),
            regulatory_status=RegulatoryStage(status="QCO_NOT_ESTABLISHED", qco_status="QCO_NOT_ESTABLISHED", explanation=message),
            mandatory_certification=MandatoryStage(status="MANDATORY_CERTIFICATION_NOT_ESTABLISHED", is_mandatory=False, explanation=message),
            certification_scheme=SchemeStage(explanation="Certification scheme applicability not established."),
            testing=TestingStage(status="TESTING_REQUIREMENTS_UNKNOWN", explanation="Testing requirements not established."),
            inspection=InspectionStage(status="INSPECTION_REQUIREMENTS_UNKNOWN", explanation="Inspection requirements not established."),
            sampling=SamplingStage(status="SAMPLING_REQUIREMENTS_UNKNOWN", explanation="Sampling requirements not established."),
            laboratories=LaboratoriesStage(status=LaboratoryStageStatus.NO_MATCHING_LABORATORY, explanation=message),
            certification_process=CertificationProcessStage(status="CERTIFICATION_PROCESS_UNKNOWN", is_generic_procedure=True, explanation="Certification process not established."),
            provenance=[],
            warnings=[message],
            limitations=["Applicable Indian Standard could not be established from available BIS evidence."]
        )


# Global singleton instance for high-performance reuse
_orchestrator_instance: Optional[ComplianceJourneyOrchestrator] = None


def get_compliance_orchestrator() -> ComplianceJourneyOrchestrator:
    """Returns the shared ComplianceJourneyOrchestrator singleton."""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = ComplianceJourneyOrchestrator()
    return _orchestrator_instance
