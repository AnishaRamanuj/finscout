"""Rate a user-uploaded CSV row — short-term, long-term, chart, combined.

Four axes, each 0-100:
  short_term  — recent returns + volume surge + delivery slope + MACD trend
                + ADX trend-strength bonus when direction is already up
  long_term   — ROE (level + 3Y avg + YoY change) + sales / net-profit /
                operating-profit growth + PE discount vs its own 3Y/5Y/7Y
                historical PEs + 3-year return track record
  chart       — pulled from pattern engine (which now covers ADX, OBV,
                Bollinger %B, ROC, Supertrend alongside MA/MACD patterns)
  combined    — 0.35 short + 0.35 long + 0.30 chart

The CSV columns are kept verbatim — our added fields are prefixed with "_".
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CSVRating:
    short_term: int
    long_term: int
    chart: int
    combined: int
    label: str
    bullets: list[str] = field(default_factory=list)
    pe_discount_3y: float | None = None
    pe_discount_5y: float | None = None
    pe_discount_7y: float | None = None
    op_profit_qoq: float | None = None
    net_profit_yoy: float | None = None
    roe_change: float | None = None


def _f(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def rate_row(row: dict, enrichment: dict) -> CSVRating:

    # ── Short-term (recent momentum + accumulation) ─────────────────
    r1d = _f(row.get("Return over 1day")) or 0
    r1w = _f(row.get("Return over 1week")) or 0
    r1m = _f(row.get("Return over 1month")) or 0
    vol_times_1w = _f(row.get("Volume Times Compared to 1 Week")) or 0

    short_pts = 0
    bullets: list[str] = []

    surge = vol_times_1w or enrichment.get("volume_surge") or 0
    if surge >= 2.5:
        short_pts += 18
        bullets.append(f"Volume at {surge:.1f}× last week — strong accumulation.")
    elif surge >= 1.5:
        short_pts += 11
    elif surge >= 1.0:
        short_pts += 5

    if r1w >= 5:
        short_pts += 9; bullets.append(f"Up {r1w:.1f}% last week.")
    elif r1w >= 2:
        short_pts += 5
    elif r1w <= -5:
        short_pts -= 5

    if r1m >= 10:
        short_pts += 9
    elif r1m >= 3:
        short_pts += 5
    elif r1m <= -10:
        short_pts -= 4

    delivery_slope = enrichment.get("delivery_slope")
    delivery_pct = enrichment.get("delivery_pct")
    if delivery_slope is not None and delivery_slope >= 1.0:
        short_pts += 14
        bullets.append(
            f"Delivery % rising +{delivery_slope:.1f}pt/day — buyers taking delivery."
        )
    elif delivery_pct is not None and delivery_pct >= 50:
        short_pts += 6

    macd_fast_trend = enrichment.get("macd_fast_trend")
    if macd_fast_trend == "bullish":
        short_pts += 14
        bullets.append("Fast MACD (7,21,9) is bullish.")
    elif macd_fast_trend == "bearish":
        short_pts -= 9

    # ADX gives short-term bonus only when MACD/MA already say direction is UP
    adx = enrichment.get("adx14")
    supertrend = enrichment.get("supertrend_dir")
    if adx is not None and adx >= 25 and (
        macd_fast_trend == "bullish" or supertrend == "bullish"
    ):
        short_pts += 8
        bullets.append(f"ADX {adx:.0f} — the trend has real strength behind it.")

    obv_slope = enrichment.get("obv_slope_pct")
    if obv_slope is not None and obv_slope >= 2:
        short_pts += 7
        bullets.append(f"OBV rising ({obv_slope:+.1f}%/bar) — smart money is accumulating.")
    elif obv_slope is not None and obv_slope <= -2:
        short_pts -= 5

    if r1d >= 3:
        short_pts += 4
    short_pts = max(0, min(100, short_pts + 22))

    # ── Long-term (fundamentals + PE discount vs history) ───────────
    # Screener's canonical PE field is "Price to Earning" (col 17 in your export).
    # "Price to Earnings Times" (col 8) is a *multiple* field — PE relative to some
    # base — not the raw trailing PE. For Nykaa (FSN), col 8 = 59.5 but the real PE
    # is 379.1. Always trust "Price to Earning" first.
    pe = _f(row.get("Price to Earning")) or _f(row.get("Price to Earnings Times"))
    pe_h3 = _f(row.get("Historical PE 3Years"))
    pe_h5 = _f(row.get("Historical PE 5Years"))
    pe_h7 = _f(row.get("Historical PE 7Years"))
    sales_growth = _f(row.get("Sales growth")) or 0
    net_profit = _f(row.get("Net profit")) or 0
    np_prev = _f(row.get("Net Profit preceding year")) or 0
    roe = _f(row.get("Return on equity")) or 0
    roe_prev = _f(row.get("Return on equity preceding year")) or 0
    roe_avg = _f(row.get("Average return on equity 3Years")) or 0
    op = _f(row.get("Operating profit latest quarter")) or 0
    op_prev = _f(row.get("Operating profit preceding year quarter")) or 0
    r1y = _f(row.get("Return over 1year")) or 0
    r3y = _f(row.get("Return over 3years")) or 0

    long_pts = 0

    # ROE level + trend
    if roe >= 20:
        long_pts += 12
        bullets.append(f"ROE of {roe:.1f}% — high capital efficiency.")
    elif roe >= 15:
        long_pts += 8
    elif roe < 8:
        long_pts -= 4

    roe_change = None
    if roe_prev:
        roe_change = roe - roe_prev
        if roe_change >= 2:
            long_pts += 7
            bullets.append(f"ROE improving {roe_change:+.1f}pt YoY — profitability getting better.")
        elif roe_change <= -3:
            long_pts -= 4

    if roe_avg >= 15:
        long_pts += 6

    # Growth
    if sales_growth >= 20:
        long_pts += 10
        bullets.append(f"Sales growing {sales_growth:.1f}% — real top-line expansion.")
    elif sales_growth >= 10:
        long_pts += 6
    elif sales_growth < 0:
        long_pts -= 3

    # Net profit YoY
    net_profit_yoy = None
    if np_prev and net_profit:
        net_profit_yoy = (net_profit - np_prev) / abs(np_prev) * 100
        if net_profit_yoy >= 30:
            long_pts += 9
            bullets.append(f"Net profit up {net_profit_yoy:.0f}% YoY.")
        elif net_profit_yoy >= 10:
            long_pts += 5
        elif net_profit_yoy <= -20:
            long_pts -= 5
            bullets.append(f"Net profit down {net_profit_yoy:.0f}% YoY — earnings weakening.")

    # Operating profit QoQ
    op_profit_qoq = None
    if op_prev and op:
        op_profit_qoq = (op - op_prev) / abs(op_prev) * 100
        if op_profit_qoq >= 25:
            long_pts += 8
            bullets.append(f"Operating profit up {op_profit_qoq:.0f}% QoQ — margin expansion.")
        elif op_profit_qoq >= 10:
            long_pts += 5

    # PE discount vs own history — the "relatively cheap by its own standards"
    pe_discount_3y = None
    pe_discount_5y = None
    pe_discount_7y = None
    if pe and pe_h3:
        pe_discount_3y = (pe_h3 - pe) / pe_h3 * 100
    if pe and pe_h5:
        pe_discount_5y = (pe_h5 - pe) / pe_h5 * 100
    if pe and pe_h7:
        pe_discount_7y = (pe_h7 - pe) / pe_h7 * 100

    discounts = [d for d in (pe_discount_3y, pe_discount_5y, pe_discount_7y) if d is not None]
    if discounts:
        avg_discount = sum(discounts) / len(discounts)
        if avg_discount >= 25:
            long_pts += 15
            bullets.append(
                f"Trading at ~{avg_discount:.0f}% discount vs its own historical PE "
                "(across 3/5/7-year averages) — materially cheaper than the market has priced it in the past."
            )
        elif avg_discount >= 10:
            long_pts += 9
            bullets.append(f"PE {avg_discount:.0f}% below its own history — mildly cheap.")
        elif avg_discount <= -20:
            long_pts -= 8
            bullets.append(f"PE {-avg_discount:.0f}% above its own history — expensive by own standards.")

    # 3-year track record
    if r3y >= 50:
        long_pts += 6
    if r1y < 0 and r3y >= 50:
        long_pts += 5
        bullets.append("Weak last year but strong 3-year track — potential pullback entry.")

    long_pts = max(0, min(100, long_pts + 18))

    # ── Chart score (from upgraded pattern engine) ──────────────────
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
    if "supertrend_bullish" in pattern_tags:
        bullets.append("Chart: Supertrend flipped bullish.")

    # ── Combined ────────────────────────────────────────────────────
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

    return CSVRating(
        short_term=short_pts,
        long_term=long_pts,
        chart=chart_pts,
        combined=combined,
        label=label,
        bullets=bullets[:6],
        pe_discount_3y=round(pe_discount_3y, 1) if pe_discount_3y is not None else None,
        pe_discount_5y=round(pe_discount_5y, 1) if pe_discount_5y is not None else None,
        pe_discount_7y=round(pe_discount_7y, 1) if pe_discount_7y is not None else None,
        op_profit_qoq=round(op_profit_qoq, 1) if op_profit_qoq is not None else None,
        net_profit_yoy=round(net_profit_yoy, 1) if net_profit_yoy is not None else None,
        roe_change=round(roe_change, 1) if roe_change is not None else None,
    )
