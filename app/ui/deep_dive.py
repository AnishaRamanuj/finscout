"""Deep Dive — full breakdown of any ticker, with price chart and AI explainers."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import select, desc

from app.db import SessionLocal, Company, Score, Financials, WhyNow, Deal
from app.scoring.verdict import verdict_for
from app.scoring.peers import peer_table, sector_median
from app.ui._styles import inject, badge
from app.agents.explainer import explain_ratio


METRIC_HINT = {
    "PE":   "Price-to-earnings — lower usually = cheaper, but not always better. Industry PE matters.",
    "P/B":  "Price-to-book — <1 means market values company below its book value. Banks live near 1-2.",
    "ROCE": "Return on capital employed — how efficiently the business uses its money. 15%+ is good.",
}


def render():
    inject()

    with SessionLocal() as s:
        all_tickers = [t for (t,) in s.execute(select(Company.ticker).order_by(Company.ticker)).all()]
    if not all_tickers:
        st.markdown('<div class="fs-header-title">Deep Dive</div>', unsafe_allow_html=True)
        st.info("No companies ingested yet. Run `python -m app.jobs.nightly 100 nifty100`.")
        return

    st.markdown('<div class="fs-header-title">Deep Dive</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="fs-header-sub">Everything our model knows about a single stock.</div>',
        unsafe_allow_html=True,
    )

    pre = st.session_state.get("fs_selected_ticker")
    if pre and pre in all_tickers:
        default = pre
    elif "RELIANCE" in all_tickers:
        default = "RELIANCE"
    else:
        default = all_tickers[0]
    ticker = st.selectbox("Pick a stock", all_tickers,
                          index=all_tickers.index(default))
    # keep selection sticky across tab switches
    st.session_state.fs_selected_ticker = ticker

    with SessionLocal() as s:
        company = s.execute(select(Company).where(Company.ticker == ticker)).scalar_one_or_none()
        score = s.execute(select(Score).where(Score.ticker == ticker)).scalar_one_or_none()
        fin = s.execute(
            select(Financials).where(Financials.ticker == ticker)
            .order_by(desc(Financials.fetched_at))
        ).scalar_one_or_none()
        why = s.execute(
            select(WhyNow).where(WhyNow.ticker == ticker)
            .order_by(desc(WhyNow.generated_at))
        ).scalar_one_or_none()
        deals = s.execute(
            select(Deal).where(Deal.ticker == ticker)
            .order_by(desc(Deal.deal_date)).limit(10)
        ).scalars().all()

    if not company:
        st.warning(f"No data for {ticker}.")
        return

    v = verdict_for(score.composite if score else 50)

    st.markdown(f'<div class="fs-card fs-hero">', unsafe_allow_html=True)

    hdr_l, hdr_r = st.columns([5, 1])
    with hdr_l:
        st.markdown(
            f"**{badge(v.label, v.color, v.text_color)}** &nbsp; "
            f'<span style="color:#9ca3af;font-size:13px;">{company.sector or "—"} · {company.industry or ""}</span>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div style="font-size:26px;font-weight:700;margin-top:4px;">{company.name} '
            f'<span style="color:#9ca3af;font-weight:500;">({company.ticker})</span></div>',
            unsafe_allow_html=True,
        )
    with hdr_r:
        if score:
            st.markdown(
                f'<div style="text-align:right;"><div class="fs-stat">Score</div>'
                f'<div style="font-size:40px;font-weight:700;color:{v.color};">{score.composite:.0f}</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown(f'<div class="fs-why"><i>{v.plain}</i></div>', unsafe_allow_html=True)

    if why and why.text:
        parts = why.text.split("Risk:")
        st.markdown(f'<div class="fs-why">{parts[0].strip()}</div>', unsafe_allow_html=True)
        if len(parts) > 1:
            st.markdown(f'<div class="fs-risk"><b>Risk:</b> {parts[1].strip()}</div>', unsafe_allow_html=True)
    else:
        st.caption("Why-Now paragraph not generated yet. Run `python -m app.jobs.monday_feed`.")

    st.markdown("</div>", unsafe_allow_html=True)

    # Price chart
    _price_chart(fin, ticker)

    # Key stats
    st.markdown("### Key numbers")
    cols = st.columns(5)
    _stat(cols[0], "Market Cap", _fmt_cr(company.market_cap))
    _stat(cols[1], "Current Price", _fmt_price(company.current_price))
    _stat(cols[2], "1Y Return", _fmt_pct(company.pct_change_1y), delta=True)
    _stat(cols[3], "3M Return", _fmt_pct(company.pct_change_3m), delta=True)
    _stat(cols[4], "1M Return", _fmt_pct(company.pct_change_1m), delta=True)

    # Factor breakdown
    if score:
        st.markdown("### How we scored it")
        for factor, weight in [
            ("growth", "25%"), ("profitability", "20%"), ("momentum", "20%"),
            ("insider", "10%"), ("sentiment", "10%"), ("valuation", "10%"), ("quality", "5%"),
        ]:
            val = getattr(score, factor) or 0
            st.progress(int(val), text=f"{factor.title()} ({weight} weight) — {val:.0f}/100")

    # Ratios with AI explain
    if fin:
        st.markdown("### Ratios")
        for name, value in [("PE", fin.pe), ("P/B", fin.pb), ("ROCE", (fin.roce or 0) * 100 if fin.roce else None)]:
            if value is None:
                continue
            c1, c2, c3 = st.columns([1, 2, 1.5])
            c1.markdown(f'<div class="fs-stat">{name}</div><div class="fs-value">{value:.2f}'
                        f'{"%" if name == "ROCE" else ""}</div>', unsafe_allow_html=True)
            with c2:
                st.caption(METRIC_HINT.get(name, ""))
            with c3:
                if st.button(f"🤖 AI explain {name}", key=f"ex_{name}"):
                    with st.spinner("..."):
                        st.caption(explain_ratio(name, value))

    # Pros / Cons
    pc = company.pros_cons or {}
    if pc.get("pros") or pc.get("cons"):
        st.markdown("### Pros &amp; Cons")
        pc_l, pc_r = st.columns(2)
        with pc_l:
            st.markdown("**✅ Pros**")
            for p in pc.get("pros", []):
                st.markdown(f"- {p}")
        with pc_r:
            st.markdown("**⚠️ Cons**")
            for c in pc.get("cons", []):
                st.markdown(f"- {c}")

    # Peer comparison
    if company.sector:
        st.markdown("### How it compares in its sector")
        metrics = ["composite", "pe", "pb", "roce", "pct_change_1y", "market_cap"]
        peers = peer_table(company.sector, ticker, metrics)
        if peers:
            df_p = pd.DataFrame(peers)
            # Convert market cap to Cr for display
            if "market_cap" in df_p.columns:
                df_p["market_cap_cr"] = (df_p["market_cap"].fillna(0) / 1e7).round(0)
                df_p = df_p.drop(columns=["market_cap"])
            if "roce" in df_p.columns:
                df_p["roce"] = (df_p["roce"].fillna(0) * 100).round(1)
            st.dataframe(
                df_p,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "composite": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%.0f"),
                    "pct_change_1y": st.column_config.NumberColumn("1Y %", format="%+.1f%%"),
                    "roce": st.column_config.NumberColumn("ROCE %", format="%.1f%%"),
                    "market_cap_cr": st.column_config.NumberColumn("Mkt Cap (Cr)", format="₹%d"),
                },
            )
            median_score = sector_median(company.sector, "composite")
            if median_score is not None and score:
                diff = score.composite - median_score
                arrow = "above" if diff >= 0 else "below"
                st.caption(f"This stock scores **{abs(diff):.0f} points {arrow}** the sector median ({median_score:.0f}).")

    # Quarterly financials snapshot
    if fin and fin.raw:
        qi = fin.raw.get("info", {})  # from yfinance info
        if qi:
            with st.expander("📊 Full fundamentals snapshot (yfinance)"):
                st.json({k: v for k, v in qi.items() if v is not None})

    # Recent trades
    if deals:
        st.markdown("### Recent high-conviction trades (NSE bulk/block)")
        d = pd.DataFrame([{
            "Date": x.deal_date.date() if x.deal_date else None,
            "Kind": x.kind,
            "Side": x.side,
            "Client": x.client_name,
            "Qty": int(x.quantity or 0),
            "Price": x.price,
        } for x in deals])
        st.dataframe(d, use_container_width=True, hide_index=True)
    elif score:
        st.caption("No bulk/block deals recorded for this ticker yet.")


def _price_chart(fin, ticker):
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
                               line=dict(color="#60a5fa", width=2.2),
                               fill="tozeroy", fillcolor="rgba(96,165,250,0.07)"))
    fig.update_layout(
        height=320,
        margin=dict(l=0, r=0, t=30, b=0),
        title=dict(text=f"{ticker} · 1-year close", font=dict(size=14, color="#d1d5db"), x=0),
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", side="right"),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _stat(col, label, value, delta=False):
    cls = "fs-value"
    if delta and value not in ("—",):
        try:
            raw = float(value.strip("%").replace(",", ""))
            cls = "fs-delta-up" if raw >= 0 else "fs-delta-down"
        except Exception:
            pass
    col.markdown(f'<div class="fs-stat">{label}</div><div class="{cls}">{value}</div>',
                 unsafe_allow_html=True)


def _fmt_price(v):
    return f"₹{v:,.2f}" if v is not None else "—"


def _fmt_cr(v):
    return f"₹{(v or 0) / 1e7:,.0f} Cr" if v else "—"


def _fmt_pct(v):
    if v is None:
        return "—"
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.1f}%"
