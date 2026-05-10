# Tech Stack Decision Records

---

## TSDR-001: PostgreSQL as the Relational Database Engine

**Status:** Accepted

### Context

The data design requires three related entities — `defect_types`, `lots`, and `defect_records` — linked by foreign keys with referential integrity enforced at the database level. A database engine was needed that supports standard SQL joins, constraint enforcement, and aggregation queries sufficient to drive defect classification and reporting.

### Decision

PostgreSQL is used as the database engine. The schema uses PostgreSQL-compatible syntax including `BIGINT GENERATED ALWAYS AS IDENTITY` for surrogate primary keys, `ON DELETE CASCADE` for referential integrity, and `CHECK` constraints for business rule enforcement (e.g., week range 1–53, non-negative quantities).

### Alternatives Considered

- **MySQL/MariaDB** — Broadly supported, but `GENERATED ALWAYS AS IDENTITY` is a SQL:2003 standard feature better supported in PostgreSQL. MySQL's default `AUTO_INCREMENT` behavior differs in edge cases.
- **SQLite** — Suitable for local development and prototyping, but lacks full constraint enforcement (e.g., foreign keys are disabled by default) and is not suited for multi-user or production deployments.
- **NoSQL (e.g., MongoDB)** — Document stores do not natively enforce relational integrity between defect types, lots, and records. Aggregation queries for classification logic would require application-level processing rather than SQL joins.

### Consequences

**Positive**
- Foreign key constraints (`fk_defect_type`, `fk_lot`) and uniqueness constraints (`uq_defect_per_lot`) are enforced at the engine level, preventing orphaned or duplicate records without application-side validation.
- Standard SQL aggregation (e.g., `COUNT(DISTINCT lot_id)`) expresses classification logic cleanly and is easy to audit.
- Indexes on `defect_type_id` and `lot_id` in `defect_records` support efficient query performance as data grows.

**Negative**
- PostgreSQL requires a running server process, adding infrastructure overhead compared to SQLite for purely local or single-user use cases.
- Contributors must have PostgreSQL installed and configured locally, which adds a setup step relative to a file-based database.

---

## TSDR-002: Excel (.xlsx) as the Data Ingestion Format

**Status:** Accepted

### Context

Inspection data originates from multiple sources — operations production logs, shipping logs, and inspector daily and weekly logs — all maintained in Excel spreadsheets. A decision was needed on the canonical format for data ingestion into the relational database.

### Decision

Excel `.xlsx` files are the accepted ingestion format, treated as the source of truth simulating an export from a legacy ERP system. The `data/sample/` directory holds five representative files: `Ops_Production_Log.xlsx`, `Ops_Shipping_Log.xlsx`, `QE_Inspector_A_DailyLog.xlsx`, `QE_Inspector_B_WeeklyLog.xlsx`, and `QE_Temp_Consolidation_CopyPaste.xlsx`.

### Alternatives Considered

- **CSV** — Simpler to parse and process programmatically, but stakeholders already produce and maintain data in Excel, and converting to CSV introduces an extra manual step and potential for data loss (e.g., date formatting, merged cells).
- **Direct ERP Database Connection** — Would provide live, structured data without manual export steps. However, a live connection is not available in this project context, and real-time monitoring is explicitly out of scope.
- **JSON** — Well suited for hierarchical or API-sourced data, but not a natural format for tabular inspection logs maintained by operations and QA teams.

### Consequences

**Positive**
- Matches the format stakeholders already use, with no additional export or conversion steps required from the data producers.
- Multiple log formats (daily, weekly, consolidated) can be ingested from the same pipeline by normalizing on the common `Lot_ID` key.

**Negative**
- Excel files can contain inconsistent formatting, merged cells, or non-standard column names. Ingestion logic must handle normalization (trimming whitespace, case alignment) before mapping to the schema.
- Data correctness at the source cannot be enforced, as preventing bad Excel entries is explicitly out of scope.

---

## TSDR-003: Python as the Application and Ingestion Language

**Status:** Accepted

### Context

The system requires a scripting or application language to read Excel files, normalize and load data into PostgreSQL, apply classification logic, and serve results to a dashboard. The `.gitignore` is configured for a Python project environment, indicating Python as the intended language.

### Decision

Python is used as the application language for data ingestion and dashboard delivery. Libraries such as `pandas` and `openpyxl` handle Excel parsing, `psycopg2` or `SQLAlchemy` manages the PostgreSQL connection, and a lightweight dashboard framework (e.g., Streamlit) presents results to the user.

### Alternatives Considered

- **Node.js** — Strong ecosystem for web dashboards, but Excel parsing libraries (e.g., `xlsx`) are less mature than Python's `pandas`/`openpyxl` stack for tabular data work. Python is more natural for data-centric workflows.
- **R** — Excellent for statistical analysis and data visualization, but less suited for building a web-facing dashboard and general-purpose data pipeline. Python's ecosystem covers both needs.
- **Java/Kotlin** — Robust for enterprise applications, but adds significant boilerplate and build complexity for a project of this scope. Not appropriate for a practicum-scale data pipeline.

### Consequences

**Positive**
- `pandas` and `openpyxl` provide mature, well-documented support for reading and normalizing `.xlsx` files with inconsistent structures across multiple source files.
- Python integrates cleanly with PostgreSQL via `psycopg2` and `SQLAlchemy`, and Streamlit enables a functional dashboard without requiring separate frontend development.
- Consistent with the Python-configured `.gitignore`, reducing configuration drift.

**Negative**
- Python is dynamically typed, which can allow ingestion bugs (e.g., type mismatches) to surface at runtime rather than compile time. Input validation must be handled explicitly.
- Performance is not a concern at this data volume, but Python would not be the first choice if the dataset grew to millions of records requiring high-throughput ingestion.

---

## TSDR-004: SQL for Classification and Aggregation Logic

**Status:** Accepted

### Context

Defect classification — determining whether a defect code is Recurring, One-Off, or Insufficient Data — requires aggregating `defect_records` across lots and reporting weeks. This logic could live in the application layer (Python) or be expressed as SQL queries executed against the database.

### Decision

Classification and aggregation logic is implemented in SQL and executed at the database layer. The `sample_queries.sql` file demonstrates this using `COUNT(DISTINCT lot_id)` and `COUNT(DISTINCT reporting_week)` grouped by `defect_code`, with a `CASE` expression producing the classification label. The `WHERE quantity_of_defects > 0` filter is also applied at the SQL layer.

### Alternatives Considered

- **Application-layer logic (Python)** — Python could fetch raw records and compute classifications in memory using `pandas`. This would make the logic more testable in isolation but moves business rules out of the database, risking inconsistency if multiple consumers query the data.
- **Database Views** — Materialized or standard views could encapsulate classification logic and expose it as a virtual table. Viable for future iterations, but adds schema maintenance overhead that is not necessary at current scale.
- **Stored Procedures** — Would embed logic directly in the database engine. Harder to version-control and test compared to plain SQL query files checked into the repository.

### Consequences

**Positive**
- Classification logic runs where the data lives, avoiding round-trips to fetch raw rows for application-side aggregation.
- SQL queries in `sample_queries.sql` are human-readable, version-controlled, and independently testable against the seeded database.
- The zero-quantity exclusion rule (`WHERE quantity_of_defects > 0`) is enforced consistently at the query layer for all consumers.

**Negative**
- Business logic embedded in SQL is harder to unit test with standard Python testing frameworks without a running database.
- If the classification rules change (e.g., new thresholds for "Recurring"), query files must be updated and re-deployed alongside any application code changes.

---

## TSDR-005: Git for Version Control

**Status:** Accepted

### Context

The project produces multiple artifact types — database schema, seed data, sample queries, documentation, and eventually application code — that evolve over time and benefit from change history, branching, and collaboration support.

### Decision

Git is used for version control, with the repository hosted on GitHub under the user `AndrewC126`. All project files including SQL schema, query files, documentation, and data design artifacts are tracked in the repository. A `.gitignore` is configured to exclude Python virtual environments, compiled files, and IDE-specific directories.

### Alternatives Considered

- **No version control** — Relying on manual file backups or shared drives. This is not acceptable for a software project of any complexity, as it provides no history, no branching, and no collaboration support.
- **SVN (Subversion)** — A centralized version control system. Git is preferred for its distributed model, widespread adoption, and native support from hosting platforms like GitHub.
- **Mercurial** — Similar in capability to Git but with significantly smaller community adoption and fewer hosting platform integrations.

### Consequences

**Positive**
- The full history of schema changes, query refinements, and documentation updates is preserved and attributable.
- Branching enables isolated development of new features (e.g., adding the ingestion script) without disrupting stable artifacts.
- GitHub hosting allows collaboration and provides a remote backup of all project artifacts.

**Negative**
- Large binary files (`.xlsx` sample data files in `data/sample/`) are tracked in Git, which is not ideal for binary formats that cannot be diffed meaningfully. A tool like Git LFS would be appropriate if file sizes grow.
- Contributors must be familiar with Git workflows; merge conflicts in generated files (e.g., `seed.sql`) can be difficult to resolve manually.
