import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Numeric, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class RiderProfile(Base):
    __tablename__ = "rider_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    vehicle_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    license_number: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    emergency_contact_phone: Mapped[Optional[str]] = mapped_column(
        String(30), nullable=True
    )
    safety_rating: Mapped[float] = mapped_column(
        Numeric(3, 2), default=5.00, nullable=False
    )
    kyc_status: Mapped[str] = mapped_column(
        String(50), default="PENDING", nullable=False
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
    user: Mapped["User"] = relationship(
        "User", back_populates="rider_profile"
    )

    __table_args__ = (
        CheckConstraint("safety_rating >= 1.00 AND safety_rating <= 5.00", name="ck_rider_profiles_safety_rating_range"),
    )
