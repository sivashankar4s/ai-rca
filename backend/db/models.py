"""SQLAlchemy ORM models for the AI-RCA CRM persistence layer.

Schema reference: CRM_PLAN.md section 4.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class CaseStatus(str, enum.Enum):
    NEW = "new"
    TRIAGED = "triaged"
    ANALYZING = "analyzing"
    ANALYZED = "analyzed"
    ASSIGNED = "assigned"
    RESOLVED = "resolved"
    RECURRING = "recurring"


class Project(Base):
    """A monitored application/tenant — owns its data source & log backend config."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    data_source_cfg: Mapped[dict] = mapped_column(JSONB, nullable=False)
    log_backend_cfg: Mapped[dict] = mapped_column(JSONB, nullable=False)
    llm_cfg: Mapped[dict | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )


class FailureRecord(Base):
    """A single FAILED event, normalized from any data source (Athena, Postgres, ...)."""

    __tablename__ = "failure_records"

    id: Mapped[uuid.UUID] = _uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    application_name: Mapped[str | None] = mapped_column(String)
    component_name: Mapped[str | None] = mapped_column(String)
    organization: Mapped[str | None] = mapped_column(String)
    file_trace_id: Mapped[str | None] = mapped_column(String)  # custom_key1
    file_name: Mapped[str | None] = mapped_column(String)  # custom_key2
    device_id: Mapped[str | None] = mapped_column(String)  # custom_key3
    error_code: Mapped[str | None] = mapped_column(String)
    stage: Mapped[str | None] = mapped_column(String)
    event_created_ts: Mapped[datetime | None]
    event_inserted_ts: Mapped[datetime | None]
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    signature_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)


class RcaCase(Base):
    """A group of related failures with a CRM-style lifecycle."""

    __tablename__ = "rca_cases"

    id: Mapped[uuid.UUID] = _uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    status: Mapped[CaseStatus] = mapped_column(
        SAEnum(CaseStatus, name="case_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=CaseStatus.NEW,
    )
    assignee: Mapped[str | None] = mapped_column(String)
    component_name: Mapped[str | None] = mapped_column(String)
    error_pattern: Mapped[str | None] = mapped_column(Text)
    root_cause: Mapped[str | None] = mapped_column(Text)
    failure_category: Mapped[str | None] = mapped_column(String)
    immediate_action: Mapped[str | None] = mapped_column(Text)
    likely_fix: Mapped[str | None] = mapped_column(Text)
    affected_files: Mapped[list | None] = mapped_column(JSONB)
    escalation_path: Mapped[str | None] = mapped_column(Text)
    impact_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cw_log_url: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )

    activities: Mapped[list["CaseActivity"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )


class CaseFailureRecord(Base):
    """Many-to-many link between rca_cases and failure_records."""

    __tablename__ = "case_failure_records"

    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rca_cases.id"), primary_key=True
    )
    failure_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("failure_records.id"), primary_key=True
    )


class CaseActivity(Base):
    """Timeline entry for a case — status changes, comments, analysis runs, signature matches."""

    __tablename__ = "case_activity"

    id: Mapped[uuid.UUID] = _uuid_pk()
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rca_cases.id"), nullable=False
    )
    activity_type: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB)
    created_by: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    case: Mapped["RcaCase"] = relationship(back_populates="activities")


class RootCauseSignature(Base):
    """Knowledge-base entry — a recognized failure pattern and its known root cause/fix."""

    __tablename__ = "root_cause_signatures"
    __table_args__ = (
        UniqueConstraint("project_id", "signature_hash", name="uq_signature_project_hash"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id")
    )  # NULL = global/cross-project pattern
    signature_hash: Mapped[str] = mapped_column(String, nullable=False)
    component_name: Mapped[str | None] = mapped_column(String)
    error_code: Mapped[str | None] = mapped_column(String)
    stage: Mapped[str | None] = mapped_column(String)
    root_cause: Mapped[str] = mapped_column(Text, nullable=False)
    fix_notes: Mapped[str | None] = mapped_column(Text)
    failure_category: Mapped[str | None] = mapped_column(String)
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_seen: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )


class CaseSignatureLink(Base):
    """Records which cases matched which knowledge-base signatures."""

    __tablename__ = "case_signature_links"

    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rca_cases.id"), primary_key=True
    )
    signature_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("root_cause_signatures.id"), primary_key=True
    )
    matched_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
