"""Chart-pattern detection from a 1-year price history.

All computations are pandas-only — no external TA library — so this can
run inside a tight page-load loop over 200+ tickers without new deps.

Patterns we flag:
  - "ma_bullish"     : 5-day MA > 20-day > 50-day > 200-day (textbook uptrend)
  - "golden_cross"   : 50-EMA crossed up through 200-EMA in last ~10 bars
  - "death_cross"    : 50-EMA crossed down through 200-EMA in last ~10 bars
  - "breakout"       : last close within 2% of the 60-day high and above the 20d MA
  - "pullback_zone"  : price down 5-15% from 60-day high but above 50-day MA
  - "consolidation"  : (high-low)/avg over last 30 bars < 7% — range-bound
  - "oversold_rebound": within 15% of 52-week low AND MACD(7,21,9) just crossed up
  - "overextended"   : price > 20% above 50-day MA (prone to reversion)
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.scoring.technicals import _series_from_price_dict, compute_macd


@dataclass(frozen=True)
class ChartPattern:
    score: int                     # 0-100 chart-strength score
    label: str                     # one-word pattern name shown in UI
    pattern_tags: list[str]        # all applicable tags, strongest first
    rsi14: float | None            # 14-period RSI
    ma20_above_ma50: bool
    ma50_above_ma200: bool
    close_vs_52w_high_pct: float | None   # distance from 52w high (negative = below)
    close_vs_52w_low_pct: float | None    # distance above 52w low


def _rsi(close: pd.Series, period: int = 14) -> float | None:
    if len(close) < period + 1:
        return None
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    rsi = 100 - 100 / (1 + rs)
    v = rsi.iloc[-1]
    return float(v) if pd.notna(v) else None


def detect(price_1y: dict | None) -> ChartPattern:
    close = _series_from_price_dict(price_1y or {})
    if close.empty or len(close) < 40:
        return ChartPattern(0, "insufficient-data", [], None, False, False, None, None)

    last = float(close.iloc[-1])
    ma5 = close.rolling(5).mean().iloc[-1]
    ma20 = close.rolling(20).mean().iloc[-1]
    ma50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else None
    ma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else None
    ema50 = close.ewm(span=50, adjust=False).mean()
    ema200 = close.ewm(span=200, adjust=False).mean() if len(close) >= 200 else None

    high52 = float(close.rolling(min(252, len(close))).max().iloc[-1])
    low52 = float(close.rolling(min(252, len(close))).min().iloc[-1])
    high60 = float(close.rolling(min(60, len(close))).max().iloc[-1])

    tags: list[str] = []
    pts = 0

    ma20_above_ma50 = bool(ma20 is not None and ma50 is not None and ma20 > ma50)
    ma50_above_ma200 = bool(ma50 is not None and ma200 is not None and ma50 > ma200)

    # 1) MA stack
    if ma5 is not None and ma20 is not None and ma50 is not None and ma200 is not None:
        if ma5 > ma20 > ma50 > ma200:
            tags.append("ma_bullish")
            pts += 25
        elif ma5 < ma20 < ma50 < ma200:
            tags.append("ma_bearish")
            pts -= 10

    # 2) Golden / Death cross on EMA 50/200 in last ~10 bars
    if ema200 is not None and len(ema50) >= 11:
        diffs = (ema50 - ema200).iloc[-11:]
        signs = diffs.map(lambda x: 1 if x > 0 else (-1 if x < 0 else 0)).tolist()
        if any(signs[i - 1] <= 0 and signs[i] > 0 for i in range(1, len(signs))):
            tags.append("golden_cross")
            pts += 20
        elif any(signs[i - 1] >= 0 and signs[i] < 0 for i in range(1, len(signs))):
            tags.append("death_cross")
            pts -= 15

    # 3) Breakout — close within 2% of 60-day high and above 20d MA
    if ma20 is not None and last >= high60 * 0.98 and last > ma20:
        tags.append("breakout")
        pts += 20

    # 4) Pullback zone — price 5-15% below 60-day high but above 50d MA
    pullback_pct = (last / high60 - 1) * 100
    if ma50 is not None and -15 <= pullback_pct <= -5 and last > ma50:
        tags.append("pullback_zone")
        pts += 12

    # 5) Consolidation — last 30 bars range < 7%
    tail = close.tail(30)
    rng = (float(tail.max()) - float(tail.min())) / float(tail.mean()) * 100
    if rng < 7:
        tags.append("consolidation")
        pts += 6

    # 6) Oversold rebound — near 52w low + fast MACD crossed up
    pct_above_low = (last / low52 - 1) * 100
    if pct_above_low < 15:
        mf = compute_macd(price_1y, 7, 21, 9)
        if mf.crossover == "up" or mf.trend == "bullish":
            tags.append("oversold_rebound")
            pts += 18

    # 7) Overextended — >20% above 50d MA
    if ma50 is not None and last > ma50 * 1.20:
        tags.append("overextended")
        pts -= 8

    rsi = _rsi(close)
    if rsi is not None:
        if 50 < rsi < 70:
            pts += 6
        elif rsi >= 80:
            pts -= 5
            tags.append("rsi_overbought")
        elif rsi <= 25:
            tags.append("rsi_oversold")

    # Baseline so the label makes sense even without strong signals
    pts = max(0, min(100, pts + 30))

    label = tags[0] if tags else "neutral"
    return ChartPattern(
        score=int(pts),
        label=label,
        pattern_tags=tags,
        rsi14=round(rsi, 1) if rsi is not None else None,
        ma20_above_ma50=ma20_above_ma50,
        ma50_above_ma200=ma50_above_ma200,
        close_vs_52w_high_pct=round((last / high52 - 1) * 100, 1),
        close_vs_52w_low_pct=round(pct_above_low, 1),
    )
