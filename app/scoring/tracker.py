"""Backtest tracker — user-triggered.

A pick becomes a tracked recommendation only when the user explicitly
clicks **Track this pick** on a card in Discover. We treat that click
as 'I'm buying this today': the anchor is today, the entry price is
today's price. From that moment on, every time the user opens the
Track Record tab we sample the live price, update the peak, and —
the instant the live price touches the model's target — mark the pick
`target_hit`. Success ratio is computed only over picks the user
chose to track.

Public calls:
- `snapshot_recommendation(...)` — called by the Track button on a card.
  Enforces the momentum ≥ 60 gate and is idempotent per ticker.
- `is_tracking(ticker)` — True if an open or closed snapshot exists.
- `refresh_all_open()` — fetches live quotes for every open pick,
  samples once per 12h, flips to `target_hit` on first touch.
- `delete_recommendation(rec_id)` — stop tracking one pick.
- `clear_all()` — wipe every recommendation. Lets the user start fresh
  after we had the auto-track bug.
- `success_rate()` — aggregate stats.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select

from app.data.live_quote import get_live_quote
from app.db import Company, Recommendation, RecommendationPrice, SessionLocal

# Gate the chart has to clear before we are willing to recommend at all.
MOMENTUM_GATE = 60

# Window inside which the target has to be hit, otherwise the pick expires.
TARGET_WINDOW_DAYS = 365

# How stale a price sample has to be before `refresh_all_open` adds a new one.
SAMPLE_FRESHNESS = timedelta(hours=12)


@dataclass(frozen=True)
class SuccessStats:
    total: int
    open: int
    hit: int
    expired: int
    closed: int
    closed_hit_rate: float | None       # hit / closed, as a percentage
    avg_days_to_target: float | None    # on hits only
    avg_return_on_hit: float | None     # on hits, (hit_price/entry - 1) * 100
    avg_return_open: float | None       # on open picks, last sample vs entry


def is_tracking(ticker: str) -> bool:
    """True if the user has already added `ticker` to Track Record."""
    with SessionLocal() as s:
        return s.execute(
            select(func.count(Recommendation.id)).where(Recommendation.ticker == ticker)
        ).scalar() > 0


def snapshot_recommendation(
    *,
    ticker: str,
    entry_price: float,
    target_price: float | None,
    upside_pct: float | None,
    composite: float | None,
    momentum: int,
    growth: float | None,
    verdict: str,
    reasons: list[str] | None = None,
) -> Recommendation | None:
    """Add `ticker` to Track Record, 'buying' it at today's price.

    Returns the Recommendation. Idempotent per ticker — a second click on
    the same ticker returns the existing row without changes.
    Returns None if the pick doesn't clear the momentum gate.
    """
    if momentum < MOMENTUM_GATE:
        return None
    if entry_price is None or entry_price <= 0:
        return None

    with SessionLocal() as s:
        existing = s.execute(
            select(Recommendation).where(Recommendation.ticker == ticker)
        ).scalar_one_or_none()
        if existing is not None:
            s.refresh(existing)
            s.expunge(existing)
            return existing

        now = datetime.utcnow()
        rec = Recommendation(
            ticker=ticker,
            recommended_at=now,
            entry_price=float(entry_price),
            target_price=float(target_price) if target_price else None,
            upside_pct_at_entry=float(upside_pct) if upside_pct is not None else None,
            composite_at_entry=float(composite) if composite is not None else None,
            momentum_at_entry=int(momentum),
            growth_at_entry=float(growth) if growth is not None else None,
            verdict_at_entry=verdict,
            reasons=list(reasons or []),
            status="open",
            peak_price=float(entry_price),
            peak_at=now,
            last_checked_at=now,
        )
        s.add(rec)
        s.flush()

        s.add(RecommendationPrice(
            recommendation_id=rec.id,
            sampled_at=now,
            price=float(entry_price),
            pct_change=0.0,
        ))
        s.commit()
        s.refresh(rec)
        s.expunge(rec)
        return rec


def delete_recommendation(rec_id: int) -> bool:
    """Stop tracking one pick. Returns True if a row was removed."""
    with SessionLocal() as s:
        s.query(RecommendationPrice).filter(
            RecommendationPrice.recommendation_id == rec_id
        ).delete(synchronize_session=False)
        n = s.query(Recommendation).filter(Recommendation.id == rec_id).delete(
            synchronize_session=False
        )
        s.commit()
        return n > 0


def clear_all() -> int:
    """Wipe every tracked pick. Returns the number removed."""
    with SessionLocal() as s:
        s.query(RecommendationPrice).delete(synchronize_session=False)
        n = s.query(Recommendation).delete(synchronize_session=False)
        s.commit()
        return n


def _refresh_one(rec: Recommendation, session) -> bool:
    """Append a fresh sample and update status. Returns True if newly hit target."""
    company = session.execute(
        select(Company).where(Company.ticker == rec.ticker)
    ).scalar_one_or_none()
    if company is None:
        return False

    yf_symbol = company.yf_symbol or f"{rec.ticker}.NS"
    quote = get_live_quote(yf_symbol, rec.ticker)
    if not quote or not quote.price:
        return False

    now = datetime.utcnow()
    price = float(quote.price)
    pct_change = (price / rec.entry_price - 1) * 100 if rec.entry_price else 0.0

    last = session.execute(
        select(RecommendationPrice)
        .where(RecommendationPrice.recommendation_id == rec.id)
        .order_by(RecommendationPrice.sampled_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if last is None or (now - last.sampled_at) > SAMPLE_FRESHNESS:
        session.add(RecommendationPrice(
            recommendation_id=rec.id,
            sampled_at=now,
            price=price,
            pct_change=round(pct_change, 2),
        ))

    if rec.peak_price is None or price > rec.peak_price:
        rec.peak_price = price
        rec.peak_at = now
    rec.last_checked_at = now

    newly_hit = False
    if rec.status == "open" and rec.target_price and price >= rec.target_price:
        rec.status = "target_hit"
        rec.target_hit_price = price
        rec.target_hit_at = now
        rec.days_to_target = max(0, (now - rec.recommended_at).days)
        newly_hit = True
    elif rec.status == "open" and (now - rec.recommended_at).days >= TARGET_WINDOW_DAYS:
        rec.status = "expired"

    session.commit()
    return newly_hit


def refresh_all_open() -> tuple[int, int]:
    """Refresh every open recommendation. Returns (refreshed, newly_hit)."""
    refreshed = 0
    hits = 0
    with SessionLocal() as s:
        open_recs = s.execute(
            select(Recommendation).where(Recommendation.status == "open")
        ).scalars().all()
        for rec in open_recs:
            if _refresh_one(rec, s):
                hits += 1
            refreshed += 1
    return refreshed, hits


def success_rate() -> SuccessStats:
    with SessionLocal() as s:
        total = s.execute(select(func.count(Recommendation.id))).scalar() or 0
        hit = s.execute(
            select(func.count(Recommendation.id))
            .where(Recommendation.status == "target_hit")
        ).scalar() or 0
        open_count = s.execute(
            select(func.count(Recommendation.id))
            .where(Recommendation.status == "open")
        ).scalar() or 0
        expired = s.execute(
            select(func.count(Recommendation.id))
            .where(Recommendation.status == "expired")
        ).scalar() or 0
        avg_days = s.execute(
            select(func.avg(Recommendation.days_to_target))
            .where(Recommendation.status == "target_hit")
        ).scalar()
        hit_rows = s.execute(
            select(Recommendation.entry_price, Recommendation.target_hit_price)
            .where(Recommendation.status == "target_hit",
                   Recommendation.target_hit_price.isnot(None))
        ).all()
        if hit_rows:
            rets = [(hp / ep - 1) * 100 for ep, hp in hit_rows if ep]
            avg_return_hit = sum(rets) / len(rets) if rets else None
        else:
            avg_return_hit = None

        open_latest = s.execute(
            select(Recommendation.id, Recommendation.entry_price)
            .where(Recommendation.status == "open")
        ).all()
        open_returns: list[float] = []
        for rid, entry in open_latest:
            if not entry:
                continue
            last = s.execute(
                select(RecommendationPrice.price)
                .where(RecommendationPrice.recommendation_id == rid)
                .order_by(RecommendationPrice.sampled_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            if last:
                open_returns.append((last / entry - 1) * 100)
        avg_return_open = sum(open_returns) / len(open_returns) if open_returns else None

    closed = hit + expired
    closed_hit_rate = (hit / closed * 100) if closed else None
    return SuccessStats(
        total=total,
        open=open_count,
        hit=hit,
        expired=expired,
        closed=closed,
        closed_hit_rate=closed_hit_rate,
        avg_days_to_target=float(avg_days) if avg_days is not None else None,
        avg_return_on_hit=avg_return_hit,
        avg_return_open=avg_return_open,
    )
