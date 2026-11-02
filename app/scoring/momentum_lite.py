"""Batch-friendly momentum scorer — fast enough to run on every pick on a page load.

Trades off the live-quote 25-point volume slice (which needs one yfinance
call per ticker) for a cheaper **recent price-trend** proxy. Still blends:

  1. MACD(7,21,9)   trend   — 25 pts
  2. MACD(12,26,9)  trend   — 25 pts
  3. Delivery %     + slope — 25 pts  (from today's cached NSE bhavcopy)
  4. Recent price   trend   — 25 pts  (5-day vs 20-day moving average)

Everything is computed from data we already have in Postgres (price_1y
in Financials.raw) plus one HTTP call to NSE for the day's bhavcopy
which is cached globally. No per-ticker API hits.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache

import pandas as pd

from app.data.delivery import _fetch_bhav, _trading_days
from app.scoring.technicals import macd_fast, macd_standard, _series_from_price_dict


@dataclass(frozen=True)
class LiteSignal:
    score: int                    # 0-100
    label: str                    # Strong / Building / Mixed / Fading / Quiet
    delivery_pct: float | None
    delivery_slope: float | None
    macd_fast_trend: str
    macd_std_trend: str
    price_trend: str              # "up" | "flat" | "down"


# ---- Bhavcopy preload -----------------------------------------------------
@lru_cache(maxsize=1)
def _bhav_last_n(n: int = 10) -> list[tuple[date, pd.DataFrame]]:
    """Fetch the last `n` daily bhavcopies and return them keyed by date.

    Everything in-memory — a single call feeds delivery stats for every
    ticker on the page.
    """
    out: list[tuple[date, pd.DataFrame]] = []
    for d in reversed(_trading_days(date.today(), n)):
        df = _fetch_bhav(d)
        if df.empty:
            continue
        df = df.rename(columns=lambda c: str(c).strip())
        # Normalize symbol column for fast lookup
        df["_SYM"] = df["SYMBOL"].astype(str).str.strip().str.upper()
        out.append((d, df))
    return out


def _delivery_for(ticker: str) -> tuple[float | None, float | None]:
    """Return (latest_delivery_pct, slope_pt_per_day) using the cached bhavcopies."""
    rows: list[tuple[int, float]] = []
    latest: float | None = None
    for i, (_d, df) in enumerate(_bhav_last_n()):
        hit = df[df["_SYM"] == ticker.upper()]
        if hit.empty:
            continue
        try:
            v = float(hit.iloc[0].get("DELIV_PER") or 0) or None
        except Exception:
            v = None
        if v is None:
            continue
        rows.append((i, v))
        latest = v
    if len(rows) < 3:
        return latest, None
    xs, ys = zip(*rows)
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = sum((x - mx) ** 2 for x in xs) or 1
    return latest, num / den


def _price_trend_pts(price_1y: dict) -> tuple[int, str]:
    """5-day vs 20-day moving average — proxy for recent momentum when live is unavailable."""
    s = _series_from_price_dict(price_1y)
    if s.empty or len(s) < 25:
        return 0, "flat"
    ma5 = s.rolling(5).mean().iloc[-1]
    ma20 = s.rolling(20).mean().iloc[-1]
    if not ma5 or not ma20:
        return 0, "flat"
    delta_pct = (ma5 - ma20) / ma20 * 100
    if delta_pct >= 5:
        return 25, "up"
    if delta_pct >= 2:
        return 18, "up"
    if delta_pct >= 0:
        return 10, "flat"
    if delta_pct >= -3:
        return 5, "flat"
    return 0, "down"


def _macd_pts(trend: str, crossover: str | None) -> int:
    if trend == "bullish":
        return 25 if crossover == "up" else 20
    if trend == "neutral":
        return 15 if crossover == "up" else 10
    return 0 if crossover == "down" else 3


def _delivery_pts(latest_pct: float | None, slope: float | None) -> int:
    base = 0
    if latest_pct is not None:
        if latest_pct >= 60:
            base = 10
        elif latest_pct >= 45:
            base = 7
        elif latest_pct >= 30:
            base = 4
    if slope is not None:
        if slope >= 1.5:
            base += 15
        elif slope >= 0.5:
            base += 10
        elif slope <= -1.0:
            base = max(0, base - 10)
    return min(25, base)


def _label(score: int) -> str:
    if score >= 75:
        return "Strong"
    if score >= 55:
        return "Building"
    if score >= 35:
        return "Mixed"
    if score >= 15:
        return "Fading"
    return "Quiet"


def score_momentum(ticker: str, price_1y: dict | None) -> LiteSignal:
    """Compute a lite 0-100 momentum signal for one ticker. Safe for use in a tight loop."""
    price_1y = price_1y or {}
    mf = macd_fast(price_1y)
    ms = macd_standard(price_1y)
    delivery_pct, slope = _delivery_for(ticker)
    price_pts, price_trend = _price_trend_pts(price_1y)

    score = (
        _macd_pts(mf.trend, mf.crossover)
        + _macd_pts(ms.trend, ms.crossover)
        + _delivery_pts(delivery_pct, slope)
        + price_pts
    )
    return LiteSignal(
        score=int(score),
        label=_label(int(score)),
        delivery_pct=round(delivery_pct, 1) if delivery_pct is not None else None,
        delivery_slope=round(slope, 2) if slope is not None else None,
        macd_fast_trend=mf.trend,
        macd_std_trend=ms.trend,
        price_trend=price_trend,
    )
