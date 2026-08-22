import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Index, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class TelemetryBatch(Base):
    __tablename__ = "telemetry_batches"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    shift_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shifts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    redis_stream_id: Mapped[Optional[str]] = mapped_column(
        String(100), unique=True, nullable=True
    )
    batch_sequence: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    sample_count: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    start_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    end_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    shift: Mapped["Shift"] = relationship("Shift", back_populates="telemetry_batches")
    samples: Mapped[list["TelemetrySample"]] = relationship(
        "TelemetrySample", back_populates="batch", cascade="all, delete-orphan"
    )
    incidents: Mapped[list["Incident"]] = relationship("Incident", back_populates="batch")

    __table_args__ = (
        UniqueConstraint("shift_id", "batch_sequence", name="uq_telemetry_batches_shift_sequence"),
        CheckConstraint("batch_sequence >= 0", name="ck_telemetry_batches_sequence_non_negative"),
        CheckConstraint("sample_count > 0", name="ck_telemetry_batches_sample_count_positive"),
        CheckConstraint("end_timestamp >= start_timestamp", name="ck_telemetry_batches_end_after_start"),
        Index("idx_telemetry_batches_shift_start_timestamp", "shift_id", "start_timestamp"),
    )


class TelemetrySample(Base):
    __tablename__ = "telemetry_samples"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("telemetry_batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    latitude: Mapped[float] = mapped_column(
        Float, nullable=False
    )
    longitude: Mapped[float] = mapped_column(
        Float, nullable=False
    )
    altitude: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    gps_accuracy: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    speed: Mapped[float] = mapped_column(
        Float, nullable=False
    )
    accel_x: Mapped[float] = mapped_column(
        Float, nullable=False
    )
    accel_y: Mapped[float] = mapped_column(
        Float, nullable=False
    )
    accel_z: Mapped[float] = mapped_column(
        Float, nullable=False
    )
    gyro_x: Mapped[float] = mapped_column(
        Float, nullable=False
    )
    gyro_y: Mapped[float] = mapped_column(
        Float, nullable=False
    )
    gyro_z: Mapped[float] = mapped_column(
        Float, nullable=False
    )

    # Relationships
    batch: Mapped["TelemetryBatch"] = relationship("TelemetryBatch", back_populates="samples")

    __table_args__ = (
        CheckConstraint("speed >= 0", name="ck_telemetry_samples_speed_non_negative"),
        Index("idx_telemetry_samples_batch_timestamp", "batch_id", "timestamp"),
    )
