"""add failure_records table

Revision ID: 002_add_failure_records
Revises: 001_initial_projects
Create Date: 2026-06-16

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002_add_failure_records"
down_revision: str | tuple[str, ...] | None = "001_initial_projects"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "failure_records",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("application_name", sa.String(), nullable=True),
        sa.Column("component_name", sa.String(), nullable=True),
        sa.Column("organization", sa.String(), nullable=True),
        sa.Column("file_trace_id", sa.String(), nullable=True),
        sa.Column("file_name", sa.String(), nullable=True),
        sa.Column("device_id", sa.String(), nullable=True),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("stage", sa.String(), nullable=True),
        sa.Column("event_created_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("event_inserted_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "raw_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("signature_hash", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "file_trace_id", name="uq_failure_project_trace"),
    )


def downgrade() -> None:
    op.drop_table("failure_records")
