import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.core.base import Base

class IncidentEvidence(Base):
    __tablename__ = "incident_evidence"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    claim_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claims.id", ondelete="SET NULL"), nullable=True, index=True
    )
    file_url: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    file_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    file_hash: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    incident: Mapped["Incident"] = relationship("Incident")
    claim: Mapped[Optional["Claim"]] = relationship("Claim", back_populates="evidence")
