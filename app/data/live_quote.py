"""Real-time quote fetcher — yfinance primary, NSE direct as a fallback.

Returns the current (or latest known) price, today's cumulative traded
volume, and a 30-day average volume so the UI can flag unusual activity.

Primary: `yf.Ticker(symbol).fast_info` + a short price history.
  - No API key, no account.
  - Updates every ~15 min during IST market hours.
  - Occasionally throttled by Yahoo under heavy use.

Fallback: NSE's own public quote endpoint.
  - `https://www.nseindia.com/api/quote-equity?symbol=TCS`
  - Needs cookie warm-up (hit nseindia.com first); the session is
    cached and refreshed every 5 minutes.
  - Returns last price, intraday high/low, cumulative volume.

If you want true tick-by-tick, swap `_fetch_yfinance` for a Zerodha
Kite / Upstox / AngelOne call. Everything else keeps working.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache

import httpx
import yfinance as yf


@dataclass(frozen=True)
class LiveQuote:
    symbol: str
    price: float | None
    volume_today: int | None
    avg_volume_30d: int | None
    volume_surge: float | None    # today / 30d avg
    day_high: float | None
    day_low: float | None
    prev_close: float | None
    last_update: datetime
    source: str                   # "yfinance" | "nse" | "stale"


# ---- NSE session ----------------------------------------------------------
_nse_client: httpx.Client | None = None
_nse_session_at: float = 0.0
_NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
        "AppleWebKit/537.36 (KHTML, like Gecko) FinScout"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}


def _nse_session() -> httpx.Client:
    """Lazily build an httpx.Client with warm NSE cookies. Rebuilt every 5 min."""
    global _nse_client, _nse_session_at
    if _nse_client is None or (time.time() - _nse_session_at) > 300:
        _nse_client = httpx.Client(headers=_NSE_HEADERS, timeout=10.0, follow_redirects=True)
        try:
            _nse_client.get("https://www.nseindia.com/")
            _nse_session_at = time.time()
        except Exception:
            pass
    return _nse_client


# ---- yfinance fetcher -----------------------------------------------------
def _fetch_yfinance(yf_symbol: str) -> LiveQuote | None:
    try:
        t = yf.Ticker(yf_symbol)
        info = t.fast_info or {}
        hist = t.history(period="30d", interval="1d")
        avg_vol = int(hist["Volume"].mean()) if not hist.empty else None
        today_vol = None
        if not hist.empty:
            today_vol = int(hist["Volume"].iloc[-1])
        last_vol = info.get("last_volume")
        if last_vol:
            today_vol = int(last_vol)
        surge = round(today_vol / avg_vol, 2) if (avg_vol and today_vol) else None

        price = info.get("last_price") or info.get("lastPrice")
        return LiveQuote(
            symbol=yf_symbol,
            price=float(price) if price else None,
            volume_today=today_vol,
            avg_volume_30d=avg_vol,
            volume_surge=surge,
            day_high=info.get("day_high"),
            day_low=info.get("day_low"),
            prev_close=info.get("previous_close"),
            last_update=datetime.now(),
            source="yfinance",
        )
    except Exception:
        return None


# ---- NSE direct fetcher ---------------------------------------------------
def _fetch_nse(nse_symbol: str) -> LiveQuote | None:
    try:
        s = _nse_session()
        r = s.get(f"https://www.nseindia.com/api/quote-equity?symbol={nse_symbol.upper()}")
        r.raise_for_status()
        data = r.json()
        pi = data.get("priceInfo", {}) or {}
        pre = data.get("preOpenMarket", {}) or {}
        intra = pi.get("intraDayHighLow", {}) or {}
        # Cumulative traded volume comes from marketDeptOrderBook.totalTradedVolume (lakhs)
        md = (data.get("marketDeptOrderBook", {}) or {}).get("totalTradedVolume")
        if md:
            # NSE reports in lakhs — multiply by 100,000 for shares
            total_vol = int(float(md) * 100000)
        else:
            total_vol = None
        return LiveQuote(
            symbol=nse_symbol,
            price=pi.get("lastPrice"),
            volume_today=total_vol,
            avg_volume_30d=None,
            volume_surge=None,
            day_high=intra.get("max"),
            day_low=intra.get("min"),
            prev_close=pi.get("previousClose"),
            last_update=datetime.now(),
            source="nse",
        )
    except Exception:
        return None


# ---- Public API with 60s cache -------------------------------------------
@lru_cache(maxsize=512)
def _cached(yf_symbol: str, nse_symbol: str, _bucket: int) -> LiveQuote | None:
    q = _fetch_yfinance(yf_symbol)
    if q and q.price:
        return q
    return _fetch_nse(nse_symbol)


def get_live_quote(yf_symbol: str, nse_symbol: str, bust: bool = False) -> LiveQuote | None:
    """Return the latest known quote (cached up to 60 seconds).

    bust=True clears the current minute's cache so a manual refresh button
    always goes to the network.
    """
    bucket = int(time.time() // 60)
    if bust:
        _cached.cache_clear()
    return _cached(yf_symbol, nse_symbol, bucket)


def format_volume(v: int | None) -> str:
    """Human-readable volume: 12,345 -> '12.3k', 1_234_567 -> '12.3L'."""
    if v is None:
        return "—"
    if v >= 10_000_000:
        return f"{v / 10_000_000:.2f} Cr"
    if v >= 100_000:
        return f"{v / 100_000:.2f} L"
    if v >= 1_000:
        return f"{v / 1_000:.1f} k"
    return str(v)
