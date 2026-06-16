"""Repository tests for failure_repo — run against a real test DB (Constitution IV).

Tests cover:
- Upsert creates new records correctly (FR-012)
- Dedup: calling upsert twice with same (project_id, file_trace_id) does NOT
  create duplicates (FR-012, SC-005)
- Returns ORM objects with correct fields
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import FailureRecord as FailureRecordORM
from backend.models.schemas import FailureRecord as FailureRecordSchema
from backend.repositories.failure_repo import upsert_failure_records
from backend.repositories.project_repo import get_or_create_default_project


def _make_schema(
    file_trace_id: str | None = "trace-abc",
    application_name: str = "app1",
    component_name: str = "comp1",
    organization: str = "org1",
    error_code: str = "E001",
    stage: str = "PROCESS",
) -> FailureRecordSchema:
    return FailureRecordSchema(
        file_trace_id=file_trace_id,
        application_name=application_name,
        component_name=component_name,
        organization=organization,
        file_name="file.csv",
        device_id="dev-1",
        error_code=error_code,
        stage=stage,
        status="FAILED",
        event_created_ts=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        event_inserted_ts=datetime(2026, 1, 1, 12, 5, 0, tzinfo=UTC),
        raw_payload={"key": "value"},
        signature_hash="abc123",
    )


class TestUpsertFailureRecords:
    def test_upsert_creates_new_records(self, db_session: Session) -> None:
        """Upserting a list of schemas inserts new rows and returns ORM objects."""
        project = get_or_create_default_project(db_session)
        schemas = [_make_schema("trace-001"), _make_schema("trace-002")]

        result = upsert_failure_records(db_session, project.id, schemas)

        assert len(result) == 2
        ids = {r.id for r in result}
        assert len(ids) == 2  # two distinct UUIDs
        for orm_obj in result:
            assert isinstance(orm_obj, FailureRecordORM)
            assert orm_obj.project_id == project.id

    def test_upsert_returns_correct_fields(self, db_session: Session) -> None:
        """Returned ORM objects carry all fields from the schema."""
        project = get_or_create_default_project(db_session)
        schema = _make_schema("trace-fields")

        result = upsert_failure_records(db_session, project.id, [schema])

        assert len(result) == 1
        orm_obj = result[0]
        assert orm_obj.file_trace_id == "trace-fields"
        assert orm_obj.application_name == "app1"
        assert orm_obj.component_name == "comp1"
        assert orm_obj.organization == "org1"
        assert orm_obj.file_name == "file.csv"
        assert orm_obj.device_id == "dev-1"
        assert orm_obj.error_code == "E001"
        assert orm_obj.stage == "PROCESS"
        assert orm_obj.raw_payload == {"key": "value"}
        assert orm_obj.signature_hash == "abc123"

    def test_upsert_dedup_no_duplicate_rows(self, db_session: Session) -> None:
        """Upserting the same (project_id, file_trace_id) twice must NOT create a duplicate row."""
        project = get_or_create_default_project(db_session)
        schema = _make_schema("trace-dedup")

        upsert_failure_records(db_session, project.id, [schema])
        # Count rows before second upsert
        count_after_first = db_session.execute(
            select(FailureRecordORM).where(
                FailureRecordORM.project_id == project.id,
                FailureRecordORM.file_trace_id == "trace-dedup",
            )
        ).scalars().all()
        assert len(count_after_first) == 1

        # Upsert again with updated data — must update, not insert
        schema_updated = _make_schema("trace-dedup", error_code="E002")
        upsert_failure_records(db_session, project.id, [schema_updated])

        count_after_second = db_session.execute(
            select(FailureRecordORM).where(
                FailureRecordORM.project_id == project.id,
                FailureRecordORM.file_trace_id == "trace-dedup",
            )
        ).scalars().all()
        assert len(count_after_second) == 1  # still one row — no duplicate

    def test_upsert_updates_existing_record_on_conflict(self, db_session: Session) -> None:
        """On conflict, the existing row is updated with the new values."""
        project = get_or_create_default_project(db_session)
        schema_v1 = _make_schema("trace-update", error_code="E001")
        schema_v2 = _make_schema("trace-update", error_code="E999")

        upsert_failure_records(db_session, project.id, [schema_v1])
        result = upsert_failure_records(db_session, project.id, [schema_v2])

        assert len(result) == 1
        assert result[0].error_code == "E999"

    def test_upsert_empty_list_returns_empty(self, db_session: Session) -> None:
        """Passing an empty list returns an empty list without error."""
        project = get_or_create_default_project(db_session)
        result = upsert_failure_records(db_session, project.id, [])
        assert result == []

    def test_upsert_none_file_trace_id_each_insert_is_independent(
        self, db_session: Session
    ) -> None:
        """Records with file_trace_id=None are treated as distinct inserts (no upsert key)."""
        project = get_or_create_default_project(db_session)
        schema = _make_schema(file_trace_id=None)

        # Two separate calls with file_trace_id=None should each create a new row
        # because the unique constraint is on (project_id, file_trace_id) — NULL != NULL in SQL
        result1 = upsert_failure_records(db_session, project.id, [schema])
        result2 = upsert_failure_records(db_session, project.id, [schema])

        assert len(result1) == 1
        assert len(result2) == 1
        # Both rows must have distinct UUIDs
        assert result1[0].id != result2[0].id
