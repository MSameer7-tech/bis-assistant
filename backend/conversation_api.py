"""
Conversation Title Generation API for BIS AI Technical Assistant.

Exposes:
  POST /api/v1/conversation/title
  Payload: { "first_message": str }
  Response: { "title": str, "source": "groq" | "fallback" }

Guarantees & Invariants:
1. Lightweight & Single-Turn: Only accepts the first user message; never requires or processes full chat history.
2. Non-blocking & Resilient: Designed for asynchronous detached frontend calls. If Groq is unavailable, rate-limited,
   or unconfigured, it immediately falls back to deterministic rule-based extraction.
3. Strict Output Constraints: Generates 3-7 words plain text title. No quotes, no markdown, no emojis, no trailing punctuation,
   and no conversational prefixes (e.g. 'Title:', 'Summary:').
4. Title Hierarchy Priority:
     Standard + Task (e.g. "IS 4985 Certification Requirements")
     -> Product + Task (e.g. "Ceiling Fan Testing Requirements")
     -> Main Subject + Context (e.g. "IS 4985 Labs in Delhi")
     -> Deterministic Fallback (e.g. "IS 374 Standard Overview")
5. Privacy: Never logs user message contents or generated titles to stdout or persistent logs.
"""

import re
import os
import logging
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = logging.getLogger("backend.conversation_api")

router = APIRouter(tags=["conversations"])


class ConversationTitleRequest(BaseModel):
    first_message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The initial user message in a new conversation session."
    )


class ConversationTitleResponse(BaseModel):
    title: str = Field(..., description="Concise 3-7 word conversation title.")
    source: str = Field(..., description="'groq' or 'fallback'.")


# ---------------------------------------------------------------------------
# Deterministic Fallback Title Extraction
# ---------------------------------------------------------------------------

_STOP_WORDS = {
    "a", "an", "the", "in", "on", "at", "for", "to", "of", "and", "or", "is",
    "are", "am", "do", "does", "did", "can", "could", "would", "should", "what",
    "how", "where", "which", "who", "why", "tell", "me", "about", "please", "i",
    "need", "want", "help", "with", "any", "some", "my", "our", "find", "get",
    "give", "show", "check", "verify", "detail", "details", "information"
}

_COMMON_PRODUCT_WORDS = {
    "pipe", "pipes", "fan", "fans", "cement", "steel", "cylinder", "cylinders",
    "battery", "batteries", "cell", "cells", "helmet", "helmets", "cable", "cables",
    "wire", "wires", "plywood", "glass", "water", "food", "valve", "valves",
    "transformer", "switch", "switches", "solar", "pvc", "hdpe", "upvc"
}


def _deterministic_title_fallback(query: str) -> str:
    """
    Extracts an informative 3 to 7 word title deterministically without LLM calls.
    Hierarchy:
      1. Standard + Task / Scope (e.g. 'IS 4985 Testing Requirements')
      2. Product + Task (e.g. 'PVC Pipes Compliance Guide')
      3. Main Subject (e.g. 'Ceiling Fans BIS Standard')
    """
    if not query:
        return "New Session"

    clean_q = query.strip()

    # 1. Standard pattern match (IS 4985, IS:4985, IS-4985, IS 16046 Part 2, etc.)
    std_match = re.search(r'\bIS[\s:-]?(\d+(?:\s*(?:Part|Pt)[\s.]*\d+)?(?:\s*:\s*\d{4})?)\b', clean_q, re.IGNORECASE)
    lower_q = clean_q.lower()

    # Determine task intent
    task_word = ""
    if any(w in lower_q for w in ["lab", "labs", "laboratory", "laboratories", "test facility"]):
        task_word = "Laboratory Search"
    elif any(w in lower_q for w in ["fee", "fees", "cost", "costs", "pricing", "charge"]):
        task_word = "Fee Structure"
    elif any(w in lower_q for w in ["qco", "order", "statutory", "notif"]):
        task_word = "QCO & Compliance"
    elif any(w in lower_q for w in ["test", "testing", "method", "parameter", "clause"]):
        task_word = "Testing Requirements"
    elif any(w in lower_q for w in ["certif", "license", "licence", "mandatory", "scheme"]):
        task_word = "Certification Requirements"
    elif any(w in lower_q for w in ["what is", "overview", "scope", "specification"]):
        task_word = "Standard Overview"

    if std_match:
        std_num = f"IS {std_match.group(1).strip()}"
        # Standard + Location (e.g. IS 4985 Labs in Delhi)
        loc_match = re.search(r'\b(?:in|near|at)\s+([A-Za-z]+)\b', clean_q, re.IGNORECASE)
        if "lab" in lower_q and loc_match:
            city = loc_match.group(1).title()
            return f"{std_num} Labs in {city}"
        if task_word:
            return f"{std_num} {task_word}"
        return f"{std_num} Compliance Overview"

    # 2. Product + Task matching (e.g. Ceiling Fans Testing Requirements)
    clean_words = re.sub(r'[^\w\s]', ' ', clean_q).split()
    prod_candidates = []
    lower_words = [w.lower() for w in clean_words]
    
    # Check multi-word product phrases first
    if "ceiling" in lower_words and ("fan" in lower_words or "fans" in lower_words):
        prod_candidates = ["Ceiling", "Fans"]
    elif "pvc" in lower_words and ("pipe" in lower_words or "pipes" in lower_words):
        prod_candidates = ["PVC", "Pipes"]
    else:
        for w in clean_words:
            if w.lower() in _COMMON_PRODUCT_WORDS and w.capitalize() not in prod_candidates:
                prod_candidates.append(w.capitalize())
                if len(prod_candidates) >= 2:
                    break

    if prod_candidates:
        prod = " ".join(prod_candidates)
        if task_word:
            return f"{prod} {task_word}"
        return f"{prod} Compliance Guide"

    # 3. Keyword-based concise truncation
    words = [w for w in clean_words if w.lower() not in _STOP_WORDS]
    if words:
        title_words = words[:5]
        return " ".join(w.capitalize() for w in title_words)

    # 4. Clean sentence truncation fallback
    first_few = clean_words[:5]
    res = " ".join(first_few)
    return res[:40].strip()


# ---------------------------------------------------------------------------
# Groq Title Generator
# ---------------------------------------------------------------------------

_GROQ_SYSTEM_PROMPT = (
    "You are an AI assistant specialized in Indian Standards (BIS) technical documentation.\n"
    "Generate a concise, informative 3 to 7 word conversation title for a sidebar list based on the user's first query.\n"
    "Strict Priority Hierarchy:\n"
    "1. Standard + Task (e.g., 'IS 4985 Certification Requirements', 'IS 374 Testing Methods')\n"
    "2. Product + Task (e.g., 'Ceiling Fan Testing Requirements', 'PVC Pipe Compliance')\n"
    "3. Standard/Product + Location (e.g., 'IS 4985 Labs in Delhi')\n"
    "4. Main Subject (e.g., 'Direct Cool Fridge QCO Status')\n\n"
    "Strict Formatting Rules:\n"
    "- Output ONLY the plain title text (no quotes, no markdown, no asterisks, no emojis).\n"
    "- Length MUST be between 3 and 7 words.\n"
    "- Never include prefixes like 'Title:', 'Topic:', or 'Summary:'.\n"
    "- Never add a trailing period or punctuation."
)


def _clean_llm_title(raw_title: str) -> Optional[str]:
    """
    Cleans, validates, and standardizes raw text output from the LLM.
    Ensures 3-7 words, strips quotes, emojis, and boilerplate prefixes.
    """
    if not raw_title or not isinstance(raw_title, str):
        return None

    cleaned = raw_title.strip()
    # Remove surrounding quotes
    cleaned = cleaned.strip('"\'`“”‘’')

    # Remove boilerplate prefixes
    cleaned = re.sub(r'^(?:Title|Topic|Summary|Subject|Name|Conversation Title):\s*', '', cleaned, flags=re.IGNORECASE)

    # Remove trailing periods, colons, or punctuation
    cleaned = re.sub(r'[\.\:\;\!\?]+$', '', cleaned).strip()

    # Remove markdown bold/italic
    cleaned = re.sub(r'[*_#]', '', cleaned).strip()

    # Split into words and validate length
    words = cleaned.split()
    if 2 <= len(words) <= 8:
        # If slightly outside 3-7 (e.g. 2 or 8 words), clamp or accept
        if len(words) > 7:
            cleaned = " ".join(words[:7])
        return cleaned

    return None


@router.post(
    "/conversation/title",
    response_model=ConversationTitleResponse,
    summary="Generate concise conversation title via Groq LLM with deterministic fallback."
)
async def generate_conversation_title(payload: ConversationTitleRequest) -> ConversationTitleResponse:
    """
    Generates a concise 3-7 word conversation title for the sidebar manager.
    Asynchronous, non-blocking, privacy-preserving.
    """
    query = payload.first_message.strip()
    fallback_title = _deterministic_title_fallback(query)

    try:
        from scripts.phase12_f2_orchestrator import GroqClient, DEFAULT_GROQ_MODEL
        client = GroqClient(model=DEFAULT_GROQ_MODEL, timeout=4.5)

        if not client.is_configured:
            return ConversationTitleResponse(title=fallback_title, source="fallback")

        messages = [
            {"role": "system", "content": _GROQ_SYSTEM_PROMPT},
            {"role": "user", "content": f"User query: {query}"}
        ]

        # Use asyncio.to_thread to avoid blocking event loop, max_tokens=250 for reasoning models
        import asyncio
        raw_result = await asyncio.to_thread(
            client.chat_completion,
            messages=messages,
            max_tokens=250
        )
        cleaned = _clean_llm_title(raw_result)

        if cleaned:
            return ConversationTitleResponse(title=cleaned, source="groq")
        else:
            return ConversationTitleResponse(title=fallback_title, source="fallback")

    except Exception:
        # Fail gracefully and silently without logging query or breaking frontend
        return ConversationTitleResponse(title=fallback_title, source="fallback")
