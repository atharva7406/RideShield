import json
import logging
import argparse
from datetime import datetime

from redis.client.connection import get_redis_client
from db.core.session import SessionLocal
from db.models.telemetry import TelemetryBatch, TelemetrySample

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

STREAM_KEY = "rideshield:telemetry"
GROUP_NAME = "telemetry-workers"
CONSUMER_NAME = "worker-1"

def process_message(msg_id: str, payload_str: str) -> bool:
    """
    Processes a single telemetry batch message.
    Returns True if the message was successfully processed (or dropped as invalid) and should be XACKed.
    Returns False if processing failed (e.g., DB error) and should NOT be XACKed.
    """
    # 1. Parse JSON payload
    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError as e:
        logger.error(f"Message {msg_id} is malformed JSON. Dropping. Error: {e}")
        return True # Non-retryable, return True to XACK

    # Basic payload validation
    required_keys = {"shift_id", "batch_sequence", "samples"}
    if not required_keys.issubset(payload.keys()) or not isinstance(payload["samples"], list) or not payload["samples"]:
        logger.error(f"Message {msg_id} payload missing required fields or empty samples. Dropping.")
        return True # Non-retryable, return True to XACK

    shift_id_str = payload["shift_id"]
    batch_seq = payload["batch_sequence"]
    samples_data = payload["samples"]

    db = SessionLocal()
    try:
        # 2. Idempotency Check 1: redis_stream_id
        existing_by_msg_id = db.query(TelemetryBatch).filter(TelemetryBatch.redis_stream_id == msg_id).first()
        if existing_by_msg_id:
            logger.info(f"Message {msg_id} already processed (Idempotency Check 1). Skipping.")
            return True

        # 3. Idempotency Check 2: (shift_id, batch_sequence)
        existing_by_seq = db.query(TelemetryBatch).filter(
            TelemetryBatch.shift_id == shift_id_str,
            TelemetryBatch.batch_sequence == batch_seq
        ).first()
        if existing_by_seq:
            logger.info(f"Message {msg_id} already processed (Idempotency Check 2 for shift {shift_id_str}, seq {batch_seq}). Skipping.")
            return True

        # 4. Process and insert
        # Parse timestamps to find start and end
        # We assume ISO-8601 strings from the payload
        try:
            parsed_samples = []
            for s in samples_data:
                ts = datetime.fromisoformat(s["timestamp"].replace("Z", "+00:00"))
                parsed_samples.append({**s, "timestamp": ts})
        except ValueError as e:
            logger.error(f"Message {msg_id} has invalid timestamp format. Dropping. Error: {e}")
            return True

        start_timestamp = min(s["timestamp"] for s in parsed_samples)
        end_timestamp = max(s["timestamp"] for s in parsed_samples)
        sample_count = len(parsed_samples)

        # Create Batch
        batch = TelemetryBatch(
            shift_id=shift_id_str,
            redis_stream_id=msg_id,
            batch_sequence=batch_seq,
            sample_count=sample_count,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp
        )
        db.add(batch)
        db.flush() # flush to get batch.id if needed, though UUIDs might be generated locally

        # Create Samples
        for s in parsed_samples:
            sample = TelemetrySample(
                batch_id=batch.id,
                timestamp=s["timestamp"],
                latitude=s["latitude"],
                longitude=s["longitude"],
                altitude=s.get("altitude"),
                gps_accuracy=s.get("gps_accuracy"),
                speed=s["speed"],
                accel_x=s["accel_x"],
                accel_y=s["accel_y"],
                accel_z=s["accel_z"],
                gyro_x=s["gyro_x"],
                gyro_y=s["gyro_y"],
                gyro_z=s["gyro_z"],
            )
            db.add(sample)

        # COMMIT
        db.commit()
        logger.info(f"Successfully processed message {msg_id} (shift: {shift_id_str}, seq: {batch_seq})")
        return True

    except Exception as e:
        db.rollback()
        logger.error(f"Database failure while processing message {msg_id}: {e}")
        return False
    finally:
        db.close()

def recover_stale_messages(client, idle_threshold_ms: int):
    """
    Uses XAUTOCLAIM to claim pending messages that have been idle for more than idle_threshold_ms.
    Processes and XACKs them.
    """
    start_id = "0-0"
    while True:
        # xautoclaim returns: [next_start_id, list_of_messages] in redis-py (or slightly different based on version, we unpack safely)
        # Using redis-py signature: xautoclaim(name, groupname, consumername, min_idle_time, start_id, count=100, justid=False)
        result = client.xautoclaim(
            name=STREAM_KEY,
            groupname=GROUP_NAME,
            consumername=CONSUMER_NAME,
            min_idle_time=idle_threshold_ms,
            start_id=start_id,
            count=10
        )

        if not result:
            break

        next_start_id, messages = result[0], result[1]

        if not messages:
            break

        for msg_id, fields in messages:
            if "data" not in fields:
                logger.error(f"Claimed message {msg_id} missing 'data' field. Dropping and XACKing.")
                client.xack(STREAM_KEY, GROUP_NAME, msg_id)
                continue

            payload_str = fields["data"]
            logger.info(f"Recovering stale message {msg_id}")
            success = process_message(msg_id, payload_str)
            if success:
                client.xack(STREAM_KEY, GROUP_NAME, msg_id)

        start_id = next_start_id
        if start_id == "0-0" or start_id == b"0-0":
            break

def run_worker(run_once: bool = False, idle_threshold_ms: int = 30000):
    client = get_redis_client()

    # 1. Recover stale messages first
    recover_stale_messages(client, idle_threshold_ms)

    # 2. Main loop
    while True:
        try:
            # Block for new messages. If run_once, block time is small or 0 so it returns quickly.
            block_time = 1 if run_once else 5000
            streams = {STREAM_KEY: ">"}

            # xreadgroup returns a list of streams: [[stream_key, [(msg_id, {fields}), ...]], ...]
            result = client.xreadgroup(
                groupname=GROUP_NAME,
                consumername=CONSUMER_NAME,
                streams=streams,
                count=10,
                block=block_time
            )

            if not result:
                if run_once:
                    break
                continue

            for stream_name, messages in result:
                for msg_id, fields in messages:
                    if "data" not in fields:
                        logger.error(f"Message {msg_id} missing 'data' field. Dropping and XACKing.")
                        client.xack(STREAM_KEY, GROUP_NAME, msg_id)
                        continue

                    payload_str = fields["data"]
                    success = process_message(msg_id, payload_str)

                    if success:
                        client.xack(STREAM_KEY, GROUP_NAME, msg_id)

            if run_once:
                break

        except Exception as e:
            logger.error(f"Worker encountered an error: {e}")
            if run_once:
                break

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Telemetry Worker for RideShield")
    parser.add_argument("--run-once", action="store_true", help="Run one iteration and exit (for testing)")
    parser.add_argument("--idle-threshold-ms", type=int, default=30000, help="Idle threshold for XAUTOCLAIM in ms")
    args = parser.parse_args()

    logger.info(f"Starting Telemetry Worker (run_once={args.run_once}, idle_threshold_ms={args.idle_threshold_ms})")
    run_worker(run_once=args.run_once, idle_threshold_ms=args.idle_threshold_ms)
