"""add health_profiles column to app_config

Revision ID: 008_add_health_profiles
Revises: 007_add_health_config
Create Date: 2026-07-08

The existing single ``health_config`` is surfaced lazily as a "Default" profile by the
repository, so no data migration is needed here — this only adds the column.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "008_add_health_profiles"
down_revision: str | tuple[str, ...] | None = "007_add_health_config"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "app_config",
        sa.Column("health_profiles", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("app_config", "health_profiles")
