"""Translate a natural-language stock screening prompt into a safe JSON filter spec.

Example:
    "small cap banks growing 20%+ with no debt"
      -> {"filters": [
            {"field": "market_cap_cr", "op": "<", "value": 20000},
            {"field": "sector", "op": "=", "value": "Financial Services"},
            {"field": "growth", "op": ">=", "value": 70},
            {"field": "debt_equity_bucket", "op": "=", "value": "low"}
          ],
          "sort": "composite",
          "limit": 25}

Never executes SQL from the LLM — only a bounded JSON schema the UI applies.
"""
from __future__ import annotations

import json

from app.llm import get_llm
from app.llm.base import CompletionRequest


ALLOWED_FIELDS = {
    "composite", "growth", "momentum", "valuation", "profitability",
    "sentiment", "insider", "quality",
    "pe", "pb", "roce",
    "market_cap_cr", "current_price",
    "pct_change_1y", "pct_change_3m", "pct_change_1m",
    "sector",
}
ALLOWED_OPS = {">", ">=", "<", "<=", "=", "!="}
ALLOWED_SORTS = {
    "composite", "growth", "momentum", "pe", "pct_change_1y",
    "pct_change_3m", "market_cap_cr",
}


SYSTEM = (
    "You translate a retail investor's natural-language stock screen into a strict JSON filter spec. "
    "ALLOWED fields: composite, growth, momentum, valuation, profitability, sentiment, insider, quality, "
    "pe, pb, roce, market_cap_cr, current_price, pct_change_1y, pct_change_3m, pct_change_1m, sector. "
    "ALLOWED ops: >, >=, <, <=, =, !=. "
    "Rules of thumb: 'small cap' => market_cap_cr < 20000, 'mid cap' => market_cap_cr between 20000 and 100000, "
    "'large cap' => market_cap_cr >= 100000. 'cheap' => pe < 20. 'growing' => growth >= 60. "
    "'high quality' => quality >= 70 OR roce >= 20. 'momentum' => momentum >= 70. "
    "Sectors use Yahoo Finance names: 'Technology', 'Financial Services', 'Healthcare', 'Energy', "
    "'Consumer Cyclical', 'Consumer Defensive', 'Industrials', 'Basic Materials', 'Utilities', "
    "'Communication Services', 'Real Estate'. "
    "Output ONLY the JSON object matching: "
    "{\"filters\": [{\"field\":\"...\",\"op\":\"...\",\"value\":...}], \"sort\":\"composite\", \"limit\": 25}. "
    "No prose. No markdown."
)


def nl_to_spec(query: str) -> dict:
    try:
        raw = get_llm().reasoning(CompletionRequest(
            system=SYSTEM,
            user=query,
            max_tokens=600,
            temperature=0.1,
        ))
    except Exception as e:
        return {"filters": [], "sort": "composite", "limit": 25, "error": str(e)}

    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`").lstrip("json").strip()
    try:
        spec = json.loads(text)
    except Exception as e:
        return {"filters": [], "sort": "composite", "limit": 25, "error": f"parse: {e}", "raw": text[:400]}

    safe_filters = []
    for f in spec.get("filters", []):
        field = str(f.get("field", "")).strip()
        op = str(f.get("op", "")).strip()
        value = f.get("value")
        if field not in ALLOWED_FIELDS or op not in ALLOWED_OPS or value is None:
            continue
        safe_filters.append({"field": field, "op": op, "value": value})

    sort = spec.get("sort", "composite")
    if sort not in ALLOWED_SORTS:
        sort = "composite"
    try:
        limit = int(spec.get("limit", 25))
    except Exception:
        limit = 25
    limit = max(1, min(100, limit))

    return {"filters": safe_filters, "sort": sort, "limit": limit}
