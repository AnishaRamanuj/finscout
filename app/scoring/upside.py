"""Upside / "room to grow" calculator.

Answers two questions for every stock:
  1. **How much is it currently undervalued?** — by comparing its P/E to
     peers in the same sector, with bumps for quality (ROCE) and growth,
     and a bump down for stocks that have already rallied hard.
  2. **What's a reasonable 12-18 month target price?** — derived from the
     "fair P/E" the model thinks it deserves, applied to current earnings.

Nothing predicts a stock price. These are **model-based estimates** that
help a retail investor compare opportunities, not guarantees.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UpsideEstimate:
    target_price: float | None
    upside_pct: float | None       # (target / current - 1) * 100
    is_hidden_gem: bool            # strong fundamentals + hasn't rallied yet
    reasons: list[str]             # short bullets explaining the number


def compute_upside(
    *,
    current_price: float | None,
    pe: float | None,
    roce: float | None,              # as a decimal, e.g. 0.25 for 25%
    growth_score: float | None,      # 0-100
    quality_score: float | None,     # 0-100
    composite_score: float | None,   # 0-100
    pct_change_1y: float | None,     # % change in last year
    peer_median_pe: float | None,    # sector median P/E
) -> UpsideEstimate:
    reasons: list[str] = []

    if not current_price or not pe or pe <= 0:
        return UpsideEstimate(None, None, False, [])

    # Anchor: start at the sector median P/E (if we have it), else assume no re-rating.
    anchor_pe = peer_median_pe if peer_median_pe and peer_median_pe > 0 else pe

    # Growth bump: high-growth stocks earn a premium multiple.
    growth_bump = 1.0
    if (growth_score or 0) >= 80:
        growth_bump = 1.25
        reasons.append("Growth score is strong — markets usually pay a premium multiple for growers.")
    elif (growth_score or 0) >= 60:
        growth_bump = 1.12

    # Quality bump: high ROCE deserves higher multiples.
    quality_bump = 1.0
    roce_pct = (roce or 0) * 100
    if roce_pct >= 25:
        quality_bump = 1.15
        reasons.append(f"ROCE of {roce_pct:.0f}% is excellent — capital-efficient businesses re-rate higher.")
    elif roce_pct >= 15:
        quality_bump = 1.08

    # 1-year rally penalty: already-rallied stocks have less headroom.
    rally_adj = 1.0
    y1 = pct_change_1y or 0
    if y1 < -20:
        rally_adj = 1.25
        reasons.append(f"Down {abs(y1):.0f}% last year — contrarian setup, more room if fundamentals turn.")
    elif y1 < 0:
        rally_adj = 1.15
        reasons.append(f"Hasn't moved in 12 months ({y1:+.0f}%) despite the fundamentals.")
    elif y1 < 20:
        rally_adj = 1.05
    elif y1 > 100:
        rally_adj = 0.75
        reasons.append(f"Already up {y1:.0f}% in 12 months — most of the easy upside is in.")
    elif y1 > 50:
        rally_adj = 0.88

    fair_pe = anchor_pe * growth_bump * quality_bump * rally_adj

    # Target price: scale current price by (fair_pe / current_pe)
    target_price = current_price * (fair_pe / pe)
    upside_pct = (target_price / current_price - 1) * 100

    # Clamp sanity bounds — our model isn't magic.
    upside_pct = max(-40.0, min(150.0, upside_pct))
    target_price = current_price * (1 + upside_pct / 100)

    # Hidden gem = good fundamentals + hasn't rallied + decent upside
    is_hidden_gem = (
        (composite_score or 0) >= 55
        and y1 < 30
        and upside_pct >= 25
    )
    if is_hidden_gem:
        reasons.insert(0, "💎 Hidden gem — strong fundamentals, hasn't been noticed by the market yet.")

    if peer_median_pe and peer_median_pe > pe * 1.2:
        reasons.append(
            f"Trades at P/E {pe:.1f} vs sector median {peer_median_pe:.1f} — materially cheaper than peers."
        )

    return UpsideEstimate(
        target_price=round(target_price, 2),
        upside_pct=round(upside_pct, 1),
        is_hidden_gem=is_hidden_gem,
        reasons=reasons[:4],
    )
