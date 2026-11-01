"""Discover — the "What should I buy?" page.

Designed for a first-time investor. Each pick is one card with:
  - Verdict badge (STRONG PICK / PICK / HOLD / WATCH / AVOID)
  - Company name + sector
  - 3 numbers only: Price, 1-year return, Market cap
  - AI paragraph explaining why, with a Risk line
  - Price chart
  - One button → full research page

Deeper breakdowns (factor scores, ratios, peers) live on Deep Dive,
hidden behind collapsible sections.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import select, desc

from app.db import SessionLocal, Score, Company, WhyNow, Financials
from app.scoring.verdict import verdict_for
from app.ui._styles import inject, badge


def _goto_deep_dive(ticker: str):
    st.session_state.fs_selected_ticker = ticker
    st.session_state.fs_tab = "Research a Stock"


def render():
    inject()

    st.markdown('<div class="fs-header-title">This Week\'s AI Picks</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="fs-header-sub">Our AI reads the market every night and ranks the strongest 500+ Indian stocks. Here are its top picks right now.</div>',
        unsafe_allow_html=True,
    )

    with SessionLocal() as s:
        rows = s.execute(
            select(Score, Company)
            .join(Company, Score.ticker == Company.ticker)
            .where(Company.current_price.isnot(None))
            .order_by(desc(Score.composite))
            .limit(50)
        ).all()

    if not rows:
        st.info("No data yet. Run `python -m app.jobs.nightly 500 nifty500` to populate.")
        return

    # Simple controls — tucked inline, no feature-explainer paragraph.
    picks_to_show = st.slider("How many picks to show?", 3, 20, 6, key="dc_count")

    filtered = []
    for score, company in rows:
        v = verdict_for(score.composite)
        if v.label in ("Watch", "Avoid"):
            continue
        filtered.append((score, company, v))
        if len(filtered) >= picks_to_show:
            break

    for i, row in enumerate(filtered):
        _render_pick(row, hero=(i == 0))


def _render_pick(row, hero: bool):
    score, company, v = row
    card_class = "fs-card fs-hero" if hero else "fs-card"

    st.markdown(f'<div class="{card_class}">', unsafe_allow_html=True)

    # Row 1: verdict + ticker + name
    st.markdown(
        f"{badge(v.label, v.color, v.text_color)} &nbsp;"
        f'<span style="color:#9ca3af;font-size:13px;">{company.sector or "—"}</span>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div style="font-size:22px;font-weight:700;margin-top:6px;margin-bottom:4px;">{company.name} '
        f'<span style="color:#9ca3af;font-weight:500;">({company.ticker})</span></div>',
        unsafe_allow_html=True,
    )

    # Row 2: the three numbers that actually matter
    cols = st.columns(3)
    _stat(cols[0], "Price", _fmt_price(company.current_price))
    _stat(cols[1], "Last year", _fmt_pct(company.pct_change_1y), delta=True)
    _stat(cols[2], "Size", _fmt_cr(company.market_cap))

    # Row 3: the story
    with SessionLocal() as s:
        why = s.execute(
            select(WhyNow).where(WhyNow.ticker == company.ticker)
            .order_by(desc(WhyNow.generated_at)).limit(1)
        ).scalar_one_or_none()
        fin = s.execute(
            select(Financials).where(Financials.ticker == company.ticker)
            .order_by(desc(Financials.fetched_at)).limit(1)
        ).scalar_one_or_none()

    if why and why.text:
        parts = why.text.strip().split("Risk:")
        story = parts[0].replace("Why Now:", "").strip()
        st.markdown(f'<div class="fs-why">{story}</div>', unsafe_allow_html=True)
        if len(parts) > 1:
            st.markdown(f'<div class="fs-risk"><b>Risk:</b> {parts[1].strip()}</div>', unsafe_allow_html=True)

    # Row 4: chart (hero only — keeps non-hero cards short)
    if hero:
        _chart(fin)

    # Row 5: single call-to-action
    st.button(
        f"See full details for {company.ticker} →",
        key=f"dd_{company.ticker}",
        type="primary" if hero else "secondary",
        use_container_width=True,
        on_click=_goto_deep_dive,
        args=(company.ticker,),
    )

    st.markdown("</div>", unsafe_allow_html=True)


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


def _fmt_cr(v):
    if not v:
        return "—"
    cr = v / 1e7
    if cr >= 100_000:
        return f"₹{cr/1_00_000:.1f}L Cr"
    if cr >= 1000:
        return f"₹{cr/1000:.0f}k Cr"
    return f"₹{cr:,.0f} Cr"
