import math
from datetime import datetime, timezone
import uuid
from sqlalchemy.orm import Session
from db.models.telemetry import TelemetryBatch, TelemetrySample
from db.models.incident import Incident
from db.models.risk import RiskScore
from db.models.shift import Shift
from db.models.enums import IncidentStatus, RiskLevel

def process_telemetry_batch_sync(db: Session, payload: dict) -> None:
    shift_id = uuid.UUID(payload["shift_id"])
    rider_id = uuid.UUID(payload["rider_id"])
    batch_sequence = payload["batch_sequence"]
    samples_data = payload["samples"]

    if not samples_data:
        return

    # Convert timestamps
    start_ts = datetime.fromtimestamp(samples_data[0]["timestamp"], timezone.utc)
    end_ts = datetime.fromtimestamp(samples_data[-1]["timestamp"], timezone.utc)
    if end_ts <= start_ts:
        from datetime import timedelta
        end_ts = start_ts + timedelta(seconds=1)

    # 1. Create TelemetryBatch
    db_batch = TelemetryBatch(
        shift_id=shift_id,
        batch_sequence=batch_sequence,
        sample_count=len(samples_data),
        start_timestamp=start_ts,
        end_timestamp=end_ts,
        ingested_at=datetime.now(timezone.utc)
    )
    db.add(db_batch)
    db.flush()  # Acquire batch ID

    # 2. Add TelemetrySamples
    samples_to_add = []
    max_g_force = 0.0
    lat_sum = 0.0
    lng_sum = 0.0
    speed_sum = 0.0
    hard_accel = 0
    hard_braking = 0
    overspeeding = 0
    
    for sample in samples_data:
        # Calculate g-force: sqrt(ax^2 + ay^2 + az^2) / 9.8
        ax, ay, az = sample["accel_x"], sample["accel_y"], sample["accel_z"]
        g_force = math.sqrt(ax**2 + ay**2 + az**2) / 9.8
        if g_force > max_g_force:
            max_g_force = g_force
            
        if g_force > 1.8:
            hard_accel += 1
        elif g_force < 0.5:
            hard_braking += 1

        lat_sum += sample["latitude"]
        lng_sum += sample["longitude"]
        speed_sum += sample["speed"]
        
        if sample["speed"] > 60.0:
            overspeeding += 1

        ts = datetime.fromtimestamp(sample["timestamp"], timezone.utc)
        db_sample = TelemetrySample(
            batch_id=db_batch.id,
            timestamp=ts,
            latitude=sample["latitude"],
            longitude=sample["longitude"],
            altitude=sample.get("altitude"),
            gps_accuracy=sample.get("gps_accuracy"),
            speed=sample["speed"],
            accel_x=ax,
            accel_y=ay,
            accel_z=az,
            gyro_x=sample["gyro_x"],
            gyro_y=sample["gyro_y"],
            gyro_z=sample["gyro_z"]
        )
        samples_to_add.append(db_sample)
        
    db.add_all(samples_to_add)

    # Calculate average position & speed for metrics/rules
    sample_count = len(samples_data)
    avg_lat = lat_sum / sample_count
    avg_lng = lng_sum / sample_count
    avg_speed = speed_sum / sample_count

    # 3. Crash Detection Algorithm
    # Legacy Telemetry-based Crash Detector (DISABLED)
    # The Rider App local high-frequency detector is now the source of truth.
    USE_LEGACY_CRASH_DETECTOR = False
    
    CRASH_THRESHOLD_G = 4.0
    if USE_LEGACY_CRASH_DETECTOR and max_g_force >= CRASH_THRESHOLD_G:
        # Deduplication check
        from datetime import timedelta
        recent_incident = db.query(Incident).filter(
            Incident.shift_id == shift_id,
            Incident.detected_at >= datetime.now(timezone.utc) - timedelta(seconds=60)
        ).first()
        
        if not recent_incident:
            confidence = min(0.95, 0.5 + (max_g_force - CRASH_THRESHOLD_G) / 10.0)
            db_incident = Incident(
                shift_id=shift_id,
                rider_id=rider_id,
                batch_id=db_batch.id,
                status=IncidentStatus.DETECTED,
                peak_g_force=max_g_force,
                confidence_score=confidence,
                latitude=avg_lat,
                longitude=avg_lng,
                detected_at=datetime.now(timezone.utc)
            )
            db.add(db_incident)


    # 4. Risk Scoring Engine (Continuous evaluation)
    calculated_risk = RiskLevel.LOW
    score = 100.0 - (hard_accel * 5 + hard_braking * 5 + overspeeding * 10)
    score = max(0.0, min(100.0, score))
    
    if score < 40.0:
        calculated_risk = RiskLevel.HIGH
    elif score < 75.0:
        calculated_risk = RiskLevel.MEDIUM

    db_risk = RiskScore(
        shift_id=shift_id,
        rider_id=rider_id,
        risk_score=score,
        risk_level=calculated_risk,
        hard_braking_count=hard_braking,
        hard_acceleration_count=hard_accel,
        overspeeding_count=overspeeding,
        window_start=start_ts,
        window_end=end_ts,
        evaluated_at=datetime.now(timezone.utc)
    )
    db.add(db_risk)

    # 5. Update shift accumulated distance (hackathon simulation: increment distance)
    db_shift = db.query(Shift).filter(Shift.id == shift_id).first()
    if db_shift:
        # Increment mock distance based on time * speed
        duration_hours = (end_ts - start_ts).total_seconds() / 3600.0
        distance_delta = avg_speed * duration_hours
        db_shift.distance_km = float(db_shift.distance_km) + distance_delta
        db.add(db_shift)

    db.commit()
    print(f"[TELEMETRY STORED IN DB] Batch ID: {db_batch.id} | Saved {len(samples_to_add)} samples to Database | Shift Distance: {db_shift.distance_km:.2f} km | Risk Score: {score:.1f} ({calculated_risk.value})")
