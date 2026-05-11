"""
E2E test fixtures.

Starts a Streamlit process backed by the test database and provides a
`pagit statue` fixture pre-navigated to the running app.  All tests in this
directory are skipped when the test database is not reachable.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Generator
from pathlib import Path

import pytest

from tests.conftest import apply_schema_and_seed

ROOT = Path(__file__).parent.parent.parent
_PORT = 8502
_BASE_URL = f"http://localhost:{_PORT}"
_HEALTH = f"{_BASE_URL}/_stcore/health"
_STARTUP_TIMEOUT = 45  # seconds


def _wait_for_streamlit(timeout: int = _STARTUP_TIMEOUT) -> bool:
    for _ in range(timeout):
        try:
            with urllib.request.urlopen(_HEALTH, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(1)
    return False


@pytest.fixture(scope="session", autouse=True)
def setup_test_db_for_e2e(db_params: dict) -> None:
    """Ensure the test DB is initialised before the Streamlit process starts."""
    apply_schema_and_seed(db_params)


@pytest.fixture(scope="session")
def streamlit_app(setup_test_db_for_e2e, db_params: dict) -> Generator[str, None, None]:
    """Start the Streamlit app pointed at the test database. Yields the base URL."""
    env = {**os.environ}  # DATABASE_URL already overridden by db_params fixture

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(ROOT / "app" / "main.py"),
            f"--server.port={_PORT}",
            "--server.headless=true",
            "--server.runOnSave=false",
            "--server.fileWatcherType=none",
        ],
        env=env,
        cwd=str(ROOT),
    )

    ready = _wait_for_streamlit()
    if not ready:
        proc.terminate()
        proc.wait()
        pytest.fail(f"Streamlit did not become healthy within {_STARTUP_TIMEOUT}s")

    yield _BASE_URL

    proc.terminate()
    proc.wait()


@pytest.fixture
def app_page(page, streamlit_app: str):
    """
    A Playwright `page` pre-loaded with the Streamlit app.

    Waits for the dashboard title to appear before returning so tests can
    immediately interact with a fully-rendered page.
    """
    page.goto(streamlit_app, wait_until="domcontentloaded")
    # Wait until Streamlit has finished its initial data load
    page.wait_for_selector("h1:has-text('Defect Recurrence Analysis')", timeout=20_000)
    return page
