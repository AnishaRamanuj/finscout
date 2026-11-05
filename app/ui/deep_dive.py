"""Research a Stock — full breakdown, but with the advanced stuff folded away by default.

What a first-time investor sees on landing:
  - Verdict + Why-Now + Risk
  - 1-year price chart
  - 3 numbers: Price, 1Y return, Market cap
  - Pros & Cons (if generated)

Expand to see: full score breakdown, all ratios, peer comparison, raw data.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import func, select, desc

from app.db import SessionLocal, Company, Score, Financials, WhyNow, Deal
from app.scoring.verdict import verdict_for
from app.scoring.peers import peer_table, sector_median
from app.scoring.upside import compute_upside
from app.data.live_quote import get_live_quote, format_volume
from app.data.delivery import get_delivery_trend, delivery_trend_slope
from app.scoring.technicals import macd_fast, macd_standard
from app.scoring.momentum_signal import compute_signal
from app.ui._styles import inject, badge
from app.agents.explainer import explain_ratio

HIDDEN_GEM_BADGE_BG = "#8b5cf6"

MOMENTUM_COLOR = {
    "Strong":   ("#16a34a", "#ffffff"),
    "Building": ("#2563eb", "#ffffff"),
    "Mixed":    ("#64748b", "#ffffff"),
    "Fading":   ("#f59e0b", "#111827"),
    "Quiet":    ("#374151", "#d1d5db"),
}


METRIC_HINT = {
    "PE":   "How many years of earnings you'd pay to buy the whole company at today's price. Lower = cheaper.",
    "P/B":  "Price vs the company's book value. Below 1 = the market values it less than its assets.",
    "ROCE": "How much profit the business makes for every ₹100 it uses. Above 15% is solid.",
}


def render():
    inject()

    with SessionLocal() as s:
        all_tickers = [t for (t,) in s.execute(select(Company.ticker).order_by(Company.ticker)).all()]
        scored_count = s.execute(select(func.count(Score.ticker))).scalar() or 0
        financials_count = s.execute(
            select(func.count(func.distinct(Financials.ticker)))
        ).scalar() or 0
    if not all_tickers:
        st.markdown('<div class="fs-header-title">Research a Stock</div>', unsafe_allow_html=True)
        st.info("No companies ingested yet. Run `python -m app.jobs.nightly 500 nifty500`.")
        return

    st.markdown('<div class="fs-header-title">Research a Stock</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="fs-header-sub">'
        f'Searching across <b>{len(all_tickers):,}</b> stocks in your database · '
        f'<b>{scored_count:,}</b> with model scores · '
        f'<b>{financials_count:,}</b> with financials cached.'
        '</div>',
        unsafe_allow_html=True,
    )

    pre = st.session_state.get("fs_selected_ticker")
    if pre and pre in all_tickers:
        default = pre
    elif "RELIANCE" in all_tickers:
        default = "RELIANCE"
    else:
        default = all_tickers[0]
    ticker = st.selectbox("Which stock?", all_tickers, index=all_tickers.index(default))
    st.session_state.fs_selected_ticker = ticker

    with SessionLocal() as s:
        company = s.execute(select(Company).where(Company.ticker == ticker)).scalar_one_or_none()
        score = s.execute(select(Score).where(Score.ticker == ticker)).scalar_one_or_none()
        fin = s.execute(
            select(Financials).where(Financials.ticker == ticker)
            .order_by(desc(Financials.fetched_at)).limit(1)
        ).scalar_one_or_none()
        why = s.execute(
            select(WhyNow).where(WhyNow.ticker == ticker)
            .order_by(desc(WhyNow.generated_at)).limit(1)
        ).scalar_one_or_none()
        deals = s.execute(
            select(Deal).where(Deal.ticker == ticker)
            .order_by(desc(Deal.deal_date)).limit(10)
        ).scalars().all()

    if not company:
        st.warning(f"No data for {ticker}.")
        return

    v = verdict_for(score.composite if score else 50)

    # Upside estimate
    peer_pe = None
    try:
        peer_pe = sector_median(company.sector, "pe")
    except Exception:
        pass
    est = compute_upside(
        current_price=company.current_price,
        pe=fin.pe if fin else None,
        roce=fin.roce if fin else None,
        growth_score=score.growth if score else None,
        quality_score=score.quality if score else None,
        composite_score=score.composite if score else None,
        pct_change_1y=company.pct_change_1y,
        peer_median_pe=peer_pe,
    )

    # --- Hero: verdict + name + Why-Now + Risk ----------------------------
    st.markdown('<div class="fs-card fs-hero">', unsafe_allow_html=True)
    badges_html = badge(v.label, v.color, v.text_color)
    if est.is_hidden_gem:
        badges_html += " &nbsp;" + badge("💎 Hidden Gem", HIDDEN_GEM_BADGE_BG, "#ffffff")
    st.markdown(
        f'{badges_html} &nbsp;<span style="color:#9ca3af;font-size:13px;">{company.sector or "—"}</span>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div style="font-size:26px;font-weight:700;margin-top:6px;">{company.name} '
        f'<span style="color:#9ca3af;font-weight:500;">({company.ticker})</span></div>',
        unsafe_allow_html=True,
    )

    if why and why.text:
        parts = why.text.split("Risk:")
        story = parts[0].replace("Why Now:", "").strip()
        st.markdown(f'<div class="fs-why">{story}</div>', unsafe_allow_html=True)
        if len(parts) > 1:
            st.markdown(f'<div class="fs-risk"><b>Risk:</b> {parts[1].strip()}</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # --- Live Market Activity ---------------------------------------------
    _live_market_section(company, ticker)

    # --- Momentum signals (volume + delivery + MACDs) ---------------------
    _momentum_signals_section(ticker, company, fin)

    # --- Chart --------------------------------------------------------------
    _price_chart(fin, ticker)

    # --- The 5 numbers everyone cares about --------------------------------
    cols = st.columns(5)
    _stat(cols[0], "Price today", _fmt_price(company.current_price))
    _stat(cols[1], "Our target", _fmt_price(est.target_price))
    _stat(cols[2], "Upside", _fmt_pct_signed(est.upside_pct), delta=True)
    _stat(cols[3], "Last year", _fmt_pct_signed(company.pct_change_1y), delta=True)
    _stat(cols[4], "Size", _fmt_cr(company.market_cap))

    if est.reasons:
        with st.expander(f"🎯 Why we see {_fmt_pct_signed(est.upside_pct)} upside"):
            for reason in est.reasons:
                st.markdown(f"- {reason}")
            st.caption("Model-based estimate — not a guarantee. Based on peer P/E, quality, growth and the price's 12-month path.")

    # --- Pros & Cons (if generated) ----------------------------------------
    pc = company.pros_cons or {}
    if pc.get("pros") or pc.get("cons"):
        st.markdown("### What's good / What's not")
        pc_l, pc_r = st.columns(2)
        with pc_l:
            st.markdown("**✅ What's good**")
            for p in pc.get("pros", [])[:3]:
                st.markdown(f"- {p}")
        with pc_r:
            st.markdown("**⚠️ What's not**")
            for c in pc.get("cons", [])[:3]:
                st.markdown(f"- {c}")

    # --- Everything else: collapsed by default -----------------------------
    with st.expander("📊 How we scored it (7 factors)"):
        if score:
            for factor, weight in [
                ("growth", "25%"), ("profitability", "20%"), ("momentum", "20%"),
                ("insider", "10%"), ("sentiment", "10%"), ("valuation", "10%"), ("quality", "5%"),
            ]:
                val = getattr(score, factor) or 0
                st.progress(int(val), text=f"{factor.title()} ({weight} weight) — {val:.0f}/100")

    if fin and any(x is not None for x in (fin.pe, fin.pb, fin.roce)):
        with st.expander("💰 Ratios (with AI explanations)"):
            for name, value in [("PE", fin.pe), ("P/B", fin.pb),
                                ("ROCE", (fin.roce or 0) * 100 if fin.roce else None)]:
                if value is None:
                    continue
                c1, c2, c3 = st.columns([1, 2, 1.5])
                c1.markdown(
                    f'<div class="fs-stat">{name}</div><div class="fs-value">{value:.2f}'
                    f'{"%" if name == "ROCE" else ""}</div>',
                    unsafe_allow_html=True,
                )
                with c2:
                    st.caption(METRIC_HINT.get(name, ""))
                with c3:
                    if st.button(f"🤖 Explain {name}", key=f"ex_{name}"):
                        with st.spinner("..."):
                            st.caption(explain_ratio(name, value))

    if company.sector:
        with st.expander(f"🏢 Compare with other {company.sector} stocks"):
            metrics = ["composite", "pe", "pb", "roce", "pct_change_1y", "market_cap"]
            peers = peer_table(company.sector, ticker, metrics)
            if peers:
                df_p = pd.DataFrame(peers)
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
                        "composite": st.column_config.ProgressColumn(
                            "Score", min_value=0, max_value=100, format="%.0f"),
                        "pct_change_1y": st.column_config.NumberColumn("1Y %", format="%+.1f%%"),
                        "roce": st.column_config.NumberColumn("ROCE %", format="%.1f%%"),
                        "market_cap_cr": st.column_config.NumberColumn("Size (Cr)", format="₹%d"),
                    },
                )
                median_score = sector_median(company.sector, "composite")
                if median_score is not None and score:
                    diff = score.composite - median_score
                    arrow = "above" if diff >= 0 else "below"
                    st.caption(
                        f"This stock scores **{abs(diff):.0f} points {arrow}** "
                        f"the typical {company.sector} stock ({median_score:.0f})."
                    )

    if deals:
        with st.expander(f"📈 Recent high-conviction trades ({len(deals)})"):
            d = pd.DataFrame([{
                "Date": x.deal_date.date() if x.deal_date else None,
                "Kind": x.kind, "Side": x.side,
                "Client": x.client_name,
                "Qty": int(x.quantity or 0), "Price": x.price,
            } for x in deals])
            st.dataframe(d, use_container_width=True, hide_index=True)

    if fin and fin.raw:
        with st.expander("🔧 Raw data (for the curious)"):
            qi = fin.raw.get("info", {}) or {}
            st.json({k: v for k, v in qi.items() if v is not None})


def _live_market_section(company, ticker: str):
    """Live price + volume widget — cached 60 s, with a manual refresh button."""
    yf_symbol = company.yf_symbol or f"{ticker}.NS"

    header_l, header_r = st.columns([5, 1])
    with header_l:
        st.markdown("### 📡 Live Market Activity")
    with header_r:
        refresh = st.button("🔄 Refresh", key=f"refresh_{ticker}", use_container_width=True)

    with st.spinner("Fetching live quote…"):
        q = get_live_quote(yf_symbol, ticker, bust=refresh)

    if not q:
        st.caption("Live data unavailable right now (markets closed or source throttled).")
        return

    cols = st.columns(4)
    _stat(cols[0], "Live price",
          f"₹{q.price:,.2f}" if q.price else "—")
    _stat(cols[1], "Volume today",
          format_volume(q.volume_today))
    _stat(cols[2], "30-day avg",
          format_volume(q.avg_volume_30d))
    _stat(cols[3], "Volume ratio",
          f"{q.volume_surge:.2f}×" if q.volume_surge else "—",
          delta=False)

    if q.volume_surge is not None and q.volume_surge >= 2.0:
        st.success(
            f"🚨 **Volume surge detected** — trading at **{q.volume_surge:.1f}× normal volume** today. "
            "Often signals an incoming move (news, breakout, institutional interest)."
        )
    elif q.volume_surge is not None and q.volume_surge >= 1.5:
        st.info(f"👀 Volume elevated at **{q.volume_surge:.1f}× normal**. Worth watching.")
    elif q.volume_surge is not None and q.volume_surge < 0.6:
        st.caption(f"Quiet session — only {q.volume_surge:.1f}× normal volume.")

    footer = f"Source: **{q.source}** · updated {q.last_update.strftime('%H:%M:%S')}"
    if q.day_high and q.day_low:
        footer += f" · intraday range ₹{q.day_low:,.2f}–₹{q.day_high:,.2f}"
    st.caption(footer)


def _momentum_signals_section(ticker: str, company, fin):
    """Volume surge + delivery % trend + MACD(7,21,9) + MACD(12,26,9) → combined label."""
    st.markdown("### 📊 Momentum Signals")

    yf_symbol = company.yf_symbol or f"{ticker}.NS"
    with st.spinner("Reading price + delivery data…"):
        quote = get_live_quote(yf_symbol, ticker)
        trend = get_delivery_trend(ticker, days=10)
        slope = delivery_trend_slope(trend)
        price_1y = (fin.raw or {}).get("price_1y") if fin else None
        mf = macd_fast(price_1y) if price_1y else None
        ms = macd_standard(price_1y) if price_1y else None

    signal = compute_signal(
        volume_surge=quote.volume_surge if quote else None,
        latest_delivery_pct=trend[-1].delivery_pct if trend else None,
        delivery_slope=slope,
        macd_fast_trend=mf.trend if mf else "neutral",
        macd_fast_cross=mf.crossover if mf else None,
        macd_std_trend=ms.trend if ms else "neutral",
        macd_std_cross=ms.crossover if ms else None,
    )

    bg, fg = MOMENTUM_COLOR.get(signal.label, ("#64748b", "#ffffff"))
    hdr_l, hdr_r = st.columns([2, 1])
    with hdr_l:
        st.markdown(
            f'{badge(signal.label, bg, fg)} '
            f'<span style="color:#9ca3af;font-size:13px;">&nbsp;overall momentum</span>',
            unsafe_allow_html=True,
        )
    with hdr_r:
        st.markdown(
            f'<div style="text-align:right;">'
            f'<div class="fs-stat">Momentum score</div>'
            f'<div style="font-size:30px;font-weight:700;color:{bg};">{signal.score}/100</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # 4-stat breakdown
    cols = st.columns(4)
    _stat(cols[0], "Volume signal",
          f"{signal.volume_part}/25")
    _stat(cols[1], "Delivery signal",
          f"{signal.delivery_part}/25")
    _stat(cols[2], "Fast MACD (7,21,9)",
          f"{signal.macd_fast_part}/25")
    _stat(cols[3], "Std MACD (12,26,9)",
          f"{signal.macd_std_part}/25")

    # Human-readable reasons
    if signal.reasons:
        for r in signal.reasons:
            st.markdown(f"- {r}")

    # Delivery trend chart (sparkline-style)
    if trend and len([d for d in trend if d.delivery_pct]) >= 3:
        with st.expander(f"📦 Delivery % trend — last {len(trend)} trading days"):
            df_d = pd.DataFrame([{
                "Date": d.date, "Delivery %": d.delivery_pct,
                "Volume": d.total_volume, "Close": d.close,
            } for d in trend if d.delivery_pct is not None])
            fig = go.Figure(go.Scatter(
                x=df_d["Date"], y=df_d["Delivery %"], mode="lines+markers",
                line=dict(color="#a78bfa", width=2.4),
                marker=dict(size=7, color="#a78bfa"),
            ))
            fig.update_layout(
                height=180, margin=dict(l=0, r=0, t=10, b=0),
                xaxis=dict(showgrid=False, title=""),
                yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)",
                           side="right", ticksuffix="%"),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            st.dataframe(df_d, use_container_width=True, hide_index=True)

    # MACD details for the technically-minded
    if mf and ms and mf.macd is not None:
        with st.expander("📐 MACD details"):
            m_l, m_r = st.columns(2)
            with m_l:
                st.markdown(f"**Fast MACD (7, 21, 9)** — {mf.trend}")
                st.markdown(
                    f"- MACD line: `{mf.macd:.2f}`\n"
                    f"- Signal line: `{mf.signal:.2f}`\n"
                    f"- Histogram: `{mf.histogram:+.2f}` (prev: `{mf.prev_histogram:+.2f}`)"
                )
                if mf.crossover:
                    arrow = "🟢 Crossed UP" if mf.crossover == "up" else "🔴 Crossed DOWN"
                    st.markdown(f"**{arrow}** on the latest bar.")
            with m_r:
                st.markdown(f"**Standard MACD (12, 26, 9)** — {ms.trend}")
                st.markdown(
                    f"- MACD line: `{ms.macd:.2f}`\n"
                    f"- Signal line: `{ms.signal:.2f}`\n"
                    f"- Histogram: `{ms.histogram:+.2f}` (prev: `{ms.prev_histogram:+.2f}`)"
                )
                if ms.crossover:
                    arrow = "🟢 Crossed UP" if ms.crossover == "up" else "🔴 Crossed DOWN"
                    st.markdown(f"**{arrow}** on the latest bar.")
            st.caption(
                "MACD crosses up when the fast line pierces the signal line from below — classic buy signal. "
                "Having **both** the fast (7,21,9) and standard (12,26,9) MACDs in agreement is the stronger confirmation."
            )


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
    fig = go.Figure(go.Scatter(
        x=df["date"], y=df["close"], mode="lines",
        line=dict(color="#60a5fa", width=2.2),
        fill="tozeroy", fillcolor="rgba(96,165,250,0.07)",
    ))
    fig.update_layout(
        height=280,
        margin=dict(l=0, r=0, t=30, b=0),
        title=dict(text=f"Last 1 year", font=dict(size=13, color="#d1d5db"), x=0),
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
            raw = float(str(value).strip("%").replace(",", "").replace("+", ""))
            cls = "fs-delta-up" if raw >= 0 else "fs-delta-down"
        except Exception:
            pass
    col.markdown(
        f'<div class="fs-stat">{label}</div><div class="{cls}">{value}</div>',
        unsafe_allow_html=True,
    )


def _fmt_price(v):
    return f"₹{v:,.0f}" if v is not None else "—"


def _fmt_cr(v):
    if not v:
        return "—"
    cr = v / 1e7
    if cr >= 100_000:
        return f"₹{cr/1_00_000:.1f}L Cr"
    if cr >= 1000:
        return f"₹{cr/1000:.0f}k Cr"
    return f"₹{cr:,.0f} Cr"


def _fmt_pct(v):
    if v is None:
        return "—"
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.0f}%"


_fmt_pct_signed = _fmt_pct
