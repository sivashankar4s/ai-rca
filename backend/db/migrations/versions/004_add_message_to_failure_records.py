"""add message column to failure_records

Revision ID: 004_add_message
Revises: 003_add_app_config
Create Date: 2026-06-30

"""

import sqlalchemy as sa
from alembic import op

revision: str = "004_add_message"
down_revision: str | tuple[str, ...] | None = "003_add_app_config"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column("failure_records", sa.Column("message", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("failure_records", "message")
