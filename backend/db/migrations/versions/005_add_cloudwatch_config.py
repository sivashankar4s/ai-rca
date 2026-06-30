"""add cloudwatch_config column to app_config

Revision ID: 005_add_cw_config
Revises: 004_add_message
Create Date: 2026-06-30

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005_add_cw_config"
down_revision: str | tuple[str, ...] | None = "004_add_message"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "app_config",
        sa.Column("cloudwatch_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("app_config", "cloudwatch_config")
