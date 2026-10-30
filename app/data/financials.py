"""Pulls financials, prices and insider data via yfinance (free)."""
import yfinance as yf
from tenacity import retry, stop_after_attempt, wait_exponential


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def fetch_company_financials(yf_symbol: str) -> dict:
    t = yf.Ticker(yf_symbol)
    info = t.info or {}

    def safe_dict(df):
        """Convert a DataFrame to a nested dict with JSON-safe (string) keys."""
        try:
            if df is None or df.empty:
                return {}
            raw = df.to_dict()
            # Pandas index keys (dates / Timestamps) break JSON. Stringify them.
            return {
                str(col): {
                    (k.isoformat() if hasattr(k, "isoformat") else str(k)): v
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
