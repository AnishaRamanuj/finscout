"""Shared Streamlit CSS — one place to tune the whole look."""
CSS = """
<style>
  /* Tighten the main padding */
  .block-container { padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1300px; }

  /* Verdict badges */
  .fs-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 999px;
    font-weight: 600;
    font-size: 13px;
    letter-spacing: 0.3px;
    text-transform: uppercase;
  }

  /* Pick card */
  .fs-card {
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    padding: 20px 24px;
    margin-bottom: 20px;
    background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01));
  }

  .fs-hero {
    border: 1px solid rgba(37,99,235,0.35);
    background: linear-gradient(180deg, rgba(37,99,235,0.09), rgba(255,255,255,0.02));
  }

  .fs-why {
    font-size: 15.5px;
    line-height: 1.55;
    color: #e5e7eb;
    margin: 10px 0 14px 0;
  }

  .fs-risk {
    color: #fbbf24;
    font-size: 13.5px;
    margin-top: 6px;
  }

  .fs-stat { color: #9ca3af; font-size: 12px; text-transform: uppercase; letter-spacing: 0.4px; }
  .fs-value { color: #f3f4f6; font-size: 20px; font-weight: 600; margin-top: 2px; }
  .fs-delta-up { color: #22c55e; font-size: 13px; }
  .fs-delta-down { color: #ef4444; font-size: 13px; }

  .fs-header-title { font-size: 28px; font-weight: 700; margin-bottom: 2px; }
  .fs-header-sub { color: #9ca3af; font-size: 14px; margin-bottom: 16px; }

  .fs-help-box {
    background: rgba(37,99,235,0.08);
    border-left: 3px solid #2563eb;
    padding: 12px 16px;
    border-radius: 6px;
    margin-bottom: 20px;
    font-size: 14px;
    color: #d1d5db;
  }
</style>
"""


def inject():
    """Call at the top of each page."""
    import streamlit as st
    st.markdown(CSS, unsafe_allow_html=True)


def badge(label: str, bg: str, fg: str) -> str:
    return f'<span class="fs-badge" style="background:{bg};color:{fg};">{label}</span>'
