# RideShield Database & Infrastructure Package (`db/`)

This directory contains the core PostgreSQL/Neon database infrastructure, ORM models, and migration scripts for the **RideShield** platform.

---

## 1. Stack & Architecture

- **Database Engine**: PostgreSQL 15+ (Serverless Lakebase Postgres on Neon)
- **Target Branch (Dev)**: `dev/database-schema-v1` (`br-lingering-pine-azpaahdv`)
- **ORM**: SQLAlchemy 2.0+ Declarative Mapping
- **Migration Engine**: Alembic

> [!CAUTION]
> **PRODUCTION BRANCH SAFETY**:
> The production branch (`production` / `br-little-smoke-azlwp91k`) is **STRICTLY OFF-LIMITS**. DDL/DML migrations and manual schema operations must NEVER be executed directly against production.

---

## 2. Directory Structure

```
db/
├── models/       SQLAlchemy domain models and PostgreSQL enum definitions
├── core/         Database engine, SessionLocal factory, and Base declarative class
├── migrations/   Alembic migration environment and version history
├── seed/         Development and demonstration seed data generators
├── scripts/      Database verification, schema audit, and utility scripts
└── README.md     Database infrastructure documentation
```

---

## 3. Ownership & Scope Boundaries

### What belongs in `db/`:
- SQLAlchemy ORM models (`db/models/*.py`)
- Database connection sessions and engine pooling (`db/core/session.py`, `db/core/base.py`)
- Alembic migration scripts and env configuration (`db/migrations/`)
- Database seed scripts and schema verification utilities (`db/seed/`, `db/scripts/`)

### What does NOT belong in `db/`:
- Production FastAPI routes, request handlers, or API endpoints.
- Authentication/identity token endpoints.
- Redis stream workers or consumer logic (located under `redis/`).
- Temporary test harness runners (located under `db_test_backend/`).
