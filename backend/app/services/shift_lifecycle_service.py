"""
Shared shift-ending logic — extracted from POST /shifts/{id}/end so the
same server-authoritative distance/behaviour-summary/profile-rebuild path
runs whether the shift is ended by the rider tapping "End Shift" or
auto-ended by the backend on a VERIFIED_ACCIDENT escalation (WhatsApp HELP
reply, the automated no-response ladder, or the in-app SOS button).

Before this existed, a verified accident never touched Shift.status —
coverage stayed ACTIVE in the DB until the rider manually reopened the app
and tapped "End Shift", even after emergency services had already been
contacted. auto_end_shift_for_incident() closes that gap: a verified
accident always ends the shift, no manual step required.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.services import behaviour_summary_service, distance_service, rider_behaviour_profile_service
from db.models.enums import ShiftStatus
from db.models.shift import Shift
from db.models.shift_behaviour_summary import ShiftBehaviourSummary

logger = logging.getLogger(__name__)


def end_active_shift(db: Session, db_shift: Shift) -> list:
    """Ends db_shift (caller has already verified it's ACTIVE and resolved
    ownership/auth). Advances status, computes server-authoritative
    distance from retained telemetry, creates the ShiftBehaviourSummary
    (idempotent — safe to call again for the same shift), rebuilds the
    rider's RiderBehaviourProfile, and commits. Returns the shift's
    TelemetrySample rows (already fetched here) so a caller that needs to
    build a human-readable summary doesn't have to query them twice.
    """
    from db.models.telemetry import TelemetryBatch, TelemetrySample

    batches = db.query(TelemetryBatch).filter(TelemetryBatch.shift_id == db_shift.id).all()
    batch_ids = [b.id for b in batches]
    samples = (
        db.query(TelemetrySample).filter(TelemetrySample.batch_id.in_(batch_ids)).all()
        if batch_ids else []
    )

    db_shift.status = ShiftStatus.COMPLETED
    db_shift.end_time = datetime.now(timezone.utc)

    duration_seconds = max(0.0, (db_shift.end_time - db_shift.start_time).total_seconds())

    distance_result = distance_service.compute_distance_km(samples)
    db_shift.distance_km = distance_result.distance_km

    existing_summary = db.query(ShiftBehaviourSummary).filter(
        ShiftBehaviourSummary.shift_id == db_shift.id
    ).first()

    if existing_summary is None:
        metrics = behaviour_summary_service.compute_behaviour_metrics(samples)
        quality = behaviour_summary_service.compute_data_quality(samples, duration_seconds, distance_result)
        sampling_density = (metrics.sample_count / (duration_seconds / 60.0)) if duration_seconds > 0 else 0.0

        db_summary = ShiftBehaviourSummary(
            shift_id=db_shift.id,
            rider_id=db_shift.rider_id,
            duration_seconds=int(duration_seconds),
            distance_km=distance_result.distance_km,
            sample_count=metrics.sample_count,
            average_speed=metrics.average_speed,
            max_speed=metrics.max_speed,
            hard_braking_count=metrics.hard_braking_count,
            hard_acceleration_count=metrics.hard_acceleration_count,
            overspeeding_count=metrics.overspeeding_count,
            sharp_turn_count=metrics.sharp_turn_count,
            hard_braking_rate=behaviour_summary_service.compute_hourly_rate(
                metrics.hard_braking_count, duration_seconds),
            hard_acceleration_rate=behaviour_summary_service.compute_hourly_rate(
                metrics.hard_acceleration_count, duration_seconds),
            overspeeding_rate=behaviour_summary_service.compute_hourly_rate(
                metrics.overspeeding_count, duration_seconds),
            sharp_turn_rate=behaviour_summary_service.compute_hourly_rate(
                metrics.sharp_turn_count, duration_seconds),
            max_g=metrics.max_g,
            accel_std=metrics.accel_std,
            jerk_mean=metrics.jerk_mean,
            sampling_density=sampling_density,
            data_quality_score=quality.score,
            is_valid=behaviour_summary_service.is_summary_valid(metrics.sample_count, quality.score),
        )
        db.add(db_summary)

    db.add(db_shift)
    try:
        db.commit()
    except IntegrityError:
        # Lost a race with a concurrent end (e.g. the rider tapped "End
        # Shift" at the same moment an escalation auto-ended it) — the
        # other caller's summary already committed. Roll back and retry
        # the idempotent status/end_time/distance writes only.
        db.rollback()
        db_shift.status = ShiftStatus.COMPLETED
        db_shift.end_time = db_shift.end_time or datetime.now(timezone.utc)
        db_shift.distance_km = distance_result.distance_km
        db.add(db_shift)
        db.commit()
    db.refresh(db_shift)

    try:
        rider_behaviour_profile_service.rebuild_rider_profile(db, db_shift.rider_id)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to rebuild RiderBehaviourProfile for rider {db_shift.rider_id}: {e}")

    return samples


def auto_end_shift_for_incident(db: Session, shift_id, reason: str) -> bool:
    """Ends the shift tied to a just-escalated VERIFIED_ACCIDENT incident,
    if it's still ACTIVE. Idempotent: a shift already ended (by the rider,
    or by an earlier escalation call for the same incident) is a no-op,
    not an error — safe to call from every VERIFIED_ACCIDENT transition
    point (WhatsApp HELP reply, the automated no-response ladder, in-app
    SOS, the manual /incidents/{id}/help route) without double-processing.
    Never raises: an auto-end failure must not break the caller's own
    escalation flow (claim filing, emergency call), same fallback-safety
    principle as the rest of this codebase's ML/pricing fallbacks.
    """
    try:
        db_shift = db.query(Shift).filter(Shift.id == shift_id).first()
        if db_shift is None or db_shift.status != ShiftStatus.ACTIVE:
            return False
        print(f"[Shift Auto-End] Ending shift {shift_id} ({reason}) — verified accident.")
        end_active_shift(db, db_shift)
        return True
    except Exception as e:
        logger.error(f"Failed to auto-end shift {shift_id} for {reason}: {e}")
        return False
