"""Excel ingestion — normalizes, validates, and upserts .xlsx inspection exports."""

from __future__ import annotations

import os
import re
from datetime import date as _date
from typing import Any

import pandas as pd

REQUIRED_COLUMNS: set[str] = {
    "Lot_ID",
    "Defect_Code",
    "Qty_Defects",
}

# Maps Excel-style spaced column names (after strip) to underscore equivalents.
_COLUMN_MAP: dict[str, str] = {
    "Lot ID": "Lot_ID",
    "Defect Code": "Defect_Code",
    "Qty Defects": "Qty_Defects",
    "Inspection Date": "Inspection_Date",
    "Lot ID (Normalized?)": "Lot_ID_Normalized",
}

_INSERT_SQL = """
INSERT INTO defect_records
    (defect_type_id, lot_id, quantity_of_defects, reporting_week, reporting_year)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (defect_type_id, lot_id) DO NOTHING
"""


# ── Helpers (also used by unit tests) ────────────────────────────────────────


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Strip whitespace from column names and string cell values."""
    df = df.copy()
    df.columns = df.columns.str.strip()
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].str.strip()
    return df


def filter_nonzero_defects(df: pd.DataFrame) -> pd.DataFrame:
    """Return only rows where Qty_Defects > 0 (AC3)."""
    return df[df["Qty_Defects"] > 0].reset_index(drop=True)


def validate_required_columns(df: pd.DataFrame) -> None:
    """Raise ValueError listing any column from REQUIRED_COLUMNS that is absent."""
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")


def normalize_lot_id(lot_id: Any) -> str:
    """Canonicalize a messily-formatted lot ID to LOT-YYYYMMDD-NNN.

    Handles common variants: L0T (zero mistyped), spaces, underscores,
    mixed case, and run-together digits (LOT20251215001).
    """
    s = str(lot_id).strip().upper()
    s = s.replace("L0T", "LOT")  # fix digit-zero mistyped as letter-O
    digits_only = re.sub(r"[^A-Z0-9]", "", s)
    m = re.match(r"^LOT(\d{8})(\d{3})$", digits_only)
    if m:
        return f"LOT-{m.group(1)}-{m.group(2)}"
    return s  # return cleaned original if the pattern doesn't match


def _standardize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Rename spaced Excel headers to their underscore equivalents."""
    return df.rename(columns=_COLUMN_MAP)


def _parse_date_series(s: pd.Series) -> pd.Series:
    """Parse a Series of mixed-format date strings into Timestamps.

    Tries month-first (MM/DD/YYYY, YYYY-MM-DD) then day-first (DD-MM-YYYY)
    for any entries that remain NaT after the first pass.
    """
    if pd.api.types.is_datetime64_any_dtype(s):
        return s

    str_s = s.astype(str).str.strip()
    result = pd.to_datetime(str_s, dayfirst=False, errors="coerce")

    # Retry NaT rows with day-first (catches DD-MM-YYYY like Inspector B)
    mask = result.isna() & (str_s != "nan") & str_s.notna()
    if mask.any():
        retry = pd.to_datetime(str_s[mask], dayfirst=True, errors="coerce")
        result = result.copy()
        result[mask] = retry

    return result


# ── Orchestrator ──────────────────────────────────────────────────────────────


def ingest_excel(filepath: str, conn: Any) -> int:
    """Read one .xlsx file, normalize it, and upsert qualifying records into the DB.

    Skips files that lack the required columns (e.g. Ops logs).
    Returns the number of rows newly inserted (conflicts not counted).
    """
    df = pd.read_excel(filepath)
    df = normalize_columns(df)
    df = _standardize_column_names(df)

    # Consolidation file may include a pre-normalized lot ID column — prefer it.
    if "Lot_ID_Normalized" in df.columns:
        mask = df["Lot_ID_Normalized"].notna() & df["Lot_ID_Normalized"].astype(str).str.strip().ne(
            ""
        )
        df.loc[mask, "Lot_ID"] = df.loc[mask, "Lot_ID_Normalized"]

    try:
        validate_required_columns(df)
    except ValueError:
        return 0  # Ops-style logs without defect columns — skip silently

    df = df.dropna(subset=["Defect_Code"])
    df = filter_nonzero_defects(df)
    if df.empty:
        return 0

    df["Lot_ID"] = df["Lot_ID"].apply(normalize_lot_id)

    # Derive ISO reporting week/year from Inspection_Date when available.
    if "Inspection_Date" in df.columns:
        dates = _parse_date_series(df["Inspection_Date"])
    else:
        dates = pd.Series([pd.NaT] * len(df), dtype="datetime64[ns]")

    iso_cal = dates.dt.isocalendar()  # DataFrame with columns year, week, weekday
    today = _date.today()
    today_iso = today.isocalendar()
    rweeks = iso_cal["week"].fillna(today_iso[1]).astype(int)
    ryears = iso_cal["year"].fillna(today_iso[0]).astype(int)

    # Pre-fetch lookup maps to avoid per-row queries.
    with conn.cursor() as cur:
        cur.execute("SELECT lot_number, lot_id FROM lots")
        lot_map: dict[str, int] = {row[0]: row[1] for row in cur.fetchall()}

        cur.execute("SELECT defect_code, defect_type_id FROM defect_types")
        defect_map: dict[str, int] = {row[0]: row[1] for row in cur.fetchall()}

    # Build records, deduplicating by (defect_type_id, lot_id) — keep first.
    seen: set[tuple[int, int]] = set()
    records: list[tuple[int, int, int, int, int]] = []
    for i, (_, row) in enumerate(df.iterrows()):
        lot_id_db = lot_map.get(str(row["Lot_ID"]))
        defect_type_id = defect_map.get(str(row["Defect_Code"]).upper())
        if lot_id_db is None or defect_type_id is None:
            continue
        key = (defect_type_id, lot_id_db)
        if key in seen:
            continue
        seen.add(key)
        records.append(
            (
                defect_type_id,
                lot_id_db,
                int(row["Qty_Defects"]),
                int(rweeks.iloc[i]),
                int(ryears.iloc[i]),
            )
        )

    if not records:
        return 0

    inserted = 0
    with conn.cursor() as cur:
        for rec in records:
            cur.execute(_INSERT_SQL, rec)
            if cur.rowcount > 0:
                inserted += 1
    conn.commit()
    return inserted


def ingest_directory(directory: str, conn: Any) -> dict[str, int]:
    """Process every .xlsx file in *directory* via *conn*.

    Returns a mapping of filename → rows inserted.
    Files without the required columns (Ops logs) are skipped with count 0.
    """
    results: dict[str, int] = {}
    for filename in sorted(os.listdir(directory)):
        if not filename.lower().endswith(".xlsx"):
            continue
        filepath = os.path.join(directory, filename)
        results[filename] = ingest_excel(filepath, conn)
    return results
