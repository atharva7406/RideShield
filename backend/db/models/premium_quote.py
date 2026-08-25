import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.core.base import Base


class PremiumQuoteRecord(Base):
    """
    Phase 7 audit trail: the ACTUAL PremiumQuote
    (app/services/premium_pricing_service.py) that produced a given
    shift's premium — persisted at the moment the premium is computed
    (POST /shifts/start or POST /payments/create-order), one row per
    shift. Exists to answer "why was this rider charged Rs.X for this
    shift?" without recomputing anything — the computed_at snapshot is
    the answer, not a live re-derivation (a rider's profile keeps
    changing after this row is written).

    Deliberately NOT the live pricing engine's source of truth — that's
    always premium_pricing_service.calculate_premium_quote(), computed
    fresh at shift-start time. This table is read-only history.

    ISOLATION: no relationship to ml_incident_engine or
    behaviour_risk_engine; scoring_method/model_version are plain strings
    copied from whatever RiderBehaviourRiskResult produced them, same
    "the DB doesn't know about ML internals" boundary every other model
    in this codebase keeps.
    """
    __tablename__ = "premium_quotes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # One quote per shift — RESTRICT matches the FK convention used by
    # every other rider_id/shift_id link in this codebase (see shift.py,
    # shift_behaviour_summary.py).
    shift_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shifts.id", ondelete="RESTRICT"),
        unique=True, nullable=False, index=True,
    )
    rider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    is_cold_start: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    risk_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=True)
    risk_band: Mapped[str] = mapped_column(String(20), nullable=True)
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=0.0)
    scoring_method: Mapped[str] = mapped_column(String(50), nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)

    pricing_mode: Mapped[str] = mapped_column(String(30), nullable=False)
    base_premium: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    previous_premium: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    adjustment_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    final_premium: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    rate_of_change_capped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    explanation: Mapped[str] = mapped_column(Text, nullable=False)

    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )

    # Relationships
    shift: Mapped["Shift"] = relationship("Shift")
    rider: Mapped["User"] = relationship("User")

    __table_args__ = (
        CheckConstraint("final_premium >= 0", name="ck_premium_quotes_final_premium_non_negative"),
        CheckConstraint("base_premium >= 0", name="ck_premium_quotes_base_premium_non_negative"),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_premium_quotes_confidence_range",
        ),
        CheckConstraint(
            "risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 100)",
            name="ck_premium_quotes_risk_score_range",
        ),
    )
