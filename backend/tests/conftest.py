"""Shared pytest fixtures.

Repository/persistence tests run against the real Postgres instance configured
via DATABASE_URL (JSONB/UUID columns aren't portable to SQLite). Each test runs
inside a SAVEPOINT that is rolled back afterwards, so no data is left behind.
"""
from __future__ import annotations

import pytest
from sqlalchemy.orm import sessionmaker

from backend.db.session import engine
from backend.models.schemas import EventData, FailureGroup, FailureRecord


@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")
    session = session_factory()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


def make_failure_record(**overrides) -> FailureRecord:
    defaults = dict(
        application_name="db11224",
        component_name="dp-lz-s3-event-processor",
        custom_key1="trace-1",
        custom_key2="file.raw",
        custom_key3="device-1",
        event_created_timestamp="2026-05-06T14:13:09.152000",
        event_inserted_timestamp="2026-05-06T14:14:17.519000",
        organization="db11224",
        status="FAILED",
        event_data=EventData(error_code="S3_PUT_FAILED", stage="lz-processor"),
    )
    defaults.update(overrides)
    return FailureRecord(**defaults)


def make_failure_group(**overrides) -> FailureGroup:
    defaults = dict(
        group_id="grp-1",
        component="dp-lz-s3-event-processor",
        error_pattern="S3_PUT_FAILED at lz-processor stage",
        root_cause="IAM role missing s3:PutObject permission on the landing-zone bucket.",
        failure_category="Configuration",
        impact_count=1,
        immediate_action="Check IAM role permissions",
        likely_fix="Add s3:PutObject to the Lambda execution role policy",
        affected_files=["dp-lz-s3-event-processor"],
        escalation_path="#platform-infra",
        records=[make_failure_record()],
        log_samples=["ERROR S3_PUT_FAILED"],
        cw_log_url="https://console.aws.amazon.com/cloudwatch/...",
    )
    defaults.update(overrides)
    return FailureGroup(**defaults)
