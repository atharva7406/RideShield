import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.core.base import Base


class HelmetVerification(Base):
    """
    A single helmet-selfie check (POST /helmet/verify) and its result.
    Server-authoritative gate for shift start — same principle as
    PremiumQuoteRecord: the client can claim whatever it wants, only a
    row here (created by the server's own ML inference) can satisfy the
    gate in POST /shifts/start / POST /payments/create-order.

    LIFECYCLE: created with shift_id=NULL, consumed_at=NULL at verify
    time. When a shift actually starts using this verification, the
    shift-start endpoint stamps consumed_at + shift_id — preventing the
    same passed verification from being replayed to start a second shift
    later (each shift needs its own fresh selfie check). A verification
    also expires after HELMET_VERIFICATION_VALIDITY_MINUTES
    (helmet_verification_service.py) regardless of consumed_at.

    Does NOT store the uploaded image itself — only the model's verdict.
    Keeping raw selfies out of the DB is a deliberate privacy choice; the
    verdict + confidence + model_version is enough to answer "why was
    this rider allowed/blocked from starting a shift."
    """
    __tablename__ = "helmet_verifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    rider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    # Set only once this verification is actually consumed to start a
    # shift (see lifecycle note above) — NULL until then.
    shift_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shifts.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    predicted_class: Mapped[str] = mapped_column(String(30), nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    helmet_worn: Mapped[bool] = mapped_column(Boolean, nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)

    consumed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True,
    )

    rider: Mapped["User"] = relationship("User")
    shift: Mapped[Optional["Shift"]] = relationship("Shift")

    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_helmet_verifications_confidence_range"),
    )
