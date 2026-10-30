import streamlit as st
from sqlalchemy import select, desc
from app.db import SessionLocal, Company, Score, Financials, WhyNow
from app.agents.explainer import explain_ratio


def render():
    st.header("Deep Dive")
    ticker = st.text_input("Enter ticker", value="RELIANCE").upper().strip()

    with SessionLocal() as s:
        company = s.execute(select(Company).where(Company.ticker == ticker)).scalar_one_or_none()
        score = s.execute(select(Score).where(Score.ticker == ticker)).scalar_one_or_none()
        fin = s.execute(
            select(Financials).where(Financials.ticker == ticker).order_by(desc(Financials.fetched_at))
        ).scalar_one_or_none()
        why = s.execute(
            select(WhyNow).where(WhyNow.ticker == ticker).order_by(desc(WhyNow.generated_at))
        ).scalar_one_or_none()

    if not company:
        st.warning(f"No data for {ticker}. Run the nightly job first.")
        return

    st.subheader(f"{company.name} ({ticker})")
    st.caption(f"{company.sector} · {company.industry}")

    if why:
        st.markdown(f"**AI Take:** {why.text}")

    if score:
        st.markdown("### Score Breakdown")
        for factor in ["growth", "profitability", "momentum", "valuation", "sentiment"]:
            val = getattr(score, factor)
            st.progress(int(val), text=f"{factor.title()}: {val:.0f}/100")

    if fin:
        st.markdown("### Key Ratios")
        for name, value in [("PE", fin.pe), ("P/B", fin.pb), ("ROCE", fin.roce)]:
            if value is None:
                continue
            cols = st.columns([1, 4])
            cols[0].metric(name, f"{value:.2f}")
            with cols[1]:
                if st.button(f"Explain {name}", key=f"ex{name}"):
                    with st.spinner("..."):
                        st.caption(explain_ratio(name, value))
