import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.core.base import Base
from db.models.enums import UserRole

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    phone_number: Mapped[str] = mapped_column(
        String(30), unique=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    full_name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole, name="user_role_enum"),
        default=UserRole.RIDER,
        nullable=False,
    )
    wallet_balance: Mapped[float] = mapped_column(
        default=500.0,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
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
    rider_profile: Mapped["RiderProfile"] = relationship(
        "RiderProfile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    shifts: Mapped[list["Shift"]] = relationship(
        "Shift", back_populates="rider", cascade="all, delete-orphan"
    )
