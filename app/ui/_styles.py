"""Shared Streamlit CSS — one place to tune the whole look.

Design goals: light, calm, readable. A single teal accent, soft neutrals,
plenty of breathing room, and cards that read at a glance.
"""
CSS = """
<style>
  /* ---------- Palette (available as CSS vars) ---------- */
  :root {
    --fs-accent:        #0ea5a4;   /* teal */
    --fs-accent-soft:   rgba(14, 165, 164, 0.10);
    --fs-accent-border: rgba(14, 165, 164, 0.35);
    --fs-ink:           #0f172a;
    --fs-ink-soft:      #475569;
    --fs-ink-muted:     #94a3b8;
    --fs-surface:       #ffffff;
    --fs-surface-alt:   #f8fafc;
    --fs-border:        #e2e8f0;
    --fs-good:          #16a34a;
    --fs-bad:           #dc2626;
    --fs-warn:          #d97706;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --fs-ink:         #f1f5f9;
      --fs-ink-soft:    #cbd5e1;
      --fs-ink-muted:   #94a3b8;
      --fs-surface:     #0f172a;
      --fs-surface-alt: #111c2e;
      --fs-border:      rgba(148, 163, 184, 0.18);
    }
  }

  /* ---------- Layout ---------- */
  .block-container {
    padding-top: 1.25rem;
    padding-bottom: 3rem;
    max-width: 1280px;
  }

  /* ---------- Headers ---------- */
  .fs-header-title {
    font-size: 30px;
    font-weight: 700;
    color: var(--fs-ink);
    letter-spacing: -0.3px;
    margin: 4px 0 4px 0;
  }
  .fs-header-sub {
    color: var(--fs-ink-soft);
    font-size: 15px;
    margin-bottom: 18px;
  }

  /* ---------- Cards ---------- */
  .fs-card {
    border: 1px solid var(--fs-border);
    border-radius: 16px;
    padding: 22px 26px;
    margin-bottom: 20px;
    background: var(--fs-surface);
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    transition: box-shadow 0.15s ease, border-color 0.15s ease;
  }
  .fs-card:hover {
    border-color: var(--fs-accent-border);
    box-shadow: 0 4px 16px rgba(14, 165, 164, 0.08);
  }
  .fs-hero {
    border: 1px solid var(--fs-accent-border);
    background: linear-gradient(180deg, var(--fs-accent-soft), var(--fs-surface));
  }

  /* ---------- Verdict / signal badges ---------- */
  .fs-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 999px;
    font-weight: 600;
    font-size: 12px;
    letter-spacing: 0.4px;
    text-transform: uppercase;
  }

  /* ---------- Why-Now paragraph ---------- */
  .fs-why {
    font-size: 15.5px;
    line-height: 1.6;
    color: var(--fs-ink);
    margin: 12px 0 14px 0;
  }
  .fs-risk {
    color: var(--fs-warn);
    font-size: 13.5px;
    margin-top: 6px;
  }

  /* ---------- Stat tiles ---------- */
  .fs-stat {
    color: var(--fs-ink-muted);
    font-size: 11.5px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-weight: 600;
  }
  .fs-value {
    color: var(--fs-ink);
    font-size: 21px;
    font-weight: 700;
    margin-top: 4px;
    letter-spacing: -0.2px;
  }
  .fs-delta-up   { color: var(--fs-good); font-size: 13px; font-weight: 600; }
  .fs-delta-down { color: var(--fs-bad);  font-size: 13px; font-weight: 600; }

  /* ---------- Help / info banner ---------- */
  .fs-help-box {
    background: var(--fs-accent-soft);
    border-left: 3px solid var(--fs-accent);
    padding: 12px 16px;
    border-radius: 8px;
    margin-bottom: 20px;
    font-size: 14px;
    color: var(--fs-ink);
  }

  /* ---------- Sidebar navigation ---------- */
  .fs-brand {
    font-size: 24px;
    font-weight: 800;
    letter-spacing: -0.4px;
    color: var(--fs-ink);
    margin-top: 8px;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .fs-brand span { color: var(--fs-accent); }
  .fs-brand-sub {
    color: var(--fs-ink-muted);
    font-size: 12.5px;
    margin: 2px 0 20px 0;
  }
  .fs-nav-hint {
    margin-top: 14px;
    font-size: 12.5px;
    color: var(--fs-ink-muted);
    padding: 10px 12px;
    background: var(--fs-accent-soft);
    border-radius: 8px;
    line-height: 1.45;
  }
  .fs-sidebar-divider {
    height: 1px;
    background: var(--fs-border);
    margin: 18px 0 10px 0;
  }

  /* Pretty up the radio items in the sidebar */
  section[data-testid="stSidebar"] div[role="radiogroup"] > label {
    border-radius: 10px;
    padding: 6px 10px;
    margin: 2px 0;
    transition: background 0.15s ease;
  }
  section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
    background: var(--fs-accent-soft);
  }

  /* Primary Streamlit buttons pick up the accent */
  button[kind="primary"] {
    background-color: var(--fs-accent) !important;
    border-color: var(--fs-accent) !important;
  }
</style>
"""


def inject():
    """Call at the top of each page (and once from main for sidebar styles)."""
    import streamlit as st
    st.markdown(CSS, unsafe_allow_html=True)


def badge(label: str, bg: str, fg: str) -> str:
    return f'<span class="fs-badge" style="background:{bg};color:{fg};">{label}</span>'
