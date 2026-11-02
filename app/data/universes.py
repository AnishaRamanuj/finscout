"""Named NSE universes for curated ingestion.

Instead of pulling the first N tickers alphabetically from the NSE
master list (which gives you microcaps like 20MICRONS), FinScout
filters to a known universe of large/mid caps that are actually
worth tracking.

Larger universes (nifty500) are fetched live from NSE's own
constituent CSV so they stay in sync with index rebalancing.
"""
from __future__ import annotations

import io
import logging
from functools import lru_cache

import httpx

log = logging.getLogger(__name__)

NIFTY_500_URL = "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv"
NIFTY_MIDCAP_150_URL = "https://nsearchives.nseindia.com/content/indices/ind_niftymidcap150list.csv"
NIFTY_SMALLCAP_250_URL = "https://nsearchives.nseindia.com/content/indices/ind_niftysmallcap250list.csv"
NIFTY_MICROCAP_250_URL = "https://nsearchives.nseindia.com/content/indices/ind_niftymicrocap250_list.csv"
NIFTY_TOTAL_MARKET_URL = "https://nsearchives.nseindia.com/content/indices/ind_niftytotalmarket_list.csv"

# NIFTY 50 constituents (symbol as it appears in NSE's EQUITY_L.csv).
# Source: nseindia.com NIFTY 50 index composition.
# Covers ~65% of total NSE market cap across sectors.
NIFTY_50: frozenset[str] = frozenset({
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
    "HINDUNILVR", "SBIN", "BHARTIARTL", "ITC", "LT",
    "KOTAKBANK", "HCLTECH", "ASIANPAINT", "AXISBANK", "BAJFINANCE",
    "MARUTI", "SUNPHARMA", "TITAN", "ULTRACEMCO", "WIPRO",
    "NESTLEIND", "ONGC", "NTPC", "TATAMOTORS", "POWERGRID",
    "M&M", "TATASTEEL", "ADANIENT", "ADANIPORTS", "COALINDIA",
    "BAJAJFINSV", "GRASIM", "JSWSTEEL", "HINDALCO", "HDFCLIFE",
    "SBILIFE", "DIVISLAB", "DRREDDY", "CIPLA", "APOLLOHOSP",
    "BAJAJ-AUTO", "EICHERMOT", "HEROMOTOCO", "BRITANNIA",
    "TATACONSUM", "INDUSINDBK", "LTIM", "TECHM", "BPCL",
    "SHRIRAMFIN",
})

# NIFTY NEXT 50 — the next tier down, if you want ~100 companies total.
NIFTY_NEXT_50: frozenset[str] = frozenset({
    "DMART", "ADANIGREEN", "ATGL", "DLF", "GODREJCP",
    "HAVELLS", "SIEMENS", "TATAPOWER", "VEDL", "VBL",
    "ZOMATO", "PIDILITIND", "CHOLAFIN", "ICICIGI", "SBICARD",
    "LICI", "ADANIPOWER", "AMBUJACEM", "BEL", "BOSCHLTD",
    "COLPAL", "DABUR", "GAIL", "HAL", "ICICIPRULI",
    "INDIGO", "IOC", "IRCTC", "JINDALSTEL", "LTTS",
    "MARICO", "MOTHERSON", "NAUKRI", "NMDC", "PETRONET",
    "PIIND", "PFC", "PNB", "RECLTD", "SAIL",
    "SHREECEM", "SRF", "TRENT", "TVSMOTOR", "UNITDSPR",
    "ZYDUSLIFE", "MUTHOOTFIN", "LUPIN", "JUBLFOOD", "ABB",
})

@lru_cache(maxsize=4)
def _fetch_index_symbols(url: str) -> frozenset[str]:
    """Pull Symbol column from a live NSE index constituent CSV."""
    try:
        r = httpx.get(url, headers={"User-Agent": "Mozilla/5.0 FinScout"},
                      timeout=20.0, follow_redirects=True)
        r.raise_for_status()
    except Exception as e:
        log.warning("Could not fetch %s: %s", url, e)
        return frozenset()

    import pandas as pd
    try:
        df = pd.read_csv(io.StringIO(r.text))
    except Exception as e:
        log.warning("CSV parse failed for %s: %s", url, e)
        return frozenset()
    col = next((c for c in df.columns if c.strip().lower() == "symbol"), None)
    if not col:
        return frozenset()
    return frozenset(str(s).strip().upper() for s in df[col].dropna())


def nifty_500() -> frozenset[str]:
    return _fetch_index_symbols(NIFTY_500_URL) or (NIFTY_50 | NIFTY_NEXT_50)


def nifty_midcap_150() -> frozenset[str]:
    return _fetch_index_symbols(NIFTY_MIDCAP_150_URL)


def nifty_smallcap_250() -> frozenset[str]:
    return _fetch_index_symbols(NIFTY_SMALLCAP_250_URL)


def nifty_microcap_250() -> frozenset[str]:
    return _fetch_index_symbols(NIFTY_MICROCAP_250_URL)


def nifty_total_market() -> frozenset[str]:
    """Nifty Total Market Index — the full ~750-stock investable universe."""
    return _fetch_index_symbols(NIFTY_TOTAL_MARKET_URL) or (nifty_500() | nifty_smallcap_250())


_STATIC: dict[str, frozenset[str]] = {
    "nifty50": NIFTY_50,
    "nifty100": NIFTY_50 | NIFTY_NEXT_50,
    "midcap150": frozenset(),      # resolved at call time
    "smallcap250": frozenset(),    # resolved at call time
    "microcap250": frozenset(),    # resolved at call time
    "nifty500": frozenset(),       # resolved at call time
    "totalmarket": frozenset(),    # ~750 investable stocks
    "all": frozenset(),            # empty = no filter
}


_RESOLVERS = {
    "nifty500": nifty_500,
    "midcap150": nifty_midcap_150,
    "smallcap250": nifty_smallcap_250,
    "microcap250": nifty_microcap_250,
    "totalmarket": nifty_total_market,
}


def get_universe(name: str) -> frozenset[str]:
    name = (name or "nifty100").lower()
    if name not in _STATIC:
        raise ValueError(f"unknown universe '{name}'. Options: {list(_STATIC)}")
    if name in _RESOLVERS:
        return _RESOLVERS[name]()
    return _STATIC[name]
