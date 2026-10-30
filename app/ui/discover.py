"""Discover — AI-curated weekly stock picks for retail investors.

The whole page answers one question: "Which stocks should I buy right now?"
Each pick carries a plain-English verdict, the AI's Why-Now story, and the
key numbers behind the call.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import select, desc, asc

from app.db import SessionLocal, Score, Company, WhyNow, Financials
from app.scoring.verdict import verdict_for
from app.ui._styles import inject, badge


def render():
    inject()

    st.markdown('<div class="fs-header-title">Discover — This Week\'s AI Picks</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="fs-header-sub">Not sure where to put your money? Start here. Each pick shows what to do, why, and what the risk is.</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="fs-help-box">'
        "<b>How to read this page.</b> Each card shows a <b>Verdict</b> (Strong Pick / Pick / Hold / Watch / Avoid), "
        "a one-paragraph <b>Why Now</b> written by our AI, and the <b>numbers</b> behind the call. "
        "Pick 3–8 names across different sectors — don't put everything into one."
        "</div>",
        unsafe_allow_html=True,
    )

    with SessionLocal() as s:
        all_rows = s.execute(
            select(Score, Company)
            .join(Company, Score.ticker == Company.ticker)
            .order_by(desc(Score.composite))
        ).all()

    if not all_rows:
        st.info("No data yet. Run `python -m app.jobs.nightly 100 nifty100` to populate.")
        return

    sectors = sorted({c.sector for _, c in all_rows if c.sector})
    verdicts = ["Strong Pick", "Pick", "Hold", "Watch", "Avoid"]

    f1, f2, f3 = st.columns([2, 2, 1])
    with f1:
        chosen_sectors = st.multiselect("Sector", sectors, default=sectors)
    with f2:
        chosen_verdicts = st.multiselect("Verdict", verdicts, default=["Strong Pick", "Pick"])
    with f3:
        limit = st.slider("Show top", 3, 30, 10)

    filtered = []
    for score, company in all_rows:
        v = verdict_for(score.composite)
        if company.sector not in chosen_sectors and company.sector is not None:
            continue
        if v.label not in chosen_verdicts:
            continue
        filtered.append((score, company, v))

    filtered = filtered[:limit]
    if not filtered:
        st.warning("No picks match these filters. Loosen them to see more.")
        return

    st.caption(f"Showing {len(filtered)} picks")
    st.markdown("")

    _render_pick(filtered[0], hero=True)
    for row in filtered[1:]:
        _render_pick(row, hero=False)


def _render_pick(row, hero: bool):
    score, company, v = row
    card_class = "fs-card fs-hero" if hero else "fs-card"

    with st.container():
        st.markdown(f'<div class="{card_class}">', unsafe_allow_html=True)

        top_l, top_r = st.columns([5, 1])
        with top_l:
            st.markdown(
                f"**{badge(v.label, v.color, v.text_color)}** &nbsp; "
                f'<span style="color:#9ca3af;font-size:13px;">{company.sector or "—"} · '
                f'₹{(company.market_cap or 0) / 1e7:,.0f} Cr mkt cap</span>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div style="font-size:22px;font-weight:700;margin-top:4px;">{company.name} '
                f'<span style="color:#9ca3af;font-weight:500;">({company.ticker})</span></div>',
                unsafe_allow_html=True,
            )
        with top_r:
            st.markdown(
                f'<div style="text-align:right;"><div class="fs-stat">Score</div>'
                f'<div style="font-size:34px;font-weight:700;color:{v.color};">{score.composite:.0f}</div></div>',
                unsafe_allow_html=True,
            )

        st.markdown(f'<div class="fs-why"><i>{v.plain}</i></div>', unsafe_allow_html=True)

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
            story = parts[0].strip()
            risk = parts[1].strip() if len(parts) > 1 else None
            st.markdown(f'<div class="fs-why">{story}</div>', unsafe_allow_html=True)
            if risk:
                st.markdown(f'<div class="fs-risk"><b>Risk:</b> {risk}</div>', unsafe_allow_html=True)
        else:
            st.caption("Why-Now paragraph not generated yet. Run `python -m app.jobs.monday_feed`.")

        _stat_row(company, fin)
        _factor_bars(score)

        _chart_from_raw(fin, hero)

        st.markdown("</div>", unsafe_allow_html=True)


def _stat_row(company, fin):
    cols = st.columns(5)
    _stat(cols[0], "Current Price", _fmt_price(company.current_price))
    _stat(cols[1], "1Y Return", _fmt_pct(company.pct_change_1y), delta_color=True)
    _stat(cols[2], "3M Return", _fmt_pct(company.pct_change_3m), delta_color=True)
    _stat(cols[3], "P/E", _fmt_num(fin.pe) if fin else "—")
    _stat(cols[4], "ROCE", _fmt_pct((fin.roce or 0) * 100) if fin and fin.roce else "—")


def _stat(col, label, value, delta_color=False):
    with col:
        cls = "fs-value"
        if delta_color and value not in ("—",):
            try:
                raw = float(value.strip("%").replace(",", ""))
                cls = "fs-delta-up" if raw >= 0 else "fs-delta-down"
            except Exception:
                pass
        st.markdown(
            f'<div class="fs-stat">{label}</div><div class="{cls}">{value}</div>',
            unsafe_allow_html=True,
        )


def _factor_bars(score):
    st.markdown('<div style="margin-top:14px;"></div>', unsafe_allow_html=True)
    factors = [
        ("Growth", score.growth),
        ("Momentum", score.momentum),
        ("Valuation", score.valuation),
        ("Sentiment", score.sentiment),
        ("Insider", score.insider),
        ("Quality", score.quality),
    ]
    cols = st.columns(len(factors))
    for col, (name, val) in zip(cols, factors):
        col.progress(int(val or 0), text=f"{name} {val or 0:.0f}")


def _chart_from_raw(fin, hero: bool):
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
    fig = go.Figure(go.Scatter(x=df["date"], y=df["close"], mode="lines",
                               line=dict(color="#60a5fa", width=2),
                               fill="tozeroy", fillcolor="rgba(96,165,250,0.08)"))
    fig.update_layout(
        height=180 if hero else 140,
        margin=dict(l=0, r=0, t=20, b=0),
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
    return f"₹{v:,.2f}"


def _fmt_pct(v):
    if v is None:
        return "—"
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.1f}%"


def _fmt_num(v):
    if v is None:
        return "—"
    return f"{v:.1f}"
