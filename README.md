# RideShield 🏍️🛡️

RideShield is an end-to-end shift-based accident microinsurance and telematics platform for gig workers. It captures real-time sensor data (GPS, Accelerometer, Gyroscope) from a rider's mobile device, processes incidents (such as high G-force crashes) via an asynchronous telemetry pipeline, and provides insurance providers with a dedicated web dashboard to monitor active shifts, review claims, and assess safety risk.

---

## 🏗️ Monorepo Architecture

The repository is structured into focused, decoupled packages:

- **`backend/`**: Application FastAPI server for business logic, authentication, shift management, claims, and incident endpoints.
- **`db/`**: Authoritative PostgreSQL / Neon database layer containing SQLAlchemy ORM models, Alembic migrations, database sessions, seed data, and schema definitions.
- **`redis/`**: Authoritative Redis / Upstash infrastructure layer handling real-time telemetry streams (`rideshield:telemetry`), stream producers, and background `XREADGROUP` / `XAUTOCLAIM` workers.
- **`db_test_backend/`**: Dedicated DB/Redis integration test harness for validating telemetry ingestion, idempotency, redelivery, and error recovery.
- **`rider-app/`**: Expo (React Native) mobile application that tracks live telemetry data using mobile hardware sensors.
- **`insurer-dashboard/`**: Insurer web dashboard (`frontend-web/`) for monitoring active shifts, reviewing claims, and evaluating risk scores.
- **`docs/`**: Canonical documentation including database schema (`docs/database/schema.md`) and data infrastructure specifications.

---

## 🚀 Getting Started

To run the complete RideShield ecosystem locally:

### 1. Prerequisites
- **Python**: 3.10+
- **Node.js**: 18+
- **PostgreSQL / Neon**: Configured via `DATABASE_URL` in `.env`
- **Redis / Upstash**: Configured via `REDIS_URL` in `.env`

### 2. Run Application Backend & Infrastructure

**Terminal 1: Start Application Server**
```bash
cd backend
python -m venv venv
.\venv\Scripts\activate  # Windows
# source venv/bin/activate  # Mac/Linux

pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2: Start Telemetry Worker**
```bash
# Run from project root using project environment
python redis/workers/telemetry_worker.py
```

### 3. Run Integration Tests
```bash
python -m pytest db_test_backend/tests/test_telemetry_pipeline.py -v
```

### 4. Run Mobile Rider App (Terminal 3)
```bash
cd rider-app
npm install
npx expo start --clear
```

### 5. Run Insurer Dashboard (Terminal 4)
```bash
cd insurer-dashboard/frontend-web
npm install
npm run dev
```

---

## 📄 Database & Migrations

Database migrations are managed centrally via Alembic in `db/migrations/`.
To check migration status or run migrations:

```bash
python -m alembic history
python -m alembic heads
python -m alembic upgrade head
```

---

*RideShield — Real-time protection for gig riders.*
