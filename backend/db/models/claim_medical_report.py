import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.core.base import Base

class ClaimMedicalReport(Base):
    __tablename__ = "claim_medical_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True
    )
    hospital_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    file_reference: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    document_type: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    claim: Mapped["Claim"] = relationship("Claim", back_populates="medical_reports")
    hospital: Mapped["Hospital"] = relationship("Hospital")
    uploader: Mapped["User"] = relationship("User")
