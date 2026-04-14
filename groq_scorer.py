# =============================================================================
# groq_scorer.py — ExpatScore.de Lead Scoring Engine
# Version: 1.2 | Model updated: llama-3.3-70b-versatile → llama-3.1-8b-instant
# Purpose: Scores incoming leads 0–100 using Groq LLM inference
#          High score = high-intent expat in Germany needing financial help
# Fallback: If Groq API fails, returns keyword-count-based heuristic score
# =============================================================================

import os
import json
import logging
from groq import Groq

log = logging.getLogger("GroqScorer")

# Initialise client once at module load — reused across all scoring calls
_client = None

def _get_client():
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key:
            log.warning("⚠  [Groq] GROQ_API_KEY not set — fallback scoring active")
            return None
        _client = Groq(api_key=api_key)
        log.info("✅ [Groq] Client initialised")
    return _client

# =============================================================================
# SCORING PROMPT — Tuned for ExpatScore.de ICP
# ICP: Non-German expats who are confused, rejected, or desperate about:
#      Schufa, bank accounts, apartments, loans, credit history
# =============================================================================

SYSTEM_PROMPT = """You are a lead-scoring engine for ExpatScore.de, a website that helps
expats in Germany understand and build their credit score (Schufa).

Your job: read a piece of text (Reddit post or YouTube comment) and score it from 0 to 100
based on how likely the author is to benefit from ExpatScore.de right now.

Scoring rubric:
90-100: Person is actively rejected (bank, apartment, loan) OR desperately asking for help
        with Schufa/credit. Immediate high-intent lead.
70-89:  Person is confused about German financial system, asking questions about Schufa,
        banking, or credit history as a newcomer. Warm lead.
40-69:  Person mentions expat life in Germany with some financial context but not urgent pain.
        Low-medium signal.
0-39:   General expat content, tourism, language learning, no financial pain. Ignore.

Rules:
- Return ONLY a JSON object: {"score": <integer 0-100>, "reason": "<10 words max>"}
- No preamble, no explanation outside JSON, no markdown.
- If text is not in English or German, score it 0."""

# =============================================================================
# PUBLIC INTERFACE
# =============================================================================

def score_lead(content: str, matched_keywords: list, source: str = "") -> int:
    """
    Scores a lead using Groq LLM.

    Args:
        content:          The post body or comment text (truncated to 800 chars)
        matched_keywords: Keywords already matched locally (used for fallback)
        source:           "reddit" or "youtube"

    Returns:
        Integer 0-100. Higher = more likely to convert on ExpatScore.de.
    """
    client = _get_client()

    if client is None:
        return _fallback_score(matched_keywords)

    text_preview = content[:800].strip()

    user_message = (
        f"Source: {source}\n"
        f"Keywords matched: {', '.join(matched_keywords[:5])}\n\n"
        f"Text to score:\n{text_preview}"
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_message},
            ],
            max_tokens=60,
            temperature=0.1,
            response_format={"type": "json_object"},  # Forces valid JSON — no markdown wrapping
        )

        raw    = response.choices[0].message.content.strip()
        parsed = json.loads(raw)
        score  = int(parsed.get("score", 50))
        reason = parsed.get("reason", "")
        score  = max(0, min(100, score))

        log.info(f"  🧠 [Groq] Score: {score}/100 | Reason: {reason}")
        return score

    except Exception as e:
        log.warning(f"  ⚠  [Groq] Scoring failed ({e}) — using fallback")
        return _fallback_score(matched_keywords)


def _fallback_score(matched_keywords: list) -> int:
    """
    Keyword-count heuristic when Groq is unavailable.
    Caps at 80 — Groq real scores can reach 100.
    """
    base  = min(len(matched_keywords) * 10, 60)
    bonus = 0
    desperation_signals = ["rejected", "denied", "blocked", "keine", "ohne", "can't", "problem"]
    for kw in matched_keywords:
        if any(signal in kw.lower() for signal in desperation_signals):
            bonus += 8
    score = min(base + bonus, 80)
    log.info(f"  📊 [Groq/Fallback] Score: {score}/100 | Keywords: {len(matched_keywords)}")
    return score