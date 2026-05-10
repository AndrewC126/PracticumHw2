# Defect Recurrence Analysis

A quality-engineering dashboard that identifies whether a defect type appears across multiple production lots over time, distinguishing recurring issues from one-off incidents.

---

## Project Description

Manufacturing inspection data is exported from a legacy ERP system as Excel files. This tool ingests those files into a PostgreSQL database and presents a Streamlit dashboard where quality engineers can:

- See every defect code classified as **Recurring**, **One-Off**, or **Insufficient Data**
- Filter the list to show only recurring defects
- Select a date range to scope the analysis to a specific production window
- Drill into any defect code to see a week-by-week breakdown of affected lots and total defect quantities
- View the underlying inspection records used to make each classification

**Classification rules**

| Status | Condition |
|---|---|
| Recurring | Same defect code observed in > 1 calendar week AND > 1 lot |
| One-Off | Defect appears in exactly 1 lot |
| Insufficient Data | No non-zero defect records found in the selected period |

Records with `Qty Defects = 0` are excluded from all counts and classification logic.

**Tech stack:** PostgreSQL · Python 3.12 · Streamlit · pandas · psycopg2

---

## How to Run / Build

### Prerequisites

- Python 3.12+
- PostgreSQL 14+ running locally (or accessible via network)

### 1 — Clone and install dependencies

```bash
git clone <repo-url>
cd Markdown_Hw1
pip install -r requirements.txt
```

### 2 — Create the database

Connect to PostgreSQL and create an empty database:

```sql
CREATE DATABASE defect_db;
```

### 3 — Apply the schema

```bash
psql -U postgres -d defect_db -f db/schema.sql
```

### 4 — Load seed data

```bash
psql -U postgres -d defect_db -f db/seed.sql
```

This populates the database from the normalised Excel source files. The seed file truncates and reloads all three tables, so it is safe to re-run.

### 5 — Configure environment variables

| Variable | Default | Description |
|---|---|---|
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_NAME` | `defect_db` | Database name |
| `DB_USER` | `postgres` | Database user |
| `DB_PASS` | _(empty)_ | Database password |

**PowerShell**

```powershell
$env:DB_NAME = "defect_db"
$env:DB_USER = "postgres"
$env:DB_PASS = "your_password"
```

**Bash / macOS / Linux**

```bash
export DB_NAME=defect_db
export DB_USER=postgres
export DB_PASS=your_password
```

### 6 — Start the dashboard

```bash
streamlit run app/main.py
```

The app opens in your browser at `http://localhost:8501`.

---

## Usage Examples

### Viewing the defect summary

When the dashboard loads, the **Defect Summary** table displays all defect codes sorted by priority — recurring defects appear first, ordered by the number of weeks with occurrences (descending), then by lots affected (descending).

Each row shows:

| Column | Description |
|---|---|
| Defect Code | Short code (e.g. `BURR`, `WELD`) |
| Status | 🔴 Recurring · 🔵 One-Off · ⚠️ Insufficient Data |
| Weeks w/ Occurrences | Distinct calendar weeks where `Qty Defects > 0` |
| Lots Affected | Distinct lots where the defect appeared |
| First Seen | Earliest production date with a defect occurrence |
| Last Seen | Most recent production date with a defect occurrence |
| Total Qty Defects | Sum of all defect quantities in the selected period |

### Filtering by date range

Use the **Production Date Range** picker in the left sidebar to narrow the analysis to a specific window. All counts, classifications, and drill-down results update automatically.

### Filtering to recurring defects only

Toggle **Recurring Only** in the sidebar to hide One-Off and Insufficient Data rows. This is useful when reviewing only the defects that require corrective action.

**Example:** With the full date range selected, toggling Recurring Only shows defects like `BURR`, `WELD`, and `POR` — each observed across multiple weeks and lots.

### Drilling into a defect

Use the **Select a defect code** dropdown under the Defect Detail heading. Two tables appear:

**Weekly Breakdown** — one row per calendar week:

| Year | ISO Week | Week Start (Mon) | Week End (Sun) | Lots | Qty Defects | Lots Involved |
|---|---|---|---|---|---|---|
| 2025 | 51 | 2025-12-15 | 2025-12-21 | 2 | 4 | LOT-20251216-001, LOT-20251220-003 |
| 2026 | 2 | 2025-12-29 | 2026-01-04 | 1 | 1 | LOT-20260102-001 |

**Underlying Inspection Records** — every raw record contributing to the classification:

| Lot Number | Production Date | Defect Code | Qty Defects | Reporting Week | Reporting Year |
|---|---|---|---|---|---|
| LOT-20251216-001 | 2025-12-16 | BURR | 1 | 51 | 2025 |

### Insufficient data

When a defect code has no non-zero records in the selected period, the detail panel shows a warning explaining the date range and that classification cannot be made. Narrowing the date range further or re-examining the source Excel files is recommended.

---

## How to Run Tests

There is no automated test suite yet. The sections below describe the manual verification steps and the structure to follow when adding automated tests.

### Manual verification — SQL queries

The file `db/sample_queries.sql` contains three reference queries that can be run directly against the seeded database to verify classification logic:

```bash
psql -U postgres -d defect_db -f db/sample_queries.sql
```

**Query 1** — classification summary: confirms every defect code is classified correctly using the same `COUNT(DISTINCT lot_id)` and `COUNT(DISTINCT reporting_week)` logic used by the dashboard.

**Query 2** — lot-level detail for a single defect code: replace `'D-001'` with any code (e.g. `'BURR'`) to inspect the individual lot records contributing to the classification.

**Query 3** — insufficient data check: returns defect codes that have no non-zero defect records, confirming the Insufficient Data classification is applied correctly.

### Adding automated tests with pytest

Install pytest:

```bash
pip install pytest
```

Place test files in a `tests/` directory at the project root. A recommended starting structure:

```
tests/
  test_classification.py   # unit tests for classification logic
  test_queries.py          # integration tests against a test database
  conftest.py              # shared fixtures (test DB connection, seed data)
```

Run all tests:

```bash
pytest tests/
```

Run with verbose output:

```bash
pytest tests/ -v
```

**Example test cases to implement:**

- A defect appearing in 2 lots across 2 weeks is classified as `Recurring`
- A defect appearing in 1 lot only is classified as `One-Off`
- A record with `Qty Defects = 0` does not count toward occurrence totals
- A defect code with no records returns `Insufficient Data`
- The summary query returns results sorted: Recurring first, then by weeks descending
