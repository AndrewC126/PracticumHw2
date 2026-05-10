# Architecture Decision Records

---

## ADR-001: Client–Server Architecture over Event-Driven Architecture

**Status:** Accepted
**Date:** 2026-05-10

### Context

The system needs to serve defect analysis results to users who want to explore inspection data across lots and time periods. Two patterns were considered: a traditional Client–Server model where a client requests data from a server on demand, and an Event-Driven model where components react to data change events asynchronously.

Event-Driven architecture is well suited for systems where data changes continuously and downstream consumers need to react in near real-time. However, the project assumptions establish that Excel files represent a static export from a legacy ERP system — not a live data stream — and real-time production monitoring is explicitly out of scope.

### Decision

A Client–Server architecture is used. A server layer exposes query results from the relational database, and a client (dashboard) requests data on demand. There are no event producers, message brokers, or reactive consumers in this system.

### Consequences

- The system is simpler to build, test, and reason about given the static nature of the data source.
- Adding real-time or streaming data in the future would require significant rework, but that is an accepted trade-off given scope constraints.
- The client can be a lightweight dashboard that issues SQL-backed queries without any event subscription infrastructure.

---

## ADR-002: Monolith over Microservices

**Status:** Accepted
**Date:** 2026-05-10

### Context

The system covers a narrow domain: ingesting Excel-exported defect records, storing them in a relational database, and presenting aggregated results on a dashboard. Microservices decompose a system into independently deployable services, each owning a bounded context, which adds operational complexity including service discovery, inter-service communication, and distributed data management.

The project scope excludes user authentication, real-time monitoring, predictive analytics, and other features that would naturally become independent services. The team is working with a small, well-defined dataset derived from two assumptions: a common `Lot_ID` key across files and Excel as the source of truth.

### Decision

A single monolithic application is used. The ingestion logic, business rules, and query layer are deployed together as one unit backed by a single relational database.

### Consequences

- Deployment, debugging, and local development are straightforward with no inter-service networking to manage.
- All defect classification logic (Recurring, One-Off, Insufficient Data) lives in one place, making it easy to audit and change.
- If the system grows to include additional data domains or real-time feeds, extracting services from the monolith will require refactoring — this is an accepted risk given the current scope.

---

## ADR-003: Layered Architecture over Feature-Based Architecture

**Status:** Accepted
**Date:** 2026-05-10

### Context

Two internal code organization strategies were considered. A Layered Architecture organizes code by technical responsibility — data access, business logic, and presentation — stacked horizontally. A Feature-Based Architecture organizes code vertically by domain feature, so all layers for a given feature (e.g., "defect classification") are grouped together.

Feature-Based organization pays off when features are numerous, independently developed, or frequently added. This project has a small and stable feature set: defect ingestion, classification, and reporting. The data model has three entities — `defect_types`, `lots`, and `defect_records` — all tightly coupled through shared queries.

### Decision

A Layered Architecture is used. Code is organized into distinct layers: a data layer (schema, seed data, SQL queries), a logic layer (classification rules, aggregation), and a presentation layer (dashboard). Each layer depends only on the layer below it.

### Consequences

- The separation of concerns matches the structure of the project deliverables: schema files, query files, and a reporting interface.
- Cross-cutting concerns like the zero-quantity exclusion rule (`WHERE quantity_of_defects > 0`) are applied consistently at the data layer rather than duplicated across features.
- Adding a new feature (e.g., a second defect metric) requires touching multiple layers, but this is manageable given the small scope.

---

## ADR-004: Single Database over Database per Service

**Status:** Accepted
**Date:** 2026-05-10

### Context

The data design defines three related entities: `defect_types`, `lots`, and `defect_records`. These are linked by foreign keys and queried together via joins to produce classification results. Database-per-Service is a pattern associated with Microservices where each service owns its data store to enforce loose coupling.

Since a Monolith was chosen (ADR-002) and the entities are tightly related — a `defect_record` cannot exist without both a `defect_type` and a `lot` — splitting these into separate databases would introduce cross-database join complexity with no architectural benefit.

Both assumptions reinforce this decision: all Excel files share a common `Lot_ID` key (Assumption 1), and the files collectively represent one source of truth (Assumption 2), making a unified schema the natural fit.

### Decision

A single relational database is used for all three tables. Referential integrity is enforced through foreign key constraints (`fk_defect_type`, `fk_lot`) and uniqueness constraints (`uq_defect_code`, `uq_lot_number`, `uq_defect_per_lot`).

### Consequences

- Foreign key enforcement at the database level prevents orphaned defect records and duplicate reporting for the same defect on the same lot.
- Aggregation queries (e.g., counting distinct lots per defect code) are expressed as standard SQL joins without distributed query coordination.
- This approach does not scale to a multi-service architecture without redesigning the data layer, but that is outside the current scope.

---

## ADR-005: Synchronous Processing over Asynchronous Processing

**Status:** Accepted
**Date:** 2026-05-10

### Context

Data ingestion (loading Excel exports into the database) and query execution (producing defect classification results) could be handled either synchronously — where the caller waits for the operation to complete — or asynchronously — where operations are queued and results are returned later via callbacks, polling, or events.

Asynchronous processing is valuable when operations are long-running, data volumes are large, or the system must remain responsive under concurrent load. The project works with periodic Excel exports from a legacy ERP system, not a continuous high-volume stream. Ingestion is a batch operation run on demand, and query results are expected immediately when the dashboard loads.

### Decision

All data ingestion and query operations are handled synchronously. Excel data is loaded into the database in a single batch operation, and dashboard queries execute and return results within the same request cycle. No queues, background workers, or async callbacks are used.

### Consequences

- The system is simpler to implement and debug — execution flow is linear and results are immediate.
- The dashboard user receives query results in a single round trip without polling or waiting on async jobs.
- If dataset size grows substantially or ingestion frequency increases, synchronous batch loading may introduce perceptible delays. Introducing async processing at that point would be a scoped enhancement, not a redesign of the core system.
