"""
Integration tests for app/ingest.py — run against the real test database.

Covers:
 - normalize_lot_id: round-trips through the canonical format
 - ingest_excel:     file-level upsert against a real DB
 - ingest_directory: full directory sweep, idempotency
"""

from __future__ import annotations

from pathlib import Path

import psycopg2
import pytest

from app.ingest import ingest_directory, ingest_excel, normalize_lot_id

ROOT = Path(__file__).parent.parent.parent
SAMPLE_DIR = str(ROOT / "data" / "sample")

QE_FILES = [
    "QE_Inspector_A_DailyLog.xlsx",
    "QE_Inspector_B_WeeklyLog.xlsx",
    "QE_Temp_Consolidation_CopyPaste.xlsx",
]
OPS_FILES = [
    "Ops_Production_Log.xlsx",
    "Ops_Shipping_Log.xlsx",
]


# ── normalize_lot_id (round-trip via DB) ──────────────────────────────────────


class TestNormalizeLotIdIntegration:
    """Verify that the canonical lot IDs produced by normalize_lot_id actually
    exist in the lots table (i.e. round-trip matches the seed data)."""

    _MESSY_VALID = [
        ("L0T-20251216-001", "LOT-20251216-001"),
        ("LOT 20251220 003", "LOT-20251220-003"),
        ("LOT_20260108-001", "LOT-20260108-001"),
        ("LOT20251225001", "LOT-20251225-001"),
        ("Lot-20260101-001", "LOT-20260101-001"),
    ]

    @pytest.mark.parametrize("raw,expected", _MESSY_VALID)
    def test_normalized_lot_exists_in_db(self, raw, expected, conn):
        result = normalize_lot_id(raw)
        assert result == expected
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM lots WHERE lot_number = %s", (result,))
            assert cur.fetchone() is not None, f"{result} not found in lots table"


# ── ingest_excel — idempotency ────────────────────────────────────────────────


class TestIngestExcelIdempotency:
    """Running ingest on already-seeded data must insert 0 new rows (ON CONFLICT DO NOTHING)."""

    @pytest.mark.parametrize("filename", QE_FILES)
    def test_second_run_inserts_nothing(self, filename, db_params, setup_test_db):
        filepath = str(ROOT / "data" / "sample" / filename)
        conn = psycopg2.connect(**db_params)
        try:
            inserted = ingest_excel(filepath, conn)
        finally:
            conn.close()
        assert inserted == 0, f"Expected 0 new rows on second run of {filename}, got {inserted}"

    @pytest.mark.parametrize("filename", OPS_FILES)
    def test_ops_files_are_skipped(self, filename, db_params, setup_test_db):
        """Ops logs lack Defect_Code / Qty_Defects — ingest must skip them gracefully."""
        filepath = str(ROOT / "data" / "sample" / filename)
        conn = psycopg2.connect(**db_params)
        try:
            inserted = ingest_excel(filepath, conn)
        finally:
            conn.close()
        assert inserted == 0


# ── ingest_excel — fresh insert ───────────────────────────────────────────────


class TestIngestExcelFreshInsert:
    """With defect_records empty, ingesting the QE files should produce > 0 new rows."""

    @pytest.mark.parametrize("filename", QE_FILES)
    def test_inserts_rows_into_empty_table(self, filename, empty_records_conn):
        filepath = str(ROOT / "data" / "sample" / filename)
        inserted = ingest_excel(filepath, empty_records_conn)
        assert inserted > 0, f"Expected rows inserted from {filename}, got 0"

    def test_records_respect_ac3_no_zero_qty(self, empty_records_conn):
        """AC3: No zero-defect row should end up in defect_records after ingestion."""
        filepath = str(ROOT / "data" / "sample" / "QE_Inspector_A_DailyLog.xlsx")
        ingest_excel(filepath, empty_records_conn)
        with empty_records_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM defect_records WHERE quantity_of_defects = 0")
            assert cur.fetchone()[0] == 0

    def test_inserted_rows_reference_valid_lots(self, empty_records_conn):
        """Every inserted record must reference an existing lot via FK."""
        filepath = str(ROOT / "data" / "sample" / "QE_Inspector_A_DailyLog.xlsx")
        ingest_excel(filepath, empty_records_conn)
        with empty_records_conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM defect_records dr
                LEFT JOIN lots l ON dr.lot_id = l.lot_id
                WHERE l.lot_id IS NULL
                """
            )
            assert cur.fetchone()[0] == 0

    def test_inserted_rows_reference_valid_defect_types(self, empty_records_conn):
        filepath = str(ROOT / "data" / "sample" / "QE_Inspector_B_WeeklyLog.xlsx")
        ingest_excel(filepath, empty_records_conn)
        with empty_records_conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM defect_records dr
                LEFT JOIN defect_types dt ON dr.defect_type_id = dt.defect_type_id
                WHERE dt.defect_type_id IS NULL
                """
            )
            assert cur.fetchone()[0] == 0

    def test_uniqueness_constraint_not_violated(self, empty_records_conn):
        """Duplicate (defect_type_id, lot_id) pairs must be deduplicated before insert."""
        filepath = str(ROOT / "data" / "sample" / "QE_Inspector_A_DailyLog.xlsx")
        # Should not raise psycopg2.errors.UniqueViolation
        ingest_excel(filepath, empty_records_conn)

    def test_consolidation_file_prefers_normalized_lot_id(self, empty_records_conn):
        """QE_Temp_Consolidation uses 'Lot ID (Normalized?)' — those lots must be matched."""
        filepath = str(ROOT / "data" / "sample" / "QE_Temp_Consolidation_CopyPaste.xlsx")
        inserted = ingest_excel(filepath, empty_records_conn)
        # The file has 12 rows, all POR; some have messy lot IDs but normalized col is provided.
        # At least some should resolve and be inserted.
        assert inserted > 0


# ── ingest_directory ──────────────────────────────────────────────────────────


class TestIngestDirectoryIntegration:
    def test_returns_dict_keyed_by_filename(self, db_params, setup_test_db):
        conn = psycopg2.connect(**db_params)
        try:
            results = ingest_directory(SAMPLE_DIR, conn)
        finally:
            conn.close()
        assert isinstance(results, dict)
        for key in results:
            assert key.endswith(".xlsx")

    def test_all_five_files_processed(self, db_params, setup_test_db):
        conn = psycopg2.connect(**db_params)
        try:
            results = ingest_directory(SAMPLE_DIR, conn)
        finally:
            conn.close()
        assert len(results) == 5

    def test_ops_files_produce_zero_insertions(self, db_params, setup_test_db):
        conn = psycopg2.connect(**db_params)
        try:
            results = ingest_directory(SAMPLE_DIR, conn)
        finally:
            conn.close()
        for ops_file in OPS_FILES:
            assert results.get(ops_file, 0) == 0

    def test_idempotent_on_seeded_db(self, db_params, setup_test_db):
        """Running over an already-seeded DB should insert 0 total rows."""
        conn = psycopg2.connect(**db_params)
        try:
            results = ingest_directory(SAMPLE_DIR, conn)
        finally:
            conn.close()
        assert sum(results.values()) == 0

    def test_fresh_db_inserts_positive_total(self, empty_records_conn):
        results = ingest_directory(SAMPLE_DIR, empty_records_conn)
        assert sum(results.values()) > 0
