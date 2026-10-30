"""Generate a 3-pros / 3-cons summary for a company from its score + ratios.

Uses the configured LLM's `fast` tier so it scales to 100s of companies
without hitting API costs (free entirely under Ollama).
"""
from __future__ import annotations

import json

from app.llm import get_llm
from app.llm.base import CompletionRequest


SYSTEM = (
    "You are a stock analyst writing bullet-point pros and cons for a retail investor. "
    "Return ONLY valid JSON matching: {\"pros\": [\"...\", \"...\", \"...\"], \"cons\": [\"...\", \"...\", \"...\"]}. "
    "Each bullet is one short sentence (max 20 words), concrete, and references a specific number from the data. "
    "No disclaimers, no 'consult an advisor', no markdown, no extra text — just the JSON."
)


def generate_pros_cons(name: str, ticker: str, scores: dict, data: dict) -> dict:
    user = f"""Company: {name} ({ticker})
Sector: {data.get('sector')}
Market cap: ₹{(data.get('market_cap') or 0) / 1e7:,.0f} Cr
Current price: ₹{data.get('current_price')}
1Y return: {data.get('pct_change_1y')}%
P/E: {data.get('pe')}
P/B: {data.get('pb')}
ROCE: {(data.get('roce') or 0) * 100:.1f}%
Score factors (0-100): {scores}

Write 3 pros + 3 cons as JSON only."""
    try:
        raw = get_llm().fast(CompletionRequest(
            system=SYSTEM,
            user=user,
            max_tokens=500,
            temperature=0.2,
        ))
        text = raw.strip()
        # Some models wrap in ```json fences; strip them.
        if text.startswith("```"):
            text = text.strip("`").lstrip("json").strip()
        parsed = json.loads(text)
        pros = [str(p)[:200] for p in (parsed.get("pros") or [])][:3]
        cons = [str(c)[:200] for c in (parsed.get("cons") or [])][:3]
        return {"pros": pros, "cons": cons}
    except Exception as e:
        return {"pros": [], "cons": [], "error": str(e)}
