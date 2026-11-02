"""Combined 'momentum building' signal.

Four independent inputs; each contributes to a 0-100 score. A stock
scoring high across all four is in a textbook accumulation setup —
smart money is coming in, the chart agrees, and the retail crowd
hasn't piled in yet.

  1. Volume surge        — today vs 30-day average
  2. Delivery % rising   — slope of delivery_pct over last 10 days
  3. MACD(7,21,9) status — bullish / neutral / bearish
  4. MACD(12,26,9) agree — same, to confirm the fast signal

Returns a MomentumSignal dataclass with the breakdown so the UI can
show the user *why* the score is what it is.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MomentumSignal:
    score: int                 # 0-100 overall
    volume_part: int           # 0-25
    delivery_part: int         # 0-25
    macd_fast_part: int        # 0-25
    macd_std_part: int         # 0-25
    label: str                 # "Building" | "Strong" | "Fading" | "Quiet"
    reasons: list[str]


def _volume_contribution(volume_surge: float | None) -> tuple[int, str | None]:
    if volume_surge is None:
        return 0, None
    if volume_surge >= 3.0:
        return 25, f"Today's volume is {volume_surge:.1f}× the 30-day average — strong institutional interest."
    if volume_surge >= 2.0:
        return 22, f"Today's volume is {volume_surge:.1f}× normal — a classic breakout tell."
    if volume_surge >= 1.5:
        return 15, f"Volume is {volume_surge:.1f}× normal — mild accumulation."
    if volume_surge >= 1.0:
        return 8, None
    return 0, None


def _delivery_contribution(delivery_slope: float | None, latest_delivery: float | None) -> tuple[int, str | None]:
    """delivery_slope: % change in delivery_pct per trading day over last ~10 days."""
    base = 0
    reason = None
    if latest_delivery is not None:
        if latest_delivery >= 60:
            base = 10
        elif latest_delivery >= 45:
            base = 7
        elif latest_delivery >= 30:
            base = 4

    if delivery_slope is not None:
        if delivery_slope >= 1.5:
            base += 15
            reason = (
                f"Delivery % is climbing +{delivery_slope:.1f}pt/day — buyers are taking delivery, "
                "not just day-trading."
            )
        elif delivery_slope >= 0.5:
            base += 10
            reason = f"Delivery % trending up (+{delivery_slope:.1f}pt/day) — slow accumulation."
        elif delivery_slope <= -1.0:
            base = max(0, base - 10)
            reason = f"Delivery % is falling ({delivery_slope:.1f}pt/day) — speculators dominating."

    return min(25, base), reason


def _macd_contribution(trend: str, crossover: str | None, label: str) -> tuple[int, str | None]:
    if trend == "bullish":
        if crossover == "up":
            return 25, f"{label} MACD just crossed up — fresh bullish signal."
        return 20, f"{label} MACD is bullish and expanding."
    if trend == "neutral":
        if crossover == "up":
            return 15, f"{label} MACD just crossed up — early momentum."
        return 10, None
    if trend == "bearish":
        if crossover == "down":
            return 0, f"{label} MACD just crossed down — bearish."
        return 3, None
    return 0, None


def compute_signal(
    *,
    volume_surge: float | None,
    latest_delivery_pct: float | None,
    delivery_slope: float | None,
    macd_fast_trend: str,
    macd_fast_cross: str | None,
    macd_std_trend: str,
    macd_std_cross: str | None,
) -> MomentumSignal:
    v, v_reason = _volume_contribution(volume_surge)
    d, d_reason = _delivery_contribution(delivery_slope, latest_delivery_pct)
    mf, mf_reason = _macd_contribution(macd_fast_trend, macd_fast_cross, "Fast (7,21,9)")
    ms, ms_reason = _macd_contribution(macd_std_trend, macd_std_cross, "Standard (12,26,9)")

    score = v + d + mf + ms
    if score >= 75:
        label = "Strong"
    elif score >= 55:
        label = "Building"
    elif score >= 35:
        label = "Mixed"
    elif score >= 15:
        label = "Fading"
    else:
        label = "Quiet"

    reasons = [r for r in (v_reason, d_reason, mf_reason, ms_reason) if r]
    if macd_fast_trend == "bullish" and macd_std_trend == "bullish":
        reasons.insert(0, "Both fast and standard MACDs are bullish — timeframes agree.")
    return MomentumSignal(
        score=score, volume_part=v, delivery_part=d,
        macd_fast_part=mf, macd_std_part=ms,
        label=label, reasons=reasons,
    )
