"""add health_config column to app_config

Revision ID: 007_add_health_config
Revises: 006_add_athena_config
Create Date: 2026-07-06

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007_add_health_config"
down_revision: str | tuple[str, ...] | None = "006_add_athena_config"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "app_config",
        sa.Column("health_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("app_config", "health_config")
