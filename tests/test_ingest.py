"""Unit tests for ingest.py — covers AC3 and column normalization."""

import pandas as pd
import pytest

from app.ingest import (
    filter_nonzero_defects,
    normalize_columns,
    validate_required_columns,
)


# ---------------------------------------------------------------------------
# AC3 — Zero-defect records are excluded from all counts and sums
# ---------------------------------------------------------------------------


class TestAC3ZeroDefectExclusion:
    def test_removes_rows_where_qty_is_zero(self):
        df = pd.DataFrame({"Qty_Defects": [0, 1, 0, 5]})
        result = filter_nonzero_defects(df)
        assert list(result["Qty_Defects"]) == [1, 5]

    def test_all_zero_rows_return_empty_dataframe(self):
        df = pd.DataFrame({"Qty_Defects": [0, 0, 0]})
        result = filter_nonzero_defects(df)
        assert result.empty

    def test_all_nonzero_rows_pass_through_unchanged(self):
        df = pd.DataFrame({"Qty_Defects": [1, 2, 3]})
        result = filter_nonzero_defects(df)
        assert len(result) == 3

    def test_preserves_other_columns_for_passing_rows(self):
        df = pd.DataFrame(
            {
                "Lot_ID": ["LOT-001", "LOT-002"],
                "Qty_Defects": [0, 4],
            }
        )
        result = filter_nonzero_defects(df)
        assert result["Lot_ID"].iloc[0] == "LOT-002"


# ---------------------------------------------------------------------------
# Column normalization (supports Assumption 1: column names may differ slightly)
# ---------------------------------------------------------------------------


class TestNormalizeColumns:
    def test_strips_leading_and_trailing_whitespace_from_column_names(self):
        df = pd.DataFrame({" Lot_ID ": [1], "  Defect_Code  ": ["DC-A"]})
        result = normalize_columns(df)
        assert "Lot_ID" in result.columns
        assert "Defect_Code" in result.columns

    def test_strips_whitespace_from_string_cell_values(self):
        df = pd.DataFrame(
            {
                "Lot_ID": [" LOT-001 "],
                "Defect_Code": [" BURR  "],
            }
        )
        result = normalize_columns(df)
        assert result["Lot_ID"].iloc[0] == "LOT-001"
        assert result["Defect_Code"].iloc[0] == "BURR"

    def test_non_string_columns_are_unaffected(self):
        df = pd.DataFrame({"Qty_Defects": [3]})
        result = normalize_columns(df)
        assert result["Qty_Defects"].iloc[0] == 3


# ---------------------------------------------------------------------------
# Required column validation
# ---------------------------------------------------------------------------


class TestValidateRequiredColumns:
    def test_passes_silently_when_all_required_columns_are_present(self):
        df = pd.DataFrame({"Lot_ID": [], "Defect_Code": [], "Qty_Defects": []})
        validate_required_columns(df)  # must not raise

    def test_raises_value_error_when_one_column_is_missing(self):
        df = pd.DataFrame({"Lot_ID": [], "Defect_Code": []})
        with pytest.raises(ValueError):
            validate_required_columns(df)

    def test_raises_value_error_when_dataframe_is_empty_schema(self):
        df = pd.DataFrame()
        with pytest.raises(ValueError):
            validate_required_columns(df)

    def test_error_message_names_the_missing_column(self):
        df = pd.DataFrame({"Lot_ID": [], "Defect_Code": []})
        with pytest.raises(ValueError, match="Qty_Defects"):
            validate_required_columns(df)
