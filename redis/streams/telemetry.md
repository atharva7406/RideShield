# Telemetry Stream Contract (`rideshield:telemetry`)

## Stream Overview
- **Stream Key**: `rideshield:telemetry`
- **Consumer Group**: `telemetry-workers`
- **Purpose**: One stream entry represents exactly one telemetry batch. In the PostgreSQL persistence layer, one batch maps to **one `telemetry_batches` row** plus **$N$ `telemetry_samples` rows**.

---

## Payload Specification

Each entry in the Redis Stream contains a JSON string under the key `data` or a structured dictionary payload matching the following JSON schema:

```json
{
  "shift_id": "UUID",
  "rider_id": "UUID",
  "batch_sequence": 0,
  "samples": [
    {
      "timestamp": "2026-08-22T12:00:00.000Z",
      "latitude": 37.7749,
      "longitude": -122.4194,
      "altitude": 15.2,
      "gps_accuracy": 4.5,
      "speed": 12.5,
      "accel_x": 0.01,
      "accel_y": -0.05,
      "accel_z": 9.81,
      "gyro_x": 0.001,
      "gyro_y": 0.002,
      "gyro_z": -0.001
    }
  ]
}
```

### Field Mapping to PostgreSQL Schema

#### `telemetry_batches` Table
| Redis Stream / Payload Field | PostgreSQL Column | Data Type | Notes / Constraints |
| :--- | :--- | :--- | :--- |
| Generated primary key | `id` | `UUID` | Generated at insert (`uuid.uuid4()`) |
| `shift_id` | `shift_id` | `UUID` | Required foreign key to `shifts.id` |
| Redis Entry ID (e.g. `1755869400000-0`) | `redis_stream_id` | `VARCHAR(100)` | **Idempotency Key 1** (Unique) |
| `batch_sequence` | `batch_sequence` | `INTEGER` | **Idempotency Key 2** part 2 (Check `batch_sequence >= 0`) |
| Computed (`len(samples)`) | `sample_count` | `INTEGER` | Must be > 0 |
| Computed (`min(samples.timestamp)`) | `start_timestamp` | `TIMESTAMPTZ` | Minimum sample timestamp in batch |
| Computed (`max(samples.timestamp)`) | `end_timestamp` | `TIMESTAMPTZ` | Maximum sample timestamp (`end_timestamp >= start_timestamp`) |
| DB timestamp | `ingested_at` | `TIMESTAMPTZ` | Timestamp when inserted into PostgreSQL |

#### `telemetry_samples` Table
| Payload Sample Field | PostgreSQL Column | Data Type | Notes / Constraints |
| :--- | :--- | :--- | :--- |
| Generated primary key | `id` | `UUID` | Generated at insert (`uuid.uuid4()`) |
| Parent batch ID | `batch_id` | `UUID` | FK to `telemetry_batches.id` (CASCADE) |
| `timestamp` | `timestamp` | `TIMESTAMPTZ` | Sample observation ISO-8601 timestamp |
| `latitude` | `latitude` | `DOUBLE PRECISION` | Required |
| `longitude` | `longitude` | `DOUBLE PRECISION` | Required |
| `altitude` | `altitude` | `DOUBLE PRECISION` | Nullable |
| `gps_accuracy` | `gps_accuracy` | `DOUBLE PRECISION` | Nullable |
| `speed` | `speed` | `DOUBLE PRECISION` | Required (Check `speed >= 0`) |
| `accel_x` | `accel_x` | `DOUBLE PRECISION` | Required |
| `accel_y` | `accel_y` | `DOUBLE PRECISION` | Required |
| `accel_z` | `accel_z` | `DOUBLE PRECISION` | Required |
| `gyro_x` | `gyro_x` | `DOUBLE PRECISION` | Required |
| `gyro_y` | `gyro_y` | `DOUBLE PRECISION` | Required |
| `gyro_z` | `gyro_z` | `DOUBLE PRECISION` | Required |

---

## Non-Negotiable Stream Processing Rules

The following stream ingestion and acknowledgement rules are mandatory and non-negotiable across all consumer workers:

a. The Redis-generated stream entry ID becomes `telemetry_batches.redis_stream_id` (idempotency key 1).
b. `(shift_id, batch_sequence)` is idempotency key 2.
c. XACK only fires after the PostgreSQL transaction commits — never before, never in an unconditional finally block.
d. On DB failure: rollback, do not XACK, leave pending for retry.
e. On malformed/unparseable payload: log as non-retryable, XACK immediately (don't let bad data jam the queue forever).
