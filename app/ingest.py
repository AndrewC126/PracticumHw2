"""Excel ingestion scaffold — normalizes and validates .xlsx exports before DB load."""

import pandas as pd

REQUIRED_COLUMNS: set[str] = {
    "Lot_ID",
    "Defect_Code",
    "Qty_Defects",
}


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
