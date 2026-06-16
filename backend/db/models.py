"""SQLAlchemy ORM models for the AI-RCA CRM persistence layer.

Only the Project table is defined in this WU (T008). FailureRecord and the
signature/case tables are added in WU6 and WU3-US3 respectively.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, String, Text, func
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
