import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.core.base import Base


class HelmetVerification(Base):
    """
    A single mandatory helmet safety acknowledgment (POST
    /helmet/acknowledge) — the rider explicitly checked the "I will wear
    a helmet at all times" checkbox on the rider-app helmet-check screen.
    Server-authoritative gate for shift start — same principle as
    PremiumQuoteRecord: the client can claim whatever it wants, only a
    row here (created by the server, only once the acknowledgment request
    actually reaches it) can satisfy the gate in POST /shifts/start /
    POST /payments/create-order.

    NOT a photo/ML verdict — see helmet_verification_service.py's module
    docstring for why that approach was removed entirely. helmet_worn is
    always True for a row created via the acknowledgment endpoint; it
    exists as its own column (rather than the row's mere presence being
    the signal) so get_usable_verification's query stays a plain,
    readable filter.

    LIFECYCLE: created with shift_id=NULL, consumed_at=NULL at
    acknowledgment time. When a shift actually starts using this
    acknowledgment, the shift-start endpoint stamps consumed_at +
    shift_id — preventing the same acknowledgment from being replayed to
    start a second shift later (each shift needs its own fresh
    checkbox confirmation). An acknowledgment also expires after
    VERIFICATION_VALIDITY_MINUTES (helmet_verification_service.py)
    regardless of consumed_at.
    """
    __tablename__ = "helmet_verifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    rider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    # Set only once this acknowledgment is actually consumed to start a
    # shift (see lifecycle note above) — NULL until then.
    shift_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shifts.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    helmet_worn: Mapped[bool] = mapped_column(Boolean, nullable=False)

    consumed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True,
    )

    rider: Mapped["User"] = relationship("User")
    shift: Mapped[Optional["Shift"]] = relationship("Shift")
