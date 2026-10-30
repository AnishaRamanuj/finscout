"""FinScout — Streamlit entry point."""
import streamlit as st
from app.ui import discover, portfolio, deep_dive
from app.db import init_db

st.set_page_config(
    page_title="FinScout",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()

st.sidebar.title("🔍 FinScout")
st.sidebar.caption("AI-powered stock discovery")

tab = st.sidebar.radio("Navigate", ["Discover", "My Portfolio", "Deep Dive"])

st.sidebar.markdown("---")
st.sidebar.caption("Powered by Claude Opus 5.5 + Haiku 5.5")

if tab == "Discover":
    discover.render()
elif tab == "My Portfolio":
    portfolio.render()
else:
    deep_dive.render()
