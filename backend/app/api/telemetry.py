import json
from typing import Any
import redis
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api import deps
from app.core.config import settings
from app.schemas import TelemetryBatchSchema
from db.core.session import get_db
from db.models.user import User

router = APIRouter()

# Try initializing Redis Client
try:
    redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
except Exception:
    redis_client = None

@router.post("/batch")
def receive_telemetry_batch(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
    batch_in: TelemetryBatchSchema
) -> Any:
    # Print formatted telemetry batch info to console
    print(f"\n============================================================")
    print(f"[TELEMETRY RECEIVED] Batch #{batch_in.batch_sequence} | Shift: {batch_in.shift_id} | Rider: {current_user.full_name}")
    print(f"Sample Count: {len(batch_in.samples)}")
    if batch_in.samples:
        latest = batch_in.samples[-1]
        print(f"Latest Sample -> Lat: {latest.latitude:.5f}, Lng: {latest.longitude:.5f}, Speed: {latest.speed:.1f} km/h, Accel: ({latest.accel_x:.2f}, {latest.accel_y:.2f}, {latest.accel_z:.2f})")
    print(f"============================================================\n")

    # Serialize data using Pydantic's built-in encoder which handles UUID serialization safely
    payload_dict = json.loads(batch_in.model_dump_json())
    # Add rider context
    payload_dict["rider_id"] = str(current_user.id)
    
    serialized_payload = json.dumps(payload_dict)
    
    # Try sending to Redis Queue
    if redis_client:
        try:
            redis_client.rpush("telemetry_queue", serialized_payload)
            return {"status": "queued", "message": "Telemetry batch queued successfully"}
        except Exception as e:
            # Fallback to direct DB write if Redis fails during demo/sprint
            pass
            
    # Fallback/Direct processing
    # Import locally to avoid circular dependencies
    from app.services.telemetry_service import process_telemetry_batch_sync
    try:
        process_telemetry_batch_sync(db, payload_dict)
        return {"status": "synced", "message": "Telemetry batch processed synchronously (fallback)"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process telemetry: {str(e)}"
        )
