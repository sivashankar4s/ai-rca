"""SQLAlchemy ORM models for the AI-RCA CRM persistence layer.

Project and FailureRecord tables are defined here. Signature/case tables are
added in WU3-US3.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Project(Base):
    """A monitored application/tenant — owns its data-source and log-backend config."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    data_source_cfg: Mapped[dict] = mapped_column(JSONB, nullable=False)
    log_backend_cfg: Mapped[dict] = mapped_column(JSONB, nullable=False)
    llm_cfg: Mapped[dict | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AppConfig(Base):
    """Single-row global configuration store for integration credentials."""

    __tablename__ = "app_config"
    __table_args__ = (CheckConstraint("id = 1", name="ck_app_config_single_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    aws_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    github_mcp_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    cloudwatch_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class FailureRecord(Base):
    """A single failed production event (spec Key Entity: Failure Record)."""

    __tablename__ = "failure_records"
    __table_args__ = (
        UniqueConstraint("project_id", "file_trace_id", name="uq_failure_project_trace"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    application_name: Mapped[str | None] = mapped_column(String, nullable=True)
    component_name: Mapped[str | None] = mapped_column(String, nullable=True)
    organization: Mapped[str | None] = mapped_column(String, nullable=True)
    file_trace_id: Mapped[str | None] = mapped_column(String, nullable=True)
    file_name: Mapped[str | None] = mapped_column(String, nullable=True)
    device_id: Mapped[str | None] = mapped_column(String, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    stage: Mapped[str | None] = mapped_column(String, nullable=True)
    message: Mapped[str | None] = mapped_column(String, nullable=True)
    event_created_ts: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    event_inserted_ts: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    signature_hash: Mapped[str | None] = mapped_column(String, nullable=True)
