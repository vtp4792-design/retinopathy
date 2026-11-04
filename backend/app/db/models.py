import enum
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Integer, SmallInteger, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class ModelStatus(str, enum.Enum):
    STAGING = "staging"
    ACTIVE = "active"
    RETIRED = "retired"


class InferenceOutcome(str, enum.Enum):
    GRADED = "graded"
    QUALITY_REJECTED = "quality_rejected"
    ABSTAINED = "abstained"
    INVALID_INPUT = "invalid_input"
    ERROR = "error"


class QualityStatus(str, enum.Enum):
    ACCEPTABLE = "acceptable"
    REJECTED = "rejected"
    NOT_ASSESSED = "not_assessed"


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    version: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    model_name: Mapped[str] = mapped_column(String(160), nullable=False)
    task: Mapped[str] = mapped_column(
        String(80), nullable=False, server_default=text("'dr_grading'")
    )
    label_scheme: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    preprocessing: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    quality_model: Mapped[str | None] = mapped_column(String(160))
    grading_model: Mapped[str] = mapped_column(String(160), nullable=False)
    calibration: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    abstention_rule: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    artifact_digest: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[ModelStatus] = mapped_column(
        String(20), nullable=False, server_default=text("'staging'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    inference_events: Mapped[list["InferenceEvent"]] = relationship(back_populates="model_version")


class InferenceEvent(Base):
    __tablename__ = "inference_events"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    model_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("model_versions.id"), nullable=False
    )
    request_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), unique=True, nullable=False
    )
    outcome: Mapped[InferenceOutcome] = mapped_column(String(32), nullable=False)
    predicted_grade: Mapped[int | None] = mapped_column(SmallInteger)
    confidence: Mapped[float | None] = mapped_column(Float)
    quality_status: Mapped[QualityStatus | None] = mapped_column(String(24))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    model_version: Mapped[ModelVersion] = relationship(back_populates="inference_events")
