import streamlit as st
import pandas as pd
from sqlalchemy import select
from app.db import SessionLocal, Score, Company
from app.agents.copilot import answer_portfolio_question


def render():
    st.header("My Portfolio — AI Copilot")

    st.caption("Upload a CSV with columns: `ticker, shares, buy_price`")
    uploaded = st.file_uploader("", type="csv")
    if uploaded:
        st.session_state.portfolio = pd.read_csv(uploaded)

    if "portfolio" not in st.session_state:
        st.info("Upload your holdings to begin.")
        return

    df = st.session_state.portfolio
    enriched = _enrich(df)
    st.dataframe(enriched, use_container_width=True)

    st.subheader("Ask about your portfolio")
    q = st.text_input("", placeholder="Which of my holdings looks weakest right now?")
    if q:
        context = _build_context(enriched)
        with st.spinner("Claude Opus 5.5 is analyzing..."):
            answer = answer_portfolio_question(context, q)
        st.markdown(answer)


def _enrich(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    with SessionLocal() as s:
        for _, h in df.iterrows():
            ticker = str(h.ticker).upper()
            score = s.execute(select(Score).where(Score.ticker == ticker)).scalar_one_or_none()
            company = s.execute(select(Company).where(Company.ticker == ticker)).scalar_one_or_none()
            rows.append({
                "ticker": ticker,
                "name": company.name if company else "—",
                "shares": h.shares,
                "buy_price": h.buy_price,
                "composite": score.composite if score else None,
                "growth": score.growth if score else None,
                "momentum": score.momentum if score else None,
            })
    return pd.DataFrame(rows)


def _build_context(df: pd.DataFrame) -> str:
    lines = []
    for _, r in df.iterrows():
        lines.append(
            f"{r.ticker} ({r.name}) | {r.shares} shares @ ₹{r.buy_price} | "
            f"Composite {r.composite} | Growth {r.growth} | Momentum {r.momentum}"
        )
    return "\n".join(lines)
