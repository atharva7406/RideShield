# RideShield Temporary Database Test Backend Harness

> **IMPORTANT**: This directory is a **temporary DB integration and testing harness**. It is **NOT** the main RideShield application backend.

---

## Purpose

This test harness exists exclusively to validate:
- **SQLAlchemy → Neon PostgreSQL** database connectivity and ORM session behavior.
- **Alembic** migration execution and schema validation.
- **Redis → Worker → PostgreSQL** telemetry pipeline flow.
- Database **constraints**, foreign key integrity, and ingestion idempotency.
- Local integration tests for database operations.

---

## Ownership Boundary

The main production RideShield application backend (FastAPI routes, identity/auth, insurer dashboards, claim workflows) is developed and owned by another workstream.

---

## Directory Organization

- **`app/`**: Lightweight test runners and mock entrypoints for local testing.
- **`tests/`**: Integration tests verifying database models, constraints, and ingestion handlers.
