"""NSE daily delivery-percentage fetcher.

Delivery % tells you how much of today's traded volume was actually taken
for delivery (as opposed to intraday speculation). A rising delivery %
alongside a volume surge is one of the cleanest "institutions are
accumulating quietly" signals the Indian market offers for free.

Source: NSE's own daily "Bhavcopy with delivery" CSV:
    https://nsearchives.nseindia.com/products/content/
      sec_bhavdata_full_DDMMYYYY.csv

Published after close each trading day. Columns we care about:
  SYMBOL, DATE1, TTL_TRD_QNTY, DELIV_QTY, DELIV_PER, CLOSE_PRICE
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache

import httpx
import pandas as pd


_BHAV_URL = "https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{d}.csv"
_HEADERS = {"User-Agent": "Mozilla/5.0 FinScout", "Accept": "text/csv,*/*"}


@dataclass(frozen=True)
class DeliveryDay:
    date: date
    close: float | None
    total_volume: int | None
    delivery_qty: int | None
    delivery_pct: float | None


@lru_cache(maxsize=20)
def _fetch_bhav(d: date) -> pd.DataFrame:
    url = _BHAV_URL.format(d=d.strftime("%d%m%Y"))
    try:
        r = httpx.get(url, headers=_HEADERS, timeout=20.0, follow_redirects=True)
        if r.status_code != 200:
            return pd.DataFrame()
        df = pd.read_csv(io.StringIO(r.text))
        df.columns = [c.strip() for c in df.columns]
        return df
    except Exception:
        return pd.DataFrame()


def _trading_days(ending: date, back: int) -> list[date]:
    """Return the last `back` weekdays ending at `ending` (inclusive)."""
    days: list[date] = []
    cursor = ending
    while len(days) < back and cursor >= ending - timedelta(days=back * 2 + 10):
        if cursor.weekday() < 5:   # Mon-Fri
            days.append(cursor)
        cursor -= timedelta(days=1)
    return days


def get_delivery_trend(ticker: str, days: int = 10) -> list[DeliveryDay]:
    """Return the last `days` trading-day delivery stats for a ticker, newest last."""
    out: list[DeliveryDay] = []
    for d in reversed(_trading_days(date.today(), days)):
        df = _fetch_bhav(d)
        if df.empty:
            continue
        row = df[df["SYMBOL"].astype(str).str.strip().str.upper() == ticker.upper()]
        if row.empty:
            continue
        r = row.iloc[0]
        try:
            out.append(DeliveryDay(
                date=d,
                close=float(r.get("CLOSE_PRICE") or 0) or None,
                total_volume=int(r.get("TTL_TRD_QNTY") or 0) or None,
                delivery_qty=int(r.get("DELIV_QTY") or 0) or None,
                delivery_pct=float(r.get("DELIV_PER") or 0) or None,
            ))
        except Exception:
            continue
    return out


def delivery_trend_slope(trend: list[DeliveryDay]) -> float | None:
    """Linear-regression slope of delivery_pct over time (positive = rising conviction)."""
    pts = [(i, d.delivery_pct) for i, d in enumerate(trend) if d.delivery_pct is not None]
    if len(pts) < 3:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = sum((x - mx) ** 2 for x in xs) or 1
    return num / den
