import uuid
from datetime import datetime, timezone
from sqlalchemy import Numeric, Integer, DateTime, ForeignKey, Enum as SQLEnum, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.core.base import Base
from db.models.enums import RiskLevel

class RiskScore(Base):
    __tablename__ = "risk_scores"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    shift_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shifts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    rider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    risk_score: Mapped[float] = mapped_column(
        Numeric(5, 2), nullable=False
    )
    risk_level: Mapped[RiskLevel] = mapped_column(
        SQLEnum(RiskLevel, name="risk_level_enum"),
        default=RiskLevel.LOW,
        nullable=False,
        index=True,
    )
    hard_braking_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    hard_acceleration_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    overspeeding_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    window_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    shift: Mapped["Shift"] = relationship("Shift", back_populates="risk_scores")
    rider: Mapped["User"] = relationship("User")

    __table_args__ = (
        CheckConstraint("risk_score >= 0 AND risk_score <= 100", name="ck_risk_scores_score_range"),
        CheckConstraint("hard_braking_count >= 0", name="ck_risk_scores_hard_braking_non_negative"),
        CheckConstraint("hard_acceleration_count >= 0", name="ck_risk_scores_hard_acceleration_non_negative"),
        CheckConstraint("overspeeding_count >= 0", name="ck_risk_scores_overspeeding_non_negative"),
        CheckConstraint("window_end > window_start", name="ck_risk_scores_window_end_after_start"),
    )
