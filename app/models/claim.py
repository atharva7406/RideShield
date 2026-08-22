import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Text, Numeric, DateTime, ForeignKey, Enum as SQLEnum, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.models.enums import ClaimStatus

class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="RESTRICT"), unique=True, nullable=False, index=True
    )
    rider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    shift_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shifts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    claim_number: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )
    status: Mapped[ClaimStatus] = mapped_column(
        SQLEnum(ClaimStatus, name="claim_status_enum"),
        default=ClaimStatus.DRAFT,
        nullable=False,
        index=True,
    )
    claimed_amount: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False
    )
    approved_amount: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    filed_at: Mapped[datetime] = mapped_column(
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
    incident: Mapped["Incident"] = relationship("Incident", back_populates="claims")
    rider: Mapped["User"] = relationship("User")
    shift: Mapped["Shift"] = relationship("Shift")
    evidence: Mapped[list["IncidentEvidence"]] = relationship(
        "IncidentEvidence", back_populates="claim"
    )
    audit_events: Mapped[list["AuditEvent"]] = relationship(
        "AuditEvent", back_populates="claim"
    )
    payments: Mapped[list["Payment"]] = relationship(
        "Payment", back_populates="claim"
    )

    __table_args__ = (
        CheckConstraint("claimed_amount >= 0", name="ck_claims_claimed_amount_non_negative"),
        CheckConstraint("approved_amount IS NULL OR approved_amount >= 0", name="ck_claims_approved_amount_non_negative"),
    )
