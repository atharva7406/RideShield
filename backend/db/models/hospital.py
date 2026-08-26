import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, DateTime, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from db.core.base import Base

class Hospital(Base):
    __tablename__ = "hospitals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    locality: Mapped[str] = mapped_column(
        String(500), nullable=False, index=True
    )
    contact_number: Mapped[str] = mapped_column(
        String(30), nullable=False
    )
    latitude: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, default=19.0760
    )
    longitude: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, default=72.8777
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
