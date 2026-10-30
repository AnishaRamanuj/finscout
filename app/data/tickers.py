"""Pulls the NSE equity master list (free, no key)."""
import io
import httpx
import pandas as pd

NSE_EQ_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (FinScout bot)",
    "Accept": "text/csv",
}


def fetch_nse_tickers() -> pd.DataFrame:
    r = httpx.get(NSE_EQ_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    df.columns = [c.strip() for c in df.columns]
    df["ticker"] = df["SYMBOL"].str.strip()
    df["name"] = df["NAME OF COMPANY"].str.strip()
    df["yf_symbol"] = df["ticker"] + ".NS"
    return df[["ticker", "name", "yf_symbol"]]
