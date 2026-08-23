import os
import sys
import uuid
import time
import pytest
from datetime import datetime, timezone
from sqlalchemy import text

# Add backend directory to Python path so db and redis_workers are importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend")))

from db.core.session import SessionLocal
from db.models.telemetry import TelemetryBatch, TelemetrySample
from redis_workers.client.connection import get_redis_client
from redis_workers.streams.producer import publish_telemetry_batch
from redis_workers.workers.telemetry_stream_worker import run_worker, STREAM_KEY, GROUP_NAME, process_message, recover_stale_messages


# We use fixed UUIDs for deterministic testing
TEST_SHIFT_ID_1 = uuid.uuid4()
TEST_SHIFT_ID_2 = uuid.uuid4()
TEST_RIDER_ID = uuid.uuid4()

@pytest.fixture(scope="module", autouse=True)
def setup_shift():
    """
    Ensure the shift exists in the DB so foreign key constraints pass.
    We use raw SQL to avoid ORM model field mismatches.
    """
    db = SessionLocal()
    try:
        rand_str = str(uuid.uuid4().int)[:8]
        db.execute(text(f"INSERT INTO users (id, email, hashed_password, full_name, phone_number, role, wallet_balance, is_active, created_at, updated_at) VALUES ('{TEST_RIDER_ID}', 'test{rand_str}@example.com', 'hash', 'Test Rider', '+1555{rand_str}', 'RIDER', 500.0, true, NOW(), NOW()) ON CONFLICT DO NOTHING;"))
        db.execute(text(f"INSERT INTO rider_profiles (id, user_id, vehicle_type, safety_rating, kyc_status, created_at, updated_at) VALUES ('{TEST_RIDER_ID}', '{TEST_RIDER_ID}', 'Bicycle', 5.00, 'PENDING', NOW(), NOW()) ON CONFLICT DO NOTHING;"))
        db.execute(text(f"INSERT INTO shifts (id, rider_id, status, start_time, distance_km, premium_amount, created_at, updated_at) VALUES ('{TEST_SHIFT_ID_1}', '{TEST_RIDER_ID}', 'ACTIVE', NOW(), 0.0, 0.0, NOW(), NOW()) ON CONFLICT DO NOTHING;"))
        db.execute(text(f"INSERT INTO shifts (id, rider_id, status, start_time, distance_km, premium_amount, created_at, updated_at) VALUES ('{TEST_SHIFT_ID_2}', '{TEST_RIDER_ID}', 'ACTIVE', NOW(), 0.0, 0.0, NOW(), NOW()) ON CONFLICT DO NOTHING;"))
        db.commit()

        # Create consumer group if it doesn't exist, do NOT wipe the stream
        client = get_redis_client()
        try:
            client.xgroup_create(STREAM_KEY, GROUP_NAME, id="$", mkstream=True)
        except Exception:
            pass # Group already exists

    except Exception as e:
        db.rollback()
        print(f"Test setup failed: {e}")
        raise e

    yield

    # Cleanup DB
    try:
        db.execute(text(f"DELETE FROM shifts WHERE id IN ('{TEST_SHIFT_ID_1}', '{TEST_SHIFT_ID_2}');"))
        db.execute(text(f"DELETE FROM rider_profiles WHERE id = '{TEST_RIDER_ID}';"))
        db.execute(text(f"DELETE FROM users WHERE id = '{TEST_RIDER_ID}';"))
        db.commit()
    except:
        db.rollback()
    finally:
        db.close()

def build_payload(shift_id, batch_sequence, speed=10.0):
    return {
        "shift_id": str(shift_id),
        "rider_id": str(TEST_RIDER_ID),
        "batch_sequence": batch_sequence,
        "samples": [
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "latitude": 37.77,
                "longitude": -122.41,
                "altitude": 10.0,
                "gps_accuracy": 5.0,
                "speed": speed,
                "accel_x": 0.0,
                "accel_y": 0.0,
                "accel_z": 9.8,
                "gyro_x": 0.0,
                "gyro_y": 0.0,
                "gyro_z": 0.0
            }
        ]
    }

def test_1_normal_path():
    payload = build_payload(TEST_SHIFT_ID_1, 1)
    entry_id = publish_telemetry_batch(payload)

    # Run worker for one iteration
    run_worker(run_once=True)

    # Verify
    db = SessionLocal()
    batch = db.query(TelemetryBatch).filter(TelemetryBatch.redis_stream_id == entry_id).first()
    assert batch is not None
    assert batch.shift_id == TEST_SHIFT_ID_1
    assert batch.batch_sequence == 1
    assert batch.sample_count == 1

    samples = db.query(TelemetrySample).filter(TelemetrySample.batch_id == batch.id).all()
    assert len(samples) == 1

    # Verify Redis ACK
    client = get_redis_client()
    pending = client.xpending(STREAM_KEY, GROUP_NAME)
    assert pending["pending"] >= 0
    # Check specifically this message
    pending_details = client.xpending_range(STREAM_KEY, GROUP_NAME, min=entry_id, max=entry_id, count=1)
    assert len(pending_details) == 0

    db.close()

    # Clean up own message
    client.xdel(STREAM_KEY, entry_id)

def test_2_logical_duplicate():
    # Publish same shift_id and batch_sequence
    payload = build_payload(TEST_SHIFT_ID_1, 1)
    entry_id = publish_telemetry_batch(payload)

    run_worker(run_once=True)

    db = SessionLocal()
    # Verify no second batch exists
    batches = db.query(TelemetryBatch).filter(
        TelemetryBatch.shift_id == TEST_SHIFT_ID_1,
        TelemetryBatch.batch_sequence == 1
    ).all()
    assert len(batches) == 1 # Only the one from Test 1

    # Verify Redis ACK
    client = get_redis_client()
    pending_details = client.xpending_range(STREAM_KEY, GROUP_NAME, min=entry_id, max=entry_id, count=1)
    assert len(pending_details) == 0 # It should be ACKed due to idempotency

    db.close()

    # Clean up own message
    client.xdel(STREAM_KEY, entry_id)

def test_3_redelivery():
    # Create a fresh message for redelivery
    payload = build_payload(TEST_SHIFT_ID_1, 1)
    # We will just process it directly to simulate redelivery
    import json
    # Use a fake but valid redis ID format
    fake_entry_id = f"{int(time.time()*1000)}-0"
    success = process_message(fake_entry_id, json.dumps(payload))

    assert success is True # Idempotency check returns True to XACK

    db = SessionLocal()
    # Still only 1 batch in DB for batch_sequence 1
    batches = db.query(TelemetryBatch).filter(
        TelemetryBatch.shift_id == TEST_SHIFT_ID_1,
        TelemetryBatch.batch_sequence == 1
    ).all()
    assert len(batches) == 1
    db.close()

def test_4_database_failure():
    # Publish a batch with invalid data that violates DB constraints
    # speed = -1.0 violates ck_telemetry_samples_speed_non_negative
    payload = build_payload(TEST_SHIFT_ID_2, 1, speed=-1.0)
    entry_id = publish_telemetry_batch(payload)

    run_worker(run_once=True)

    db = SessionLocal()
    # Verify transaction rolled back
    batch = db.query(TelemetryBatch).filter(TelemetryBatch.redis_stream_id == entry_id).first()
    assert batch is None

    # Verify message is NOT XACKed (remains pending)
    client = get_redis_client()
    pending_details = client.xpending_range(STREAM_KEY, GROUP_NAME, min=entry_id, max=entry_id, count=1)
    assert len(pending_details) == 1
    assert pending_details[0]["message_id"] == entry_id
    db.close()

    # Clean up own message
    client.xack(STREAM_KEY, GROUP_NAME, entry_id)
    client.xdel(STREAM_KEY, entry_id)

def test_5_recovery():
    client = get_redis_client()

    # Inject a GOOD message
    good_payload = build_payload(TEST_SHIFT_ID_2, 2, speed=15.0)
    good_entry_id = publish_telemetry_batch(good_payload)

    # Read it but don't process it (simulating a crash before ACK)
    # xreadgroup reads and puts it in pending
    client.xreadgroup(GROUP_NAME, "crashed-worker", {STREAM_KEY: ">"}, count=1)

    # It is now pending for "crashed-worker".
    # Wait for idle threshold
    time.sleep(0.1)

    # Run recovery with idle_threshold_ms=1
    recover_stale_messages(client, idle_threshold_ms=1)

    # Verify it was processed by recovery and ACKed
    pending_details_good = client.xpending_range(STREAM_KEY, GROUP_NAME, min=good_entry_id, max=good_entry_id, count=1)
    assert len(pending_details_good) == 0

    db = SessionLocal()
    good_batch = db.query(TelemetryBatch).filter(TelemetryBatch.redis_stream_id == good_entry_id).first()
    assert good_batch is not None
    db.close()

    # Clean up own message
    client.xdel(STREAM_KEY, good_entry_id)
