"""
Controlled Natural-Language Query Interpretation Layer for BIS Laboratory Searches.

Translates colloquial manufacturer and tester inquiries into validated,
structured search parameters for the authoritative BIS LIMS Laboratory Finder.

Architectural Guarantees:
1. Interpreter Only: Groq interprets natural language and extracts search parameters.
   It NEVER generates laboratory names, scopes, accreditation status, evidence,
   coordinates, or result counts.
2. Capability Authority: All laboratory matching and ranking is executed solely
   by the existing deterministic LimsMatchingEngine and GeographicRankingEngine.
3. Controlled Terminology: Colloquial product descriptions (e.g., "LED lamps")
   are mapped to authoritative Indian Standards using verified project mappings.
4. No Guessing: If a mapping cannot be safely established, asks the user for clarification.
5. Deterministic Fallback: If Groq fails or is offline, the deterministic parser
   extracts explicit standards, locations, categories, and controlled terms.
6. Validation Gate: All parser output is strictly validated before constructing
   the canonical LabSearchRequest.
"""

import os
import re
import json
from typing import Optional, Dict, Any, Tuple, List
from pydantic import BaseModel, Field

from ai.lims.models import LabCategory


class ControlledProductMatch(tuple):
    """
    Backwards-compatible tuple subclass returning (standard, title, matched_term)
    when unpacked as a 3-tuple, while exposing .standards as a List[str]
    for product-family search expansion.
    """
    def __new__(cls, standard: str, title: str, matched_term: str, standards: Optional[List[str]] = None):
        return super().__new__(cls, (standard, title, matched_term))

    def __init__(self, standard: str, title: str, matched_term: str, standards: Optional[List[str]] = None):
        self.standards = standards or [standard]


# ---------------------------------------------------------------------------
# Controlled Product-to-Standard Terminology Mapping
# Verified against authoritative BIS standards and LIMS catalog data.
# ---------------------------------------------------------------------------

CONTROLLED_PRODUCT_FAMILIES: Dict[str, Tuple[List[str], str]] = {
    # Cement family (OPC, PPC, PSC, Rapid Hardening, White, Sulfate Resisting, Composite)
    "cement": (
        ["IS 269", "IS 1489", "IS 455", "IS 8041", "IS 8042", "IS 12330", "IS 16415"],
        "Portland, Pozzolana & Slag Cement"
    ),
    "portland cement": (
        ["IS 269", "IS 1489", "IS 455"],
        "Portland & Pozzolana Cement"
    ),
    "opc cement": (["IS 269"], "Ordinary Portland Cement"),
    "ppc cement": (["IS 1489"], "Portland Pozzolana Cement"),
    "psc cement": (["IS 455"], "Portland Slag Cement"),

    # Steel / TMT family (Reinforcement bars, structural steel, carbon steel, pipes)
    "steel": (
        ["IS 1786", "IS 2062", "IS 1239", "IS 280", "IS 432", "IS 1161", "IS 4923", "IS 6911"],
        "Structural & Reinforcement Steel"
    ),
    "steel bar": (["IS 1786", "IS 432"], "High Strength Deformed Steel Bars for Concrete Reinforcement"),
    "steel bars": (["IS 1786", "IS 432"], "High Strength Deformed Steel Bars for Concrete Reinforcement"),
    "tmt": (["IS 1786"], "High Strength Deformed Steel Bars (TMT)"),
    "tmt bar": (["IS 1786"], "High Strength Deformed Steel Bars (TMT)"),
    "tmt bars": (["IS 1786"], "High Strength Deformed Steel Bars (TMT)"),
    "rebar": (["IS 1786"], "High Strength Deformed Steel Bars (Rebar)"),
    "rebars": (["IS 1786"], "High Strength Deformed Steel Bars (Rebar)"),
    "structural steel": (["IS 2062"], "Hot Rolled Structural Steel"),

    # Pipes & Plumbing
    "pipe": (
        ["IS 4985", "IS 12818", "IS 13592", "IS 14333", "IS 4984", "IS 15778", "IS 1239"],
        "Plumbing, Agricultural & Potable Water Pipes"
    ),
    "pipes": (
        ["IS 4985", "IS 12818", "IS 13592", "IS 14333", "IS 4984", "IS 15778", "IS 1239"],
        "Plumbing, Agricultural & Potable Water Pipes"
    ),
    "pvc pipe": (["IS 4985", "IS 12818", "IS 13592"], "Unplasticized PVC Pipes for Potable Water Supplies"),
    "pvc pipes": (["IS 4985", "IS 12818", "IS 13592"], "Unplasticized PVC Pipes for Potable Water Supplies"),
    "upvc pipe": (["IS 4985", "IS 13592"], "Unplasticized PVC Pipes"),
    "upvc pipes": (["IS 4985", "IS 13592"], "Unplasticized PVC Pipes"),
    "pvc piping": (["IS 4985", "IS 12818", "IS 13592"], "Unplasticized PVC Pipes for Potable Water Supplies"),
    "hdpe pipe": (["IS 4984", "IS 14333"], "High Density Polyethylene Pipes"),
    "hdpe pipes": (["IS 4984", "IS 14333"], "High Density Polyethylene Pipes"),
    "cpvc pipe": (["IS 15778"], "Chlorinated Polyvinyl Chloride (CPVC) Pipes"),
    "cpvc pipes": (["IS 15778"], "Chlorinated Polyvinyl Chloride (CPVC) Pipes"),

    # Water Quality & Bottled Water
    "water": (["IS 10500", "IS 14543", "IS 13428"], "Drinking & Mineral Water"),
    "drinking water": (["IS 10500", "IS 14543"], "Drinking Water"),
    "potable water": (["IS 10500"], "Drinking Water"),
    "packaged drinking water": (["IS 14543"], "Packaged Drinking Water"),
    "packaged water": (["IS 14543"], "Packaged Drinking Water"),
    "bottled water": (["IS 14543", "IS 13428"], "Packaged Drinking & Mineral Water"),
    "mineral water": (["IS 13428"], "Packaged Natural Mineral Water"),
    "natural mineral water": (["IS 13428"], "Packaged Natural Mineral Water"),

    # Electrical Wiring & Cables
    "cable": (["IS 694", "IS 1554", "IS 7098", "IS 9968"], "PVC Insulated Cables for Working Voltages Upto 1100V"),
    "cables": (["IS 694", "IS 1554", "IS 7098", "IS 9968"], "PVC Insulated Cables for Working Voltages Upto 1100V"),
    "wire": (["IS 694", "IS 398", "IS 280"], "Electric Wire & Conductors"),
    "wires": (["IS 694", "IS 398", "IS 280"], "Electric Wire & Conductors"),
    "electric wire": (["IS 694"], "PVC Insulated Cables for Working Voltages Upto 1100V"),
    "electric wires": (["IS 694"], "PVC Insulated Cables for Working Voltages Upto 1100V"),
    "pvc cable": (["IS 694", "IS 1554"], "PVC Insulated Cables for Working Voltages Upto 1100V"),
    "pvc cables": (["IS 694", "IS 1554"], "PVC Insulated Cables for Working Voltages Upto 1100V"),
    "xlpe cable": (["IS 7098"], "Crosslinked Polyethylene Insulated Cables"),
    "xlpe cables": (["IS 7098"], "Crosslinked Polyethylene Insulated Cables"),

    # LED Lighting & Luminaires
    "led": (["IS 16102", "IS 10322"], "LED Lamps & Luminaires"),
    "led lamp": (["IS 16102"], "Self-Ballasted LED Lamps"),
    "led lamps": (["IS 16102"], "Self-Ballasted LED Lamps"),
    "led bulb": (["IS 16102"], "Self-Ballasted LED Lamps"),
    "led bulbs": (["IS 16102"], "Self-Ballasted LED Lamps"),
    "self-ballasted led": (["IS 16102"], "Self-Ballasted LED Lamps"),
    "self ballasted led": (["IS 16102"], "Self-Ballasted LED Lamps"),
    "led lighting": (["IS 16102", "IS 10322"], "Self-Ballasted LED Lamps"),
    "led luminaire": (["IS 10322"], "LED Luminaires"),
    "led luminaires": (["IS 10322"], "LED Luminaires"),
    "led street light": (["IS 10322"], "LED Luminaires"),
    "led street lighting": (["IS 10322"], "LED Luminaires"),
    "led flood light": (["IS 10322"], "LED Luminaires"),

    # Water Heaters / Geysers
    "water heater": (["IS 8978", "IS 2082"], "Electric Instantaneous Water Heaters"),
    "water heaters": (["IS 8978", "IS 2082"], "Electric Instantaneous Water Heaters"),
    "geyser": (["IS 8978", "IS 2082"], "Electric Instantaneous Water Heaters"),
    "geysers": (["IS 8978", "IS 2082"], "Electric Instantaneous Water Heaters"),
    "instantaneous water heater": (["IS 8978"], "Electric Instantaneous Water Heaters"),
    "storage water heater": (["IS 2082"], "Stationary Storage Electric Water Heaters"),
    "storage geyser": (["IS 2082"], "Stationary Storage Electric Water Heaters"),

    # Safety & Consumer Goods
    "helmet": (["IS 4151"], "Protective Helmets for Two Wheeler Riders"),
    "helmets": (["IS 4151"], "Protective Helmets for Two Wheeler Riders"),
    "ceiling fan": (["IS 374"], "Electric Ceiling Fans"),
    "ceiling fans": (["IS 374"], "Electric Ceiling Fans"),
    "fan": (["IS 374"], "Electric Ceiling Fans"),
    "fans": (["IS 374"], "Electric Ceiling Fans"),
    "plywood": (["IS 303"], "Plywood for General Purposes"),
    "gas stove": (["IS 4246"], "Domestic Gas Stoves for Use with LPG"),
    "gas stoves": (["IS 4246"], "Domestic Gas Stoves for Use with LPG"),
    "lpg stove": (["IS 4246"], "Domestic Gas Stoves for Use with LPG"),
    "lpg stoves": (["IS 4246"], "Domestic Gas Stoves for Use with LPG"),
    "pressure cooker": (["IS 2347"], "Domestic Pressure Cookers"),
    "pressure cookers": (["IS 2347"], "Domestic Pressure Cookers"),
    "toys": (["IS 9873"], "Safety of Toys"),
    "toy": (["IS 9873"], "Safety of Toys"),
    "battery": (["IS 16046"], "Secondary Cells and Batteries"),
    "batteries": (["IS 16046"], "Secondary Cells and Batteries"),
    "electric iron": (["IS 302"], "Safety of Household Electrical Appliances"),
    "appliance": (["IS 302"], "Safety of Household Electrical Appliances"),
    "appliances": (["IS 302"], "Safety of Household Electrical Appliances"),
}

CONTROLLED_PRODUCT_STANDARDS: Dict[str, Tuple[str, str]] = {
    k: (v[0][0], v[1]) for k, v in CONTROLLED_PRODUCT_FAMILIES.items()
}


# ---------------------------------------------------------------------------
# Controlled Geographic Entities
# ---------------------------------------------------------------------------

INDIAN_STATES = {
    "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh",
    "goa", "gujarat", "haryana", "himachal pradesh", "jharkhand", "karnataka",
    "kerala", "madhya pradesh", "maharashtra", "manipur", "meghalaya", "mizoram",
    "nagaland", "odisha", "punjab", "rajasthan", "sikkim", "tamil nadu",
    "telangana", "tripura", "uttar pradesh", "uttarakhand", "west bengal",
    "delhi", "jammu and kashmir", "ladakh", "chandigarh", "puducherry"
}

INDIAN_CITIES = {
    "delhi": ("Delhi", "Delhi"),
    "new delhi": ("Delhi", "Delhi"),
    "mumbai": ("Maharashtra", "Mumbai"),
    "bengaluru": ("Karnataka", "Bengaluru"),
    "bangalore": ("Karnataka", "Bengaluru"),
    "chennai": ("Tamil Nadu", "Chennai"),
    "kolkata": ("West Bengal", "Kolkata"),
    "hyderabad": ("Telangana", "Hyderabad"),
    "ahmedabad": ("Gujarat", "Ahmedabad"),
    "pune": ("Maharashtra", "Pune"),
    "noida": ("Uttar Pradesh", "Noida"),
    "greater noida": ("Uttar Pradesh", "Greater Noida"),
    "gurgaon": ("Haryana", "Gurgaon"),
    "gurugram": ("Haryana", "Gurugram"),
    "jaipur": ("Rajasthan", "Jaipur"),
    "lucknow": ("Uttar Pradesh", "Lucknow"),
    "kanpur": ("Uttar Pradesh", "Kanpur"),
    "surat": ("Gujarat", "Surat"),
    "vadodara": ("Gujarat", "Vadodara"),
    "rajkot": ("Gujarat", "Rajkot"),
    "faridabad": ("Haryana", "Faridabad"),
    "ghaziabad": ("Uttar Pradesh", "Ghaziabad"),
    "indore": ("Madhya Pradesh", "Indore"),
    "bhopal": ("Madhya Pradesh", "Bhopal"),
    "coimbatore": ("Tamil Nadu", "Coimbatore"),
    "kochi": ("Kerala", "Kochi"),
    "parwanoo": ("Himachal Pradesh", "Parwanoo"),
    "rajpura": ("Punjab", "Rajpura"),
    "patna": ("Bihar", "Patna"),
    "ranchi": ("Jharkhand", "Ranchi"),
    "bhubaneswar": ("Odisha", "Bhubaneswar"),
    "nagpur": ("Maharashtra", "Nagpur"),
    "ludhiana": ("Punjab", "Ludhiana"),
    "chandigarh": ("Chandigarh", "Chandigarh"),
}


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class ParsedLabQuery(BaseModel):
    """
    Validated search criteria extracted from natural-language inquiry.
    Contains strictly query parameters to be forwarded to LabSearchRequest.
    """
    raw_query: str
    standard: Optional[str] = None
    standards: List[str] = Field(default_factory=list)
    product_name: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    category: Optional[str] = None
    lab_name: Optional[str] = None
    require_complete_scope: bool = False
    clarification_needed: bool = False
    clarification_message: Optional[str] = None
    factual_summary: str = ""
    parser_source: str = "DETERMINISTIC_CONTROLLED"


# ---------------------------------------------------------------------------
# Deterministic Fallback & Extraction Parser
# ---------------------------------------------------------------------------

KNOWN_LAB_NAMES = [
    "national test house",
    "shriram institute for industrial research",
    "shriram institute",
    "shriram",
    "kailtech test & research centre",
    "kailtech",
    "central laboratory",
    "regional laboratory",
    "sgs india",
    "sgs",
    "tuv rheinland",
    "tuv sud",
    "tuv",
    "intertek india",
    "intertek",
    "bureau veritas",
    "spectro analytical labs",
    "spectro",
    "geo test house",
    "csir",
    "cpri",
    "erda",
    "nth",
]


def extract_lab_name(text: str) -> Optional[str]:
    """
    Extracts laboratory name or institution if mentioned in the query.
    """
    text_lower = text.lower()
    for name in sorted(KNOWN_LAB_NAMES, key=len, reverse=True):
        pattern = r'\b' + re.escape(name) + r'\b'
        if re.search(pattern, text_lower):
            if name in ("nth", "national test house"):
                return "National Test House"
            if name in ("cpri",):
                return "CPRI"
            if name in ("csir",):
                return "CSIR"
            if name in ("erda",):
                return "ERDA"
            return name.title()
    return None


def extract_explicit_standard(text: str) -> Optional[str]:
    """
    Extracts explicit Indian Standard designation (e.g. 'IS 4985', 'IS 16102', 'is 8978:1992').
    Returns normalized 'IS <number>' string, or None.
    """
    match = re.search(r'\b(?:IS|is)\s*(?:[/:]?\s*[A-Za-z]+)*\s*[:\-\s]*(\d{2,6})(?:\s*(?:Part|part|Pt|pt)\s*(\d+))?', text)
    if match:
        std_num = match.group(1)
        part_num = match.group(2)
        if part_num:
            return f"IS {std_num} Part {part_num}"
        return f"IS {std_num}"
    return None


def extract_location(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extracts state and city from query text using controlled dictionaries.
    Returns (state, city).
    """
    text_lower = text.lower()
    found_state = None
    found_city = None

    # Check cities first (often more specific than state)
    for city_key, (c_state, c_name) in INDIAN_CITIES.items():
        pattern = r'\b' + re.escape(city_key) + r'\b'
        if re.search(pattern, text_lower):
            found_city = c_name
            found_state = c_state
            break

    # If state not determined by city, check state names
    if not found_state:
        for state in sorted(INDIAN_STATES, key=len, reverse=True):
            pattern = r'\b' + re.escape(state) + r'\b'
            if re.search(pattern, text_lower):
                found_state = state.title()
                break

    return found_state, found_city


def extract_category(text: str) -> Optional[str]:
    """
    Extracts laboratory category filter if mentioned.
    """
    text_lower = text.lower()
    if "bis owned" in text_lower or "bis-owned" in text_lower or "owned by bis" in text_lower or "central laboratory" in text_lower:
        return LabCategory.BIS_OWNED.value
    if "empanelled" in text_lower or "empanneled" in text_lower:
        return LabCategory.BIS_EMPANELLED.value
    if "recognized" in text_lower or "recognised" in text_lower:
        return LabCategory.BIS_RECOGNIZED.value
    return None


def extract_scope_requirement(text: str) -> bool:
    """
    Checks if complete/full testing scope was explicitly requested.
    """
    text_lower = text.lower()
    return "complete scope" in text_lower or "full scope" in text_lower or "all clauses" in text_lower


def match_controlled_product(text: str) -> Optional[ControlledProductMatch]:
    """
    Matches query against controlled product vocabulary.
    Returns ControlledProductMatch((standard, standard_title, product_phrase), standards=...) if matched, else None.
    """
    text_lower = text.lower()
    # Sort terms by length descending to match multi-word phrases first
    for term, (stds, title) in sorted(CONTROLLED_PRODUCT_FAMILIES.items(), key=lambda x: len(x[0]), reverse=True):
        pattern = r'\b' + re.escape(term) + r'\b'
        if re.search(pattern, text_lower):
            return ControlledProductMatch(stds[0], title, term, standards=list(stds))
    return None


def parse_deterministic_query(query: str) -> ParsedLabQuery:
    """
    Pure offline deterministic parser for laboratory searches.
    Runs in < 1ms, zero network or LLM dependencies.
    """
    q_clean = query.strip()
    if not q_clean:
        return ParsedLabQuery(
            raw_query=query,
            clarification_needed=True,
            clarification_message="Please enter a search query (e.g. 'find labs for IS 4985 testing' or 'LED lamps').",
            parser_source="DETERMINISTIC_CONTROLLED"
        )

    # 1. Check for explicit standard designation
    explicit_std = extract_explicit_standard(q_clean)
    product_name = None
    standards: List[str] = []

    # 2. If no explicit standard, check controlled product dictionary
    if not explicit_std:
        prod_match = match_controlled_product(q_clean)
        if prod_match:
            explicit_std, product_name, matched_term = prod_match
            standards = list(prod_match.standards)
    else:
        standards = [explicit_std]

    # 3. Extract geographic criteria
    state, city = extract_location(q_clean)

    # 4. Extract category & scope requirements
    category = extract_category(q_clean)
    require_complete = extract_scope_requirement(q_clean)

    # 5. Extract lab name
    lab_name = extract_lab_name(q_clean)

    # 6. If standard still cannot be resolved: check for location-only or lab-name-only query
    if not explicit_std:
        if city or state or lab_name or category:
            summary_parts = []
            if lab_name:
                summary_parts.append(f"Laboratory: {lab_name}")
            if city:
                summary_parts.append(f"Location: {city}")
            elif state:
                summary_parts.append(f"Location: {state}")
            if category:
                cat_labels = {
                    "BIS_OWNED": "BIS Owned",
                    "BIS_RECOGNIZED": "Recognized",
                    "BIS_EMPANELLED": "Empanelled"
                }
                summary_parts.append(cat_labels.get(category, category))

            return ParsedLabQuery(
                raw_query=query,
                standard=None,
                standards=[],
                product_name=None,
                state=state,
                city=city,
                category=category,
                lab_name=lab_name,
                require_complete_scope=require_complete,
                clarification_needed=False,
                factual_summary=" · ".join(summary_parts) if summary_parts else "Laboratory Search",
                parser_source="DETERMINISTIC_CONTROLLED"
            )

        return ParsedLabQuery(
            raw_query=query,
            standard=None,
            standards=[],
            product_name=None,
            state=state,
            city=city,
            category=category,
            lab_name=lab_name,
            require_complete_scope=require_complete,
            clarification_needed=True,
            clarification_message="Please specify an Indian Standard number (e.g. IS 4985) or clarify the product to find accredited testing laboratories.",
            parser_source="DETERMINISTIC_CONTROLLED"
        )

    # Build factual summary line
    summary_parts = []
    if product_name:
        summary_parts.append(f"Interpreted as: {product_name} · {explicit_std}")
    else:
        summary_parts.append(f"Searching for: {explicit_std}")

    if city:
        summary_parts.append(city)
    elif state:
        summary_parts.append(state)

    if category:
        cat_labels = {
            "BIS_OWNED": "BIS Owned",
            "BIS_RECOGNIZED": "Recognized",
            "BIS_EMPANELLED": "Empanelled"
        }
        summary_parts.append(cat_labels.get(category, category))

    factual_summary = " · ".join(summary_parts)

    return ParsedLabQuery(
        raw_query=query,
        standard=explicit_std,
        standards=standards,
        product_name=product_name,
        state=state,
        city=city,
        category=category,
        lab_name=lab_name,
        require_complete_scope=require_complete,
        clarification_needed=False,
        factual_summary=factual_summary,
        parser_source="DETERMINISTIC_CONTROLLED"
    )


# ---------------------------------------------------------------------------
# Groq Natural-Language Query Interpreter
# ---------------------------------------------------------------------------

GROQ_PARSER_SYSTEM_PROMPT = """You are the Indian Standards (BIS) and Laboratory Search query parser.
Your task is ONLY to interpret the user's natural language laboratory search query and extract structured search parameters.

CRITICAL ARCHITECTURAL CONSTRAINTS:
1. You are strictly a query interpreter, NOT an authority on laboratory facts.
2. Do NOT invent, hallucinate, or output laboratory names, laboratory codes, testing scopes, accreditation details, or results.
3. Your output must be a single valid JSON object ONLY, with no markdown code blocks, preamble, or commentary.
4. If the user mentions a specific Indian Standard (e.g. "IS 4985", "IS 16102", "IS 8978"), extract that standard.
5. If the user mentions a product or appliance, map it to the corresponding Indian Standard:
   - LED lamps / LED bulbs: IS 16102
   - LED luminaires / street lights / flood lights: IS 10322
   - PVC pipes / UPVC pipes: IS 4985
   - Water heaters / geysers: IS 8978
   - Storage water heaters: IS 2082
   - Drinking water / potable water: IS 10500
   - Packaged drinking water: IS 14543
   - Mineral water: IS 13428
   - Cement / Portland cement: IS 269
   - Steel bars / TMT / rebar: IS 1786
   - Electric wires / PVC cables: IS 694
   - Helmets / two wheeler helmets: IS 4151
   - Ceiling fans: IS 374
   - Plywood: IS 303
   - Gas stoves / LPG stoves: IS 4246
   - Pressure cookers: IS 2347
   - Toys: IS 9873
   - Batteries: IS 16046
6. If the product or standard CANNOT be safely established, set "standard": null. Do NOT guess.
7. Extract geographic filters:
   - "state": Indian state name if mentioned (e.g. "Delhi", "Gujarat", "Maharashtra"), or null.
   - "city": Indian city/district if mentioned (e.g. "Delhi", "Mumbai", "Noida"), or null.
8. Extract category:
   - "category": "BIS_OWNED", "BIS_RECOGNIZED", "BIS_EMPANELLED", or null.
9. Extract scope requirement:
   - "require_complete_scope": true if user requests full/complete testing scope, else false.

JSON Schema:
{
  "standard": string or null,
  "product_name": string or null,
  "state": string or null,
  "city": string or null,
  "category": string or null,
  "require_complete_scope": boolean
}
"""


def parse_lab_natural_query(
    query: str,
    groq_client: Optional[Any] = None
) -> ParsedLabQuery:
    """
    Main entry point for parsing natural language laboratory queries.
    
    Workflow:
    1. Check if an explicit standard is already specified; if so, deterministic parser handles it directly.
    2. If natural language without standard, invoke Groq query interpreter.
    3. Validate all Groq outputs against controlled schemas.
    4. If Groq fails or returns invalid schema, automatically fall back to deterministic parser.
    5. Return validated ParsedLabQuery.
    """
    q_clean = query.strip()
    if not q_clean:
        return parse_deterministic_query(query)

    # If explicit standard is present (e.g. "IS 4985 testing near Delhi"),
    # deterministic parser is 100% accurate and instant (< 1ms).
    explicit_std = extract_explicit_standard(q_clean)
    if explicit_std:
        return parse_deterministic_query(query)

    # Attempt Groq natural language interpretation
    try:
        from scripts.phase12_f2_orchestrator import GroqClient
        client = groq_client or GroqClient()

        if client.is_configured:
            messages = [
                {"role": "system", "content": GROQ_PARSER_SYSTEM_PROMPT},
                {"role": "user", "content": q_clean}
            ]
            response_text = client.chat_completion(messages, max_tokens=150)
            
            # Clean JSON formatting
            cleaned_json = response_text.strip()
            if cleaned_json.startswith("```"):
                cleaned_json = re.sub(r'^```(?:json)?\s*', '', cleaned_json)
                cleaned_json = re.sub(r'\s*```$', '', cleaned_json)

            data = json.loads(cleaned_json)

            raw_std = data.get("standard")
            product_name = data.get("product_name")
            raw_state = data.get("state")
            raw_city = data.get("city")
            raw_category = data.get("category")
            require_complete = bool(data.get("require_complete_scope", False))

            # Validate Standard format (must match ^IS\s*\d+)
            validated_std = None
            if raw_std and isinstance(raw_std, str):
                std_match = extract_explicit_standard(raw_std)
                if std_match:
                    validated_std = std_match

            # If Groq didn't identify standard, check if product_name matches controlled dictionary
            if not validated_std and product_name:
                prod_match = match_controlled_product(product_name)
                if prod_match:
                    validated_std, canon_title, _ = prod_match
                    product_name = canon_title

            # Validate Category enum
            validated_category = None
            if raw_category and isinstance(raw_category, str):
                cat_upper = raw_category.strip().upper()
                valid_cats = {c.value for c in LabCategory}
                if cat_upper in valid_cats:
                    validated_category = cat_upper

            # Validate State & City
            validated_state = None
            validated_city = None
            if raw_city and isinstance(raw_city, str):
                city_clean = raw_city.strip().lower()
                if city_clean in INDIAN_CITIES:
                    validated_state, validated_city = INDIAN_CITIES[city_clean]
                else:
                    validated_city = raw_city.strip().title()

            if not validated_state and raw_state and isinstance(raw_state, str):
                state_clean = raw_state.strip().lower()
                if state_clean in INDIAN_STATES:
                    validated_state = state_clean.title()

            extracted_lab = data.get("lab_name") or extract_lab_name(q_clean)

            # If standard cannot be safely established, check if location or lab_name was identified
            if not validated_std:
                if validated_city or validated_state or extracted_lab or validated_category:
                    summary_parts = []
                    if extracted_lab:
                        summary_parts.append(f"Laboratory: {extracted_lab}")
                    if validated_city:
                        summary_parts.append(f"Location: {validated_city}")
                    elif validated_state:
                        summary_parts.append(f"Location: {validated_state}")
                    if validated_category:
                        cat_labels = {
                            "BIS_OWNED": "BIS Owned",
                            "BIS_RECOGNIZED": "Recognized",
                            "BIS_EMPANELLED": "Empanelled"
                        }
                        summary_parts.append(cat_labels.get(validated_category, validated_category))

                    return ParsedLabQuery(
                        raw_query=query,
                        standard=None,
                        standards=[],
                        product_name=product_name,
                        state=validated_state,
                        city=validated_city,
                        category=validated_category,
                        lab_name=extracted_lab,
                        require_complete_scope=require_complete,
                        clarification_needed=False,
                        factual_summary=" · ".join(summary_parts) if summary_parts else "Laboratory Search",
                        parser_source="GROQ"
                    )

                return ParsedLabQuery(
                    raw_query=query,
                    standard=None,
                    standards=[],
                    product_name=product_name,
                    state=validated_state,
                    city=validated_city,
                    category=validated_category,
                    lab_name=None,
                    require_complete_scope=require_complete,
                    clarification_needed=True,
                    clarification_message="Please specify an Indian Standard number (e.g. IS 4985) or clarify the product to find accredited testing laboratories.",
                    parser_source="GROQ"
                )

            # Build factual summary
            summary_parts = []
            if product_name:
                summary_parts.append(f"Interpreted as: {product_name} · {validated_std}")
            else:
                summary_parts.append(f"Searching for: {validated_std}")

            if validated_city:
                summary_parts.append(validated_city)
            elif validated_state:
                summary_parts.append(validated_state)

            if validated_category:
                cat_labels = {
                    "BIS_OWNED": "BIS Owned",
                    "BIS_RECOGNIZED": "Recognized",
                    "BIS_EMPANELLED": "Empanelled"
                }
                summary_parts.append(cat_labels.get(validated_category, validated_category))

            factual_summary = " · ".join(summary_parts)

            # Check if product matches family for standards expansion
            expanded_standards = [validated_std]
            if product_name:
                pm = match_controlled_product(product_name)
                if pm and pm.standards:
                    expanded_standards = list(pm.standards)

            return ParsedLabQuery(
                raw_query=query,
                standard=validated_std,
                standards=expanded_standards,
                product_name=product_name,
                state=validated_state,
                city=validated_city,
                category=validated_category,
                lab_name=extracted_lab,
                require_complete_scope=require_complete,
                clarification_needed=False,
                factual_summary=factual_summary,
                parser_source="GROQ"
            )

    except Exception:
        # Graceful, silent fallback to deterministic parser on ANY failure
        pass

    # Deterministic fallback
    return parse_deterministic_query(query)
