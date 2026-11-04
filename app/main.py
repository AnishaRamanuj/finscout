"""FinScout — Streamlit entry point."""
import sys
from pathlib import Path

# Ensure the project root is importable when launched via `streamlit run app/main.py`
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from app.config import settings
from app.ui import discover, portfolio, deep_dive, screener, csv_rate, tracker
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

if "fs_tab" not in st.session_state:
    st.session_state.fs_tab = "This Week's Picks"

tab = st.sidebar.radio(
    " ",
    ["This Week's Picks", "Find Stocks", "Rate my CSV", "My Money", "Research a Stock", "Track Record"],
    key="fs_tab",
    label_visibility="collapsed",
)

st.sidebar.markdown("---")
st.sidebar.caption("Not sure where to start? Try **This Week's Picks** or **My Money → Build me a portfolio**.")
st.sidebar.markdown("---")
if settings.llm_provider == "ollama":
    st.sidebar.caption(f"Powered by local AI (Ollama · {settings.ollama_reasoning_model})")
else:
    st.sidebar.caption(f"Powered by {settings.model_reasoning}")

if tab == "This Week's Picks":
    discover.render()
elif tab == "Find Stocks":
    screener.render()
elif tab == "Rate my CSV":
    csv_rate.render()
elif tab == "My Money":
    portfolio.render()
elif tab == "Track Record":
    tracker.render()
else:
    deep_dive.render()
