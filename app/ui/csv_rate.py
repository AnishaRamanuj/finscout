"""Rate my CSV — the user uploads a Screener-style export and we rank each row.

Short-term, long-term, chart-pattern + combined, with filters and a
drill-through into Research a Stock. The CSV's own volume / returns /
PE columns are kept as-is; we only *add* columns from our enrichment
(delivery %, MACD, momentum label, pattern tags).
"""
from __future__ import annotations

import io

import pandas as pd
import streamlit as st
from sqlalchemy import select, desc

from app.db import SessionLocal, Company, Financials
from app.scoring.momentum_lite import score_momentum
from app.scoring.patterns import detect as detect_pattern
from app.scoring.technicals import macd_fast
from app.scoring.csv_rating import rate_row, CSVRating
from app.data.delivery import _fetch_bhav, _trading_days
from app.ui._styles import inject, badge


LABEL_COLOR = {
    "Strong Buy": ("#16a34a", "#ffffff"),
    "Buy":        ("#2563eb", "#ffffff"),
    "Hold":       ("#64748b", "#ffffff"),
    "Watch":      ("#f59e0b", "#111827"),
    "Avoid":      ("#dc2626", "#ffffff"),
}

PATTERN_LABEL = {
    "breakout":          "🚀 Breakout",
    "golden_cross":      "✨ Golden cross",
    "death_cross":       "⚠️ Death cross",
    "ma_bullish":        "📈 MA stacked",
    "ma_bearish":        "📉 MA bearish",
    "pullback_zone":     "🎯 Pullback zone",
    "consolidation":     "💤 Consolidating",
    "oversold_rebound":  "🔄 Oversold rebound",
    "overextended":      "⚠️ Overextended",
    "rsi_overbought":    "⚠️ RSI overbought",
    "rsi_oversold":      "📉 RSI oversold",
}


def _goto_deep_dive(ticker: str):
    st.session_state.fs_selected_ticker = ticker
    st.session_state.fs_tab = "Research a Stock"


def render():
    inject()
    st.markdown('<div class="fs-header-title">Rate my CSV</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="fs-header-sub">Upload a Screener-style CSV. We keep your Volume / Returns / PE columns as-is '
        'and add short-term, long-term and chart-pattern ratings for every stock, with filters below.</div>',
        unsafe_allow_html=True,
    )

    uploaded = st.file_uploader(
        "Upload your CSV", type="csv", key="csv_rate_upload",
        help="Must include NSE Code / Current Price / Volume / Return columns.",
    )

    df_user: pd.DataFrame | None = None
    if uploaded:
        df_user = pd.read_csv(uploaded)
        st.session_state["csv_df"] = df_user
    elif "csv_df" in st.session_state:
        df_user = st.session_state["csv_df"]

    if df_user is None:
        st.info("Upload a CSV to begin. The format matches Screener.in exports — Name, NSE Code, Current Price, Volume, Returns, PE etc.")
        return

    st.caption(f"Loaded **{len(df_user)}** rows · {len(df_user.columns)} columns")

    with st.spinner("Rating every row — fetching delivery, computing MACD, detecting chart patterns…"):
        rated = _rate_all(df_user)

    if rated.empty:
        st.warning("No rows could be rated — missing NSE Code or price history.")
        return

    _render_filters_and_table(rated)


def _rate_all(df_user: pd.DataFrame) -> pd.DataFrame:
    # Preload today's bhavcopy once for delivery %
    out_rows: list[dict] = []

    for _, row in df_user.iterrows():
        ticker = str(row.get("NSE Code") or "").strip().upper()
        if not ticker:
            continue

        # Pull our enrichment from Postgres (price_1y lives in Financials.raw)
        with SessionLocal() as s:
            company = s.execute(select(Company).where(Company.ticker == ticker)).scalar_one_or_none()
            fin = s.execute(
                select(Financials).where(Financials.ticker == ticker)
                .order_by(desc(Financials.fetched_at)).limit(1)
            ).scalar_one_or_none()

        price_1y = (fin.raw or {}).get("price_1y") if fin else None
        pattern = detect_pattern(price_1y)
        mom = score_momentum(ticker, price_1y)
        mf = macd_fast(price_1y) if price_1y else None

        enrichment = {
            "delivery_pct": mom.delivery_pct,
            "delivery_slope": mom.delivery_slope,
            "macd_fast_trend": mf.trend if mf else "neutral",
            "chart_score": pattern.score,
            "pattern_tags": pattern.pattern_tags,
            "adx14": pattern.adx14,
            "obv_slope_pct": pattern.obv_slope_pct,
            "supertrend_dir": pattern.supertrend_dir,
            "volume_surge": None,
        }

        rating = rate_row(row.to_dict(), enrichment)

        # Keep the CSV columns verbatim and append our added fields
        rec = row.to_dict()
        rec["_Rating"] = rating.label
        rec["_Short"] = rating.short_term
        rec["_Long"] = rating.long_term
        rec["_Chart"] = rating.chart
        rec["_Combined"] = rating.combined
        rec["_Momentum"] = mom.label
        rec["_MomentumScore"] = mom.score
        rec["_DeliveryPct"] = mom.delivery_pct
        rec["_DeliverySlope"] = mom.delivery_slope
        rec["_Pattern"] = pattern.label
        rec["_PatternTags"] = ", ".join(PATTERN_LABEL.get(t, t) for t in pattern.pattern_tags)
        rec["_RSI14"] = pattern.rsi14
        rec["_ADX14"] = pattern.adx14
        rec["_BollingerPctB"] = pattern.bollinger_pct_b
        rec["_ROC20"] = pattern.roc20
        rec["_OBVSlope"] = pattern.obv_slope_pct
        rec["_Supertrend"] = pattern.supertrend_dir
        rec["_PEDiscount3Y"] = rating.pe_discount_3y
        rec["_PEDiscount5Y"] = rating.pe_discount_5y
        rec["_PEDiscount7Y"] = rating.pe_discount_7y
        rec["_OpProfitQoQ"] = rating.op_profit_qoq
        rec["_NetProfitYoY"] = rating.net_profit_yoy
        rec["_ROEChange"] = rating.roe_change
        rec["_Reasons"] = " · ".join(rating.bullets)
        rec["_InDB"] = company is not None
        out_rows.append(rec)

    return pd.DataFrame(out_rows)


def _render_filters_and_table(rated: pd.DataFrame):
    with st.expander("🔎 Filters (no defaults — set what you want)", expanded=False):
        f1, f2, f3, f4 = st.columns(4)
        with f1:
            verdicts = ["Strong Buy", "Buy", "Hold", "Watch", "Avoid"]
            chosen_verdicts = st.multiselect("Rating", verdicts, default=[])
        with f2:
            industries = sorted(rated["Industry"].dropna().unique()) if "Industry" in rated.columns else []
            chosen_industries = st.multiselect("Industry", industries, default=[])
        with f3:
            max_pe = int(rated["Price to Earnings Times"].dropna().max()) if "Price to Earnings Times" in rated.columns else 300
            max_pe = max(max_pe, 50)
            pe_range = st.slider("PE range", 0, min(max_pe, 500), (0, min(max_pe, 500)))
        with f4:
            min_combined = st.slider("Minimum combined rating", 0, 100, 0)

        f5, f6, f7 = st.columns(3)
        with f5:
            patterns_available = {p for row in rated["_PatternTags"].fillna("") for p in row.split(", ") if p}
            chosen_patterns = st.multiselect("Chart pattern (any of)", sorted(patterns_available), default=[])
        with f6:
            mom_opts = ["Strong", "Building", "Mixed", "Fading", "Quiet"]
            chosen_mom = st.multiselect("Momentum", mom_opts, default=[])
        with f7:
            min_pe_discount = st.slider(
                "Minimum avg PE discount vs its own history (%)",
                -100, 100, -100,
                help="How much cheaper the current PE is vs the stock's own 3/5/7-year averages. 0 = at history, 25 = materially cheaper.",
            )

    df = rated.copy()
    if chosen_verdicts:
        df = df[df["_Rating"].isin(chosen_verdicts)]
    if chosen_industries:
        df = df[df["Industry"].isin(chosen_industries)]
    if "Price to Earnings Times" in df.columns:
        df = df[df["Price to Earnings Times"].between(pe_range[0], pe_range[1], inclusive="both")]
    if min_combined > 0:
        df = df[df["_Combined"] >= min_combined]
    if chosen_mom:
        df = df[df["_Momentum"].isin(chosen_mom)]
    if chosen_patterns:
        df = df[df["_PatternTags"].fillna("").apply(lambda s: any(p in s for p in chosen_patterns))]
    if min_pe_discount > -100:
        avg_disc = df[["_PEDiscount3Y", "_PEDiscount5Y", "_PEDiscount7Y"]].mean(axis=1, skipna=True)
        df = df[avg_disc >= min_pe_discount]

    df = df.sort_values("_Combined", ascending=False)
    st.caption(f"Showing **{len(df)}** of {len(rated)} rows")

    # Pick which columns to show — keep user's cols intact + our ratings
    priority_user_cols = [
        c for c in [
            "Name", "NSE Code", "Industry", "Current Price",
            "Price to Earnings Times", "Volume", "Volume Times Compared to 1 Week",
            "Return over 1week", "Return over 1month", "Return over 1year",
            "Return on equity", "Sales growth",
        ] if c in df.columns
    ]
    added_cols = [
        "_Rating", "_Combined", "_Short", "_Long", "_Chart",
        "_Momentum", "_DeliveryPct",
        "_PEDiscount3Y", "_PEDiscount5Y", "_PEDiscount7Y",
        "_NetProfitYoY", "_OpProfitQoQ", "_ROEChange",
        "_RSI14", "_ADX14", "_BollingerPctB", "_ROC20", "_OBVSlope", "_Supertrend",
        "_Pattern", "_PatternTags", "_Reasons",
    ]
    show_cols = priority_user_cols + [c for c in added_cols if c in df.columns]

    st.dataframe(
        df[show_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "_Combined": st.column_config.ProgressColumn(
                "Combined", min_value=0, max_value=100, format="%d",
            ),
            "_Short": st.column_config.ProgressColumn(
                "Short-term", min_value=0, max_value=100, format="%d",
            ),
            "_Long": st.column_config.ProgressColumn(
                "Long-term", min_value=0, max_value=100, format="%d",
            ),
            "_Chart": st.column_config.ProgressColumn(
                "Chart", min_value=0, max_value=100, format="%d",
            ),
            "_DeliveryPct": st.column_config.NumberColumn("Delivery %", format="%.1f%%"),
            "_RSI14": st.column_config.NumberColumn("RSI(14)", format="%.0f"),
            "_ADX14": st.column_config.NumberColumn("ADX(14)", format="%.0f",
                                                   help="Trend strength. >25 = real trend, <15 = sideways."),
            "_BollingerPctB": st.column_config.NumberColumn("Boll %B", format="%.2f",
                                                           help="0 = lower band, 1 = upper band."),
            "_ROC20": st.column_config.NumberColumn("ROC(20)", format="%+.1f%%"),
            "_OBVSlope": st.column_config.NumberColumn("OBV slope", format="%+.1f%%",
                                                      help="Normalised slope of On-Balance Volume over last 20 bars."),
            "_PEDiscount3Y": st.column_config.NumberColumn("PE vs 3Y hist", format="%+.0f%%",
                                                          help="Positive = currently cheaper than 3-year average."),
            "_PEDiscount5Y": st.column_config.NumberColumn("PE vs 5Y hist", format="%+.0f%%"),
            "_PEDiscount7Y": st.column_config.NumberColumn("PE vs 7Y hist", format="%+.0f%%"),
            "_NetProfitYoY": st.column_config.NumberColumn("Net profit YoY", format="%+.0f%%"),
            "_OpProfitQoQ": st.column_config.NumberColumn("Op profit QoQ", format="%+.0f%%"),
            "_ROEChange": st.column_config.NumberColumn("ROE change", format="%+.1fpt"),
            "Return over 1week": st.column_config.NumberColumn("1W %", format="%+.1f%%"),
            "Return over 1month": st.column_config.NumberColumn("1M %", format="%+.1f%%"),
            "Return over 1year": st.column_config.NumberColumn("1Y %", format="%+.1f%%"),
            "Current Price": st.column_config.NumberColumn("Price", format="₹%.2f"),
            "Volume": st.column_config.NumberColumn("Volume", format="%d"),
        },
    )

    # Hero: the top 5 picks after filters
    st.markdown("### Top picks after your filters")
    top5 = df.head(5)
    if top5.empty:
        st.info("No matches — loosen the filters.")
        return

    for _, r in top5.iterrows():
        bg, fg = LABEL_COLOR.get(r["_Rating"], ("#64748b", "#ffffff"))
        with st.container(border=True):
            st.markdown(
                f"{badge(r['_Rating'], bg, fg)} &nbsp;"
                f"{badge(r['_Momentum'] + ' ' + str(r['_MomentumScore']), '#2563eb', '#ffffff')} "
                f"&nbsp;<span style='color:#9ca3af;font-size:13px;'>{r.get('Industry', '—')} · {r.get('Industry Group', '')}</span>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<div style='font-size:22px;font-weight:700;margin-top:4px;'>{r.get('Name', '—')} "
                f"<span style='color:#9ca3af;font-weight:500;'>({r.get('NSE Code', '')})</span></div>",
                unsafe_allow_html=True,
            )

            k1, k2, k3, k4 = st.columns(4)
            k1.markdown(f'<div class="fs-stat">Price</div><div class="fs-value">₹{r.get("Current Price", 0):,.2f}</div>', unsafe_allow_html=True)
            k2.markdown(f'<div class="fs-stat">1-year return</div><div class="fs-value">{r.get("Return over 1year") or 0:+.1f}%</div>', unsafe_allow_html=True)
            k3.markdown(f'<div class="fs-stat">PE</div><div class="fs-value">{r.get("Price to Earnings Times") or 0:.1f}</div>', unsafe_allow_html=True)
            k4.markdown(f'<div class="fs-stat">Combined</div><div class="fs-value" style="color:{bg}">{r["_Combined"]}/100</div>', unsafe_allow_html=True)

            if r.get("_PatternTags"):
                st.caption(f"**Chart patterns:** {r['_PatternTags']}")
            if r.get("_Reasons"):
                for part in r["_Reasons"].split(" · "):
                    st.markdown(f"- {part}")

            if r.get("_InDB"):
                st.button(
                    f"Open {r['NSE Code']} in Research →",
                    key=f"csv_dd_{r['NSE Code']}",
                    on_click=_goto_deep_dive,
                    args=(r["NSE Code"],),
                )

    csv_out = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇ Download rated CSV",
                       csv_out, file_name="finscout_rated.csv", mime="text/csv")
