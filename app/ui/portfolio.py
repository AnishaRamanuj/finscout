"""My Portfolio — two tools:

1. **Portfolio Builder** — tell FinScout your budget + risk → get a diversified
   basket you can actually act on.
2. **Portfolio Analyzer** — paste your real holdings → the AI Copilot answers
   questions grounded in current scores.
"""
from __future__ import annotations

import io

import pandas as pd
import streamlit as st
from sqlalchemy import select, desc

from app.db import SessionLocal, Score, Company
from app.scoring.verdict import verdict_for
from app.ui._styles import inject, badge
from app.agents.copilot import answer_portfolio_question


def render():
    inject()
    st.markdown('<div class="fs-header-title">My Portfolio</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="fs-header-sub">New to investing? Start with the Builder. Already holding stocks? Try the Analyzer.</div>',
        unsafe_allow_html=True,
    )

    tab_builder, tab_analyzer = st.tabs(["🛠 Portfolio Builder", "📊 Portfolio Analyzer"])
    with tab_builder:
        _render_builder()
    with tab_analyzer:
        _render_analyzer()


def _render_builder():
    st.markdown(
        '<div class="fs-help-box">'
        "<b>How this works.</b> Tell us your <b>budget</b> and <b>risk comfort</b>. "
        "We pick 6–10 stocks from the top of our model, split your money across sectors "
        "so you're not over-exposed, and show you exactly how many shares of each to buy."
        "</div>",
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        budget = st.number_input("How much to invest (₹)", min_value=5000, max_value=50_00_000,
                                 value=1_00_000, step=5000)
    with c2:
        risk = st.selectbox("Risk comfort",
                            ["Conservative", "Balanced", "Aggressive"],
                            index=1,
                            help="Conservative = large caps, steady. Balanced = mix. Aggressive = higher growth, more volatility.")
    with c3:
        picks = st.slider("How many stocks", 5, 12, 8,
                          help="More stocks = better diversification but smaller position in each.")

    build_clicked = st.button("🔎 Build my basket", type="primary", use_container_width=True)

    if build_clicked or st.session_state.get("fs_basket") is not None:
        basket = _build_basket(risk, picks, budget)
        if basket.empty:
            st.warning("Not enough scored companies yet. Run the ingestion first.")
            return
        st.session_state["fs_basket"] = basket
        _show_basket(basket, budget)


def _build_basket(risk: str, picks: int, budget: int) -> pd.DataFrame:
    with SessionLocal() as s:
        rows = s.execute(
            select(Score, Company)
            .join(Company, Score.ticker == Company.ticker)
            .where(Company.current_price.isnot(None))
            .where(Company.current_price > 0)
            .order_by(desc(Score.composite))
        ).all()

    if not rows:
        return pd.DataFrame()

    candidates = []
    for score, company in rows:
        v = verdict_for(score.composite)
        if v.label in ("Watch", "Avoid"):
            continue
        if risk == "Conservative":
            if (company.market_cap or 0) < 50_000 * 1e7:   # ≥ ₹50 kcr
                continue
            if v.label not in ("Strong Pick", "Pick", "Hold"):
                continue
        elif risk == "Balanced":
            if (company.market_cap or 0) < 10_000 * 1e7:   # ≥ ₹10 kcr
                continue
        candidates.append((score, company, v))

    # sector-diversify: at most 2 picks per sector
    chosen: list[tuple] = []
    sector_count: dict[str, int] = {}
    for score, company, v in candidates:
        sec = company.sector or "Other"
        if sector_count.get(sec, 0) >= 2:
            continue
        chosen.append((score, company, v))
        sector_count[sec] = sector_count.get(sec, 0) + 1
        if len(chosen) >= picks:
            break

    if not chosen:
        return pd.DataFrame()

    # tier-weighted allocation
    weights = []
    for score, _, v in chosen:
        w = 1.4 if v.label == "Strong Pick" else (1.1 if v.label == "Pick" else 0.8)
        weights.append(w)
    total = sum(weights)
    allocs = [w / total for w in weights]

    out = []
    for (score, company, v), alloc in zip(chosen, allocs):
        amount = budget * alloc
        price = company.current_price or 1
        shares = int(amount // price) if price > 0 else 0
        out.append({
            "Verdict": v.label,
            "Ticker": company.ticker,
            "Name": company.name,
            "Sector": company.sector or "—",
            "Price (₹)": round(price, 2),
            "Shares": shares,
            "Invest (₹)": round(shares * price, 0),
            "Allocation %": round(alloc * 100, 1),
            "Score": round(score.composite, 1),
        })
    return pd.DataFrame(out)


def _show_basket(df: pd.DataFrame, budget: int):
    invested = int(df["Invest (₹)"].sum())
    cash_left = budget - invested
    n = len(df)
    sectors = df["Sector"].nunique()

    st.markdown("### Your suggested basket")
    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(f'<div class="fs-stat">Stocks</div><div class="fs-value">{n}</div>', unsafe_allow_html=True)
    k2.markdown(f'<div class="fs-stat">Sectors</div><div class="fs-value">{sectors}</div>', unsafe_allow_html=True)
    k3.markdown(f'<div class="fs-stat">Invested</div><div class="fs-value">₹{invested:,}</div>', unsafe_allow_html=True)
    k4.markdown(f'<div class="fs-stat">Cash Left</div><div class="fs-value">₹{cash_left:,}</div>', unsafe_allow_html=True)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Allocation %": st.column_config.ProgressColumn(
                "Allocation %", min_value=0, max_value=30, format="%.1f%%"
            ),
            "Score": st.column_config.ProgressColumn(
                "Score", min_value=0, max_value=100, format="%.0f"
            ),
        },
    )

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇ Download basket as CSV", csv, file_name="finscout_basket.csv", mime="text/csv")

    with st.expander("ℹ What to do with this basket"):
        st.markdown(
            "- These are **suggestions**, not advice. Nothing here guarantees returns.\n"
            "- Place the trades through your own broker (Zerodha, Groww, Dhan, etc.).\n"
            "- Buy in **small lots over 2–4 weeks** rather than everything on day one.\n"
            "- Re-run the Builder every 2–4 weeks and re-balance only if the mix drifts significantly.\n"
            "- Keep **20–30% in cash or an index fund** for emergencies — the Builder sizes only what you give it."
        )


def _render_analyzer():
    st.caption("Upload a CSV of your real holdings — columns: `ticker, shares, buy_price`")
    uploaded = st.file_uploader(" ", type="csv", key="port_upload", label_visibility="collapsed")
    if uploaded:
        st.session_state["fs_portfolio"] = pd.read_csv(uploaded)

    if "fs_portfolio" not in st.session_state:
        st.info("Upload your holdings to begin, or use the Builder tab to create one.")
        return

    df = st.session_state["fs_portfolio"]
    enriched = _enrich(df)
    st.dataframe(enriched, use_container_width=True, hide_index=True)

    st.markdown("### Ask the AI about your portfolio")
    q = st.text_input(
        "",
        placeholder="e.g. 'Which of my holdings looks weakest right now?'",
        key="fs_q",
    )
    if q:
        context = _ctx_lines(enriched)
        with st.spinner("Thinking..."):
            answer = answer_portfolio_question(context, q)
        st.markdown(answer)


def _enrich(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    with SessionLocal() as s:
        for _, h in df.iterrows():
            ticker = str(h.ticker).upper()
            score = s.execute(select(Score).where(Score.ticker == ticker)).scalar_one_or_none()
            company = s.execute(select(Company).where(Company.ticker == ticker)).scalar_one_or_none()
            price_now = company.current_price if company else None
            invested = float(h.shares) * float(h.buy_price)
            now_val = (price_now or 0) * float(h.shares)
            rows.append({
                "Ticker": ticker,
                "Name": company.name if company else "—",
                "Shares": int(h.shares),
                "Buy Price": float(h.buy_price),
                "Price Now": price_now,
                "Invested (₹)": round(invested, 0),
                "Value (₹)": round(now_val, 0),
                "P&L (₹)": round(now_val - invested, 0),
                "Score": round(score.composite, 1) if score else None,
                "Verdict": verdict_for(score.composite).label if score else "—",
            })
    return pd.DataFrame(rows)


def _ctx_lines(df: pd.DataFrame) -> str:
    lines = []
    for _, r in df.iterrows():
        lines.append(
            f"{r.Ticker} ({r.Name}) | {r.Shares} shares @ ₹{r['Buy Price']} "
            f"(now ₹{r['Price Now']}) | P&L ₹{r['P&L (₹)']} | "
            f"Score {r.Score} ({r.Verdict})"
        )
    return "\n".join(lines)
