"""
Database access layer.

Connection is configured via environment variables:
  DB_HOST  (default: localhost)
  DB_PORT  (default: 5432)
  DB_NAME  (default: defect_db)
  DB_USER  (default: postgres)
  DB_PASS  (default: empty string)
"""

import os
from datetime import date

import pandas as pd
import psycopg2
import psycopg2.extras
import streamlit as st

# ── Connection ────────────────────────────────────────────────────────────────


def _conn_params() -> dict:
    return dict(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "defect_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASS", ""),
    )


def _query(sql: str, params=None) -> pd.DataFrame:
    conn = psycopg2.connect(**_conn_params())
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or ())
            rows = cur.fetchall()
        return pd.DataFrame([dict(r) for r in rows])
    finally:
        conn.close()


# ── Date bounds (for the date-range picker) ───────────────────────────────────


@st.cache_data(ttl=300)
def get_date_bounds() -> tuple:
    df = _query("SELECT MIN(production_date) AS min_d, MAX(production_date) AS max_d FROM lots")
    return df["min_d"].iloc[0], df["max_d"].iloc[0]


# ── Summary query (AC1-AC5, AC9) ──────────────────────────────────────────────
#
# Classification rules (AC1, AC2, AC4):
#   RECURRING        → same defect code in > 1 calendar week  AND  > 1 lot
#   ONE-OFF          → defect appears in exactly 1 lot
#   INSUFFICIENT DATA → no non-zero records exist in the selected period
#
# AC3: WHERE quantity_of_defects > 0 is applied inside the CTE so zero-defect
#      records are excluded from all counts and sums.
#
# AC9: ORDER BY Recurring first, then weeks DESC, then lots DESC.

_SUMMARY_SQL = """
WITH filtered AS (
    SELECT
        dr.defect_type_id,
        dr.lot_id,
        dr.quantity_of_defects,
        dr.reporting_week,
        dr.reporting_year,
        l.production_date
    FROM defect_records dr
    JOIN lots l ON dr.lot_id = l.lot_id
    WHERE dr.quantity_of_defects > 0          -- AC3
      AND l.production_date BETWEEN %s AND %s
)
SELECT
    dt.defect_code                                                     AS "Defect Code",
    COALESCE(COUNT(DISTINCT f.lot_id), 0)                              AS "Lots Affected",
    COALESCE(
        COUNT(DISTINCT (f.reporting_year * 100 + f.reporting_week)), 0
    )                                                                  AS "Weeks w/ Occurrences",
    MIN(f.production_date)                                             AS "First Seen",
    MAX(f.production_date)                                             AS "Last Seen",
    COALESCE(SUM(f.quantity_of_defects), 0)                            AS "Total Qty Defects",
    CASE
        WHEN COUNT(DISTINCT f.lot_id) > 1
             AND COUNT(DISTINCT (f.reporting_year * 100 + f.reporting_week)) > 1
             THEN 'Recurring'           -- AC1
        WHEN COUNT(DISTINCT f.lot_id) = 1
             THEN 'One-Off'             -- AC2
        ELSE 'Insufficient Data'        -- AC4
    END AS "Status"
FROM defect_types dt
LEFT JOIN filtered f ON dt.defect_type_id = f.defect_type_id
GROUP BY dt.defect_code
ORDER BY
    CASE
        WHEN COUNT(DISTINCT f.lot_id) > 1
             AND COUNT(DISTINCT (f.reporting_year * 100 + f.reporting_week)) > 1 THEN 1
        WHEN COUNT(DISTINCT f.lot_id) = 1 THEN 2
        ELSE 3
    END,
    COUNT(DISTINCT (f.reporting_year * 100 + f.reporting_week)) DESC,  -- AC9
    COUNT(DISTINCT f.lot_id) DESC
"""


@st.cache_data(ttl=300)
def fetch_summary(start_date: date, end_date: date) -> pd.DataFrame:
    return _query(_SUMMARY_SQL, (start_date, end_date))


# ── Weekly breakdown query (AC7) ──────────────────────────────────────────────

_WEEKLY_SQL = """
SELECT
    dr.reporting_year                                                   AS year,
    dr.reporting_week                                                   AS week,
    COUNT(DISTINCT dr.lot_id)                                           AS lots,
    SUM(dr.quantity_of_defects)                                         AS qty_defects,
    STRING_AGG(DISTINCT l.lot_number, ', ' ORDER BY l.lot_number)       AS lots_involved
FROM defect_records dr
JOIN defect_types dt ON dr.defect_type_id = dt.defect_type_id
JOIN lots         l  ON dr.lot_id         = l.lot_id
WHERE dt.defect_code         = %s
  AND dr.quantity_of_defects > 0      -- AC3
  AND l.production_date BETWEEN %s AND %s
GROUP BY dr.reporting_year, dr.reporting_week
ORDER BY dr.reporting_year, dr.reporting_week
"""


@st.cache_data(ttl=300)
def fetch_weekly_breakdown(defect_code: str, start_date: date, end_date: date) -> pd.DataFrame:
    df = _query(_WEEKLY_SQL, (defect_code, start_date, end_date))
    if df.empty:
        return df

    # Compute ISO week start (Monday) and end (Sunday) in Python — avoids
    # dialect-specific TO_DATE formatting in SQL.
    df["week_start"] = df.apply(
        lambda r: date.fromisocalendar(int(r["year"]), int(r["week"]), 1), axis=1
    )
    df["week_end"] = df.apply(
        lambda r: date.fromisocalendar(int(r["year"]), int(r["week"]), 7), axis=1
    )

    return df.rename(
        columns={
            "year": "Year",
            "week": "ISO Week",
            "week_start": "Week Start (Mon)",
            "week_end": "Week End (Sun)",
            "lots": "Lots",
            "qty_defects": "Qty Defects",
            "lots_involved": "Lots Involved",
        }
    )[
        [
            "Year",
            "ISO Week",
            "Week Start (Mon)",
            "Week End (Sun)",
            "Lots",
            "Qty Defects",
            "Lots Involved",
        ]
    ]


# ── Underlying records query (AC7) ────────────────────────────────────────────

_RECORDS_SQL = """
SELECT
    l.lot_number            AS "Lot Number",
    l.production_date       AS "Production Date",
    dt.defect_code          AS "Defect Code",
    dr.quantity_of_defects  AS "Qty Defects",
    dr.reporting_week       AS "Reporting Week",
    dr.reporting_year       AS "Reporting Year"
FROM defect_records dr
JOIN defect_types dt ON dr.defect_type_id = dt.defect_type_id
JOIN lots         l  ON dr.lot_id         = l.lot_id
WHERE dt.defect_code         = %s
  AND dr.quantity_of_defects > 0      -- AC3
  AND l.production_date BETWEEN %s AND %s
ORDER BY l.production_date, l.lot_number
"""


@st.cache_data(ttl=300)
def fetch_records(defect_code: str, start_date: date, end_date: date) -> pd.DataFrame:
    return _query(_RECORDS_SQL, (defect_code, start_date, end_date))
