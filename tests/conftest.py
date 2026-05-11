"""
Root conftest — applies to all tests in tests/.

1. Patches streamlit before any app module is imported so @st.cache_data
   becomes a no-op in unit and integration tests.
2. Provides the shared `db_params` fixture used by integration and e2e tests.
   Tests that don't request it are unaffected.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock
from urllib.parse import urlparse

import psycopg2
import pytest
from dotenv import load_dotenv

# ── Streamlit mock ────────────────────────────────────────────────────────────

_st = MagicMock()
_st.cache_data = lambda ttl=None, **kwargs: lambda f: f
sys.modules["streamlit"] = _st

# ── Shared helpers ────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent.parent


def _parse_db_url(url: str) -> dict:
    u = urlparse(url)
    return dict(
        host=u.hostname,
        port=u.port or 5432,
        dbname=(u.path or "/testdb").lstrip("/"),
        user=u.username,
        password=u.password or "",
    )


def _exec_sql_file(cur, path: Path) -> None:
    """Execute every non-empty statement in a SQL file individually."""
    sql = path.read_text(encoding="utf-8")
    # Split on semicolons; filter out comment-only or whitespace-only fragments.
    for raw in sql.split(";"):
        stmt = raw.strip()
        # Skip pure-comment or empty fragments produced by the split.
        lines = [ln for ln in stmt.splitlines() if ln.strip() and not ln.strip().startswith("--")]
        if lines:
            cur.execute(stmt)


def apply_schema_and_seed(params: dict) -> None:
    """Drop existing tables, recreate from schema.sql, then load seed.sql."""
    conn = psycopg2.connect(**params)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS defect_records, lots, defect_types CASCADE")
        _exec_sql_file(cur, ROOT / "db" / "schema.sql")
        _exec_sql_file(cur, ROOT / "db" / "seed.sql")
    conn.close()


# ── Shared fixture ─────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def db_params():
    """Load .env.test and return psycopg2 connection params.

    Skips the requesting test (and any dependents) when the test database
    is not reachable, so the regular unit-test suite is never broken by a
    missing local Postgres instance.
    """
    load_dotenv(ROOT / ".env.test", override=True)
    url = os.getenv("DATABASE_URL", "")
    if not url:
        pytest.skip("DATABASE_URL not set in .env.test")
    params = _parse_db_url(url)
    try:
        conn = psycopg2.connect(**params, connect_timeout=5)
        conn.close()
    except Exception as exc:
        pytest.skip(f"Test database not reachable: {exc}")
    return params
