"""FinScout — Streamlit entry point."""
import sys
from pathlib import Path

# Ensure the project root is importable when launched via `streamlit run app/main.py`
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from app.config import settings
from app.ui import discover, portfolio, deep_dive, screener
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
    st.session_state.fs_tab = "Discover"

tab = st.sidebar.radio(
    "Navigate",
    ["Discover", "Screener", "My Portfolio", "Deep Dive"],
    key="fs_tab",
)

st.sidebar.markdown("---")
if settings.llm_provider == "ollama":
    st.sidebar.caption(f"Powered by Ollama · {settings.ollama_reasoning_model} + {settings.ollama_fast_model}")
else:
    st.sidebar.caption(f"Powered by {settings.model_reasoning} + {settings.model_fast}")

if tab == "Discover":
    discover.render()
elif tab == "Screener":
    screener.render()
elif tab == "My Portfolio":
    portfolio.render()
else:
    deep_dive.render()
