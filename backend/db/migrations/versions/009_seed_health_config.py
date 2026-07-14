"""seed health_config data in app_config

Revision ID: 009_seed_health_config
Revises: 008_add_health_profiles
Create Date: 2026-07-13

Upserts the health_config JSON value into the single-row app_config table (id=1).
If the row does not exist yet it is created; if it already exists only health_config
is updated so other columns are left untouched.
"""

import json

from alembic import op
import sqlalchemy as sa

revision: str = "009_seed_health_config"
down_revision: str | tuple[str, ...] | None = "008_add_health_profiles"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None

HEALTH_CONFIG = [
    {
        "name": "prod-db10824",
        "glue_jobs": [
            "dpct-prod-euc1-Astack-dp-json-to-parquet-db10824",
            "dpct-prod-euc1-Astack-dp-das-integration-db10824",
            "dpct-prod-euc1-Astack-dp-s3-azure-db10824-rchdbmamericaslive-logs-validated",
            "dpct-prod-euc1-Astack-dp-s3-azure-db10824-rchdbmeuropelive-data-validated",
            "dpct-prod-euc1-Astack-dp-s3-azure-db10824-rchdbmamericaslive-data-validated",
            "dpct-prod-euc1-Astack-dp-s3-azure-db10824-rchdbmcanadalive-data-validated",
            "dpct-prod-euc1-Astack-dp-s3-azure-db10824-rchdbmeuropelive-logs-validated",
            "dpct-prod-euc1-Astack-dp-s3-azure-db10824-rchdbmcanadalive-logs-validated",
        ],
        "datasync_tasks": [
            {
                "id": "arn:aws:datasync:eu-central-1:855246887708:task/task-04316f7d11c18da24",
                "label": "dpct-prod-euc1-Astack-datasync-task-db10824-rchdbmcanadalive-data-validated",
            },
            {
                "id": "arn:aws:datasync:eu-central-1:855246887708:task/task-081b2f1c045c5db2d",
                "label": "dpct-prod-euc1-Astack-datasync-task-db10824-rchdbmamericaslive-logs-validated",
            },
            {
                "id": "arn:aws:datasync:eu-central-1:855246887708:task/task-0e3dbb4d96c82c06d",
                "label": "dpct-prod-euc1-Astack-datasync-task-db10824-rchdbmeuropelive-logs-validated",
            },
            {
                "id": "arn:aws:datasync:eu-central-1:855246887708:task/task-027ba6aa66ddf4158",
                "label": "dpct-prod-euc1-Astack-datasync-task-db10824-rchdbmeuropelive-data-validated",
            },
            {
                "id": "arn:aws:datasync:eu-central-1:855246887708:task/task-0946d4530e318e59a",
                "label": "dpct-prod-euc1-Astack-datasync-task-db10824-rchdbmamericaslive-data-validated",
            },
            {
                "id": "arn:aws:datasync:eu-central-1:855246887708:task/task-0c94eb74356731335",
                "label": "dpct-prod-euc1-Astack-datasync-task-db10824-rchdbmcanadalive-logs-validated",
            },
        ],
        "glue_workflows": [
            "dpct-prod-euc1-Astack-dp-das-integrator-workflow-db10824",
        ],
        "lambda_functions": [
            "dpct-prod-euc1-Astack-dp-lz-s3-event-processor-lambda-db10824",
            "dpct-prod-euc1-Astack-dp-decryptor-db10824",
            "dpct-prod-euc1-Astack-dp-dl-s3-event-processor-db10824",
            "dpct-prod-euc1-Astack-dp-sqlite-to-parquet-db10824",
            "dpct-prod-euc1-Astack-dp-sqlite-to-parquet-db10824-rep",
            "dpct-prod-euc1-Astack-dp-voice-transformation-db10824",
            "onedbm-dpct-prod-euc1-harmonization-task-1-db10824",
            "onedbm-dpct-prod-euc1-harmonization-task-1-db10824-rep",
            "onedbm-dpct-prod-euc1-harmonization-task-2-db10824",
            "onedbm-dpct-prod-euc1-harmonization-task-2-db10824-rep",
            "onedbm-dpct-prod-euc1-harmonization-task-3-db10824",
            "onedbm-dpct-prod-euc1-harmonization-task-3-db10824-rep",
            "onedbm-dpct-prod-euc1-feature-calculation-prism-db10824",
            "onedbm-dpct-prod-euc1-feature-calculation-prism-db10824-rep",
            "onedbm-dpct-prod-euc1-inventory-db10824",
            "onedbm-dpct-prod-euc1-inventory-db10824-rep",
            "onedbm-dpct-prod-euc1-readiness-checker-db10824",
            "onedbm-dpct-prod-euc1-readiness-checker-db10824-rep",
            "onedbm-dpct-prod-euc1-astack-data-access-db10824",
            "dpct-prod-euc1-Astack-dp-monitor-db10824",
            "dpct-prod-euc1-Astack-dp-monitor-db10824-rep",
            "dpct-prod-euc1-Astack-dp-audit-db10824",
            "dpct-prod-euc1-Astack-dp-audit-db10824-rep",
        ],
    },
    {
        "name": "prod-investhd",
        "glue_jobs": [
            "dpct-prod-euc1-Astack-dp-json-to-parquet-investhd",
            "dpct-prod-euc1-Astack-dp-das-integration-investhd",
        ],
        "datasync_tasks": [],
        "glue_workflows": [
            "dpct-prod-euc1-Astack-dp-das-integrator-workflow-investhd",
        ],
        "lambda_functions": [
            "dpct-prod-euc1-Astack-dp-lz-s3-event-processor-lambda-investhd",
            "dpct-prod-euc1-Astack-dp-dl-s3-event-processor-investhd",
            "dpct-prod-euc1-Astack-dp-decryptor-investhd",
            "onedbm-dpct-prod-euc1-harmonization-task-1-investhd",
            "onedbm-dpct-prod-euc1-harmonization-task-1-investhd-rep",
            "onedbm-dpct-prod-euc1-harmonization-task-2-investhd",
            "onedbm-dpct-prod-euc1-harmonization-task-2-investhd-rep",
            "onedbm-dpct-prod-euc1-feature-calculation-prism-investhd",
            "onedbm-dpct-prod-euc1-feature-calculation-prism-investhd-rep",
            "onedbm-dpct-prod-euc1-astack-data-access-investhd",
            "dpct-prod-euc1-Astack-dp-sqlite-to-parquet-investhd",
            "dpct-prod-euc1-Astack-dp-sqlite-to-parquet-investhd-rep",
            "dpct-prod-euc1-Astack-dp-voice-transformation-investhd",
            "onedbm-dpct-prod-euc1-inventory-investhd",
            "onedbm-dpct-prod-euc1-inventory-investhd-rep",
            "onedbm-dpct-prod-euc1-readiness-checker-investhd",
            "onedbm-dpct-prod-euc1-readiness-checker-investhd-rep",
            "dpct-prod-euc1-Astack-dp-audit-investhd-rep",
            "dpct-prod-euc1-Astack-dp-audit-investhd",
            "dpct-prod-euc1-Astack-dp-monitor-investhd",
            "dpct-prod-euc1-Astack-dp-monitor-investhd-rep",
        ],
    },
    {
        "name": "prod-HTT02001",
        "glue_jobs": [
            "dpct-prod-euc1-Astack-dp-json-to-parquet-htt02001",
            "dpct-prod-euc1-Astack-dp-das-integration-htt02001",
        ],
        "datasync_tasks": [],
        "glue_workflows": [
            "dpct-prod-euc1-Astack-dp-das-integrator-workflow-htt02001",
        ],
        "lambda_functions": [
            "dpct-prod-euc1-Astack-dp-lz-s3-event-processor-lambda-htt02001",
            "dpct-prod-euc1-Astack-dp-dl-s3-event-processor-htt02001",
            "dpct-prod-euc1-Astack-dp-decryptor-htt02001",
            "dpct-prod-euc1-Astack-dp-sqlite-to-parquet-htt02001",
            "dpct-prod-euc1-Astack-dp-sqlite-to-parquet-htt02001-rep",
            "dpct-prod-euc1-Astack-dp-voice-transformation-htt02001",
            "onedbm-dpct-prod-euc1-harmonization-task-1-htt02001",
            "onedbm-dpct-prod-euc1-harmonization-task-1-htt02001-rep",
            "onedbm-dpct-prod-euc1-harmonization-task-2-htt02001",
            "onedbm-dpct-prod-euc1-harmonization-task-2-htt02001-rep",
            "onedbm-dpct-prod-euc1-inventory-htt02001",
            "onedbm-dpct-prod-euc1-inventory-htt02001-rep",
            "onedbm-dpct-prod-euc1-feature-calculation-prism-htt02001",
            "onedbm-dpct-prod-euc1-feature-calculation-prism-htt02001-rep",
            "onedbm-dpct-prod-euc1-readiness-checker-htt02001",
            "onedbm-dpct-prod-euc1-readiness-checker-htt02001-rep",
            "onedbm-dpct-prod-euc1-astack-data-access-htt02001",
            "dpct-prod-euc1-Astack-dp-audit-htt02001",
            "dpct-prod-euc1-Astack-dp-audit-htt02001-rep",
            "dpct-prod-euc1-Astack-dp-monitor-htt02001",
            "dpct-prod-euc1-Astack-dp-monitor-htt02001-rep",
        ],
    },
    {
        "name": "prod-VO659CT01",
        "glue_jobs": [
            "dpct-prod-euc1-Astack-dp-json-to-parquet-vo659ct01",
            "dpct-prod-euc1-Astack-dp-das-integration-vo659ct01",
            "dpct-prod-euc1-Astack-dp-s3-azure-vo659ct01-rchdbmamericaslive-data-validated",
            "dpct-prod-euc1-Astack-dp-s3-azure-vo659ct01-rchdbmeuropelive-data-validated",
            "dpct-prod-euc1-Astack-dp-s3-azure-vo659ct01-rchdbmamericaslive-logs-validated",
            "dpct-prod-euc1-Astack-dp-s3-azure-vo659ct01-rchdbmeuropelive-logs-validated",
            "dpct-prod-euc1-Astack-dp-s3-azure-vo659ct01-rchdbmcanadalive-data-validated",
            "dpct-prod-euc1-Astack-dp-s3-azure-vo659ct01-rchdbmcanadalive-logs-validated",
        ],
        "datasync_tasks": [
            {
                "id": "arn:aws:datasync:eu-central-1:855246887708:task/task-0cab9a5b633d48d55",
                "label": "dpct-prod-euc1-Astack-datasync-task-vo659ct01-rchdbmcanadalive-data-validated",
            },
            {
                "id": "arn:aws:datasync:eu-central-1:855246887708:task/task-0321da4bce37a3a62",
                "label": "dpct-prod-euc1-Astack-datasync-task-vo659ct01-rchdbmamericaslive-logs-validated",
            },
            {
                "id": "arn:aws:datasync:eu-central-1:855246887708:task/task-0322de5180bde27f5",
                "label": "dpct-prod-euc1-Astack-datasync-task-vo659ct01-rchdbmeuropelive-logs-validated",
            },
            {
                "id": "arn:aws:datasync:eu-central-1:855246887708:task/task-032328f72c21ae809",
                "label": "dpct-prod-euc1-Astack-datasync-task-vo659ct01-rchdbmeuropelive-data-validated",
            },
            {
                "id": "arn:aws:datasync:eu-central-1:855246887708:task/task-010c89e2181b2cd01",
                "label": "dpct-prod-euc1-Astack-datasync-task-vo659ct01-rchdbmamericaslive-data-validated",
            },
            {
                "id": "arn:aws:datasync:eu-central-1:855246887708:task/task-0e5886a88a7f991e9",
                "label": "dpct-prod-euc1-Astack-datasync-task-vo659ct01-rchdbmcanadalive-logs-validated",
            },
        ],
        "glue_workflows": [
            "dpct-prod-euc1-Astack-dp-das-integrator-workflow-vo659ct01",
        ],
        "lambda_functions": [
            "dpct-prod-euc1-Astack-dp-lz-s3-event-processor-lambda-vo659ct01",
            "dpct-prod-euc1-Astack-dp-dl-s3-event-processor-vo659ct01",
            "dpct-prod-euc1-Astack-dp-decryptor-vo659ct01",
            "dpct-prod-euc1-Astack-dp-sqlite-to-parquet-vo659ct01",
            "dpct-prod-euc1-Astack-dp-sqlite-to-parquet-vo659ct01-rep",
            "dpct-prod-euc1-Astack-dp-voice-transformation-vo659ct01",
            "onedbm-dpct-prod-euc1-harmonization-task-1-vo659ct01",
            "onedbm-dpct-prod-euc1-harmonization-task-1-vo659ct01-rep",
            "onedbm-dpct-prod-euc1-harmonization-task-2-vo659ct01",
            "onedbm-dpct-prod-euc1-harmonization-task-2-vo659ct01-rep",
            "onedbm-dpct-prod-euc1-inventory-vo659ct01",
            "onedbm-dpct-prod-euc1-inventory-vo659ct01-rep",
            "onedbm-dpct-prod-euc1-feature-calculation-prism-vo659ct01",
            "onedbm-dpct-prod-euc1-feature-calculation-prism-vo659ct01-rep",
            "onedbm-dpct-prod-euc1-readiness-checker-vo659ct01",
            "onedbm-dpct-prod-euc1-readiness-checker-vo659ct01-rep",
            "onedbm-dpct-prod-euc1-astack-data-access-vo659ct01",
            "dpct-prod-euc1-Astack-dp-audit-vo659ct01",
            "dpct-prod-euc1-Astack-dp-audit-vo659ct01-rep",
            "dpct-prod-euc1-Astack-dp-monitor-vo659ct01",
            "dpct-prod-euc1-Astack-dp-monitor-vo659ct01-rep",
        ],
    },
    {
        "name": "sandbox-dbt",
        "glue_jobs": [
            "onedbm-dsdev-usw2-db10824-dbt-schema-build-run",
            "onedbm-dsdev-usw2-db11225-dbt-schema-build-run",
            "onedbm-dsdev-usw2-htt02001-dbt-schema-build-run",
            "onedbm-dsdev-usw2-investhd-dbt-schema-build-run",
            "onedbm-dsdev-usw2-vo659ct01-dbt-schema-build-run",
        ],
        "datasync_tasks": [],
        "glue_workflows": [
            "dsdev-usw2-Astack-dp-das-integrator-workflow-db11223",
        ],
        "lambda_functions": [
            "dsdev-usw2-Astack-dp-extraction-manager-db11223",
            "onedbm-dsdev-usw2-feature-calculation-db11223",
            "onedbm-dsdev-usw2-harmonization-task-1-db11223",
            "onedbm-dsdev-usw2-harmonization-task-2-db11223",
            "onedbm-dsdev-usw2-harmonization-task-3-db11223",
            "onedbm-dsdev-usw2-inventory-db11223",
        ],
    },
]


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            INSERT INTO app_config (id, health_config, updated_at)
            VALUES (1, CAST(:value AS jsonb), now())
            ON CONFLICT (id) DO UPDATE
                SET health_config = EXCLUDED.health_config,
                    updated_at    = EXCLUDED.updated_at
            """
        ),
        {"value": json.dumps(HEALTH_CONFIG)},
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("UPDATE app_config SET health_config = NULL WHERE id = 1")
    )
