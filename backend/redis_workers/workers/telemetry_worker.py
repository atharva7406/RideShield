import json
import time
import os
import sys

# Ensure backend directory is in python system path to resolve imports correctly
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import redis
from app.core.config import settings
from app.services.telemetry_service import process_telemetry_batch_sync
from db.core.session import SessionLocal
from redis_workers.workers.telemetry_stream_worker import run_worker as run_stream_worker

def start_worker():
    print("Starting RideShield Telemetry Background Worker...")
    try:
        redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        print("Connected to Upstash Redis successfully.")

        stream_key = "rideshield:telemetry"
        group_name = "telemetry-workers"
        try:
            redis_client.xgroup_create(stream_key, group_name, id="$", mkstream=True)
            print(f"Created consumer group '{group_name}' on stream '{stream_key}'.")
        except Exception:
            print(f"Consumer group '{group_name}' on stream '{stream_key}' is ready.")
    except Exception as e:
        print(f"Error connecting to Redis: {e}")
        return

    while True:
        try:
            # 1. Process telemetry stream entries (consumer group)
            try:
                run_stream_worker(run_once=True)
            except Exception as stream_err:
                pass

            # 2. Process legacy telemetry_queue items if any
            result = redis_client.blpop("telemetry_queue", timeout=2)
            if result:
                _, serialized_payload = result
                print(f"Received queue batch to process: {serialized_payload[:200]}...")
                
                payload = json.loads(serialized_payload)
                
                db = SessionLocal()
                try:
                    process_telemetry_batch_sync(db, payload)
                    print("Batch processed and committed successfully.")
                except Exception as db_err:
                    print(f"Error saving batch to PostgreSQL database: {db_err}")
                finally:
                    db.close()
            else:
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("Stopping worker...")
            break
        except Exception as loop_err:
            print(f"Unexpected error in worker loop: {loop_err}")
            time.sleep(2)

if __name__ == "__main__":
    start_worker()
