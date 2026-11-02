"""Discover — the "What should I buy?" page.

Each pick is one card with:
  - Verdict badge (STRONG PICK / PICK / HIDDEN GEM / HOLD)
  - Company name + sector
  - Price + Target price + Growth potential + 1-year change
  - AI paragraph explaining why, with a Risk line
  - Price chart (hero only)
  - One button → full research page

A toggle at the top lets a user filter to **Hidden Gems only** —
stocks our model rates highly where the price hasn't moved yet.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import select, desc

from app.db import SessionLocal, Score, Company, WhyNow, Financials
from app.scoring.verdict import verdict_for
from app.scoring.upside import compute_upside, UpsideEstimate
from app.scoring.peers import sector_median
from app.scoring.momentum_lite import score_momentum, LiteSignal
from app.ui._styles import inject, badge


HIDDEN_GEM_BADGE_BG = "#8b5cf6"

MOMENTUM_COLOR = {
    "Strong":   ("#16a34a", "#ffffff"),
    "Building": ("#2563eb", "#ffffff"),
    "Mixed":    ("#64748b", "#ffffff"),
    "Fading":   ("#f59e0b", "#111827"),
    "Quiet":    ("#374151", "#d1d5db"),
}


def _goto_deep_dive(ticker: str):
    st.session_state.fs_selected_ticker = ticker
    st.session_state.fs_tab = "Research a Stock"


def render():
    inject()

    st.markdown('<div class="fs-header-title">This Week\'s AI Picks</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="fs-header-sub">Our AI reads the market every night and ranks 700+ Indian stocks by fundamentals and the room they have to run.</div>',
        unsafe_allow_html=True,
    )

    with SessionLocal() as s:
        rows = s.execute(
            select(Score, Company)
            .join(Company, Score.ticker == Company.ticker)
            .where(Company.current_price.isnot(None))
            .order_by(desc(Score.composite))
            .limit(200)
        ).all()

    if not rows:
        st.info("No data yet. Run `python -m app.jobs.nightly 500 nifty500` to populate.")
        return

    c1, c2 = st.columns([3, 1])
    with c1:
        hidden_only = st.toggle(
            "💎 Show only Hidden Gems (strong fundamentals, hasn't rallied yet)",
            value=True,
            help="These are stocks our model rates highly where the price is still below where it 'should' be. Classic 'rising stars' setup.",
        )
    with c2:
        picks_to_show = st.slider("How many picks?", 3, 20, 8, key="dc_count")

    enriched: list[tuple] = []
    sector_pe_cache: dict[str, float | None] = {}
    with st.spinner("Scoring momentum across the universe…"):
        for score, company in rows:
            fin = _latest_fin(company.ticker)
            sector = company.sector
            if sector not in sector_pe_cache:
                sector_pe_cache[sector] = _safe_median_pe(sector)
            est = compute_upside(
                current_price=company.current_price,
                pe=fin.pe if fin else None,
                roce=fin.roce if fin else None,
                growth_score=score.growth,
                quality_score=score.quality,
                composite_score=score.composite,
                pct_change_1y=company.pct_change_1y,
                peer_median_pe=sector_pe_cache[sector],
            )
            v = verdict_for(score.composite)
            if v.label in ("Watch", "Avoid"):
                continue
            price_1y = (fin.raw or {}).get("price_1y") if fin else {}
            mom = score_momentum(company.ticker, price_1y)
            enriched.append((score, company, fin, v, est, mom))

    if hidden_only:
        # Hidden Gem now ALSO requires momentum to not be Fading/Quiet — the
        # chart has to agree with the fundamentals before we flag it.
        enriched = [r for r in enriched if r[4].is_hidden_gem and r[5].label in ("Strong", "Building", "Mixed")]

    # Rank: hidden gems first; then by (composite × upside × momentum) blend.
    enriched.sort(
        key=lambda r: (
            -int(r[4].is_hidden_gem),
            -_combined_rank(r[0].composite, r[4].upside_pct, r[5].score),
        ),
    )
    enriched = enriched[:picks_to_show]

    if not enriched:
        st.warning(
            "No hidden gems match right now. Try turning off the toggle to see the full ranked list."
        )
        return

    for i, row in enumerate(enriched):
        _render_pick(row, hero=(i == 0))


def _render_pick(row, hero: bool):
    score, company, fin, v, est, mom = row
    card_class = "fs-card fs-hero" if hero else "fs-card"

    st.markdown(f'<div class="{card_class}">', unsafe_allow_html=True)

    # Verdict row (hidden-gem + momentum badges piled on when applicable)
    badges_html = badge(v.label, v.color, v.text_color)
    if est.is_hidden_gem:
        badges_html += " &nbsp;" + badge("💎 Hidden Gem", HIDDEN_GEM_BADGE_BG, "#ffffff")
    mom_bg, mom_fg = MOMENTUM_COLOR.get(mom.label, ("#64748b", "#ffffff"))
    badges_html += " &nbsp;" + badge(f"📊 {mom.label} {mom.score}", mom_bg, mom_fg)
    st.markdown(
        f'{badges_html} &nbsp;<span style="color:#9ca3af;font-size:13px;">{company.sector or "—"}</span>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div style="font-size:22px;font-weight:700;margin-top:6px;margin-bottom:4px;">{company.name} '
        f'<span style="color:#9ca3af;font-weight:500;">({company.ticker})</span></div>',
        unsafe_allow_html=True,
    )

    # Five numbers: price, target, upside, 1Y, momentum
    cols = st.columns(5)
    _stat(cols[0], "Price today", _fmt_price(company.current_price))
    _stat(cols[1], "Our target", _fmt_price(est.target_price))
    _stat(cols[2], "Upside", _fmt_pct(est.upside_pct), delta=True)
    _stat(cols[3], "Last year", _fmt_pct(company.pct_change_1y), delta=True)
    _stat(cols[4], "Momentum", f"{mom.score}/100")

    # Why Now
    with SessionLocal() as s:
        why = s.execute(
            select(WhyNow).where(WhyNow.ticker == company.ticker)
            .order_by(desc(WhyNow.generated_at)).limit(1)
        ).scalar_one_or_none()

    if why and why.text:
        parts = why.text.strip().split("Risk:")
        story = parts[0].replace("Why Now:", "").strip()
        st.markdown(f'<div class="fs-why">{story}</div>', unsafe_allow_html=True)
        if len(parts) > 1:
            st.markdown(f'<div class="fs-risk"><b>Risk:</b> {parts[1].strip()}</div>', unsafe_allow_html=True)

    # Combined "why" expander: upside reasons + momentum tells
    reasons_block: list[str] = list(est.reasons)
    mom_tells = _momentum_tells(mom)
    if mom_tells:
        reasons_block.append("**Momentum signals:**")
        reasons_block.extend(f"&nbsp;&nbsp;&nbsp;· {t}" for t in mom_tells)
    if reasons_block:
        with st.expander("Why we think it has room to grow"):
            for r in reasons_block:
                st.markdown(f"- {r}", unsafe_allow_html=True)

    if hero:
        _chart(fin)

    st.button(
        f"See full details for {company.ticker} →",
        key=f"dd_{company.ticker}",
        type="primary" if hero else "secondary",
        use_container_width=True,
        on_click=_goto_deep_dive,
        args=(company.ticker,),
    )

    st.markdown("</div>", unsafe_allow_html=True)


# --- helpers ---------------------------------------------------------------

def _combined_rank(composite: float | None, upside: float | None, momentum: int | None = None) -> float:
    """Rank combining quality, room to grow, and today's momentum confirmation."""
    c = composite or 0
    u = max(0.0, min(100.0, upside or 0))
    m = momentum or 0
    return c + u * 0.35 + m * 0.25


def _momentum_tells(mom: LiteSignal) -> list[str]:
    tells: list[str] = []
    if mom.delivery_pct is not None and mom.delivery_slope is not None:
        if mom.delivery_slope >= 1.0:
            tells.append(
                f"Delivery % at {mom.delivery_pct:.0f}% and climbing +{mom.delivery_slope:.1f}pt/day — "
                "buyers taking delivery, not just day-trading."
            )
        elif mom.delivery_pct >= 50:
            tells.append(f"Delivery % steady at {mom.delivery_pct:.0f}%.")
    if mom.macd_fast_trend == "bullish" and mom.macd_std_trend == "bullish":
        tells.append("Both fast (7,21,9) and standard (12,26,9) MACDs are bullish — timeframes agree.")
    elif mom.macd_fast_trend == "bullish":
        tells.append("Fast MACD (7,21,9) is bullish — early momentum building.")
    elif mom.macd_fast_trend == "bearish" and mom.macd_std_trend == "bearish":
        tells.append("Both MACDs are bearish — chart hasn't confirmed yet.")
    if mom.price_trend == "up":
        tells.append("5-day moving average is pulling above the 20-day — short-term trend is up.")
    return tells


def _latest_fin(ticker: str):
    with SessionLocal() as s:
        return s.execute(
            select(Financials).where(Financials.ticker == ticker)
            .order_by(desc(Financials.fetched_at)).limit(1)
        ).scalar_one_or_none()


def _safe_median_pe(sector: str | None) -> float | None:
    if not sector:
        return None
    try:
        return sector_median(sector, "pe")
    except Exception:
        return None


def _stat(col, label, value, delta=False):
    cls = "fs-value"
    if delta and value not in ("—",):
        try:
            raw = float(str(value).strip("%").replace(",", "").replace("+", ""))
            cls = "fs-delta-up" if raw >= 0 else "fs-delta-down"
        except Exception:
            pass
    col.markdown(
        f'<div class="fs-stat">{label}</div><div class="{cls}">{value}</div>',
        unsafe_allow_html=True,
    )


def _chart(fin):
    if not fin or not fin.raw:
        return
    price_1y = (fin.raw.get("price_1y") or {}).get("Close") or {}
    if not price_1y:
        return
    df = (
        pd.DataFrame({"date": list(price_1y.keys()), "close": list(price_1y.values())})
        .dropna()
        .assign(date=lambda d: pd.to_datetime(d["date"], errors="coerce"))
        .dropna()
        .sort_values("date")
    )
    if df.empty:
        return
    fig = go.Figure(go.Scatter(
        x=df["date"], y=df["close"], mode="lines",
        line=dict(color="#60a5fa", width=2),
        fill="tozeroy", fillcolor="rgba(96,165,250,0.08)",
    ))
    fig.update_layout(
        height=160,
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis=dict(showgrid=False, title=""),
        yaxis=dict(showgrid=False, title="", side="right"),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _fmt_price(v):
    if v is None:
        return "—"
    return f"₹{v:,.0f}"


def _fmt_pct(v):
    if v is None:
        return "—"
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.0f}%"
