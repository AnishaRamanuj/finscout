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
from sqlalchemy import select

from app.db import SessionLocal, Deal

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


def _col(row, *candidates):
    for c in candidates:
        if c in row.index and pd.notna(row[c]):
            return row[c]
    return None


def persist_todays_deals() -> int:
    """Fetch today's bulk + block CSVs and insert each row into the deals table.

    Idempotent per (ticker, deal_date, client, side, qty): existing rows are kept.
    Returns the number of new rows inserted.
    """
    inserted = 0
    with SessionLocal() as s:
        for kind, df in (("bulk", fetch_bulk_deals()), ("block", fetch_block_deals())):
            if df.empty:
                continue
            for _, row in df.iterrows():
                ticker = _col(row, "symbol")
                if not ticker:
                    continue
                ticker = str(ticker).upper()
                raw_date = _col(row, "date")
                try:
                    deal_date = pd.to_datetime(raw_date, dayfirst=True, errors="coerce")
                    if pd.isna(deal_date):
                        deal_date = datetime.utcnow()
                except Exception:
                    deal_date = datetime.utcnow()
                client = str(_col(row, "client_name") or "")[:255]
                side = str(_col(row, "buy_sell") or "")[:4].upper()
                qty = _col(row, "quantity_traded", "quantity")
                price = _col(row, "trade_price_wght._avg._price", "trade_price", "price")
                remarks = _col(row, "remarks")

                dup = s.execute(
                    select(Deal.id)
                    .where(Deal.ticker == ticker)
                    .where(Deal.deal_date == deal_date)
                    .where(Deal.client_name == client)
                    .where(Deal.side == side)
                    .where(Deal.quantity == (float(qty) if qty is not None else None))
                    .limit(1)
                ).scalar_one_or_none()
                if dup:
                    continue

                s.add(Deal(
                    ticker=ticker,
                    kind=kind,
                    deal_date=deal_date,
                    client_name=client,
                    side=side,
                    quantity=float(qty) if qty is not None else None,
                    price=float(price) if price is not None else None,
                    remarks=str(remarks) if remarks is not None else None,
                ))
                inserted += 1
        s.commit()
    return inserted
