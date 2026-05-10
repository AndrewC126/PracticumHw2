"""Unit tests for classifier.py — covers AC1, AC2, and AC4."""

from app.classifier import classify


# ---------------------------------------------------------------------------
# AC1 — Recurring
# ---------------------------------------------------------------------------


class TestAC1Recurring:
    def test_two_lots_two_weeks_is_recurring(self):
        assert classify(distinct_lots=2, distinct_weeks=2) == "Recurring"

    def test_many_lots_many_weeks_is_recurring(self):
        assert classify(distinct_lots=5, distinct_weeks=3) == "Recurring"

    def test_boundary_exactly_two_of_each_qualifies(self):
        assert classify(distinct_lots=2, distinct_weeks=2) == "Recurring"

    def test_multiple_lots_but_single_week_is_not_recurring(self):
        assert classify(distinct_lots=3, distinct_weeks=1) != "Recurring"

    def test_single_lot_multiple_weeks_is_not_recurring(self):
        assert classify(distinct_lots=1, distinct_weeks=4) != "Recurring"


# ---------------------------------------------------------------------------
# AC2 — One-Off
# ---------------------------------------------------------------------------


class TestAC2OneOff:
    def test_one_lot_one_week_is_one_off(self):
        assert classify(distinct_lots=1, distinct_weeks=1) == "One-Off"

    def test_one_lot_spanning_multiple_weeks_is_still_one_off(self):
        # Same lot reported across several weeks is not a recurrence
        assert classify(distinct_lots=1, distinct_weeks=4) == "One-Off"


# ---------------------------------------------------------------------------
# AC4 — Insufficient Data
# ---------------------------------------------------------------------------


class TestAC4InsufficientData:
    def test_no_qualifying_records_is_insufficient(self):
        assert classify(distinct_lots=0, distinct_weeks=0) == "Insufficient Data"

    def test_multiple_lots_in_a_single_week_is_insufficient(self):
        # AC1 requires > 1 week; two lots in one week cannot confirm recurrence
        assert classify(distinct_lots=2, distinct_weeks=1) == "Insufficient Data"

    def test_zero_lots_with_nonzero_weeks_is_insufficient(self):
        assert classify(distinct_lots=0, distinct_weeks=2) == "Insufficient Data"
