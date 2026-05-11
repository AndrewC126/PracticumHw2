"""
Integration tests for app/db.py — run against the real test database.

These tests verify the SQL queries and classification logic end-to-end
using the seeded data defined in db/seed.sql.

All tests in this module are automatically skipped when the test database
at localhost:5433 is not available (see tests/conftest.py::db_params).
"""

from __future__ import annotations

from datetime import date

import app.db as db

# Full seed date range
_START = date(2025, 12, 15)
_END = date(2026, 1, 24)

# Expected defect codes from seed.sql
_ALL_CODES = {"BURR", "COAT", "CRACK", "DIM", "POR", "SCR", "WELD"}

# Codes verified as Recurring in the seed data (>1 lot AND >1 week)
_RECURRING_CODES = {"BURR", "COAT", "CRACK", "DIM", "POR", "SCR", "WELD"}


# ── get_date_bounds ───────────────────────────────────────────────────────────


class TestGetDateBounds:
    def test_min_date_matches_seed(self, setup_test_db):
        min_d, _ = db.get_date_bounds()
        assert min_d == date(2025, 12, 15)

    def test_max_date_matches_seed(self, setup_test_db):
        _, max_d = db.get_date_bounds()
        assert max_d == date(2026, 1, 24)

    def test_min_is_before_max(self, setup_test_db):
        min_d, max_d = db.get_date_bounds()
        assert min_d < max_d


# ── fetch_summary (AC1, AC2, AC4, AC5, AC9) ──────────────────────────────────


class TestFetchSummaryIntegration:
    def test_returns_all_seven_defect_codes(self, setup_test_db):
        df = db.fetch_summary(_START, _END)
        assert set(df["Defect Code"]) == _ALL_CODES

    def test_required_columns_present(self, setup_test_db):
        df = db.fetch_summary(_START, _END)
        required = {
            "Defect Code",
            "Lots Affected",
            "Weeks w/ Occurrences",
            "First Seen",
            "Last Seen",
            "Total Qty Defects",
            "Status",
        }
        assert required.issubset(set(df.columns))

    def test_all_statuses_are_valid(self, setup_test_db):
        df = db.fetch_summary(_START, _END)
        valid = {"Recurring", "One-Off", "Insufficient Data"}
        assert set(df["Status"]).issubset(valid)

    def test_burr_is_recurring(self, setup_test_db):
        """BURR appears in 13 lots across 5 weeks in the seed — must be Recurring."""
        df = db.fetch_summary(_START, _END)
        row = df.loc[df["Defect Code"] == "BURR"].iloc[0]
        assert row["Status"] == "Recurring"

    def test_burr_lots_and_weeks_counts_are_positive(self, setup_test_db):
        df = db.fetch_summary(_START, _END)
        row = df.loc[df["Defect Code"] == "BURR"].iloc[0]
        assert row["Lots Affected"] > 1
        assert row["Weeks w/ Occurrences"] > 1

    def test_no_negative_counts(self, setup_test_db):
        df = db.fetch_summary(_START, _END)
        assert (df["Lots Affected"] >= 0).all()
        assert (df["Weeks w/ Occurrences"] >= 0).all()
        assert (df["Total Qty Defects"] >= 0).all()

    def test_ac9_recurring_rows_sort_before_others(self, setup_test_db):
        """AC9: Recurring rows must appear first in the result set."""
        df = db.fetch_summary(_START, _END)
        statuses = df["Status"].tolist()
        recurring_idx = [i for i, s in enumerate(statuses) if s == "Recurring"]
        non_recurring_idx = [i for i, s in enumerate(statuses) if s != "Recurring"]
        if recurring_idx and non_recurring_idx:
            assert max(recurring_idx) < min(non_recurring_idx), (
                "All Recurring rows must precede One-Off / Insufficient Data rows"
            )

    def test_narrow_date_range_reduces_lot_count(self, setup_test_db):
        """Filtering to a single week returns fewer or equal lots than the full range."""
        df_full = db.fetch_summary(_START, _END)
        df_narrow = db.fetch_summary(date(2026, 1, 5), date(2026, 1, 11))
        burr_full = df_full.loc[df_full["Defect Code"] == "BURR", "Lots Affected"].iloc[0]
        burr_narrow = df_narrow.loc[df_narrow["Defect Code"] == "BURR", "Lots Affected"].iloc[0]
        assert burr_narrow <= burr_full

    def test_date_range_with_no_defects_returns_insufficient_data(self, setup_test_db):
        """A date range before any production yields Insufficient Data for all codes."""
        df = db.fetch_summary(date(2024, 1, 1), date(2024, 1, 31))
        assert (df["Status"] == "Insufficient Data").all()

    def test_first_seen_lte_last_seen(self, setup_test_db):
        df = db.fetch_summary(_START, _END)
        have_data = df[df["Lots Affected"] > 0]
        assert (have_data["First Seen"] <= have_data["Last Seen"]).all()


# ── fetch_weekly_breakdown (AC7) ──────────────────────────────────────────────


class TestFetchWeeklyBreakdownIntegration:
    def test_burr_weekly_columns_present(self, setup_test_db):
        df = db.fetch_weekly_breakdown("BURR", _START, _END)
        required = {
            "Year",
            "ISO Week",
            "Week Start (Mon)",
            "Week End (Sun)",
            "Lots",
            "Qty Defects",
            "Lots Involved",
        }
        assert required.issubset(set(df.columns))

    def test_burr_has_multiple_weeks(self, setup_test_db):
        df = db.fetch_weekly_breakdown("BURR", _START, _END)
        assert len(df) > 1

    def test_week_start_is_monday(self, setup_test_db):
        df = db.fetch_weekly_breakdown("BURR", _START, _END)
        assert (df["Week Start (Mon)"].apply(lambda d: d.weekday()) == 0).all()

    def test_week_end_is_sunday(self, setup_test_db):
        df = db.fetch_weekly_breakdown("BURR", _START, _END)
        assert (df["Week End (Sun)"].apply(lambda d: d.weekday()) == 6).all()

    def test_week_start_before_week_end(self, setup_test_db):
        df = db.fetch_weekly_breakdown("BURR", _START, _END)
        assert (df["Week Start (Mon)"] <= df["Week End (Sun)"]).all()

    def test_qty_defects_all_positive(self, setup_test_db):
        """AC3: zero-defect records must never appear in the breakdown."""
        df = db.fetch_weekly_breakdown("BURR", _START, _END)
        assert (df["Qty Defects"] > 0).all()

    def test_lots_involved_contains_lot_numbers(self, setup_test_db):
        df = db.fetch_weekly_breakdown("BURR", _START, _END)
        first_lots = df["Lots Involved"].iloc[0]
        assert "LOT-" in first_lots

    def test_nonexistent_code_returns_empty(self, setup_test_db):
        df = db.fetch_weekly_breakdown("XXXXXX", _START, _END)
        assert df.empty

    def test_narrow_range_returns_subset_of_weeks(self, setup_test_db):
        df_full = db.fetch_weekly_breakdown("BURR", _START, _END)
        df_narrow = db.fetch_weekly_breakdown("BURR", date(2026, 1, 1), date(2026, 1, 14))
        assert len(df_narrow) <= len(df_full)


# ── fetch_records (AC7) ───────────────────────────────────────────────────────


class TestFetchRecordsIntegration:
    def test_burr_records_columns_present(self, setup_test_db):
        df = db.fetch_records("BURR", _START, _END)
        required = {
            "Lot Number",
            "Production Date",
            "Defect Code",
            "Qty Defects",
            "Reporting Week",
            "Reporting Year",
        }
        assert required.issubset(set(df.columns))

    def test_burr_records_defect_code_is_burr(self, setup_test_db):
        df = db.fetch_records("BURR", _START, _END)
        assert (df["Defect Code"] == "BURR").all()

    def test_burr_records_qty_all_positive(self, setup_test_db):
        """AC3: only non-zero quantity records should be returned."""
        df = db.fetch_records("BURR", _START, _END)
        assert (df["Qty Defects"] > 0).all()

    def test_records_sorted_by_production_date(self, setup_test_db):
        df = db.fetch_records("BURR", _START, _END)
        dates = df["Production Date"].tolist()
        assert dates == sorted(dates)

    def test_lot_numbers_match_canonical_format(self, setup_test_db):
        df = db.fetch_records("BURR", _START, _END)
        import re

        pattern = re.compile(r"^LOT-\d{8}-\d{3}$")
        assert df["Lot Number"].apply(lambda s: bool(pattern.match(s))).all()

    def test_nonexistent_code_returns_empty(self, setup_test_db):
        df = db.fetch_records("XXXXXX", _START, _END)
        assert df.empty
