# RideShield Relational Database Schema Documentation (Final Approved)

This document describes the PostgreSQL relational database schema for the **RideShield** shift-based accident microinsurance platform for gig workers, hosted on Neon Lakebase Postgres.

---

## 1. Overview & Architecture

RideShield provides dynamic, shift-based accident insurance for on-demand gig delivery and ride-share riders. The database handles user identity, rider profiles, shift tracking, telemetry ingestion buffering, risk scoring, collision incident detection, claims management, evidence storage, financial payments, and generalized compliance audit logging.

### Key Architectural Decisions & Integrity Rules

1. **Telemetry Normalization & Performance (`telemetry_batches` & `telemetry_samples`)**:
   - **`telemetry_batches`**: Ingestion ledger storing 1 record per compressed payload buffer uploaded from Redis stream ingestion workers. Linked directly to `shift_id` (`rider_id` is omitted as it is derivable via `shifts.rider_id`).
   - **Redis Stream Idempotency**: `redis_stream_id` is `UNIQUE` to prevent worker message replay duplicates.
   - **Sequence & Timestamp Checks**: Composite `UNIQUE(shift_id, batch_sequence)` constraint, `sample_count > 0` check, `end_timestamp >= start_timestamp` check, and index `(shift_id, start_timestamp)` for fast time-range filtering.
   - **`telemetry_samples`**: Unpacks individual 10–50 Hz 6-DOF inertial sensor datapoints (GPS coordinates, speed, 3-axis accel/gyro). Linked exclusively to `batch_id` (`shift_id` is omitted as it is derivable via `telemetry_batches → shifts`). Indexed via `(batch_id, timestamp)`.

2. **Incident-to-Claim Cardinality (1:0..1)**:
   - `claims.incident_id` carries a `UNIQUE` constraint enforcing that an accident incident can result in **at most one claim** (1:0..1).

3. **Incident Evidence Lifecycle**:
   - `incident_evidence.incident_id` is `NOT NULL` with `ON DELETE RESTRICT` (captured immediately upon accident detection during verification).
   - `incident_evidence.claim_id` is `NULLABLE` with `ON DELETE SET NULL`, enabling evidence capture before an official claim is filed and allowing evidence to survive claim deletion.

4. **Time-Windowed Risk Scoring**:
   - `risk_scores` contains explicit `window_start` and `window_end` (`TIMESTAMPTZ`) columns bounded by a `window_end > window_start` CHECK constraint.

5. **Financial Integrity & Payment Linkage**:
   - `payments.currency` defaults to **`INR`**.
   - `payments.payment_type` uses an explicit PostgreSQL `PaymentType` Enum (`PREMIUM_COLLECTION`, `CLAIM_PAYOUT`).
   - **Linkage Integrity CHECK (`ck_payments_type_linkage`)**: Enforces `(payment_type = 'PREMIUM_COLLECTION' AND shift_id IS NOT NULL) OR (payment_type = 'CLAIM_PAYOUT' AND claim_id IS NOT NULL)`.

6. **Generalized Audit Trail**:
   - `audit_events` provides an immutable/generalized audit log covering any domain entity using `entity_type` (e.g. `INCIDENT`, `CLAIM`, `PAYMENT`, `SHIFT`) and `entity_id` (`UUID`).

7. **Foreign Key Delete Behavior (`confdeltype`)**:
   - **`ON DELETE RESTRICT`**: Applied to parent entities (`users`, `shifts`, `incidents`, `claims`) to prevent accidental cascade deletion of financial records, shifts, or audit trails.
   - **`ON DELETE CASCADE`**: Applied to 1:1 profiles (`rider_profiles -> users`) and fine-grained sensor samples (`telemetry_samples -> telemetry_batches`).
   - **`ON DELETE SET NULL`**: Applied to optional links (`audit_events -> claims`, `incident_evidence -> claims`, `payments -> shifts/claims`, `incidents -> telemetry_batches`).

---

## 2. Enums (7 Total)

- **`UserRole`**: `RIDER`, `ADMIN`, `INSURER`, `SUPPORT`
- **`ShiftStatus`**: `ACTIVE`, `PAUSED`, `COMPLETED`, `CANCELLED`
- **`IncidentStatus`**: `DETECTED`, `PENDING_VERIFICATION`, `VERIFIED_ACCIDENT`, `FALSE_POSITIVE`, `DISCARDED`
- **`RiskLevel`**: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`
- **`ClaimStatus`**: `DRAFT`, `SUBMITTED`, `UNDER_REVIEW`, `APPROVED`, `REJECTED`, `PAID`
- **`PaymentStatus`**: `PENDING`, `PROCESSING`, `SUCCESSFUL`, `FAILED`, `REFUNDED`
- **`PaymentType`**: `PREMIUM_COLLECTION`, `CLAIM_PAYOUT`

---

## 3. Entity-Relationship Summary

```
users (1) ──── (0..1) rider_profiles [CASCADE]
users (1) ──── (N) shifts [RESTRICT]
shifts (1) ─── (N) telemetry_batches [RESTRICT] ─── (N) telemetry_samples [CASCADE]
shifts (1) ─── (N) incidents [RESTRICT] ─────────── (0..1) claims [RESTRICT]
shifts (1) ─── (N) risk_scores [RESTRICT]
shifts (1) ─── (N) payments [SET NULL]
incidents (1) ── (N) incident_evidence [RESTRICT]
claims (1) ─── (0..N) incident_evidence [SET NULL]
claims (1) ─── (N) audit_events [SET NULL]
claims (1) ─── (N) payments [SET NULL]
```

---

## 4. Detailed Table Specifications

### 4.1 `users`
- **`id`** (`UUID`, PK): Unique user identifier (`gen_random_uuid()`).
- **`email`** (`VARCHAR(255)`, UNIQUE, NOT NULL, Index `ix_users_email`): Login email.
- **`phone_number`** (`VARCHAR(30)`, UNIQUE, NOT NULL): Contact phone number.
- **`hashed_password`** (`VARCHAR(255)`, NOT NULL): Argon2/BCrypt password hash.
- **`full_name`** (`VARCHAR(255)`, NOT NULL): Legal full name.
- **`role`** (`ENUM UserRole`, Default `'RIDER'`, NOT NULL): System role.
- **`is_active`** (`BOOLEAN`, Default `TRUE`, NOT NULL): Account active status.
- **`created_at`** (`TIMESTAMPTZ`, Default `NOW()`, NOT NULL)
- **`updated_at`** (`TIMESTAMPTZ`, Default `NOW()`, NOT NULL)

### 4.2 `rider_profiles`
- **`id`** (`UUID`, PK): Unique profile identifier (`gen_random_uuid()`).
- **`user_id`** (`UUID`, FK → `users.id` ON DELETE CASCADE, UNIQUE, NOT NULL, Index `ix_rider_profiles_user_id`).
- **`vehicle_type`** (`VARCHAR(50)`, NOT NULL): e.g., `BICYCLE`, `SCOOTER`, `MOTORCYCLE`.
- **`license_number`** (`VARCHAR(100)`, NULLABLE).
- **`emergency_contact_phone`** (`VARCHAR(30)`, NULLABLE).
- **`safety_rating`** (`NUMERIC(3,2)`, Default `5.00`, NOT NULL, CHECK `safety_rating >= 1.00 AND safety_rating <= 5.00`).
- **`kyc_status`** (`VARCHAR(50)`, Default `'PENDING'`, NOT NULL).
- **`created_at`** (`TIMESTAMPTZ`, Default `NOW()`, NOT NULL)
- **`updated_at`** (`TIMESTAMPTZ`, Default `NOW()`, NOT NULL)

### 4.3 `shifts`
- **`id`** (`UUID`, PK): Unique shift identifier (`gen_random_uuid()`).
- **`rider_id`** (`UUID`, FK → `users.id` ON DELETE RESTRICT, NOT NULL, Index `ix_shifts_rider_id`).
- **`status`** (`ENUM ShiftStatus`, Default `'ACTIVE'`, NOT NULL, Index `ix_shifts_status`).
- **`start_time`** (`TIMESTAMPTZ`, Default `NOW()`, NOT NULL).
- **`end_time`** (`TIMESTAMPTZ`, NULLABLE).
- **`distance_km`** (`NUMERIC(8,2)`, Default `0.00`, NOT NULL, CHECK `distance_km >= 0.00`).
- **`premium_amount`** (`NUMERIC(10,2)`, Default `0.00`, NOT NULL, CHECK `premium_amount >= 0.00`).
- **`policy_number`** (`VARCHAR(100)`, UNIQUE, NULLABLE).
- **`created_at`** (`TIMESTAMPTZ`, Default `NOW()`, NOT NULL)
- **`updated_at`** (`TIMESTAMPTZ`, Default `NOW()`, NOT NULL)
- **Checks**: `end_time IS NULL OR end_time >= start_time`

### 4.4 `telemetry_batches`
- **`id`** (`UUID`, PK): Unique batch identifier (`gen_random_uuid()`).
- **`shift_id`** (`UUID`, FK → `shifts.id` ON DELETE RESTRICT, NOT NULL, Index `ix_telemetry_batches_shift_id`).
- **`redis_stream_id`** (`VARCHAR(100)`, UNIQUE, NULLABLE): Ingestion idempotency key.
- **`batch_sequence`** (`INTEGER`, NOT NULL, CHECK `batch_sequence >= 0`).
- **`sample_count`** (`INTEGER`, NOT NULL, CHECK `sample_count > 0`).
- **`start_timestamp`** (`TIMESTAMPTZ`, NOT NULL).
- **`end_timestamp`** (`TIMESTAMPTZ`, NOT NULL).
- **`ingested_at`** (`TIMESTAMPTZ`, Default `NOW()`, NOT NULL).
- **Constraints**: `UNIQUE (shift_id, batch_sequence)`
- **Checks**: `end_timestamp >= start_timestamp`
- **Indexes**: `(shift_id, start_timestamp)` (`idx_telemetry_batches_shift_start_timestamp`)

### 4.5 `telemetry_samples`
- **`id`** (`UUID`, PK): Unique sample identifier (`gen_random_uuid()`).
- **`batch_id`** (`UUID`, FK → `telemetry_batches.id` ON DELETE CASCADE, NOT NULL, Index `ix_telemetry_samples_batch_id`).
- **`timestamp`** (`TIMESTAMPTZ`, NOT NULL, Index `ix_telemetry_samples_timestamp`).
- **`latitude`** (`DOUBLE PRECISION`, NOT NULL).
- **`longitude`** (`DOUBLE PRECISION`, NOT NULL).
- **`altitude`** (`DOUBLE PRECISION`, NULLABLE).
- **`gps_accuracy`** (`DOUBLE PRECISION`, NULLABLE).
- **`speed`** (`DOUBLE PRECISION`, NOT NULL, CHECK `speed >= 0.0`).
- **`accel_x`, `accel_y`, `accel_z`** (`DOUBLE PRECISION`, NOT NULL).
- **`gyro_x`, `gyro_y`, `gyro_z`** (`DOUBLE PRECISION`, NOT NULL).
- **Indexes**: Composite `(batch_id, timestamp)` (`idx_telemetry_samples_batch_timestamp`).

### 4.6 `incidents`
- **`id`** (`UUID`, PK): Unique incident identifier (`gen_random_uuid()`).
- **`shift_id`** (`UUID`, FK → `shifts.id` ON DELETE RESTRICT, NOT NULL, Index `ix_incidents_shift_id`).
- **`rider_id`** (`UUID`, FK → `users.id` ON DELETE RESTRICT, NOT NULL, Index `ix_incidents_rider_id`).
- **`batch_id`** (`UUID`, FK → `telemetry_batches.id` ON DELETE SET NULL, NULLABLE).
- **`status`** (`ENUM IncidentStatus`, Default `'DETECTED'`, NOT NULL, Index `ix_incidents_status`).
- **`detected_at`** (`TIMESTAMPTZ`, Default `NOW()`, NOT NULL).
- **`peak_g_force`** (`NUMERIC(5,2)`, NOT NULL, CHECK `peak_g_force >= 0.00`).
- **`confidence_score`** (`NUMERIC(3,2)`, NOT NULL, CHECK `confidence_score >= 0.00 AND confidence_score <= 1.00`).
- **`latitude`, `longitude`** (`DOUBLE PRECISION`, NOT NULL).
- **`created_at`** (`TIMESTAMPTZ`, Default `NOW()`, NOT NULL)
- **`updated_at`** (`TIMESTAMPTZ`, Default `NOW()`, NOT NULL)

### 4.7 `risk_scores`
- **`id`** (`UUID`, PK): Unique score identifier (`gen_random_uuid()`).
- **`shift_id`** (`UUID`, FK → `shifts.id` ON DELETE RESTRICT, NOT NULL, Index `ix_risk_scores_shift_id`).
- **`rider_id`** (`UUID`, FK → `users.id` ON DELETE RESTRICT, NOT NULL, Index `ix_risk_scores_rider_id`).
- **`risk_score`** (`NUMERIC(5,2)`, NOT NULL, CHECK `risk_score >= 0.00 AND risk_score <= 100.00`).
- **`risk_level`** (`ENUM RiskLevel`, Default `'LOW'`, NOT NULL, Index `ix_risk_scores_risk_level`).
- **`hard_braking_count`** (`INTEGER`, Default `0`, NOT NULL, CHECK `hard_braking_count >= 0`).
- **`hard_acceleration_count`** (`INTEGER`, Default `0`, NOT NULL, CHECK `hard_acceleration_count >= 0`).
- **`overspeeding_count`** (`INTEGER`, Default `0`, NOT NULL, CHECK `overspeeding_count >= 0`).
- **`window_start`** (`TIMESTAMPTZ`, NOT NULL).
- **`window_end`** (`TIMESTAMPTZ`, NOT NULL).
- **`evaluated_at`** (`TIMESTAMPTZ`, Default `NOW()`, NOT NULL).
- **Checks**: `window_end > window_start`

### 4.8 `claims`
- **`id`** (`UUID`, PK): Unique claim identifier (`gen_random_uuid()`).
- **`incident_id`** (`UUID`, FK → `incidents.id` ON DELETE RESTRICT, UNIQUE, NOT NULL, Index `ix_claims_incident_id`).
- **`rider_id`** (`UUID`, FK → `users.id` ON DELETE RESTRICT, NOT NULL, Index `ix_claims_rider_id`).
- **`shift_id`** (`UUID`, FK → `shifts.id` ON DELETE RESTRICT, NOT NULL, Index `ix_claims_shift_id`).
- **`claim_number`** (`VARCHAR(100)`, UNIQUE, NOT NULL).
- **`status`** (`ENUM ClaimStatus`, Default `'DRAFT'`, NOT NULL, Index `ix_claims_status`).
- **`claimed_amount`** (`NUMERIC(10,2)`, NOT NULL, CHECK `claimed_amount >= 0.00`).
- **`approved_amount`** (`NUMERIC(10,2)`, NULLABLE, CHECK `approved_amount IS NULL OR approved_amount >= 0.00`).
- **`rejection_reason`** (`TEXT`, NULLABLE).
- **`filed_at`** (`TIMESTAMPTZ`, Default `NOW()`, NOT NULL).
- **`updated_at`** (`TIMESTAMPTZ`, Default `NOW()`, NOT NULL).

### 4.9 `incident_evidence`
- **`id`** (`UUID`, PK): Unique evidence identifier (`gen_random_uuid()`).
- **`incident_id`** (`UUID`, FK → `incidents.id` ON DELETE RESTRICT, NOT NULL, Index `ix_incident_evidence_incident_id`).
- **`claim_id`** (`UUID`, FK → `claims.id` ON DELETE SET NULL, NULLABLE, Index `ix_incident_evidence_claim_id`).
- **`file_url`** (`TEXT`, NOT NULL).
- **`file_type`** (`VARCHAR(50)`, NOT NULL).
- **`file_hash`** (`VARCHAR(64)`, NULLABLE).
- **`uploaded_at`** (`TIMESTAMPTZ`, Default `NOW()`, NOT NULL).

### 4.10 `payments`
- **`id`** (`UUID`, PK): Unique payment identifier (`gen_random_uuid()`).
- **`shift_id`** (`UUID`, FK → `shifts.id` ON DELETE SET NULL, NULLABLE, Index `ix_payments_shift_id`).
- **`claim_id`** (`UUID`, FK → `claims.id` ON DELETE SET NULL, NULLABLE, Index `ix_payments_claim_id`).
- **`rider_id`** (`UUID`, FK → `users.id` ON DELETE RESTRICT, NOT NULL, Index `ix_payments_rider_id`).
- **`payment_type`** (`ENUM PaymentType`, NOT NULL).
- **`amount`** (`NUMERIC(10,2)`, NOT NULL, CHECK `amount >= 0.00`).
- **`currency`** (`VARCHAR(3)`, Default `'INR'`, NOT NULL).
- **`status`** (`ENUM PaymentStatus`, Default `'PENDING'`, NOT NULL, Index `ix_payments_status`).
- **`transaction_ref`** (`VARCHAR(100)`, UNIQUE, NULLABLE).
- **`processed_at`** (`TIMESTAMPTZ`, NULLABLE).
- **`created_at`** (`TIMESTAMPTZ`, Default `NOW()`, NOT NULL).
- **Checks**: `(payment_type = 'PREMIUM_COLLECTION' AND shift_id IS NOT NULL) OR (payment_type = 'CLAIM_PAYOUT' AND claim_id IS NOT NULL)`

### 4.11 `audit_events`
- **`id`** (`UUID`, PK): Unique audit event identifier (`gen_random_uuid()`).
- **`claim_id`** (`UUID`, FK → `claims.id` ON DELETE SET NULL, NULLABLE, Index `ix_audit_events_claim_id`).
- **`performed_by_user_id`** (`UUID`, FK → `users.id` ON DELETE RESTRICT, NOT NULL).
- **`entity_type`** (`VARCHAR(50)`, NOT NULL).
- **`entity_id`** (`UUID`, NOT NULL).
- **`event_type`** (`VARCHAR(100)`, NOT NULL).
- **`old_state`** (`VARCHAR(50)`, NULLABLE).
- **`new_state`** (`VARCHAR(50)`, NULLABLE).
- **`metadata_json`** (`JSONB`, NULLABLE).
- **`created_at`** (`TIMESTAMPTZ`, Default `NOW()`, NOT NULL).
