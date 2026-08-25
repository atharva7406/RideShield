import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, Float, ForeignKey, Integer, Numeric, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.core.base import Base


class RiderBehaviourProfile(Base):
    """
    One row per rider — the current, rebuildable historical behaviour
    profile, aggregated from that rider's valid ShiftBehaviourSummary rows
    (db/models/shift_behaviour_summary.py). This is Phase 2 of the
    Behaviour Risk & Premium Engine:
        Telemetry -> ShiftBehaviourSummary -> RiderBehaviourProfile
    Rebuilt (not appended to) after every completed shift — see
    app/services/rider_behaviour_profile_service.py, which computes every
    field here; not repeated in this docstring to avoid the two drifting
    out of sync (same principle as shift_behaviour_summary.py).

    This is a behavioural-history SUMMARY, not a risk score and not an
    accident-probability estimate. `overall_behaviour_score` is a
    transparent, deterministic baseline indicator only — the eventual
    XGBoost rider-risk model (a later phase) is a separate thing that will
    read this profile as one of its inputs, not replace it.

    NAMING NOTE: the Phase 2 spec lists shift-count fields under two
    separate headings ("Identity/metadata": based_on_shift_count /
    based_on_valid_shift_count; "Overall profile": valid_shift_count /
    total_shift_count) that describe the same two underlying numbers.
    Implemented once, as based_on_shift_count / based_on_valid_shift_count
    — both headings' intent (surface how much history this profile rests
    on) is satisfied without a duplicate pair of columns holding identical
    values. Flagged explicitly in the Phase 2 report.
    """
    __tablename__ = "rider_behaviour_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # One profile per rider — RESTRICT (not CASCADE) matches every other
    # rider_id -> users.id FK in this codebase (Shift, Incident, RiskScore,
    # ShiftBehaviourSummary) except RiderProfile.user_id, which is CASCADE
    # for a different reason (it's user-authored descriptive data, a true
    # 1:1 extension of the user row). This profile is a derived, historical
    # aggregate — RESTRICT is the majority, and more defensible, pattern.
    rider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"),
        unique=True, nullable=False, index=True,
    )

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    based_on_shift_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    based_on_valid_shift_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # --- Recent (default: last RECENT_WINDOW_SHIFT_COUNT valid shifts) ---
    recent_avg_speed: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    recent_max_speed: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    recent_hard_braking_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    recent_hard_acceleration_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    recent_overspeeding_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    recent_sharp_turn_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    recent_max_g: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0.0)
    recent_data_quality: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=0.0)

    # --- Medium-term (default: last MEDIUM_WINDOW_SHIFT_COUNT valid shifts) ---
    medium_avg_speed: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    medium_max_speed: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    medium_hard_braking_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    medium_hard_acceleration_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    medium_overspeeding_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    medium_sharp_turn_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    medium_max_g: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0.0)
    medium_data_quality: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=0.0)

    # --- Long-term (default: up to LONG_TERM_WINDOW_SHIFT_COUNT_CAP valid shifts) ---
    long_term_avg_speed: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    long_term_max_speed: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    long_term_hard_braking_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    long_term_hard_acceleration_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    long_term_overspeeding_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    long_term_sharp_turn_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    long_term_max_g: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0.0)
    long_term_data_quality: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=0.0)

    # --- Consistency / stability ---
    hard_braking_rate_variance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    overspeeding_rate_variance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    speed_variability: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    behaviour_consistency_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0.0)

    # --- Overall ---
    overall_behaviour_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0.0)
    data_quality_score: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=0.0)
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=0.0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    rider: Mapped["User"] = relationship("User", back_populates="behaviour_profile")

    __table_args__ = (
        CheckConstraint("based_on_shift_count >= 0", name="ck_rider_behaviour_profiles_shift_count_non_negative"),
        CheckConstraint("based_on_valid_shift_count >= 0", name="ck_rider_behaviour_profiles_valid_shift_count_non_negative"),
        CheckConstraint("based_on_valid_shift_count <= based_on_shift_count", name="ck_rider_behaviour_profiles_valid_le_total"),
        CheckConstraint(
            "overall_behaviour_score >= 0 AND overall_behaviour_score <= 100",
            name="ck_rider_behaviour_profiles_overall_score_range",
        ),
        CheckConstraint(
            "behaviour_consistency_score >= 0 AND behaviour_consistency_score <= 100",
            name="ck_rider_behaviour_profiles_consistency_score_range",
        ),
        CheckConstraint(
            "data_quality_score >= 0 AND data_quality_score <= 1",
            name="ck_rider_behaviour_profiles_data_quality_range",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_rider_behaviour_profiles_confidence_range",
        ),
    )
