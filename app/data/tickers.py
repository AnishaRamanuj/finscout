"""Pulls the NSE equity master list (free, no key).

Covers both venues NSE operates:
  1. NSE Main Board  — ~2,600 tickers at EQUITY_L.csv (EQ + BE series mostly)
  2. NSE Emerge SME  — ~580 tickers at /emerge/corporates/content/SME_EQUITY_L.csv

Together they are the full ~2,750 tradable universe of Indian listed equities.
Rights-entitlement (RE) and when-issued rows are filtered out so what returns
is one row per real ticker, ready to feed through yfinance.
"""
from __future__ import annotations

import io
import logging

import httpx
import pandas as pd

log = logging.getLogger(__name__)

NSE_MAIN_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
NSE_SME_URL = (
    "https://nsearchives.nseindia.com/emerge/corporates/content/SME_EQUITY_L.csv"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
    ),
    "Accept": "text/csv,application/csv,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}

# Real equity series we want to trade. Everything else (rights, when-issued,
# series that only exist for a settlement event) is dropped.
_KEEP_SERIES = {"EQ", "BE", "BZ", "SM", "ST", "SZ"}


def _normalize(df: pd.DataFrame, source: str) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]
    # Main Board uses "NAME OF COMPANY" (spaces); SME uses "NAME_OF_COMPANY"
    # (underscores). Standardise.
    name_col = next(
        (c for c in df.columns if c.upper().replace("_", " ") == "NAME OF COMPANY"),
        None,
    )
    sym_col = next((c for c in df.columns if c.upper() == "SYMBOL"), None)
    series_col = next((c for c in df.columns if c.upper() == "SERIES"), None)
    if sym_col is None or name_col is None:
        return pd.DataFrame(columns=["ticker", "name", "yf_symbol", "venue"])

    out = pd.DataFrame({
        "ticker": df[sym_col].astype(str).str.strip(),
        "name": df[name_col].astype(str).str.strip(),
        "series": df[series_col].astype(str).str.strip().str.upper() if series_col else "",
    })
    # Drop rights / "-RE" rows and keep only real equity series.
    out = out[~out["ticker"].str.endswith("-RE")]
    if series_col:
        out = out[out["series"].isin(_KEEP_SERIES) | out["series"].eq("")]
    out = out.drop_duplicates(subset=["ticker"]).reset_index(drop=True)
    out["yf_symbol"] = out["ticker"] + ".NS"
    out["venue"] = source
    return out[["ticker", "name", "yf_symbol", "venue"]]


def _fetch(url: str, source: str) -> pd.DataFrame:
    """Fetch an NSE CSV with up to three tries and a 60s read timeout.

    NSE's SME archive occasionally rate-limits or hangs; we retry once with
    a short backoff before giving up on that venue.
    """
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            r = httpx.get(url, headers=HEADERS, timeout=httpx.Timeout(60.0, connect=15.0),
                          follow_redirects=True)
            r.raise_for_status()
            df = pd.read_csv(io.StringIO(r.text))
            return _normalize(df, source)
        except Exception as e:
            last_err = e
            log.warning("NSE %s fetch attempt %d failed: %s", source, attempt + 1, e)
    log.warning("NSE %s fetch giving up: %s", source, last_err)
    return pd.DataFrame(columns=["ticker", "name", "yf_symbol", "venue"])


def fetch_nse_tickers() -> pd.DataFrame:
    """Return the full NSE listed equity universe (Main Board + Emerge SME).

    Columns: ticker, name, yf_symbol, venue ('main' or 'sme').
    A ticker that appears on both venues keeps its Main Board row.
    """
    main = _fetch(NSE_MAIN_URL, "main")
    sme = _fetch(NSE_SME_URL, "sme")
    if main.empty:
        return sme
    if sme.empty:
        return main
    combined = (
        pd.concat([main, sme], ignore_index=True)
        .drop_duplicates(subset=["ticker"], keep="first")
        .reset_index(drop=True)
    )
    return combined
