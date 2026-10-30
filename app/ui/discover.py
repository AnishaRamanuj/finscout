import streamlit as st
from sqlalchemy import select, desc
from app.db import SessionLocal, Score, Company, WhyNow


def render():
    st.header("Discover — This Week's AI Picks")
    st.caption("Ranked by FinScout's 7-factor composite score. Nightly refresh.")

    col1, col2 = st.columns([3, 1])
    with col2:
        limit = st.slider("How many picks?", 5, 25, 10)

    with SessionLocal() as s:
        rows = s.execute(
            select(Score, Company)
            .join(Company, Score.ticker == Company.ticker)
            .order_by(desc(Score.composite))
            .limit(limit)
        ).all()

    if not rows:
        st.info("No scores yet. Run `python -m app.jobs.nightly` to populate the database.")
        return

    for score, company in rows:
        with st.container(border=True):
            c1, c2 = st.columns([3, 1])
            with c1:
                st.subheader(f"{company.name} ({company.ticker})")
                st.caption(
                    f"Score {score.composite:.0f}/100 · "
                    f"{company.sector or 'Unknown'} · "
                    f"Market Cap ₹{(company.market_cap or 0) / 1e7:,.0f} Cr"
                )
            with c2:
                st.metric("Composite", f"{score.composite:.0f}")

            with SessionLocal() as s:
                why = s.execute(
                    select(WhyNow)
                    .where(WhyNow.ticker == company.ticker)
                    .order_by(desc(WhyNow.generated_at))
                    .limit(1)
                ).scalar_one_or_none()

            if why:
                st.markdown(f"**Why Now:** {why.text}")
            else:
                st.caption("No Why-Now generated yet. The Monday curation job will create one.")

            cols = st.columns(4)
            cols[0].progress(int(score.growth), text=f"Growth {score.growth:.0f}")
            cols[1].progress(int(score.momentum), text=f"Momentum {score.momentum:.0f}")
            cols[2].progress(int(score.valuation), text=f"Value {score.valuation:.0f}")
            cols[3].progress(int(score.sentiment), text=f"Sentiment {score.sentiment:.0f}")
