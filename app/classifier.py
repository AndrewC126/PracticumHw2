"""
Classification rules for defect recurrence analysis.

Extracted from the SQL CASE expression so the rules can be
unit-tested without a running database.
"""


def classify(distinct_lots: int, distinct_weeks: int) -> str:
    """Return the recurrence classification for one defect code.

    AC1: Recurring  — appears in > 1 lot AND > 1 calendar week.
    AC2: One-Off    — appears in exactly 1 lot.
    AC4: Insufficient Data — no qualifying records (0 lots) or multiple
         lots but only a single week (cannot confirm recurrence).
    """
    if distinct_lots > 1 and distinct_weeks > 1:
        return "Recurring"
    if distinct_lots == 1:
        return "One-Off"
    return "Insufficient Data"
