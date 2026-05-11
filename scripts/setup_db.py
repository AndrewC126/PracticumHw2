"""Initialize the database: apply schema.sql then seed.sql.

Usage:
    python scripts/setup_db.py             # uses .env
    python scripts/setup_db.py --test      # uses .env.test
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent


def _conn_params() -> dict:
    url = os.getenv("DATABASE_URL")
    if url:
        u = urlparse(url)
        return dict(
            host=u.hostname,
            port=u.port or 5432,
            dbname=(u.path or "/defect_db").lstrip("/"),
            user=u.username,
            password=u.password or "",
        )
    return dict(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "defect_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASS", ""),
    )


def main() -> None:
    env_file = ".env.test" if "--test" in sys.argv else ".env"
    load_dotenv(ROOT / env_file, override=True)

    params = _conn_params()
    print(f"Connecting to {params['host']}:{params['port']}/{params['dbname']} ...")

    conn = psycopg2.connect(**params)
    conn.autocommit = True

    with conn.cursor() as cur:
        for sql_name in ("schema.sql", "seed.sql"):
            path = ROOT / "db" / sql_name
            print(f"  Applying {sql_name} ...", end=" ", flush=True)
            try:
                cur.execute(path.read_text(encoding="utf-8"))
                print("done")
            except psycopg2.errors.DuplicateTable:
                # schema already applied; safe to continue to seed
                conn.rollback()
                print("skipped (tables already exist)")
            except Exception as exc:
                conn.rollback()
                print(f"FAILED: {exc}", file=sys.stderr)
                sys.exit(1)

    conn.close()
    print("Database ready.")


if __name__ == "__main__":
    main()
