"""
Defect Recurrence Analysis — Streamlit dashboard.

Run from the project root:
    streamlit run app/main.py

Environment variables for the database connection (see app/db.py):
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASS
"""

from datetime import date

import pandas as pd
import streamlit as st

from app.db import (
    fetch_records,
    fetch_summary,
    fetch_weekly_breakdown,
    get_date_bounds,
)

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Defect Recurrence Analysis",
    page_icon="🔍",
    layout="wide",
)

# ── Status display helpers ────────────────────────────────────────────────────

BADGE = {
    "Recurring": "🔴 Recurring",
    "One-Off": "🔵 One-Off",
    "Insufficient Data": "⚠️ Insufficient Data",
}

_ROW_BG = {
    "🔴 Recurring": "background-color: #ffe6e6",
    "🔵 One-Off": "background-color: #e6f0ff",
    "⚠️ Insufficient Data": "background-color: #fffbe6",
}


def _highlight_row(row: pd.Series):
    """Return a list of CSS strings — one per cell — colouring the whole row."""
    bg = _ROW_BG.get(row.get("Status", ""), "")
    return [bg] * len(row)


# ── Header ────────────────────────────────────────────────────────────────────

st.title("🔍 Defect Recurrence Analysis")
st.caption(
    "Shows whether a defect type appears across multiple lots and calendar weeks.  "
    "**Recurring** = same defect code observed in more than one calendar week (AC1).  "
    "Zero-defect records are excluded from all counts (AC3)."
)

# ── Sidebar — Filters ─────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Filters")

    try:
        min_d, max_d = get_date_bounds()
    except Exception as exc:
        st.error(
            f"Cannot reach the database: {exc}\n\n"
            "Set **DB_HOST**, **DB_NAME**, **DB_USER**, and **DB_PASS** "
            "environment variables, then refresh."
        )
        st.stop()

    raw_range = st.date_input(
        "Production Date Range",
        value=(min_d, max_d),
        min_value=min_d,
        max_value=max_d,
        help="Filters lots by their production date.",
    )

    # date_input returns a tuple once both endpoints are chosen
    if isinstance(raw_range, (list, tuple)) and len(raw_range) == 2:
        start_date, end_date = raw_range[0], raw_range[1]
    else:
        assert isinstance(raw_range, date)
        start_date = end_date = raw_range  # mid-selection fallback

    st.divider()

    # AC6 — filter control
    status_filter = st.radio(
        "Show",
        options=["All Defects", "Recurring Only"],
        index=0,
    )

# ── Fetch summary data ────────────────────────────────────────────────────────

try:
    df_raw = fetch_summary(start_date, end_date)
except Exception as exc:
    st.error(f"Summary query failed: {exc}")
    st.stop()

if df_raw.empty:
    st.info("No defect data found for the selected date range.")
    st.stop()

# AC6 — apply status filter
df_filtered = df_raw.copy()
if status_filter == "Recurring Only":
    df_filtered = df_filtered[df_filtered["Status"] == "Recurring"].reset_index(
        drop=True
    )
    if df_filtered.empty:
        st.info("No recurring defects found in the selected date range.")
        st.stop()

# Replace raw Status values with badge strings for display
df_display = df_filtered.copy()
df_display["Status"] = df_display["Status"].map(BADGE)

# ── Summary table (AC5, AC6, AC9) ────────────────────────────────────────────

st.subheader("Defect Summary")

styled = (
    df_display.style.apply(_highlight_row, axis=1)  # AC6: colour rows by status
    .hide(axis="index")
    .format(
        {
            "Lots Affected": "{:.0f}",
            "Weeks w/ Occurrences": "{:.0f}",
            "Total Qty Defects": "{:.0f}",
        },
        na_rep="—",
    )
)

st.dataframe(
    styled,
    use_container_width=True,
    column_config={
        "Lots Affected": st.column_config.NumberColumn(format="%d"),
        "Weeks w/ Occurrences": st.column_config.NumberColumn(format="%d"),
        "Total Qty Defects": st.column_config.NumberColumn(format="%d"),
    },
)

# ── Drill-down detail (AC7) ───────────────────────────────────────────────────

st.divider()
st.subheader("Defect Detail")

selected_code = st.selectbox(
    "Select a defect code to inspect",
    options=df_filtered["Defect Code"].tolist(),
)

if selected_code:
    summary_row = df_raw.loc[df_raw["Defect Code"] == selected_code].iloc[0]
    status_raw = summary_row["Status"]

    # AC8 — Insufficient data message
    if status_raw == "Insufficient Data":
        st.warning(
            f"⚠️ **Insufficient Data — {selected_code}**: "
            f"No defect occurrences with Qty Defects > 0 were recorded between "
            f"**{start_date.strftime('%Y-%m-%d')}** and **{end_date.strftime('%Y-%m-%d')}**. "
            "Classification cannot be determined. "
            "Confirm that inspection records are complete for this period."
        )

    # Metric summary strip
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Status", BADGE.get(status_raw, status_raw))
    c2.metric("Weeks w/ Occurrences", int(summary_row["Weeks w/ Occurrences"]))
    c3.metric("Lots Affected", int(summary_row["Lots Affected"]))
    c4.metric("Total Qty Defects", int(summary_row["Total Qty Defects"]))

    # Weekly breakdown table
    st.markdown("#### Weekly Breakdown")
    try:
        df_weekly = fetch_weekly_breakdown(selected_code, start_date, end_date)
    except Exception as exc:
        st.error(f"Weekly breakdown query failed: {exc}")
        df_weekly = pd.DataFrame()

    if df_weekly.empty:
        st.info("No records with Qty Defects > 0 in the selected period.")
    else:
        st.dataframe(df_weekly, use_container_width=True, hide_index=True)

    # Underlying inspection records table
    st.markdown("#### Underlying Inspection Records")
    try:
        df_records = fetch_records(selected_code, start_date, end_date)
    except Exception as exc:
        st.error(f"Records query failed: {exc}")
        df_records = pd.DataFrame()

    if df_records.empty:
        st.info("No underlying records in the selected period.")
    else:
        st.dataframe(df_records, use_container_width=True, hide_index=True)
