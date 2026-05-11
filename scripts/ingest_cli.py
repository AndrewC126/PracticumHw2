"""CLI for ingesting Excel inspection files into the database.

Usage:
    python scripts/ingest_cli.py                              # .env + data/sample
    python scripts/ingest_cli.py --env-file .env.test         # test DB
    python scripts/ingest_cli.py --data-dir path/to/xlsx      # custom directory
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from app.ingest import ingest_directory  # noqa: E402


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
    parser = argparse.ArgumentParser(description="Ingest Excel inspection files into the DB.")
    parser.add_argument("--env-file", default=".env", help="Path to env file (default: .env)")
    parser.add_argument(
        "--data-dir",
        default=str(ROOT / "data" / "sample"),
        help="Directory containing .xlsx files (default: data/sample)",
    )
    args = parser.parse_args()

    load_dotenv(args.env_file, override=True)
    params = _conn_params()

    print(f"Connecting to {params['host']}:{params['port']}/{params['dbname']} ...")
    try:
        conn = psycopg2.connect(**params)
    except Exception as exc:
        print(f"Connection failed: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Ingesting files from {args.data_dir} ...")
    try:
        results = ingest_directory(args.data_dir, conn)
    finally:
        conn.close()

    total = 0
    for filename, count in results.items():
        status = f"{count} rows inserted" if count else "skipped (no qualifying rows)"
        print(f"  {filename}: {status}")
        total += count

    print(f"\nTotal rows inserted: {total}")


if __name__ == "__main__":
    main()
