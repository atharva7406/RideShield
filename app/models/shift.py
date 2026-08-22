import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Numeric, DateTime, ForeignKey, Enum as SQLEnum, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.models.enums import ShiftStatus

class Shift(Base):
    __tablename__ = "shifts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    rider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[ShiftStatus] = mapped_column(
        SQLEnum(ShiftStatus, name="shift_status_enum"),
        default=ShiftStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    end_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    distance_km: Mapped[float] = mapped_column(
        Numeric(8, 2), default=0.00, nullable=False
    )
    premium_amount: Mapped[float] = mapped_column(
        Numeric(10, 2), default=0.00, nullable=False
    )
    policy_number: Mapped[Optional[str]] = mapped_column(
        String(100), unique=True, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    rider: Mapped["User"] = relationship("User", back_populates="shifts")
    telemetry_batches: Mapped[list["TelemetryBatch"]] = relationship(
        "TelemetryBatch", back_populates="shift"
    )
    incidents: Mapped[list["Incident"]] = relationship(
        "Incident", back_populates="shift"
    )
    risk_scores: Mapped[list["RiskScore"]] = relationship(
        "RiskScore", back_populates="shift"
    )
    payments: Mapped[list["Payment"]] = relationship(
        "Payment", back_populates="shift"
    )

    __table_args__ = (
        CheckConstraint("distance_km >= 0", name="ck_shifts_distance_non_negative"),
        CheckConstraint("premium_amount >= 0", name="ck_shifts_premium_non_negative"),
        CheckConstraint("end_time IS NULL OR end_time >= start_time", name="ck_shifts_end_after_start"),
    )
