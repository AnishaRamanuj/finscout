"""Backtest tracker: snapshot every pick on the day we recommend it,
sample the price forward, and measure how often we hit the target.

Three public calls:

- `snapshot_recommendation(...)` — called from Discover when a pick is shown.
  Idempotent per (ticker, same calendar day): running it twice in one day
  does nothing the second time.
- `refresh_all_open()` — called from the Track Record tab's refresh button.
  For every open recommendation it fetches the latest live quote, appends a
  price sample if the last one is stale, updates the running peak, and
  marks the pick `target_hit` the instant the live price touches the target.
- `success_rate()` — aggregate stats: hit rate on closed picks, average
  days-to-target, open / hit / expired counts.
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
    """Create a snapshot row for `ticker` if we haven't already today.

    The momentum gate is enforced here as a second line of defence — a
    caller that forgets to filter still can't persist a pick below the bar.
    """
    if momentum < MOMENTUM_GATE:
        return None
    if entry_price is None or entry_price <= 0:
        return None

    today = datetime.utcnow().date()
    with SessionLocal() as s:
        existing = s.execute(
            select(Recommendation).where(
                Recommendation.ticker == ticker,
                func.date(Recommendation.recommended_at) == today,
            )
        ).scalar_one_or_none()
        if existing is not None:
            # Load every column before the session closes so callers can
            # safely read the detached instance.
            s.refresh(existing)
            s.expunge(existing)
            return existing

        rec = Recommendation(
            ticker=ticker,
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
            peak_at=datetime.utcnow(),
            last_checked_at=datetime.utcnow(),
        )
        s.add(rec)
        s.flush()   # assigns rec.id without ending the transaction

        s.add(RecommendationPrice(
            recommendation_id=rec.id,
            sampled_at=rec.recommended_at,
            price=float(entry_price),
            pct_change=0.0,
        ))
        s.commit()
        # Reload all columns, then detach so attrs survive session close.
        s.refresh(rec)
        s.expunge(rec)
        return rec


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
        # Average realised return on hits.
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

        # Average mark-to-market return on open picks (using latest sample).
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
