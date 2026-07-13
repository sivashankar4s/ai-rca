"""add athena_config column to app_config

Revision ID: 006_add_athena_config
Revises: 005_add_cw_config
Create Date: 2026-07-01

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006_add_athena_config"
down_revision: str | tuple[str, ...] | None = "005_add_cw_config"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "app_config",
        sa.Column("athena_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("app_config", "athena_config")
