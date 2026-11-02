"""Chart-pattern + technical-indicator detection from a 1-year price history.

All computations are pandas-only (no external TA library) so this can run
inside a tight page-load loop over 200+ tickers.

Patterns (from `pattern_tags`):
  ma_bullish        — 5-day > 20 > 50 > 200
  ma_bearish        — opposite stack
  golden_cross      — EMA50 crossed up through EMA200 in last ~10 bars
  death_cross       — EMA50 crossed down through EMA200 in last ~10 bars
  breakout          — close within 2% of 60-day high and above 20d MA
  pullback_zone     — price 5-15% below 60-day high, still above 50-day MA
  consolidation     — last 30 bars range < 7%
  oversold_rebound  — within 15% of 52w low AND fast MACD cross up
  overextended      — >20% above 50-day MA
  rsi_overbought    — RSI(14) >= 80
  rsi_oversold      — RSI(14) <= 25

Classical indicators (surfaced alongside, used to confirm momentum):
  rsi14             — Relative Strength Index(14)
  adx14             — Average Directional Index(14) — trend strength
  bollinger_pct_b   — %B over 20-day, 2σ — band position (0 = lower, 1 = upper)
  roc20             — Rate of Change over 20 bars (%)
  obv_slope_pct     — slope of OBV / avg(OBV) over last 20 bars (%)
  supertrend_dir    — "bullish" | "bearish" | "neutral"
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.scoring.technicals import _series_from_price_dict, compute_macd


@dataclass(frozen=True)
class ChartPattern:
    score: int
    label: str
    pattern_tags: list[str]
    rsi14: float | None
    adx14: float | None
    bollinger_pct_b: float | None
    roc20: float | None
    obv_slope_pct: float | None
    supertrend_dir: str
    ma20_above_ma50: bool
    ma50_above_ma200: bool
    close_vs_52w_high_pct: float | None
    close_vs_52w_low_pct: float | None


def _rsi(close: pd.Series, period: int = 14) -> float | None:
    if len(close) < period + 1:
        return None
    delta = close.diff()
    gain = delta.clip(lower=0.0).ewm(alpha=1 / period, adjust=False).mean()
    loss = -delta.clip(upper=0.0).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    v = rsi.iloc[-1]
    return float(v) if pd.notna(v) else None


def _adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float | None:
    """Simplified ADX using close-based proxies for high/low when not available."""
    if len(close) < period * 2:
        return None
    try:
        tr = (high - low).abs().astype(float)
        plus_dm = (high.diff()).clip(lower=0.0).astype(float)
        minus_dm = (-low.diff()).clip(lower=0.0).astype(float)
        atr = tr.ewm(alpha=1 / period, adjust=False).mean().replace(0, np.nan)
        plus_di = 100 * (plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr)
        minus_di = 100 * (minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr)
        di_sum = (plus_di + minus_di).replace(0, np.nan)
        dx = (plus_di - minus_di).abs() / di_sum * 100
        adx = dx.ewm(alpha=1 / period, adjust=False).mean()
        v = adx.iloc[-1]
        return float(v) if pd.notna(v) else None
    except Exception:
        return None


def _bollinger_pct_b(close: pd.Series, period: int = 20, k: float = 2.0) -> float | None:
    if len(close) < period:
        return None
    ma = close.rolling(period).mean()
    sd = close.rolling(period).std()
    upper = ma + k * sd
    lower = ma - k * sd
    denom = (upper - lower).iloc[-1]
    if not denom or pd.isna(denom):
        return None
    return float((close.iloc[-1] - lower.iloc[-1]) / denom)


def _roc(close: pd.Series, period: int = 20) -> float | None:
    if len(close) < period + 1:
        return None
    prev = close.iloc[-period - 1]
    if not prev:
        return None
    return float((close.iloc[-1] / prev - 1) * 100)


def _obv(close: pd.Series, volume: pd.Series | None = None) -> float | None:
    """OBV slope over last 20 bars normalised to the mean OBV. Returns % slope.

    When we have no volume series, falls back to signed-close-delta cumulative sum.
    """
    if volume is None or len(volume.dropna()) < 25:
        volume = close.diff().abs().fillna(0)
    direction = close.diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    obv = (direction * volume).cumsum()
    tail = obv.tail(20)
    if len(tail) < 10:
        return None
    xs = list(range(len(tail)))
    ys = tail.tolist()
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = sum((x - mx) ** 2 for x in xs) or 1
    slope = num / den
    avg = sum(ys) / n or 1
    return float(slope / abs(avg) * 100)


def _supertrend_direction(close: pd.Series, high: pd.Series, low: pd.Series, period: int = 10, factor: float = 3.0) -> str:
    """Simplified Supertrend: compares close against upper/lower bands derived from ATR."""
    if len(close) < period * 2:
        return "neutral"
    try:
        tr = (high - low).abs().astype(float)
        atr = tr.ewm(alpha=1 / period, adjust=False).mean()
        hl2 = (high + low) / 2
        upper = hl2 + factor * atr
        lower = hl2 - factor * atr
        last_close = float(close.iloc[-1])
        last_upper = float(upper.iloc[-1])
        last_lower = float(lower.iloc[-1])
        if last_close > last_upper:
            return "bullish"
        if last_close < last_lower:
            return "bearish"
        return "neutral"
    except Exception:
        return "neutral"


def detect(price_1y: dict | None) -> ChartPattern:
    close = _series_from_price_dict(price_1y or {})
    if close.empty or len(close) < 40:
        return ChartPattern(0, "insufficient-data", [], None, None, None, None, None,
                            "neutral", False, False, None, None)

    # High/low proxies if the raw payload only has closes
    high = close.rolling(2).max().fillna(close)
    low = close.rolling(2).min().fillna(close)

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
            tags.append("ma_bullish"); pts += 22
        elif ma5 < ma20 < ma50 < ma200:
            tags.append("ma_bearish"); pts -= 10

    # 2) Golden / Death cross on EMA 50/200 in last ~10 bars
    if ema200 is not None and len(ema50) >= 11:
        diffs = (ema50 - ema200).iloc[-11:]
        signs = diffs.map(lambda x: 1 if x > 0 else (-1 if x < 0 else 0)).tolist()
        if any(signs[i - 1] <= 0 and signs[i] > 0 for i in range(1, len(signs))):
            tags.append("golden_cross"); pts += 18
        elif any(signs[i - 1] >= 0 and signs[i] < 0 for i in range(1, len(signs))):
            tags.append("death_cross"); pts -= 15

    # 3) Breakout — close within 2% of 60-day high and above 20d MA
    if ma20 is not None and last >= high60 * 0.98 and last > ma20:
        tags.append("breakout"); pts += 18

    # 4) Pullback zone
    pullback_pct = (last / high60 - 1) * 100
    if ma50 is not None and -15 <= pullback_pct <= -5 and last > ma50:
        tags.append("pullback_zone"); pts += 10

    # 5) Consolidation
    tail = close.tail(30)
    rng = (float(tail.max()) - float(tail.min())) / float(tail.mean()) * 100
    if rng < 7:
        tags.append("consolidation"); pts += 5

    # 6) Oversold rebound
    pct_above_low = (last / low52 - 1) * 100
    if pct_above_low < 15:
        mf = compute_macd(price_1y, 7, 21, 9)
        if mf.crossover == "up" or mf.trend == "bullish":
            tags.append("oversold_rebound"); pts += 15

    # 7) Overextended
    if ma50 is not None and last > ma50 * 1.20:
        tags.append("overextended"); pts -= 8

    # ---- Classical indicators that *vouch* for momentum ----
    rsi = _rsi(close)
    if rsi is not None:
        if 55 <= rsi < 70:
            pts += 6
        elif rsi >= 80:
            pts -= 4; tags.append("rsi_overbought")
        elif rsi <= 25:
            tags.append("rsi_oversold")

    adx = _adx(high, low, close)
    if adx is not None:
        if adx >= 25:
            pts += 10        # strong trend (direction has to come from MA/MACD)
        elif adx < 15:
            pts -= 3         # weak / sideways

    pct_b = _bollinger_pct_b(close)
    if pct_b is not None:
        if 0.5 <= pct_b <= 0.95:
            pts += 6         # riding upper half of the band
        elif pct_b <= 0.1:
            pts += 3; tags.append("bb_lower_band")  # possible rebound
        elif pct_b >= 1.0:
            pts -= 2         # stretched past upper band

    roc20 = _roc(close, 20)
    if roc20 is not None:
        if roc20 >= 15:
            pts += 8
        elif roc20 >= 5:
            pts += 4
        elif roc20 <= -15:
            pts -= 6

    obv_slope = _obv(close)
    if obv_slope is not None:
        if obv_slope >= 2:
            pts += 10        # strong accumulation
        elif obv_slope >= 0.5:
            pts += 5
        elif obv_slope <= -2:
            pts -= 6         # distribution

    stdir = _supertrend_direction(close, high, low)
    if stdir == "bullish":
        pts += 8; tags.append("supertrend_bullish")
    elif stdir == "bearish":
        pts -= 6; tags.append("supertrend_bearish")

    pts = max(0, min(100, pts + 25))   # baseline so neutrals land ~25

    label = tags[0] if tags else "neutral"
    return ChartPattern(
        score=int(pts),
        label=label,
        pattern_tags=tags,
        rsi14=round(rsi, 1) if rsi is not None else None,
        adx14=round(adx, 1) if adx is not None else None,
        bollinger_pct_b=round(pct_b, 2) if pct_b is not None else None,
        roc20=round(roc20, 1) if roc20 is not None else None,
        obv_slope_pct=round(obv_slope, 2) if obv_slope is not None else None,
        supertrend_dir=stdir,
        ma20_above_ma50=ma20_above_ma50,
        ma50_above_ma200=ma50_above_ma200,
        close_vs_52w_high_pct=round((last / high52 - 1) * 100, 1),
        close_vs_52w_low_pct=round(pct_above_low, 1),
    )
