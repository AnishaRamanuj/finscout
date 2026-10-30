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
from app.ui._styles import inject
from app.agents.nl_query import nl_to_spec


EXAMPLE_QUERIES = [
    "Large cap IT companies with ROCE above 25%",
    "Cheap banks with strong momentum",
    "Mid-cap pharma growing 20%+ with high quality",
    "Small-cap industrials with low P/E and positive 1-year return",
    "Any sector with composite above 65 and 3-month return positive",
]


def render():
    inject()
    st.markdown('<div class="fs-header-title">Screener — Ask in Plain English</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="fs-header-sub">Describe what you\'re looking for; Ollama turns it into a safe filter and runs it on your local data. '
        "No SQL, no magic — just ranked results.</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="fs-help-box">'
        "<b>Try one of these</b> &nbsp;·&nbsp; "
        + " &nbsp;·&nbsp; ".join(f'<i>"{q}"</i>' for q in EXAMPLE_QUERIES[:3])
        + "</div>",
        unsafe_allow_html=True,
    )

    query = st.text_input(
        "Your query",
        placeholder=EXAMPLE_QUERIES[0],
        key="fs_screen_q",
    )

    if not query:
        with st.expander("More examples"):
            for q in EXAMPLE_QUERIES:
                st.markdown(f"- `{q}`")
        return

    with st.spinner("Translating your query…"):
        spec = nl_to_spec(query)

    if spec.get("error"):
        st.warning(f"Query translation issue: {spec['error']}")

    with st.expander("🤖 How the AI understood your query"):
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
            "market_cap_cr": st.column_config.NumberColumn("Mkt Cap (Cr)", format="₹%d"),
            "current_price": st.column_config.NumberColumn("Price (₹)", format="%.2f"),
            "pct_change_1y": st.column_config.NumberColumn("1Y %", format="%+.1f%%"),
            "pct_change_3m": st.column_config.NumberColumn("3M %", format="%+.1f%%"),
            "pe": st.column_config.NumberColumn("P/E", format="%.1f"),
        },
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
