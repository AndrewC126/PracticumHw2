"""
Unit tests for db.py query functions — uses mocked _query so no database is needed.

Covers AC5 (summary columns) and AC7 (drill-down columns).
The conftest.py in this directory patches streamlit before any import.
"""

from datetime import date
from unittest.mock import patch

import pandas as pd

import app.db as db

# Column contracts derived from the user story and acceptance criteria
SUMMARY_REQUIRED_COLUMNS = {
    "Defect Code",
    "Lots Affected",
    "Weeks w/ Occurrences",
    "First Seen",
    "Last Seen",
    "Total Qty Defects",
    "Status",
}

WEEKLY_REQUIRED_COLUMNS = {
    "Year",
    "ISO Week",
    "Week Start (Mon)",
    "Week End (Sun)",
    "Lots",
    "Qty Defects",
    "Lots Involved",
}

RECORDS_REQUIRED_COLUMNS = {
    "Lot Number",
    "Production Date",
    "Defect Code",
    "Qty Defects",
    "Reporting Week",
    "Reporting Year",
}

VALID_STATUSES = {"Recurring", "One-Off", "Insufficient Data"}

_START = date(2025, 12, 15)
_END = date(2026, 1, 24)


def _summary_row(status: str = "Recurring") -> dict:
    return {
        "Defect Code": "BURR",
        "Lots Affected": 5,
        "Weeks w/ Occurrences": 3,
        "First Seen": date(2025, 12, 16),
        "Last Seen": date(2026, 1, 10),
        "Total Qty Defects": 12,
        "Status": status,
    }


def _weekly_row() -> dict:
    # Raw columns as returned by _WEEKLY_SQL before rename in fetch_weekly_breakdown
    return {
        "year": 2026,
        "week": 1,
        "lots": 2,
        "qty_defects": 4,
        "lots_involved": "LOT-20260103-003, LOT-20260104-002",
    }


def _records_row() -> dict:
    return {
        "Lot Number": "LOT-20260103-003",
        "Production Date": date(2026, 1, 3),
        "Defect Code": "BURR",
        "Qty Defects": 1,
        "Reporting Week": 1,
        "Reporting Year": 2026,
    }


# ---------------------------------------------------------------------------
# AC5 — Summary table exposes all required columns with valid status values
# ---------------------------------------------------------------------------


class TestFetchSummaryAC5:
    def test_returns_all_required_columns(self):
        with patch.object(db, "_query", return_value=pd.DataFrame([_summary_row()])):
            result = db.fetch_summary(_START, _END)
        assert SUMMARY_REQUIRED_COLUMNS.issubset(set(result.columns))

    def test_recurring_is_a_valid_status(self):
        with patch.object(db, "_query", return_value=pd.DataFrame([_summary_row("Recurring")])):
            result = db.fetch_summary(_START, _END)
        assert result["Status"].iloc[0] in VALID_STATUSES

    def test_one_off_is_a_valid_status(self):
        with patch.object(db, "_query", return_value=pd.DataFrame([_summary_row("One-Off")])):
            result = db.fetch_summary(_START, _END)
        assert result["Status"].iloc[0] in VALID_STATUSES

    def test_insufficient_data_is_a_valid_status(self):
        with patch.object(
            db, "_query", return_value=pd.DataFrame([_summary_row("Insufficient Data")])
        ):
            result = db.fetch_summary(_START, _END)
        assert result["Status"].iloc[0] in VALID_STATUSES

    def test_empty_result_returns_empty_dataframe(self):
        with patch.object(db, "_query", return_value=pd.DataFrame()):
            result = db.fetch_summary(_START, _END)
        assert result.empty


# ---------------------------------------------------------------------------
# AC7 — Weekly breakdown drill-down exposes all required columns
# ---------------------------------------------------------------------------


class TestFetchWeeklyBreakdownAC7:
    def test_returns_all_required_columns(self):
        with patch.object(db, "_query", return_value=pd.DataFrame([_weekly_row()])):
            result = db.fetch_weekly_breakdown("BURR", _START, _END)
        assert WEEKLY_REQUIRED_COLUMNS.issubset(set(result.columns))

    def test_week_start_is_a_monday(self):
        with patch.object(db, "_query", return_value=pd.DataFrame([_weekly_row()])):
            result = db.fetch_weekly_breakdown("BURR", _START, _END)
        week_start = result["Week Start (Mon)"].iloc[0]
        assert week_start.weekday() == 0  # Monday == 0

    def test_week_end_is_a_sunday(self):
        with patch.object(db, "_query", return_value=pd.DataFrame([_weekly_row()])):
            result = db.fetch_weekly_breakdown("BURR", _START, _END)
        week_end = result["Week End (Sun)"].iloc[0]
        assert week_end.weekday() == 6  # Sunday == 6

    def test_empty_query_returns_empty_dataframe(self):
        with patch.object(db, "_query", return_value=pd.DataFrame()):
            result = db.fetch_weekly_breakdown("BURR", _START, _END)
        assert result.empty


# ---------------------------------------------------------------------------
# AC7 — Underlying records drill-down exposes all required columns
# ---------------------------------------------------------------------------


class TestFetchRecordsAC7:
    def test_returns_all_required_columns(self):
        with patch.object(db, "_query", return_value=pd.DataFrame([_records_row()])):
            result = db.fetch_records("BURR", _START, _END)
        assert RECORDS_REQUIRED_COLUMNS.issubset(set(result.columns))

    def test_empty_query_returns_empty_dataframe(self):
        with patch.object(db, "_query", return_value=pd.DataFrame()):
            result = db.fetch_records("BURR", _START, _END)
        assert result.empty
