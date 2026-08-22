# RideShield Redis & Message Queue Infrastructure

This directory contains the structural components for the **RideShield** Redis and streaming queue infrastructure layer.

---

## Architecture & Technology

- **Provider**: Upstash Redis (Serverless / High-Concurrency Streams)
- **Primary Mechanism**: Redis Streams for real-time mobile telemetry buffering.
- **Target Stream**: `rideshield:telemetry`
- **Target Consumer Group**: `telemetry-workers`

---

## Directory Organization

- **`client/`**: Redis client connection pooling, configuration, and resilience wrappers.
- **`streams/`**: Stream producers and stream offset/ACK management.
- **`workers/`**: Consumer group background workers responsible for parsing, validating, and writing batched telemetry into PostgreSQL `telemetry_batches` and `telemetry_samples`.
- **`tests/`**: Integration and unit tests for Redis stream ingestion and worker idempotency.

---

> **Note**: This directory is structurally prepared. Implementation of Redis streams, connection logic, and background consumers will be developed in subsequent phases.
