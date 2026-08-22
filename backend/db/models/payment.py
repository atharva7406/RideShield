import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Numeric, DateTime, ForeignKey, Enum as SQLEnum, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.core.base import Base
from db.models.enums import PaymentStatus, PaymentType

class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    shift_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shifts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    claim_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claims.id", ondelete="SET NULL"), nullable=True, index=True
    )
    rider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    payment_type: Mapped[PaymentType] = mapped_column(
        SQLEnum(PaymentType, name="payment_type_enum"),
        nullable=False,
    )
    amount: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False
    )
    currency: Mapped[str] = mapped_column(
        String(3), default="INR", nullable=False
    )
    status: Mapped[PaymentStatus] = mapped_column(
        SQLEnum(PaymentStatus, name="payment_status_enum"),
        default=PaymentStatus.PENDING,
        nullable=False,
        index=True,
    )
    transaction_ref: Mapped[Optional[str]] = mapped_column(
        String(100), unique=True, nullable=True
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    shift: Mapped[Optional["Shift"]] = relationship("Shift", back_populates="payments")
    claim: Mapped[Optional["Claim"]] = relationship("Claim", back_populates="payments")
    rider: Mapped["User"] = relationship("User")

    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_payments_amount_non_negative"),
        CheckConstraint(
            "(payment_type = 'PREMIUM_COLLECTION' AND shift_id IS NOT NULL) OR (payment_type = 'CLAIM_PAYOUT' AND claim_id IS NOT NULL)",
            name="ck_payments_type_linkage",
        ),
    )
