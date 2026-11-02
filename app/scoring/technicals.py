"""Technical indicators — MACD and friends.

Pure-python / pandas. No external TA library needed.

MACD basics:
  macd_line  = EMA(close, fast) - EMA(close, slow)
  signal     = EMA(macd_line, signal_period)
  histogram  = macd_line - signal

Signals:
  bullish  = macd_line > signal AND rising histogram
  bearish  = macd_line < signal AND falling histogram
  crossover_up / crossover_down fire on the day of the cross
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class MACDResult:
    fast: int
    slow: int
    signal_period: int
    macd: float | None
    signal: float | None
    histogram: float | None
    prev_histogram: float | None
    trend: str              # "bullish" | "bearish" | "neutral"
    crossover: str | None   # "up" | "down" | None (today vs yesterday)


def _series_from_price_dict(price_1y: dict) -> pd.Series:
    """price_1y shape from Financials.raw: {"Close": {"2026-01-02T00:00:00": 123.4, ...}}"""
    close = (price_1y or {}).get("Close") or {}
    if not close:
        return pd.Series(dtype=float)
    s = (
        pd.Series(close)
        .rename_axis("date")
        .reset_index()
        .assign(date=lambda d: pd.to_datetime(d["date"], errors="coerce"))
        .dropna()
        .sort_values("date")
        .set_index("date")[0]
    )
    s.name = "close"
    return s.astype(float)


def compute_macd(price_1y: dict, fast: int, slow: int, signal_period: int) -> MACDResult:
    s = _series_from_price_dict(price_1y)
    if s.empty or len(s) < max(slow + signal_period + 2, 30):
        return MACDResult(fast, slow, signal_period, None, None, None, None, "neutral", None)

    ema_fast = s.ewm(span=fast, adjust=False).mean()
    ema_slow = s.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    sig = macd_line.ewm(span=signal_period, adjust=False).mean()
    hist = macd_line - sig

    macd_now = float(macd_line.iloc[-1])
    sig_now = float(sig.iloc[-1])
    hist_now = float(hist.iloc[-1])
    hist_prev = float(hist.iloc[-2])

    if macd_now > sig_now and hist_now > hist_prev:
        trend = "bullish"
    elif macd_now < sig_now and hist_now < hist_prev:
        trend = "bearish"
    else:
        trend = "neutral"

    # Crossover: sign of (macd - signal) flipped between the last two bars
    cross = None
    prev_diff = float(macd_line.iloc[-2] - sig.iloc[-2])
    now_diff = macd_now - sig_now
    if prev_diff <= 0 and now_diff > 0:
        cross = "up"
    elif prev_diff >= 0 and now_diff < 0:
        cross = "down"

    return MACDResult(
        fast=fast,
        slow=slow,
        signal_period=signal_period,
        macd=round(macd_now, 3),
        signal=round(sig_now, 3),
        histogram=round(hist_now, 3),
        prev_histogram=round(hist_prev, 3),
        trend=trend,
        crossover=cross,
    )


# Convenience wrappers for the two profiles we show in the UI
def macd_fast(price_1y: dict) -> MACDResult:
    """Fast MACD — catches short-term turns earlier."""
    return compute_macd(price_1y, fast=7, slow=21, signal_period=9)


def macd_standard(price_1y: dict) -> MACDResult:
    """Standard MACD — the textbook (12, 26, 9) version used to confirm the fast signal."""
    return compute_macd(price_1y, fast=12, slow=26, signal_period=9)
