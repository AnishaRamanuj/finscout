"""Peer comparison — sector median for each tracked metric.

A company that scores 60/100 in isolation reads differently if its sector
median is 40 vs 75. These helpers surface that context on the Deep Dive page.
"""
from __future__ import annotations

from statistics import median
from typing import Any

from sqlalchemy import select

from app.db import SessionLocal, Company, Score, Financials


def sector_median(sector: str | None, metric: str) -> float | None:
    """Median of `metric` across every company in `sector`.

    `metric` can live on Score, Company or Financials.
    """
    if not sector:
        return None
    values: list[float] = []
    with SessionLocal() as s:
        rows = s.execute(
            select(Company, Score, Financials)
            .join(Score, Score.ticker == Company.ticker)
            .outerjoin(Financials, Financials.ticker == Company.ticker)
            .where(Company.sector == sector)
        ).all()
        for company, score, fin in rows:
            v = _resolve(metric, company, score, fin)
            if v is not None:
                values.append(float(v))
    if not values:
        return None
    return float(median(values))


def _resolve(metric: str, company: Company, score: Score, fin: Financials | None) -> Any:
    if score and hasattr(score, metric):
        return getattr(score, metric)
    if company and hasattr(company, metric):
        return getattr(company, metric)
    if fin and hasattr(fin, metric):
        return getattr(fin, metric)
    return None


def peer_table(sector: str | None, this_ticker: str, metrics: list[str]) -> list[dict]:
    """Return the sector peers for this_ticker with their value on each metric.

    Row shape: {ticker, name, <metric1>, <metric2>, ...}
    """
    if not sector:
        return []
    out: list[dict] = []
    with SessionLocal() as s:
        rows = s.execute(
            select(Company, Score, Financials)
            .join(Score, Score.ticker == Company.ticker)
            .outerjoin(Financials, Financials.ticker == Company.ticker)
            .where(Company.sector == sector)
        ).all()
        for company, score, fin in rows:
            row = {"Ticker": company.ticker, "Name": company.name}
            for m in metrics:
                v = _resolve(m, company, score, fin)
                row[m] = round(float(v), 2) if v is not None else None
            out.append(row)
    out.sort(key=lambda r: (0 if r["Ticker"] == this_ticker else 1,
                            -(r.get("composite") or 0)))
    return out[:12]
