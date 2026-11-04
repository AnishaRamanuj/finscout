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

from sqlalchemy import desc, func, select

from app.data.live_quote import get_live_quote
from app.db import Company, Financials, Recommendation, RecommendationPrice, SessionLocal, WhyNow

# Gate the chart has to clear before we are willing to recommend at all.
MOMENTUM_GATE = 60

# Window inside which the target has to be hit, otherwise the pick expires.
TARGET_WINDOW_DAYS = 365

# How stale a price sample has to be before `refresh_all_open` adds a new one.
SAMPLE_FRESHNESS = timedelta(hours=12)

# Backfill cadence when we replay historical samples from Financials.raw.price_1y.
BACKFILL_CADENCE_DAYS = 7


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


def _closes_for(ticker: str, session) -> dict[str, float]:
    """Return the cached daily closes for `ticker` as {YYYY-MM-DD: price}."""
    fin = session.execute(
        select(Financials).where(Financials.ticker == ticker)
        .order_by(desc(Financials.fetched_at)).limit(1)
    ).scalar_one_or_none()
    if not fin or not fin.raw:
        return {}
    raw = (fin.raw.get("price_1y") or {}).get("Close") or {}
    out: dict[str, float] = {}
    for k, v in raw.items():
        try:
            out[str(k)[:10]] = float(v)
        except (TypeError, ValueError):
            continue
    return out


def _price_on_or_near(closes: dict[str, float], when: datetime) -> float | None:
    """Return the close on `when`, else the most recent close before it."""
    if not closes:
        return None
    target = when.date().isoformat()
    best_key: str | None = None
    for k in closes.keys():
        if k <= target and (best_key is None or k > best_key):
            best_key = k
    if best_key is None:
        # `when` predates our price history — fall back to the oldest close.
        best_key = min(closes.keys())
    return closes[best_key]


def _earliest_recommendation_date(ticker: str, session) -> datetime | None:
    """Earliest WhyNow timestamp for this ticker — our proxy for 'first recommended'."""
    return session.execute(
        select(func.min(WhyNow.generated_at)).where(WhyNow.ticker == ticker)
    ).scalar_one_or_none()


def _resolve_anchor(
    ticker: str, fallback_price: float, session
) -> tuple[datetime, float, bool]:
    """Pick the recommendation date + entry price.

    Returns (recommended_at, entry_price, from_history). `from_history` is
    True when we successfully recovered an earlier date and the close price
    on that date; False means we fell back to today + today's price.
    """
    now = datetime.utcnow()
    earliest = _earliest_recommendation_date(ticker, session)
    if earliest is None or earliest >= now:
        return now, fallback_price, False
    closes = _closes_for(ticker, session)
    historical = _price_on_or_near(closes, earliest)
    if historical is None or historical <= 0:
        return now, fallback_price, False
    return earliest, historical, True


def _backfill_samples(
    rec_id: int, anchor: datetime, entry_price: float, closes: dict[str, float], session
) -> int:
    """Insert one sample at the anchor and ~weekly samples through to today."""
    if not closes:
        return 0
    anchor_key = anchor.date().isoformat()
    today_key = datetime.utcnow().date().isoformat()
    inserted = 0
    last_at: datetime | None = None
    for d_str in sorted(closes.keys()):
        if d_str < anchor_key or d_str > today_key:
            continue
        try:
            d = datetime.fromisoformat(d_str)
        except ValueError:
            continue
        if last_at is not None and (d - last_at).days < BACKFILL_CADENCE_DAYS:
            continue
        price = closes[d_str]
        pct = (price / entry_price - 1) * 100 if entry_price else 0.0
        session.add(RecommendationPrice(
            recommendation_id=rec_id,
            sampled_at=d,
            price=price,
            pct_change=round(pct, 2),
        ))
        last_at = d
        inserted += 1
    return inserted


def _peak_in(closes: dict[str, float], anchor: datetime) -> tuple[float | None, datetime | None]:
    """Highest close between anchor and today (inclusive), with its date."""
    if not closes:
        return None, None
    anchor_key = anchor.date().isoformat()
    today_key = datetime.utcnow().date().isoformat()
    best_price: float | None = None
    best_date: datetime | None = None
    for d_str, price in closes.items():
        if d_str < anchor_key or d_str > today_key:
            continue
        if best_price is None or price > best_price:
            best_price = price
            try:
                best_date = datetime.fromisoformat(d_str)
            except ValueError:
                best_date = None
    return best_price, best_date


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
    """Create a snapshot row for `ticker` if we don't already have one.

    The recommendation is anchored to the earliest WhyNow timestamp for
    this ticker (the day the model first put a pick on the board), with
    the close price on that date as the entry. If we have no earlier
    WhyNow, we fall back to today + today's price. Idempotent per ticker.
    """
    if momentum < MOMENTUM_GATE:
        return None
    if entry_price is None or entry_price <= 0:
        return None

    with SessionLocal() as s:
        # Idempotent per ticker: if any snapshot already exists for this
        # ticker we keep it (the repair pass re-anchors older wrong ones).
        existing = s.execute(
            select(Recommendation).where(Recommendation.ticker == ticker)
        ).scalar_one_or_none()
        if existing is not None:
            s.refresh(existing)
            s.expunge(existing)
            return existing

        anchor_dt, anchor_price, from_history = _resolve_anchor(ticker, entry_price, s)
        closes = _closes_for(ticker, s) if from_history else {}

        rec = Recommendation(
            ticker=ticker,
            recommended_at=anchor_dt,
            entry_price=float(anchor_price),
            target_price=float(target_price) if target_price else None,
            upside_pct_at_entry=float(upside_pct) if upside_pct is not None else None,
            composite_at_entry=float(composite) if composite is not None else None,
            momentum_at_entry=int(momentum),
            growth_at_entry=float(growth) if growth is not None else None,
            verdict_at_entry=verdict,
            reasons=list(reasons or []),
            status="open",
            peak_price=float(anchor_price),
            peak_at=anchor_dt,
            last_checked_at=datetime.utcnow(),
        )
        s.add(rec)
        s.flush()

        # Always record the anchor as sample #1.
        s.add(RecommendationPrice(
            recommendation_id=rec.id,
            sampled_at=anchor_dt,
            price=float(anchor_price),
            pct_change=0.0,
        ))
        # If the anchor was in the past, backfill weekly samples through today.
        if from_history:
            _backfill_samples(rec.id, anchor_dt, float(anchor_price), closes, s)
            peak_price, peak_date = _peak_in(closes, anchor_dt)
            if peak_price is not None and peak_price > rec.peak_price:
                rec.peak_price = peak_price
                rec.peak_at = peak_date or rec.peak_at

        s.commit()
        s.refresh(rec)
        s.expunge(rec)
        return rec


def reanchor_misdated_opens() -> int:
    """Repair open snapshots that were anchored to today because an earlier
    WhyNow record wasn't consulted. Moves the entry back to the earliest
    WhyNow timestamp, rewrites the entry price to the close on that date,
    and backfills samples. Returns the number of rows fixed.

    Idempotent — running it twice on the same data does nothing the second
    time, because the second run finds `recommended_at` already matches the
    earliest WhyNow.
    """
    fixed = 0
    with SessionLocal() as s:
        opens = s.execute(
            select(Recommendation).where(Recommendation.status == "open")
        ).scalars().all()
        for rec in opens:
            earliest = _earliest_recommendation_date(rec.ticker, s)
            if earliest is None:
                continue
            # Only re-anchor if the real recommendation predates the current entry.
            if earliest.date() >= rec.recommended_at.date():
                continue
            closes = _closes_for(rec.ticker, s)
            historical = _price_on_or_near(closes, earliest)
            if historical is None or historical <= 0:
                continue

            rec.recommended_at = earliest
            rec.entry_price = float(historical)
            # Rewrite samples: drop the wrong ones, lay down fresh ones.
            s.query(RecommendationPrice).filter(
                RecommendationPrice.recommendation_id == rec.id
            ).delete(synchronize_session=False)
            s.add(RecommendationPrice(
                recommendation_id=rec.id,
                sampled_at=earliest,
                price=float(historical),
                pct_change=0.0,
            ))
            _backfill_samples(rec.id, earliest, float(historical), closes, s)
            peak_price, peak_date = _peak_in(closes, earliest)
            if peak_price is not None:
                rec.peak_price = peak_price
                rec.peak_at = peak_date or earliest
            s.commit()
            fixed += 1
    return fixed


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
