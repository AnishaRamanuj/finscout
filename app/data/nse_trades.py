"""NSE bulk & block deals — free, no API key, no auth.

NSE publishes two daily CSV files to its archive:
  - bulk.csv  — any client who traded >0.5% of a listed scrip that day
  - block.csv — negotiated block trades (>5 lakh shares or >Rs 5 crore)

These are the public Indian equivalent of SEC Form 4 insider filings and
work as a reliable "someone with conviction just moved money" signal.
No key, no sign-up, no rate limit worth worrying about.
"""
from __future__ import annotations

import io
from datetime import date, datetime, timedelta
from functools import lru_cache

import httpx
import pandas as pd

BULK_URL = "https://archives.nseindia.com/content/equities/bulk.csv"
BLOCK_URL = "https://archives.nseindia.com/content/equities/block.csv"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 FinScout",
    "Accept": "text/csv,text/plain,*/*",
}


def _fetch_csv(url: str) -> pd.DataFrame:
    try:
        r = httpx.get(url, headers=_HEADERS, timeout=20.0, follow_redirects=True)
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text))
        df.columns = [c.strip().lower().replace(" ", "_").replace("/", "_") for c in df.columns]
        return df
    except Exception:
        return pd.DataFrame()


@lru_cache(maxsize=2)
def _cached(url: str, _day: str) -> pd.DataFrame:
    # _day in the cache key invalidates once per calendar day
    return _fetch_csv(url)


def fetch_bulk_deals() -> pd.DataFrame:
    return _cached(BULK_URL, date.today().isoformat())


def fetch_block_deals() -> pd.DataFrame:
    return _cached(BLOCK_URL, date.today().isoformat())


def fetch_trades_for_ticker(ticker: str) -> list[dict]:
    """Today's bulk + block deals for a single NSE symbol (e.g. 'TCS')."""
    out: list[dict] = []
    for kind, df in (("bulk", fetch_bulk_deals()), ("block", fetch_block_deals())):
        if df.empty:
            continue
        sym_col = next((c for c in df.columns if "symbol" in c), None)
        if not sym_col:
            continue
        rows = df[df[sym_col].astype(str).str.upper() == ticker.upper()]
        for _, row in rows.iterrows():
            out.append({"kind": kind, **{k: row[k] for k in row.index if pd.notna(row[k])}})
    return out
