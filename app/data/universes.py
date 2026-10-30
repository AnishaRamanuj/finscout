"""Named NSE universes for curated ingestion.

Instead of pulling the first N tickers alphabetically from the NSE
master list (which gives you microcaps like 20MICRONS), FinScout
filters to a known universe of large/mid caps that are actually
worth tracking.
"""
from __future__ import annotations

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

UNIVERSES: dict[str, frozenset[str]] = {
    "nifty50": NIFTY_50,
    "nifty100": NIFTY_50 | NIFTY_NEXT_50,
    "all": frozenset(),  # empty = no filter
}


def get_universe(name: str) -> frozenset[str]:
    name = (name or "nifty50").lower()
    if name not in UNIVERSES:
        raise ValueError(f"unknown universe '{name}'. Options: {list(UNIVERSES)}")
    return UNIVERSES[name]
