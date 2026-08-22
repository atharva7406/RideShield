import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Numeric, Float, DateTime, ForeignKey, Enum as SQLEnum, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.core.base import Base
from db.models.enums import IncidentStatus

class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    shift_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shifts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    rider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    batch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("telemetry_batches.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[IncidentStatus] = mapped_column(
        SQLEnum(IncidentStatus, name="incident_status_enum"),
        default=IncidentStatus.DETECTED,
        nullable=False,
        index=True,
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    peak_g_force: Mapped[float] = mapped_column(
        Numeric(5, 2), nullable=False
    )
    confidence_score: Mapped[float] = mapped_column(
        Numeric(3, 2), nullable=False
    )
    latitude: Mapped[float] = mapped_column(
        Float, nullable=False
    )
    longitude: Mapped[float] = mapped_column(
        Float, nullable=False
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
    shift: Mapped["Shift"] = relationship("Shift", back_populates="incidents")
    rider: Mapped["User"] = relationship("User")
    batch: Mapped[Optional["TelemetryBatch"]] = relationship("TelemetryBatch", back_populates="incidents")
    claims: Mapped[list["Claim"]] = relationship("Claim", back_populates="incident")

    __table_args__ = (
        CheckConstraint("peak_g_force >= 0", name="ck_incidents_peak_g_force_non_negative"),
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 1", name="ck_incidents_confidence_score_range"),
    )
