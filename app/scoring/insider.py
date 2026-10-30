"""Insider / high-conviction trade score (0-100) from NSE bulk & block deals."""
from __future__ import annotations


def score_insider(trades: list[dict]) -> float:
    """Score a scrip's recent bulk+block deals.

    Heuristic:
      - no deals → 50 (neutral)
      - net buyer count > seller count → above 50
      - net seller count > buyer count → below 50
      - block deals weigh 1.5× bulk (negotiated conviction)
    """
    if not trades:
        return 50.0

    buy = sell = 0.0
    for t in trades:
        side = str(t.get("buy_sell") or t.get("client_name_buy_sell") or "").strip().upper()
        weight = 1.5 if t.get("kind") == "block" else 1.0
        if side.startswith("B"):
            buy += weight
        elif side.startswith("S"):
            sell += weight

    total = buy + sell
    if total == 0:
        return 50.0

    net = (buy - sell) / total
    return max(0.0, min(100.0, 50.0 + net * 50.0))
