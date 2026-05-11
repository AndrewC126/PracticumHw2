"""
Integration-test fixtures.

These fixtures are only active for tests under tests/integration/.
They depend on `db_params` from the root conftest, which skips automatically
when the test database (localhost:5433) is not available.
"""

from __future__ import annotations

from pathlib import Path

import psycopg2
import pytest

from tests.conftest import apply_schema_and_seed

ROOT = Path(__file__).parent.parent.parent


@pytest.fixture(scope="session", autouse=True)
def setup_test_db(db_params: dict) -> None:
    """Drop, recreate, and seed the test database once for the whole session."""
    apply_schema_and_seed(db_params)


@pytest.fixture
def conn(db_params: dict):
    """Yield a fresh psycopg2 connection; close it after each test."""
    connection = psycopg2.connect(**db_params)
    yield connection
    connection.close()


@pytest.fixture
def empty_records_conn(db_params: dict):
    """
    Yield a connection with defect_records wiped clean.

    On teardown the full seed is re-applied so subsequent tests start from
    the canonical seeded state.
    """
    conn = psycopg2.connect(**db_params)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("TRUNCATE defect_records RESTART IDENTITY CASCADE")
    yield conn
    # Restore seed state so other tests are not affected.
    apply_schema_and_seed(db_params)
    conn.close()
