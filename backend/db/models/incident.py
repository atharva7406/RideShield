import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Numeric, Float, DateTime, ForeignKey, Enum as SQLEnum, CheckConstraint, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.core.base import Base
from db.models.enums import IncidentStatus

class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    shift_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shifts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    rider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    batch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("telemetry_batches.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[IncidentStatus] = mapped_column(
        SQLEnum(IncidentStatus, name="incident_status_enum"),
        default=IncidentStatus.DETECTED,
        nullable=False,
        index=True,
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    peak_g_force: Mapped[float] = mapped_column(
        Numeric(5, 2), nullable=False
    )
    confidence_score: Mapped[float] = mapped_column(
        Numeric(3, 2), nullable=False
    )
    latitude: Mapped[float] = mapped_column(
        Float, nullable=False
    )
    longitude: Mapped[float] = mapped_column(
        Float, nullable=False
    )
    locality: Mapped[str] = mapped_column(
        String(100), server_default="Unknown", nullable=False, index=True
    )
    # Phase 1 (offline incident queue) — minted on-device at Tier-0 detection
    # time, carried through local storage/retry/sync unchanged.
    # Phase 2 (exactly-once sync): unique at the DB level — this is the real
    # protection against two concurrent retries creating two Incident rows;
    # the app-level lookup-before-insert in incidents.py is only a fast
    # path, not the guarantee. Nullable (Postgres unique indexes treat NULLs
    # as distinct) so old submissions / the plain POST /incidents path
    # (which never sends an ID) are unaffected.
    client_incident_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, unique=True, index=True
    )

    # Phase 4 (Incident Decision Engine) — server-computed, independent of
    # any client-supplied window_metadata. "good" | "degraded" |
    # "insufficient"; see app/services/window_quality_service.py.
    window_quality: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # "high" | "medium" | "low" — how strongly the fused evidence (ML
    # score, window quality, Tier-0-style post-impact/GPS signals)
    # corroborates a real crash. Annotation only: NEVER used to skip or
    # downgrade escalation — see incident_decision_engine.py's module
    # docstring for the safety-floor rule this exists under.
    decision_confidence: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # Comma-separated human-readable evidence tags (e.g.
    # "high_ml_confidence,post_impact_stillness,gps_speed_drop") — surfaced
    # to claims/insurer review and spoken in the L3 emergency-call message,
    # not machine-parsed anywhere.
    decision_evidence: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
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
    shift: Mapped["Shift"] = relationship("Shift", back_populates="incidents")
    rider: Mapped["User"] = relationship("User")
    batch: Mapped[Optional["TelemetryBatch"]] = relationship("TelemetryBatch", back_populates="incidents")
    claims: Mapped[list["Claim"]] = relationship("Claim", back_populates="incident")

    __table_args__ = (
        CheckConstraint("peak_g_force >= 0", name="ck_incidents_peak_g_force_non_negative"),
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 1", name="ck_incidents_confidence_score_range"),
    )
