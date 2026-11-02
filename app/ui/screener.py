"""Screener — natural-language stock filter.

Type what you want in plain English: "small-cap tech growing 25%+ with no debt".
Ollama translates it to a safe JSON filter spec, we run it against Postgres.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st
from sqlalchemy import select

from app.db import SessionLocal, Company, Score, Financials
from app.scoring.verdict import verdict_for
from app.scoring.momentum_lite import score_momentum
from app.ui._styles import inject
from app.agents.nl_query import nl_to_spec


def _goto_deep_dive(ticker: str):
    st.session_state.fs_selected_ticker = ticker
    st.session_state.fs_tab = "Research a Stock"


EXAMPLE_QUERIES = [
    "Mid caps with building momentum and strong fundamentals",
    "Cheap stocks about to break out",
    "Large cap IT companies with ROCE above 25%",
    "Pharma stocks growing 20%+ with building momentum",
    "Any sector with composite above 65 and Strong momentum",
    "Hidden gems — low 1-year return but momentum building",
]


def render():
    inject()
    st.markdown('<div class="fs-header-title">Find Stocks</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="fs-header-sub">Describe what you\'re looking for in plain English. Our AI finds the matching companies.</div>',
        unsafe_allow_html=True,
    )

    query = st.text_input(
        " ",
        placeholder=EXAMPLE_QUERIES[0],
        key="fs_screen_q",
        label_visibility="collapsed",
    )

    with st.expander("💡 Example questions you can ask"):
        for q in EXAMPLE_QUERIES:
            st.markdown(f"- *{q}*")

    if not query:
        return

    with st.spinner("Reading your question…"):
        spec = nl_to_spec(query)

    if spec.get("error"):
        st.warning(f"Couldn't fully understand that — showing the best match. ({spec['error']})")

    with st.expander("🤖 How the AI understood your question (advanced)"):
        st.json(spec)

    df = _run_spec(spec)
    if df.empty:
        st.info("No companies match these filters. Loosen them or try another query.")
        return

    st.caption(f"Showing {len(df)} companies, sorted by {spec.get('sort')}")

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "composite": st.column_config.ProgressColumn(
                "Score", min_value=0, max_value=100, format="%.0f"
            ),
            "momentum_score": st.column_config.ProgressColumn(
                "📊 Momentum", min_value=0, max_value=100, format="%d"
            ),
            "market_cap_cr": st.column_config.NumberColumn("Mkt Cap (Cr)", format="₹%d"),
            "current_price": st.column_config.NumberColumn("Price (₹)", format="%.2f"),
            "pct_change_1y": st.column_config.NumberColumn("1Y %", format="%+.1f%%"),
            "pct_change_3m": st.column_config.NumberColumn("3M %", format="%+.1f%%"),
            "pe": st.column_config.NumberColumn("P/E", format="%.1f"),
        },
    )

    st.caption("Click a ticker below to open its Deep Dive →")
    picker_cols = st.columns(min(5, len(df)))
    for i, (_, row) in enumerate(df.head(5).iterrows()):
        with picker_cols[i]:
            st.button(
                f"🔍 {row['Ticker']}",
                key=f"scr_dd_{row['Ticker']}",
                use_container_width=True,
                on_click=_goto_deep_dive,
                args=(row["Ticker"],),
            )

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇ Download results as CSV", csv,
                       file_name="finscout_screen.csv", mime="text/csv")


def _run_spec(spec: dict) -> pd.DataFrame:
    with SessionLocal() as s:
        rows = s.execute(
            select(Company, Score, Financials)
            .join(Score, Score.ticker == Company.ticker)
            .outerjoin(Financials, Financials.ticker == Company.ticker)
            .where(Company.current_price.isnot(None))
        ).all()

    records = []
    for company, score, fin in rows:
        price_1y = (fin.raw or {}).get("price_1y") if fin else {}
        mom = score_momentum(company.ticker, price_1y)
        rec = {
            "Ticker": company.ticker,
            "Name": company.name,
            "sector": company.sector or "—",
            "market_cap_cr": round((company.market_cap or 0) / 1e7, 0),
            "current_price": company.current_price,
            "pct_change_1y": company.pct_change_1y,
            "pct_change_3m": company.pct_change_3m,
            "pct_change_1m": company.pct_change_1m,
            "composite": score.composite,
            "growth": score.growth,
            "momentum": score.momentum,
            "valuation": score.valuation,
            "profitability": score.profitability,
            "sentiment": score.sentiment,
            "insider": score.insider,
            "quality": score.quality,
            "pe": fin.pe if fin else None,
            "pb": fin.pb if fin else None,
            "roce": (fin.roce * 100) if (fin and fin.roce is not None) else None,
            "Verdict": verdict_for(score.composite).label,
            "momentum_signal": mom.label,
            "momentum_score": mom.score,
        }
        records.append(rec)

    df = pd.DataFrame(records)
    for f in spec.get("filters", []):
        df = _apply_filter(df, f)
    sort = spec.get("sort", "composite")
    if sort in df.columns:
        df = df.sort_values(sort, ascending=False, na_position="last")
    limit = int(spec.get("limit", 25))
    return df.head(limit)


def _apply_filter(df: pd.DataFrame, f: dict) -> pd.DataFrame:
    field, op, value = f["field"], f["op"], f["value"]
    if field not in df.columns:
        return df
    s = df[field]
    try:
        if op == ">":
            return df[s > value]
        if op == ">=":
            return df[s >= value]
        if op == "<":
            return df[s < value]
        if op == "<=":
            return df[s <= value]
        if op == "=":
            if s.dtype == object:
                return df[s.str.lower() == str(value).lower()]
            return df[s == value]
        if op == "!=":
            if s.dtype == object:
                return df[s.str.lower() != str(value).lower()]
            return df[s != value]
    except Exception:
        return df
    return df
