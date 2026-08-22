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

def start_worker():
    print("Starting RideShield Telemetry Background Worker...")
    try:
        redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        print("Connected to Redis successfully.")
    except Exception as e:
        print(f"Error connecting to Redis: {e}")
        return

    while True:
        try:
            # Block pop from telemetry_queue
            result = redis_client.blpop("telemetry_queue", timeout=5)
            if result:
                _, serialized_payload = result
                print(f"Received batch to process: {serialized_payload[:200]}...")
                
                payload = json.loads(serialized_payload)
                
                # Start new database transaction session
                db = SessionLocal()
                try:
                    process_telemetry_batch_sync(db, payload)
                    print("Batch processed and committed successfully.")
                except Exception as db_err:
                    print(f"Error saving batch to PostgreSQL database: {db_err}")
                finally:
                    db.close()
            else:
                # No messages in queue, sleep slightly
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("Stopping worker...")
            break
        except Exception as loop_err:
            print(f"Unexpected error in worker loop: {loop_err}")
            time.sleep(2)

if __name__ == "__main__":
    start_worker()
