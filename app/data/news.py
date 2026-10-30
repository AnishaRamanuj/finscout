"""News fetch via yfinance (free, no API key).

yfinance pulls company news from Yahoo Finance. For NSE tickers, pass the
.NS symbol (e.g. 'TCS.NS'). Returns a list of dicts with a 'headline' key
so the rest of the pipeline stays unchanged.
"""
from datetime import datetime, timedelta, timezone

import yfinance as yf


def fetch_news(yf_symbol: str, days: int = 30) -> list[dict]:
    try:
        raw = yf.Ticker(yf_symbol).news or []
    except Exception:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    out: list[dict] = []
    for item in raw:
        content = item.get("content") or item
        title = content.get("title") or item.get("title")
        if not title:
            continue
        pub_ts = item.get("providerPublishTime")
        if pub_ts:
            try:
                if datetime.fromtimestamp(pub_ts, tz=timezone.utc) < cutoff:
                    continue
            except (TypeError, ValueError):
                pass
        out.append({
            "headline": title,
            "publisher": content.get("provider", {}).get("displayName") or item.get("publisher", ""),
            "url": content.get("canonicalUrl", {}).get("url") or item.get("link", ""),
            "ts": pub_ts,
        })
    return out
