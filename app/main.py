"""FinScout — Streamlit entry point."""
import sys
from pathlib import Path

# Ensure the project root is importable when launched via `streamlit run app/main.py`
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from app.config import settings
from app.ui import discover, deep_dive, screener, csv_rate, tracker
from app.ui._styles import inject as inject_styles
from app.db import init_db

st.set_page_config(
    page_title="FinScout",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()
inject_styles()

TABS = [
    ("🌟", "This Week's Picks", "Hand-picked stocks for this week"),
    ("🔎", "Find Stocks", "Filter the full universe"),
    ("📄", "Rate my CSV", "Score a Screener.in CSV"),
    ("📈", "Research a Stock", "Full breakdown of any ticker"),
    ("🏆", "Track Record", "How your tracked picks are doing"),
]

st.sidebar.markdown(
    "<div class='fs-brand'>🔍 <span>FinScout</span></div>"
    "<div class='fs-brand-sub'>AI-powered stock discovery</div>",
    unsafe_allow_html=True,
)

_LABELS = [label for _, label, _ in TABS]
_ICON = {label: icon for icon, label, _ in TABS}

if "fs_tab" not in st.session_state:
    st.session_state.fs_tab = _LABELS[0]
# Fallback: another file deep-linked somewhere we no longer list
if st.session_state.fs_tab not in _LABELS and st.session_state.fs_tab != "Research a Stock":
    st.session_state.fs_tab = _LABELS[0]

selected_label = st.sidebar.radio(
    " ",
    _LABELS,
    key="fs_tab",
    format_func=lambda s: f"{_ICON.get(s, '📈')}  {s}",
    label_visibility="collapsed",
)

st.sidebar.markdown("<div class='fs-nav-hint'>New here? Start with <b>This Week's Picks</b>.</div>", unsafe_allow_html=True)

st.sidebar.markdown("<div class='fs-sidebar-divider'></div>", unsafe_allow_html=True)
if settings.llm_provider == "ollama":
    st.sidebar.caption(f"Powered by local AI · Ollama ({settings.ollama_reasoning_model})")
else:
    st.sidebar.caption(f"Powered by {settings.model_reasoning}")

if selected_label == "This Week's Picks":
    discover.render()
elif selected_label == "Find Stocks":
    screener.render()
elif selected_label == "Rate my CSV":
    csv_rate.render()
elif selected_label == "Track Record":
    tracker.render()
else:
    deep_dive.render()
