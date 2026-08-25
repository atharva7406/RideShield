import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, Numeric, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.core.base import Base


class ShiftBehaviourSummary(Base):
    """
    One row per completed shift — a deterministic, server-computed
    behaviour summary. Distinct from RiskScore (db/models/risk.py), which
    remains the LIVE/in-shift risk signal computed continuously during an
    ACTIVE shift by telemetry_service.py; this table is the durable
    historical record a future rider-risk model reads across shifts.

    This is Phase 1 of the Behaviour Risk & Premium Engine — these fields
    are descriptive counts/rates for future ML feature engineering, NOT a
    validated insurance risk score. Event-count thresholds and the
    sharp-turn definition are documented in
    app/services/behaviour_summary_service.py, which computes these
    fields — not repeated here to avoid the two drifting out of sync.
    """
    __tablename__ = "shift_behaviour_summaries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    shift_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shifts.id", ondelete="RESTRICT"),
        unique=True, nullable=False, index=True,
    )
    rider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    # Server-authoritative GPS distance — see app/services/distance_service.py.
    # NOT the client-supplied value ShiftEnd.distance_km carried historically.
    distance_km: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)

    average_speed: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_speed: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    hard_braking_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hard_acceleration_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overspeeding_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sharp_turn_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Duration-normalized (events/hour), deliberately not distance-
    # normalized this phase — see behaviour_summary_service.py.
    hard_braking_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    hard_acceleration_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    overspeeding_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    sharp_turn_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    max_g: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0.0)
    accel_std: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    jerk_mean: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # samples per minute
    sampling_density: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    data_quality_score: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=0.0)
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )

    # Relationships
    shift: Mapped["Shift"] = relationship("Shift", back_populates="behaviour_summary")
    rider: Mapped["User"] = relationship("User")

    __table_args__ = (
        CheckConstraint("duration_seconds >= 0", name="ck_shift_behaviour_summaries_duration_non_negative"),
        CheckConstraint("distance_km >= 0", name="ck_shift_behaviour_summaries_distance_non_negative"),
        CheckConstraint("sample_count >= 0", name="ck_shift_behaviour_summaries_sample_count_non_negative"),
        CheckConstraint(
            "data_quality_score >= 0 AND data_quality_score <= 1",
            name="ck_shift_behaviour_summaries_quality_score_range",
        ),
    )
