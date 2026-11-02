"""Rate a user-uploaded CSV row — short-term, long-term, pattern, combined.

Takes:
  - The row from the user's CSV (Volume, PE, growth, 1y / 3y return, etc.)
  - Our own enrichment (price_1y, delivery, MACD, momentum, chart pattern)

Returns one CSVRating per row. All scores are 0-100.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CSVRating:
    short_term: int
    long_term: int
    chart: int
    combined: int
    label: str                 # "Strong Buy" | "Buy" | "Hold" | "Watch" | "Avoid"
    bullets: list[str] = field(default_factory=list)


def _pts(cond: bool, w: int) -> int:
    return w if cond else 0


def _safe_float(v) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    # treat 0 as missing for a few fields where 0 is sentinel
    return f


def rate_row(row: dict, enrichment: dict) -> CSVRating:
    """row: a pandas row from the CSV (dict-like).  enrichment: our augmentation."""

    # ── Short-term (recent momentum + accumulation) ─────────────────
    r1d = _safe_float(row.get("Return over 1day")) or 0
    r1w = _safe_float(row.get("Return over 1week")) or 0
    r1m = _safe_float(row.get("Return over 1month")) or 0
    vol_times_1w = _safe_float(row.get("Volume Times Compared to 1 Week")) or 0

    short_pts = 0
    bullets: list[str] = []

    # Volume surge from CSV's own ratio first; fallback to our live-quote surge if present.
    surge = vol_times_1w or enrichment.get("volume_surge") or 0
    if surge >= 2.5:
        short_pts += 20
        bullets.append(f"Volume at {surge:.1f}× last week — strong accumulation.")
    elif surge >= 1.5:
        short_pts += 12
    elif surge >= 1.0:
        short_pts += 5

    if r1w >= 5:
        short_pts += 10
        bullets.append(f"Up {r1w:.1f}% last week.")
    elif r1w >= 2:
        short_pts += 6
    elif r1w <= -5:
        short_pts -= 5

    if r1m >= 10:
        short_pts += 10
    elif r1m >= 3:
        short_pts += 6
    elif r1m <= -10:
        short_pts -= 4

    delivery_slope = enrichment.get("delivery_slope")
    delivery_pct = enrichment.get("delivery_pct")
    if delivery_slope is not None and delivery_slope >= 1.0:
        short_pts += 15
        bullets.append(
            f"Delivery % rising +{delivery_slope:.1f}pt/day — buyers taking delivery."
        )
    elif delivery_pct is not None and delivery_pct >= 50:
        short_pts += 7

    macd_fast_trend = enrichment.get("macd_fast_trend")
    if macd_fast_trend == "bullish":
        short_pts += 15
        bullets.append("Fast MACD (7,21,9) is bullish.")
    elif macd_fast_trend == "bearish":
        short_pts -= 10

    if r1d >= 3:
        short_pts += 5

    short_pts = max(0, min(100, short_pts + 25))

    # ── Long-term (fundamentals + patient value) ────────────────────
    pe = _safe_float(row.get("Price to Earnings Times")) or _safe_float(row.get("Price to Earning"))
    pe_h3 = _safe_float(row.get("Historical PE 3Years"))
    pe_h5 = _safe_float(row.get("Historical PE 5Years"))
    sales_growth = _safe_float(row.get("Sales growth")) or 0
    net_profit = _safe_float(row.get("Net profit")) or 0
    np_prev = _safe_float(row.get("Net Profit preceding year")) or 0
    roe = _safe_float(row.get("Return on equity")) or 0
    roe_avg = _safe_float(row.get("Average return on equity 3Years")) or 0
    r1y = _safe_float(row.get("Return over 1year")) or 0
    r3y = _safe_float(row.get("Return over 3years")) or 0

    long_pts = 0

    if roe >= 20:
        long_pts += 15
        bullets.append(f"ROE of {roe:.1f}% — high capital efficiency.")
    elif roe >= 15:
        long_pts += 10
    elif roe < 8:
        long_pts -= 5

    if roe_avg >= 15:
        long_pts += 8

    if sales_growth >= 20:
        long_pts += 12
        bullets.append(f"Sales growing {sales_growth:.1f}% — real top-line expansion.")
    elif sales_growth >= 10:
        long_pts += 7

    if np_prev and net_profit:
        growth = (net_profit - np_prev) / abs(np_prev) * 100
        if growth >= 25:
            long_pts += 10
            bullets.append(f"Net profit up {growth:.0f}% vs preceding year.")
        elif growth >= 10:
            long_pts += 5

    # PE vs its own history — cheap by its own standards?
    if pe and pe_h5 and pe < pe_h5 * 0.8:
        long_pts += 12
        bullets.append(f"PE {pe:.1f} vs 5-yr avg {pe_h5:.1f} — trading cheap by its own history.")
    elif pe and pe_h3 and pe < pe_h3 * 0.9:
        long_pts += 6

    if r3y >= 30:
        long_pts += 7
    if r1y < 0 and r3y >= 50:
        long_pts += 5
        bullets.append("Weak last year but strong 3-year track record — potential pullback entry.")

    long_pts = max(0, min(100, long_pts + 20))

    # ── Chart score (from our pattern detector) ─────────────────────
    chart_pts = int(enrichment.get("chart_score") or 0)
    pattern_tags: list[str] = enrichment.get("pattern_tags") or []
    if "breakout" in pattern_tags:
        bullets.append("Chart: breakout — price within 2% of 60-day high on firm volume.")
    if "golden_cross" in pattern_tags:
        bullets.append("Chart: golden cross — 50-EMA just crossed above 200-EMA.")
    if "oversold_rebound" in pattern_tags:
        bullets.append("Chart: oversold rebound near 52-week low with MACD turning up.")
    if "ma_bullish" in pattern_tags:
        bullets.append("Chart: moving averages stacked bullishly (5 > 20 > 50 > 200).")

    # ── Combined and verdict ────────────────────────────────────────
    combined = int(short_pts * 0.35 + long_pts * 0.35 + chart_pts * 0.30)
    if combined >= 75:
        label = "Strong Buy"
    elif combined >= 60:
        label = "Buy"
    elif combined >= 45:
        label = "Hold"
    elif combined >= 30:
        label = "Watch"
    else:
        label = "Avoid"

    # Keep the bullets list short — top 4 wins.
    return CSVRating(short_pts, long_pts, chart_pts, combined, label, bullets[:5])
