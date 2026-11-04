"""Pulls financials, prices and insider data via yfinance (free)."""
import math

import yfinance as yf
from tenacity import retry, stop_after_attempt, wait_exponential


def _json_safe(v):
    """Return a value the Postgres JSON encoder can accept.

    yfinance quite happily returns NaN / Inf for today's bar when the market
    is still open, and Postgres' JSON type rejects those tokens outright
    ('Token "NaN" is invalid'). Convert them to None here so the whole insert
    doesn't fail.
    """
    if isinstance(v, float) and not math.isfinite(v):
        return None
    return v


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def fetch_company_financials(yf_symbol: str) -> dict:
    t = yf.Ticker(yf_symbol)
    info = t.info or {}

    def safe_dict(df):
        """Convert a DataFrame to a JSON-safe nested dict (keys stringified,
        NaN / Inf values coerced to None)."""
        try:
            if df is None or df.empty:
                return {}
            raw = df.to_dict()
            return {
                str(col): {
                    (k.isoformat() if hasattr(k, "isoformat") else str(k)): _json_safe(v)
                    for k, v in series.items()
                }
                for col, series in raw.items()
            }
        except Exception:
            return {}

    return {
        "info": {
            "name": info.get("longName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": info.get("marketCap"),
            "pe": info.get("trailingPE"),
            "pb": info.get("priceToBook"),
            "price": info.get("currentPrice"),
            "roce": info.get("returnOnEquity"),
        },
        "quarterly_income": safe_dict(t.quarterly_income_stmt),
        "quarterly_balance_sheet": safe_dict(t.quarterly_balance_sheet),
        "quarterly_cashflow": safe_dict(t.quarterly_cashflow),
        "price_1y": safe_dict(t.history(period="1y")[["Close"]]),
        "insider_tx": safe_dict(t.insider_transactions),
    }
