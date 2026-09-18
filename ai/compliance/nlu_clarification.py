"""
Phase PC-7: Interactive Natural Language Clarification & Recommendation Layer.

Architectural Guarantees:
1. Zero Regulatory Decisions in NLU:
   NLU only parses intent, extracts slots, evaluates ambiguity, and provides grounded recommendations.
   All compliance determinations (QCO, mandatory certification, testing requirements, lab qualifications)
   remain 100% governed by the deterministic PC-5 orchestrator.
2. Grounded Candidates:
   Candidates presented during AMBIGUOUS and INCOMPLETE states are strictly derived from
   official BIS compliance records (PC-3/PC-4/F3), never fabricated by LLMs.
3. Three Resolution States:
   - CLEAR: Sufficient information to proceed deterministically to PC-5.
   - AMBIGUOUS: Multiple plausible standards (e.g. 'pvc' -> pipes vs cables vs boots).
   - INCOMPLETE: Generic category missing necessary specifying attributes (e.g. 'pipes').
4. Follow-up Context Preservation:
   Multi-turn interactions safely merge contextual memory from prior turns.
"""

import os
import json
import logging
import re
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple
from pydantic import BaseModel, Field

from ai.compliance.journey_orchestrator import (
    get_compliance_orchestrator,
    ComplianceJourneyOrchestrator,
    ProductResolutionStatus,
    _canonical_key,
    _clean_str
)
from ai.compliance.journey_models import ProductCandidate

try:
    from scripts.phase12_f2_orchestrator import GroqClient
except ImportError:
    GroqClient = None

logger = logging.getLogger("compliance_nlu")


class ClarificationState(str, Enum):
    CLEAR = "CLEAR"
    AMBIGUOUS = "AMBIGUOUS"
    INCOMPLETE = "INCOMPLETE"


class ClarificationCandidate(BaseModel):
    product_name: str
    standard_number: str
    product_identifier: Optional[str] = None
    description: str
    confidence: float = 1.0
    category: Optional[str] = None


class AttributeOption(BaseModel):
    id: str
    label: str
    value: str
    refined_query_term: str


class AttributeGroup(BaseModel):
    group_id: str
    title: str
    description: Optional[str] = None
    is_multi_select: bool = False
    options: List[AttributeOption]


class ClarificationPayload(BaseModel):
    title: str
    explanation: str
    candidates: List[ClarificationCandidate] = Field(default_factory=list)
    attribute_groups: List[AttributeGroup] = Field(default_factory=list)
    suggested_examples: List[str] = Field(default_factory=list)
    disclaimer: str = (
        "Clarification narrows user intent; final compliance status, mandatory certification, "
        "and testing requirements are established deterministically by the BIS compliance engine."
    )


class QuerySlots(BaseModel):
    standard: Optional[str] = None
    product: Optional[str] = None
    application: Optional[str] = None
    material: Optional[str] = None
    location: Optional[str] = None
    raw_query: str = ""


class RefinedRequest(BaseModel):
    product: Optional[str] = None
    standard: Optional[str] = None
    location: Optional[str] = None
    query: Optional[str] = None


class ComplianceClarificationRequest(BaseModel):
    query: Optional[str] = None
    product: Optional[str] = None
    standard: Optional[str] = None
    location: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class ComplianceClarificationResponse(BaseModel):
    state: ClarificationState
    slots: QuerySlots
    refined_request: RefinedRequest
    clarification: Optional[ClarificationPayload] = None
    resolved_standard: Optional[str] = None
    resolved_product: Optional[str] = None
    message: str = ""


class GroqNLUExtractionResult(BaseModel):
    """Structured NLU extraction result from Groq."""
    product: Optional[str] = None
    product_category: Optional[str] = None
    material: Optional[str] = None
    application: Optional[str] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)
    standard: Optional[str] = None
    location: Optional[str] = None
    intent: Optional[str] = None
    resolution_hint: Optional[str] = None


# Known major Indian Cities & States for Proximity Extraction
INDIAN_LOCATIONS = [
    "delhi", "new delhi", "mumbai", "bengaluru", "bangalore", "kolkata", "chennai",
    "hyderabad", "pune", "ahmedabad", "surat", "jaipur", "lucknow", "kanpur",
    "nagpur", "indore", "thane", "bhopal", "visakhapatnam", "patna", "vadodara",
    "ghaziabad", "ludhiana", "agra", "nashik", "faridabad", "meerut", "rajkot",
    "varanasi", "srinagar", "aurangabad", "dhanbad", "amritsar", "navi mumbai",
    "allahabad", "prayagraj", "ranchi", "howrah", "coimbatore", "jabalpur", "gwalior",
    "vijayawada", "jodhpur", "madurai", "raipur", "kota", "guwahati", "chandigarh",
    "solapur", "hubli", "bareilly", "moradabad", "mysore", "gurgaon", "gurugram",
    "aligarh", "jalandhar", "tiruchirappalli", "bhubaneswar", "salem", "warangal",
    "noida", "maharashtra", "karnataka", "tamil nadu", "gujarat", "uttar pradesh",
    "west bengal", "rajasthan", "madhya pradesh", "andhra pradesh", "telangana",
    "bihar", "punjab", "haryana", "odisha", "kerala", "jharkhand", "assam",
    "uttarakhand", "chhattisgarh", "goa", "himachal pradesh"
]


# Grounded Knowledge Bases for Ambiguity Disambiguation
AMBIGUOUS_KNOWLEDGE_BASE: Dict[str, Dict[str, Any]] = {
    "pvc": {
        "title": "Which PVC product are you referring to?",
        "explanation": "PVC (Polyvinyl Chloride) is used across several distinct regulated product categories. To identify the applicable Indian Standard and compliance journey, please select your product or describe how it is used:",
        "candidates": [
            ClarificationCandidate(
                product_name="PVC pipes for potable water supplies",
                standard_number="IS 4985",
                product_identifier="PRD-pvc-water-pipe",
                description="Unplasticized PVC pipes for cold potable water services, water mains, and irrigation.",
                confidence=1.0,
                category="Pipes & Water Supply"
            ),
            ClarificationCandidate(
                product_name="PVC insulated cables and wires",
                standard_number="IS 694",
                product_identifier="PRD-pvc-cables",
                description="PVC insulated electrical cables and flexible cords for voltages up to 1100 V.",
                confidence=1.0,
                category="Electrical Cables"
            ),
            ClarificationCandidate(
                product_name="Polyvinyl chloride boots",
                standard_number="IS 12254",
                product_identifier="PRD-pvc-boots",
                description="Polyvinyl chloride boots for industrial, agricultural, and safety protection.",
                confidence=1.0,
                category="Footwear & Safety"
            ),
            ClarificationCandidate(
                product_name="UPVC pipes for soil and waste discharge",
                standard_number="IS 13592",
                product_identifier="PRD-upvc-discharge",
                description="Unplasticized PVC pipes for soil and waste discharge ventilation systems inside buildings.",
                confidence=0.9,
                category="Drainage & Sewerage"
            ),
            ClarificationCandidate(
                product_name="Rigid PVC conduits for electrical installations",
                standard_number="IS 9537 (PART 3)",
                product_identifier="PRD-pvc-conduit",
                description="Rigid plain conduits of insulating materials for electrical installations.",
                confidence=0.9,
                category="Electrical Conduits"
            ),
        ],
        "suggested_examples": [
            "PVC pipes for potable water supply",
            "PVC insulated cables up to 1100V",
            "PVC industrial boots",
            "Rigid PVC electrical conduits"
        ]
    },
    "cables": {
        "title": "Which type of electrical cable do you manufacture?",
        "explanation": "Electric cables are governed by specific Indian Standards based on insulation type and voltage rating:",
        "candidates": [
            ClarificationCandidate(
                product_name="PVC insulated cables and cords",
                standard_number="IS 694",
                product_identifier="PRD-pvc-cables",
                description="PVC insulated electrical cables and cords for voltages up to and including 1100 V.",
                confidence=1.0,
                category="Low Voltage Cables"
            ),
            ClarificationCandidate(
                product_name="Cross-linked polyethylene (XLPE) insulated cables",
                standard_number="IS 7098 (PART 1)",
                product_identifier="PRD-xlpe-cable",
                description="XLPE insulated cables for working voltages up to and including 1100 V.",
                confidence=1.0,
                category="Power Distribution"
            ),
            ClarificationCandidate(
                product_name="PVC insulated heavy duty electric cables",
                standard_number="IS 1554 (PART 1)",
                product_identifier="PRD-pvc-heavy-duty",
                description="Heavy duty PVC insulated cables for working voltages up to 1100 V.",
                confidence=0.9,
                category="Industrial Power"
            )
        ],
        "suggested_examples": [
            "PVC insulated domestic wiring cables",
            "XLPE power cables up to 1100V",
            "Heavy duty armoured power cables"
        ]
    },
    "battery": {
        "title": "Which battery chemistry and application do you produce?",
        "explanation": "Secondary batteries are categorized by electrochemical system under BIS Quality Control Orders:",
        "candidates": [
            ClarificationCandidate(
                product_name="Lithium-ion cells and batteries for portable applications",
                standard_number="IS 16046 (PART 2)",
                product_identifier="PRD-lithium-battery",
                description="Secondary lithium cells and batteries for use in portable electronic applications.",
                confidence=1.0,
                category="Lithium Systems"
            ),
            ClarificationCandidate(
                product_name="Nickel systems secondary cells and batteries",
                standard_number="IS 16046 (PART 1)",
                product_identifier="PRD-nickel-battery",
                description="Secondary cells and batteries containing alkaline electrolytes (Nickel systems).",
                confidence=1.0,
                category="Nickel Systems"
            )
        ],
        "suggested_examples": [
            "Lithium-ion cells for mobile devices",
            "Lithium battery packs for portable electronics",
            "Nickel-metal hydride rechargeable cells"
        ]
    }
}


# Domain-Adaptive Attribute Questionnaires for INCOMPLETE Queries
INCOMPLETE_QUESTIONNAIRES: Dict[str, Dict[str, Any]] = {
    "pipe": {
        "title": "What type of pipes do you manufacture?",
        "explanation": "Pipe compliance depends heavily on material composition and intended application. Please select the material and use:",
        "attribute_groups": [
            AttributeGroup(
                group_id="material",
                title="Pipe Material",
                is_multi_select=False,
                options=[
                    AttributeOption(id="mat_pvc", label="PVC / UPVC", value="PVC", refined_query_term="PVC pipe"),
                    AttributeOption(id="mat_di", label="Ductile Iron", value="Ductile Iron", refined_query_term="Ductile iron pipe"),
                    AttributeOption(id="mat_steel", label="Galvanized / Carbon Steel", value="Steel", refined_query_term="Steel pipe"),
                    AttributeOption(id="mat_hdpe", label="HDPE (Polyethylene)", value="HDPE", refined_query_term="HDPE pipe"),
                    AttributeOption(id="mat_concrete", label="Concrete", value="Concrete", refined_query_term="Concrete pipe"),
                    AttributeOption(id="mat_other", label="Other Material", value="Other", refined_query_term="pipe"),
                ]
            ),
            AttributeGroup(
                group_id="application",
                title="Intended Application",
                is_multi_select=False,
                options=[
                    AttributeOption(id="app_potable", label="Potable Water Supply", value="Potable Water", refined_query_term="for potable water supplies"),
                    AttributeOption(id="app_drainage", label="Soil, Waste & Drainage", value="Drainage", refined_query_term="for soil and waste discharge"),
                    AttributeOption(id="app_conduit", label="Electrical Conduit", value="Electrical Conduit", refined_query_term="for electrical conduit"),
                    AttributeOption(id="app_gas", label="Gas / Oil Transmission", value="Gas Transmission", refined_query_term="for gas transmission"),
                    AttributeOption(id="app_irrigation", label="Agricultural Irrigation", value="Irrigation", refined_query_term="for agricultural irrigation"),
                    AttributeOption(id="app_other", label="General / Other", value="Other", refined_query_term=""),
                ]
            )
        ],
        "suggested_examples": [
            "PVC pipes for potable water supplies",
            "UPVC pipes for drainage and soil discharge",
            "Ductile iron pipes for water supply",
            "HDPE pipes for water mains"
        ]
    }
}


# ---------------------------------------------------------------------------
# Groq NLU Prompt
# ---------------------------------------------------------------------------

GROQ_COMPLIANCE_NLU_SYSTEM_PROMPT = """You are the Bureau of Indian Standards (BIS) Natural Language Understanding (NLU) Query Interpreter.
Your SOLE task is to interpret the user's natural language compliance inquiry and extract structured entity slots.

CRITICAL ARCHITECTURAL CONSTRAINTS:
1. You are strictly an NLU query interpreter and entity extractor. You are NOT a compliance or regulatory authority.
2. DO NOT determine whether a Quality Control Order (QCO) applies.
3. DO NOT determine whether certification is mandatory or voluntary.
4. DO NOT determine certification schemes (e.g. Scheme I, Scheme IV).
5. DO NOT determine testing, sampling, or factory inspection requirements.
6. DO NOT qualify testing laboratories.
7. DO NOT invent, hallucinate, or fabricate Indian Standard numbers or compliance evidence.
8. If the user mentions an explicit Indian Standard designation (e.g. "IS 4985", "IS 694", "IS 10500"), extract it into "standard". Otherwise set "standard": null.
9. Normalize the product into "product" (e.g. "PVC pipes", "electric cables", "drinking water", "pipes").
10. Extract the base material into "material" (e.g. "PVC", "Steel", "Copper", "HDPE", "Cement") if mentioned, else null.
11. Extract the intended use or application into "application" (e.g. "potable water supply", "electrical wiring", "drainage", "irrigation") if mentioned, else null.
12. Extract any Indian city, state, or location into "location" (e.g. "Delhi", "Mumbai", "Gujarat") if mentioned, else null.
13. Set "resolution_hint":
    - "CLEAR": if the query provides a specific product with clear material/application or an explicit standard.
    - "AMBIGUOUS": if the query is a broad material or product term that could map to several distinct product categories (e.g. "pvc", "cables", "steel").
    - "INCOMPLETE": if the query is an ultra-generic category missing essential specifying attributes (e.g. "pipes", "I manufacture pipes").
14. Your output MUST be a single valid JSON object ONLY, with no markdown code blocks, preamble, or commentary.

JSON Schema:
{
  "product": string or null,
  "product_category": string or null,
  "material": string or null,
  "application": string or null,
  "attributes": {},
  "standard": string or null,
  "location": string or null,
  "intent": string or null,
  "resolution_hint": "CLEAR" | "AMBIGUOUS" | "INCOMPLETE" | null
}
"""


class ComplianceNLUClarificationEngine:
    """
    Interactive Natural Language Clarification and Slot Extraction Engine.
    Uses the production Groq pipeline for natural language understanding and
    grounds candidates deterministically against official BIS relationship datasets.
    """

    def __init__(
        self,
        orchestrator: Optional[ComplianceJourneyOrchestrator] = None,
        groq_client: Optional[Any] = None
    ):
        self.orchestrator = orchestrator or get_compliance_orchestrator()
        self.groq_client = groq_client

    def get_groq_client(self) -> Optional[Any]:
        """Returns configured GroqClient, initializing from environment if necessary."""
        if self.groq_client is not None:
            return self.groq_client
        if GroqClient is not None:
            api_key = os.getenv("GROQ_API_KEY") or os.getenv("BIS_GROQ_API_KEY")
            try:
                self.groq_client = GroqClient(api_key=api_key)
            except Exception as e:
                logger.warning("Could not initialize GroqClient: %s", e)
                self.groq_client = None
        return self.groq_client

    def extract_location(self, text: str) -> Optional[str]:
        """Extracts Indian city or state location from text."""
        if not text:
            return None
        lower = text.lower()
        
        # Check prepositional patterns first: 'in Delhi', 'at Mumbai', 'near Pune'
        prep_match = re.search(r'\b(?:in|at|from|near|located\s+in)\s+([a-zA-Z\s]+?)(?:\.|\?|,|$|\s+for|\s+with)', text, re.IGNORECASE)
        if prep_match:
            cand = prep_match.group(1).strip().lower()
            if cand in INDIAN_LOCATIONS:
                return cand.title()
        
        # Direct token / phrase check
        for loc in sorted(INDIAN_LOCATIONS, key=lambda x: -len(x)):
            pattern = r'\b' + re.escape(loc) + r'\b'
            if re.search(pattern, lower):
                return loc.title()
        return None

    def extract_slots(self, text: Optional[str]) -> QuerySlots:
        """Extracts product, standard, application, material, and location slots."""
        if not text:
            return QuerySlots()

        clean_text = text.strip()
        slots = QuerySlots(raw_query=clean_text)

        # 1. Standard extraction (IS \d+)
        slots.standard = self.orchestrator.extract_explicit_standard(clean_text)

        # 2. Location extraction
        slots.location = self.extract_location(clean_text)

        # 3. Material extraction
        materials = [
            ("upvc", "UPVC"), ("pvc", "PVC"), ("cpvc", "CPVC"),
            ("ductile iron", "Ductile Iron"), ("cast iron", "Cast Iron"),
            ("galvanized steel", "Galvanized Steel"), ("steel", "Steel"),
            ("hdpe", "HDPE"), ("polyethylene", "Polyethylene"),
            ("polyvinyl chloride", "PVC"), ("timber", "Timber"), ("wood", "Wood"),
            ("copper", "Copper"), ("aluminium", "Aluminium"), ("aluminum", "Aluminium"),
            ("lithium", "Lithium"), ("nickel", "Nickel"), ("concrete", "Concrete")
        ]
        lower_q = clean_text.lower()
        for mat_pat, mat_val in materials:
            if re.search(r'\b' + re.escape(mat_pat) + r'\b', lower_q):
                slots.material = mat_val
                break

        # 4. Application extraction
        apps = [
            (r'potable\s+water|drinking\s+water|water\s+suppl(?:y|ies)|\bwater\b', "Potable Water"),
            (r'soil\s+and\s+waste|waste\s+discharge|drainage|sewerage|sewage', "Drainage & Waste"),
            (r'electrical\s+wiring|electrical\s+cables?|domestic\s+wiring|house\s+wiring', "Electrical Wiring"),
            (r'electrical\s+conduit|conduits?\s+for\s+electrical', "Electrical Conduit"),
            (r'power\s+distribution|industrial\s+power', "Power Distribution"),
            (r'footwear|boots?|safety\s+shoes?', "Footwear"),
            (r'irrigation|agriculture', "Irrigation"),
            (r'gas\s+transmission|oil\s+transmission', "Gas/Oil Transmission"),
        ]
        for app_pat, app_val in apps:
            if re.search(app_pat, lower_q):
                slots.application = app_val
                break

        # 5. Product phrase extraction
        stripped = self.orchestrator.strip_conversational_phrases(clean_text)
        # Remove location from stripped if present
        if slots.location:
            stripped = re.sub(r'\b(?:in|at|from|near)\s+' + re.escape(slots.location) + r'\b', '', stripped, flags=re.IGNORECASE).strip()
            stripped = re.sub(r'\b' + re.escape(slots.location) + r'\b', '', stripped, flags=re.IGNORECASE).strip()
        # Remove standard from stripped if present
        if slots.standard:
            stripped = re.sub(r'\b(?:under|to|as\s+per|according\s+to)?\s*' + re.escape(slots.standard) + r'\b', '', stripped, flags=re.IGNORECASE).strip()
            # Also remove generic 'is \d+' fragments
            stripped = re.sub(r'\b(?:under|to|as\s+per|according\s+to)?\s*is\s*\d+(?:\s*\([^)]+\))?', '', stripped, flags=re.IGNORECASE).strip()
        
        # Clean lingering punctuation/prepositions
        stripped = re.sub(r'\s+', ' ', stripped).strip(' .,;:-')
        slots.product = stripped if stripped else None

        return slots

    def combine_follow_up(self, current_text: str, context: Optional[Dict[str, Any]]) -> str:
        """
        Safely merges multi-turn context (e.g. prior 'pvc' + follow-up 'water supply pipes' -> 'PVC pipes for water supply').
        """
        if not context:
            return current_text

        prev_query = context.get("query") or context.get("previous_query") or ""
        prev_product = context.get("product") or ""
        prev_material = context.get("material") or ""

        curr_lower = current_text.lower()
        prev_lower = (prev_query or prev_product).lower()

        # If previous was 'pvc' and current mentions pipes or water
        if ("pvc" in prev_lower or prev_material == "PVC") and "pvc" not in curr_lower:
            return f"PVC {current_text.strip()}"

        # If previous was 'pipe' or 'pipes' and current mentions material (e.g. 'pvc')
        if any(w in prev_lower for w in ["pipe", "pipes"]) and not any(w in curr_lower for w in ["pipe", "pipes"]):
            return f"{current_text.strip()} pipes"

        return current_text.strip()

    def _extract_slots_with_groq(self, text: str) -> Tuple[GroqNLUExtractionResult, bool]:
        """
        Executes Groq chat completion to extract structured slots.
        Returns (result, is_llm_used).
        If Groq is unconfigured, times out, or fails, gracefully falls back to regex slot extraction.
        """
        client = self.get_groq_client()
        if not client or not getattr(client, "is_configured", False):
            logger.info("GroqClient unconfigured; utilizing deterministic regex fallback.")
            return self._extract_slots_with_regex(text), False

        try:
            messages = [
                {"role": "system", "content": GROQ_COMPLIANCE_NLU_SYSTEM_PROMPT},
                {"role": "user", "content": f"User Query: {text}"}
            ]
            response_text = client.chat_completion(messages, max_tokens=600)
            cleaned = response_text.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
                cleaned = re.sub(r'\s*```$', '', cleaned)
            data = json.loads(cleaned)

            res = GroqNLUExtractionResult(
                product=data.get("product"),
                product_category=data.get("product_category"),
                material=data.get("material"),
                application=data.get("application"),
                attributes=data.get("attributes") if isinstance(data.get("attributes"), dict) else {},
                standard=data.get("standard"),
                location=data.get("location"),
                intent=data.get("intent"),
                resolution_hint=data.get("resolution_hint")
            )
            return res, True
        except Exception as e:
            logger.warning("Groq NLU extraction failed (%s); falling back to deterministic regex extraction.", e)
            return self._extract_slots_with_regex(text), False

    def _extract_slots_with_regex(self, text: str) -> GroqNLUExtractionResult:
        """
        Safe deterministic regex slot extractor used as fallback when Groq is unavailable.
        """
        slots = self.extract_slots(text)
        return GroqNLUExtractionResult(
            product=slots.product,
            product_category=None,
            material=slots.material,
            application=slots.application,
            attributes={},
            standard=slots.standard,
            location=slots.location,
            intent="compliance_journey",
            resolution_hint=None
        )

    def _ground_slots(
        self, slots: QuerySlots, raw_text: str
    ) -> Tuple[str, Optional[str], Optional[str], List[ClarificationCandidate]]:
        """
        Deterministically grounds extracted query slots against the authoritative BIS catalog.
        Returns:
            (grounded_status, resolved_standard, resolved_product_name, candidate_list)
            where grounded_status is one of: "CLEAR", "AMBIGUOUS", "INCOMPLETE", "UNESTABLISHED".
        """
        product = (slots.product or "").strip()
        material = (slots.material or "").strip()
        application = (slots.application or "").strip()

        # Step A: Construct ranked search phrases
        phrases: List[str] = []
        if product and application and material and material.lower() not in product.lower():
            phrases.append(f"{material} {product} {application}")
        if product and application:
            phrases.append(f"{product} {application}")
        if product and material and material.lower() not in product.lower():
            phrases.append(f"{material} {product}")
        if product:
            phrases.append(product)
        if material:
            phrases.append(material)

        all_matched_cands: List[ProductCandidate] = []

        for ph in phrases:
            res_status, res_name, res_id, res_cands, res_stds = self.orchestrator.resolve_product(ph)
            if res_cands:
                all_matched_cands = res_cands
                break

        if not all_matched_cands:
            return "UNESTABLISHED", None, None, []

        # Step B: Filter candidates by application if specific application was extracted
        if application:
            app_words = set(re.findall(r'\w+', application.lower())) - {
                "and", "or", "for", "the", "in", "of", "to", "supply", "supplies", "use", "services"
            }
            if app_words:
                filtered = [
                    c for c in all_matched_cands
                    if app_words & set(re.findall(r'\w+', c.product_name.lower()))
                ]
                if filtered:
                    all_matched_cands = filtered

        # Step C: Evaluate standard uniqueness across grounded candidates
        distinct_stds = list(dict.fromkeys(c.standard_number for c in all_matched_cands if c.standard_number))

        if len(distinct_stds) == 1:
            chosen_std = distinct_stds[0]
            chosen_name = all_matched_cands[0].product_name
            return "CLEAR", chosen_std, chosen_name, []

        elif len(distinct_stds) > 1:
            candidates: List[ClarificationCandidate] = []
            seen_stds = set()
            for c in all_matched_cands:
                std_num = c.standard_number or "Indian Standard"
                if std_num not in seen_stds:
                    seen_stds.add(std_num)
                    candidates.append(ClarificationCandidate(
                        product_name=c.product_name,
                        standard_number=std_num,
                        product_identifier=c.product_identifier,
                        description=f"BIS product record under {std_num}",
                        confidence=c.confidence
                    ))
            return "AMBIGUOUS", None, None, candidates

        return "UNESTABLISHED", None, None, []

    def analyze_clarification(self, req: ComplianceClarificationRequest) -> ComplianceClarificationResponse:
        """
        Evaluates user input against 3-state resolution framework:
        CLEAR -> PC-5 Full Journey
        AMBIGUOUS -> Grounded Candidate Recommendations
        INCOMPLETE -> Domain-Adaptive Questionnaire
        """
        # 1. Multi-turn context combination
        raw_text = req.query or req.product or ""
        if req.context and raw_text:
            raw_text = self.combine_follow_up(raw_text, req.context)

        # 2. Fast-Path: Explicit standard supplied or present in text
        explicit_std = self.orchestrator.extract_explicit_standard(raw_text) or req.standard
        if explicit_std:
            loc = req.location or self.extract_location(raw_text)
            prod = req.product or self.orchestrator.strip_conversational_phrases(raw_text)
            if explicit_std:
                prod = re.sub(r'\b(?:under|to|as\s+per|according\s+to)?\s*' + re.escape(explicit_std) + r'\b', '', prod, flags=re.IGNORECASE).strip()
            prod = re.sub(r'\s+', ' ', prod).strip(' .,;:-') or None

            slots = QuerySlots(
                standard=explicit_std,
                product=prod,
                application=None,
                material=None,
                location=loc,
                raw_query=raw_text
            )
            logger.info("Compliance NLU: Fast-path explicit standard %s detected.", explicit_std)
            return ComplianceClarificationResponse(
                state=ClarificationState.CLEAR,
                slots=slots,
                refined_request=RefinedRequest(
                    standard=explicit_std,
                    product=prod,
                    location=loc,
                    query=raw_text
                ),
                resolved_standard=explicit_std,
                resolved_product=prod,
                message=f"Proceeding with explicit Indian Standard {explicit_std}."
            )

        # 3. Groq NLU Extraction (with deterministic regex fallback)
        groq_res, was_groq_used = self._extract_slots_with_groq(raw_text)

        # Normalize extracted slots into QuerySlots
        slots = QuerySlots(
            standard=self.orchestrator.extract_explicit_standard(groq_res.standard) or req.standard or None,
            product=req.product or groq_res.product or None,
            application=groq_res.application or None,
            material=groq_res.material or None,
            location=req.location or groq_res.location or self.extract_location(raw_text),
            raw_query=raw_text
        )

        # 4. Standard validation guard: if Groq extracted a standard, verify it exists in BIS standard catalog
        if slots.standard and slots.standard in self.orchestrator.standard_key_map.values():
            logger.info("Compliance NLU: Standard %s verified against official catalog.", slots.standard)
            return ComplianceClarificationResponse(
                state=ClarificationState.CLEAR,
                slots=slots,
                refined_request=RefinedRequest(
                    standard=slots.standard,
                    product=slots.product,
                    location=slots.location,
                    query=raw_text
                ),
                resolved_standard=slots.standard,
                resolved_product=slots.product,
                message=f"Proceeding with Indian Standard {slots.standard}."
            )

        # 5. Check for INCOMPLETE generic categories
        prod_lower = (slots.product or raw_text).strip().lower()
        is_generic_pipe = prod_lower in ["pipe", "pipes", "piping"]
        is_generic_cable = prod_lower in ["cable", "cables", "wire", "wires"]
        is_generic_battery = prod_lower in ["battery", "batteries", "cell", "cells"]

        is_incomplete = (
            groq_res.resolution_hint == "INCOMPLETE"
            or (is_generic_pipe and not slots.material and not slots.application)
            or (is_generic_cable and not slots.material and not slots.application)
            or (is_generic_battery and not slots.material and not slots.application)
        )

        if is_incomplete:
            cat_key = "pipe" if is_generic_pipe else ("cables" if is_generic_cable else ("battery" if is_generic_battery else None))
            q_info = INCOMPLETE_QUESTIONNAIRES.get(cat_key) if cat_key else None
            
            if q_info:
                payload = ClarificationPayload(
                    title=q_info["title"],
                    explanation=q_info["explanation"],
                    attribute_groups=q_info["attribute_groups"],
                    suggested_examples=q_info["suggested_examples"]
                )
            else:
                payload = ClarificationPayload(
                    title=f"Specification Needed for '{slots.product or raw_text}'",
                    explanation="This product category is broad. Please specify the base material composition and intended application:",
                    suggested_examples=[
                        f"{slots.product or raw_text} for industrial use",
                        f"{slots.product or raw_text} for domestic use"
                    ]
                )
            logger.info("Compliance NLU: Query classified as INCOMPLETE.")
            return ComplianceClarificationResponse(
                state=ClarificationState.INCOMPLETE,
                slots=slots,
                refined_request=RefinedRequest(
                    product=slots.product,
                    location=slots.location,
                    query=raw_text
                ),
                clarification=payload,
                message="Product category is generic. Additional attributes required to determine standard."
            )

        # 6. Deterministic Grounding & Resolution Guard
        grounded_state, res_std, res_prod_name, candidate_records = self._ground_slots(slots, raw_text)
        logger.info(
            "Compliance NLU: Grounding state=%s, std=%s, prod=%s, cands=%d",
            grounded_state, res_std, res_prod_name, len(candidate_records)
        )

        if grounded_state == "CLEAR":
            return ComplianceClarificationResponse(
                state=ClarificationState.CLEAR,
                slots=slots,
                refined_request=RefinedRequest(
                    standard=res_std,
                    product=res_prod_name,
                    location=slots.location,
                    query=raw_text
                ),
                resolved_standard=res_std,
                resolved_product=res_prod_name,
                message=f"Identified applicable standard {res_std}."
            )

        if grounded_state == "AMBIGUOUS":
            # Check if rich presentation metadata exists in AMBIGUOUS_KNOWLEDGE_BASE
            ambig_key = None
            for k in AMBIGUOUS_KNOWLEDGE_BASE:
                if k in prod_lower or (slots.material and k in slots.material.lower()):
                    ambig_key = k
                    break

            if ambig_key:
                info = AMBIGUOUS_KNOWLEDGE_BASE[ambig_key]
                candidates_to_use = info["candidates"]
                title_to_use = info["title"]
                exp_to_use = info["explanation"]
                ex_to_use = info["suggested_examples"]
            else:
                candidates_to_use = candidate_records[:5]
                title_to_use = "Which specific product are you manufacturing?"
                exp_to_use = "Multiple Indian Standards match your description. Please select a candidate to establish compliance:"
                ex_to_use = [c.product_name for c in candidate_records[:3]]

            return ComplianceClarificationResponse(
                state=ClarificationState.AMBIGUOUS,
                slots=slots,
                refined_request=RefinedRequest(
                    product=slots.product,
                    location=slots.location,
                    query=raw_text
                ),
                clarification=ClarificationPayload(
                    title=title_to_use,
                    explanation=exp_to_use,
                    candidates=candidates_to_use,
                    suggested_examples=ex_to_use
                ),
                message="Multiple product matches found. Clarification required."
            )

        # 7. Unestablished / Unknown product (e.g. 'timber doors')
        # Route to CLEAR with standard=None so PC-5 deterministically returns STANDARD_NOT_ESTABLISHED
        return ComplianceClarificationResponse(
            state=ClarificationState.CLEAR,
            slots=slots,
            refined_request=RefinedRequest(
                product=slots.product or raw_text,
                standard=None,
                location=slots.location,
                query=raw_text
            ),
            resolved_standard=None,
            resolved_product=slots.product or raw_text,
            message="Submitting to compliance orchestrator for authoritative verification."
        )


_global_nlu_engine = None

def get_nlu_clarification_engine() -> ComplianceNLUClarificationEngine:
    global _global_nlu_engine
    if _global_nlu_engine is None:
        _global_nlu_engine = ComplianceNLUClarificationEngine()
    return _global_nlu_engine

def set_nlu_clarification_engine(engine: ComplianceNLUClarificationEngine):
    global _global_nlu_engine
    _global_nlu_engine = engine

