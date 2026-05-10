"""Excel ingestion scaffold — normalizes and validates .xlsx exports before DB load."""

import pandas as pd

REQUIRED_COLUMNS: set[str] = {
    "Lot_ID",
    "Defect_Code",
    "Qty_Defects",
}


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Strip whitespace from column names and string cell values."""
    pass


def filter_nonzero_defects(df: pd.DataFrame) -> pd.DataFrame:
    """Return only rows where Qty_Defects > 0 (AC3)."""
    pass


def validate_required_columns(df: pd.DataFrame) -> None:
    """Raise ValueError listing any column from REQUIRED_COLUMNS that is absent."""
    pass
