"""Track Record — backtest tab.

Every pick that clears the momentum gate in Discover gets a snapshot:
entry price, target, composite, momentum, verdict and reasons at the
moment of recommendation. From that day on this tab records how the
price moved, and whenever the price touches our target we mark the pick
`target_hit` and stop sampling.

The tiles at the top are the honest scoreboard: hit rate on closed
picks, average days-to-target, average return on hit, and the running
mark-to-market on open picks.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import desc, select

from app.db import Recommendation, RecommendationPrice, Company, SessionLocal
from app.scoring.tracker import (
    MOMENTUM_GATE, reanchor_misdated_opens, refresh_all_open, success_rate,
)
from app.ui._styles import badge, inject


STATUS_COLOR = {
    "open": ("#2563eb", "#ffffff"),
    "target_hit": ("#16a34a", "#ffffff"),
    "expired": ("#64748b", "#ffffff"),
}


def render():
    inject()

    st.markdown('<div class="fs-header-title">Track Record</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="fs-header-sub">'
        f"Every pick we put on the board clears a momentum ≥ {MOMENTUM_GATE} gate. "
        "From the day of the recommendation we log the entry price and the model's target, "
        "then track the price forward until the target is hit or the pick expires."
        '</div>',
        unsafe_allow_html=True,
    )

    # Idempotent: on every page view, re-anchor any snapshots that were
    # created before we started reading WhyNow history. This fixes the
    # "entry price == today" issue for picks that were actually first
    # recommended weeks ago.
    fixed = reanchor_misdated_opens()
    if fixed:
        st.success(
            f"Re-anchored {fixed} pick(s) to their original recommendation date "
            "and backfilled the price history from then."
        )

    c1, c2 = st.columns([3, 1])
    with c2:
        if st.button("↻ Refresh prices now", use_container_width=True):
            with st.spinner("Fetching live quotes for open picks…"):
                refreshed, hits = refresh_all_open()
            if hits:
                st.success(f"Refreshed {refreshed} open picks — {hits} hit target 🎯")
            else:
                st.info(f"Refreshed {refreshed} open picks. No new targets hit.")
    with c1:
        st.caption(
            "Entry date = the day the pick first appeared in your weekly feed. "
            "Price history is backfilled weekly from entry, then sampled live from here on."
        )

    stats = success_rate()

    if stats.total == 0:
        st.info(
            "No recommendations tracked yet. Open **This Week's Picks** — every pick that "
            "clears the momentum gate gets snapshotted here automatically."
        )
        return

    _render_tiles(stats)
    st.markdown("---")

    tab_open, tab_hits, tab_expired = st.tabs(
        [f"🟦 Open ({stats.open})", f"🟢 Target hit ({stats.hit})", f"⚪ Expired ({stats.expired})"]
    )
    with tab_open:
        _render_open_picks()
    with tab_hits:
        _render_closed_picks(status="target_hit")
    with tab_expired:
        _render_closed_picks(status="expired")


# ---- tiles ----------------------------------------------------------------

def _render_tiles(stats):
    cols = st.columns(5)
    _tile(cols[0], "Hit rate (closed)", _fmt_pct(stats.closed_hit_rate),
          sub=f"{stats.hit} of {stats.closed} closed picks")
    _tile(cols[1], "Open picks", str(stats.open),
          sub="still tracking")
    _tile(cols[2], "Avg days to target", _fmt_days(stats.avg_days_to_target),
          sub="on hits only")
    _tile(cols[3], "Avg return on hit", _fmt_pct(stats.avg_return_on_hit, signed=True),
          sub="entry → target")
    _tile(cols[4], "Open picks MTM", _fmt_pct(stats.avg_return_open, signed=True),
          sub="live vs entry")


def _tile(col, label, value, sub=""):
    col.markdown(
        f'<div class="fs-stat">{label}</div>'
        f'<div class="fs-value">{value}</div>'
        f'<div style="color:#9ca3af;font-size:12px;margin-top:2px;">{sub}</div>',
        unsafe_allow_html=True,
    )


# ---- lists ----------------------------------------------------------------

def _render_open_picks():
    with SessionLocal() as s:
        recs = s.execute(
            select(Recommendation)
            .where(Recommendation.status == "open")
            .order_by(desc(Recommendation.recommended_at))
        ).scalars().all()

    if not recs:
        st.caption("No open picks. Refresh prices to update, or add new picks from This Week's Picks.")
        return

    rows = [_row_for(rec) for rec in recs]
    df = pd.DataFrame(rows)
    st.dataframe(
        df.drop(columns=["_id"]),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Current %": st.column_config.NumberColumn("Current %", format="%+.1f%%"),
            "Progress to target": st.column_config.ProgressColumn(
                "Progress to target", min_value=0, max_value=100, format="%.0f%%"
            ),
            "Momentum": st.column_config.NumberColumn("Momentum", format="%d"),
        },
    )

    pick = st.selectbox(
        "Drill into a pick:",
        options=[r["_id"] for r in rows],
        format_func=lambda rid: next(
            f"{r['Ticker']} · entered {r['Entered']} · {r['Current %']:+.1f}%" for r in rows if r["_id"] == rid
        ),
        key="tracker_open_pick",
    )
    if pick is not None:
        _render_detail(pick)


def _render_closed_picks(status: str):
    with SessionLocal() as s:
        recs = s.execute(
            select(Recommendation)
            .where(Recommendation.status == status)
            .order_by(desc(Recommendation.target_hit_at if status == "target_hit" else Recommendation.recommended_at))
        ).scalars().all()

    if not recs:
        st.caption(
            "Nothing here yet." if status == "target_hit"
            else "No picks have aged out of the 1-year window yet."
        )
        return

    rows = [_row_for(rec) for rec in recs]
    df = pd.DataFrame(rows)
    st.dataframe(
        df.drop(columns=["_id", "Progress to target"]),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Current %": st.column_config.NumberColumn(
                "Return" if status == "target_hit" else "Last %", format="%+.1f%%"
            ),
            "Momentum": st.column_config.NumberColumn("Momentum", format="%d"),
        },
    )

    pick = st.selectbox(
        "Drill into a pick:",
        options=[r["_id"] for r in rows],
        format_func=lambda rid: next(
            f"{r['Ticker']} · {r['Entered']} → {r['Current %']:+.1f}%" for r in rows if r["_id"] == rid
        ),
        key=f"tracker_{status}_pick",
    )
    if pick is not None:
        _render_detail(pick)


def _row_for(rec: Recommendation) -> dict:
    latest_price = _latest_price(rec.id) or rec.entry_price
    current_pct = (latest_price / rec.entry_price - 1) * 100 if rec.entry_price else 0.0
    # Progress = how much of the way from entry to target we've covered.
    if rec.target_price and rec.entry_price and rec.target_price > rec.entry_price:
        covered = (latest_price - rec.entry_price) / (rec.target_price - rec.entry_price)
        progress = max(0.0, min(100.0, covered * 100))
    else:
        progress = 0.0
    name = _ticker_name(rec.ticker)
    return {
        "_id": rec.id,
        "Ticker": rec.ticker,
        "Company": name,
        "Entered": rec.recommended_at.strftime("%Y-%m-%d") if rec.recommended_at else "—",
        "Entry ₹": round(rec.entry_price, 2) if rec.entry_price else None,
        "Target ₹": round(rec.target_price, 2) if rec.target_price else None,
        "Latest ₹": round(latest_price, 2) if latest_price else None,
        "Current %": round(current_pct, 2),
        "Progress to target": round(progress, 1),
        "Verdict @ entry": rec.verdict_at_entry or "—",
        "Momentum": rec.momentum_at_entry or 0,
        "Composite": round(rec.composite_at_entry or 0, 1),
    }


def _render_detail(rec_id: int):
    with SessionLocal() as s:
        rec = s.get(Recommendation, rec_id)
        samples = s.execute(
            select(RecommendationPrice)
            .where(RecommendationPrice.recommendation_id == rec_id)
            .order_by(RecommendationPrice.sampled_at.asc())
        ).scalars().all()
    if not rec:
        return

    name = _ticker_name(rec.ticker)
    status_bg, status_fg = STATUS_COLOR.get(rec.status, ("#374151", "#ffffff"))

    header = (
        f'{badge(rec.status.replace("_", " ").upper(), status_bg, status_fg)}'
        f' &nbsp;<span style="color:#9ca3af;font-size:13px;">Verdict @ entry: '
        f'{rec.verdict_at_entry or "—"}</span>'
    )
    st.markdown(header, unsafe_allow_html=True)
    st.markdown(
        f'<div style="font-size:20px;font-weight:700;margin:6px 0 10px 0;">{name} '
        f'<span style="color:#9ca3af;font-weight:500;">({rec.ticker})</span></div>',
        unsafe_allow_html=True,
    )

    cols = st.columns(5)
    cols[0].metric("Entry", f"₹{rec.entry_price:,.2f}")
    cols[1].metric("Target", f"₹{rec.target_price:,.2f}" if rec.target_price else "—")
    if rec.status == "target_hit" and rec.target_hit_price:
        cols[2].metric("Hit at", f"₹{rec.target_hit_price:,.2f}",
                       delta=f"{(rec.target_hit_price/rec.entry_price - 1)*100:+.1f}%")
    else:
        latest = _latest_price(rec_id) or rec.entry_price
        cols[2].metric("Latest", f"₹{latest:,.2f}",
                       delta=f"{(latest/rec.entry_price - 1)*100:+.1f}%")
    cols[3].metric("Peak", f"₹{rec.peak_price:,.2f}" if rec.peak_price else "—")
    if rec.days_to_target is not None:
        cols[4].metric("Days to target", str(rec.days_to_target))
    else:
        days = (pd.Timestamp.utcnow().to_pydatetime().replace(tzinfo=None) - rec.recommended_at).days
        cols[4].metric("Days open", str(days))

    _render_chart(rec, samples)

    if rec.reasons:
        with st.expander("Why we recommended it (frozen at entry)"):
            for r in rec.reasons:
                st.markdown(f"- {r}", unsafe_allow_html=True)

    st.caption(
        f"Recommended at composite {rec.composite_at_entry:.1f} · "
        f"momentum {rec.momentum_at_entry} · "
        f"growth {rec.growth_at_entry:.1f} · "
        f"targeted upside {rec.upside_pct_at_entry:+.1f}%"
    )


def _render_chart(rec: Recommendation, samples: list[RecommendationPrice]):
    if not samples:
        st.caption("No price samples yet — click **Refresh prices** above to log one.")
        return
    df = pd.DataFrame({
        "date": [p.sampled_at for p in samples],
        "price": [p.price for p in samples],
    }).sort_values("date")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["price"], mode="lines+markers",
        line=dict(color="#60a5fa", width=2),
        marker=dict(size=6),
        name="Price",
        fill="tozeroy", fillcolor="rgba(96,165,250,0.06)",
    ))
    # Reference lines: entry + target.
    fig.add_hline(y=rec.entry_price, line=dict(color="#9ca3af", width=1, dash="dot"),
                  annotation_text="Entry", annotation_position="right")
    if rec.target_price:
        fig.add_hline(y=rec.target_price, line=dict(color="#16a34a", width=1, dash="dash"),
                      annotation_text="Target", annotation_position="right")
    if rec.target_hit_at:
        fig.add_vline(x=rec.target_hit_at, line=dict(color="#16a34a", width=1),
                      annotation_text="Target hit", annotation_position="top")

    y_min = min(df["price"].min(), rec.entry_price) * 0.97
    y_max = max(df["price"].max(), rec.target_price or 0, rec.entry_price) * 1.03

    fig.update_layout(
        height=320,
        margin=dict(l=0, r=0, t=20, b=0),
        xaxis=dict(showgrid=False, title=""),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)",
                   title="", side="right", range=[y_min, y_max]),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ---- helpers --------------------------------------------------------------

def _latest_price(rec_id: int) -> float | None:
    with SessionLocal() as s:
        return s.execute(
            select(RecommendationPrice.price)
            .where(RecommendationPrice.recommendation_id == rec_id)
            .order_by(desc(RecommendationPrice.sampled_at))
            .limit(1)
        ).scalar_one_or_none()


def _ticker_name(ticker: str) -> str:
    with SessionLocal() as s:
        name = s.execute(
            select(Company.name).where(Company.ticker == ticker)
        ).scalar_one_or_none()
    return name or ticker


def _fmt_pct(v: float | None, signed: bool = False) -> str:
    if v is None:
        return "—"
    if signed:
        sign = "+" if v >= 0 else ""
        return f"{sign}{v:.1f}%"
    return f"{v:.1f}%"


def _fmt_days(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:.0f} d"
