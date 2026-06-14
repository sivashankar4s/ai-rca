from datetime import UTC, datetime, timedelta



from backend.db.session import SessionLocal
from backend.providers.data_source.postgres import PostgresDataSource
from backend.repositories import failure_repo, project_repo
from backend.tests.conftest import make_failure_record


def test_fetch_records_returns_recently_persisted_records():
    now = datetime.now(UTC).replace(tzinfo=None)
    record = make_failure_record(
        custom_key1="pg-source-trace-1",
        event_inserted_timestamp=now.isoformat(),
    )

    db = SessionLocal()
    try:
        project = project_repo.get_or_create_default_project(db)
        failure_repo.create_failure_record(db, project.id, record)
        db.commit()

        try:
            results = PostgresDataSource().fetch_records(
                time_range="1h",
                start_date=(now - timedelta(hours=1)).isoformat(),
                end_date=(now + timedelta(hours=1)).isoformat(),
            )

            trace_ids = {r.get("custom_key1") for r in results}
            assert "pg-source-trace-1" in trace_ids
        finally:
            db.query(failure_repo.FailureRecordModel).filter(
                failure_repo.FailureRecordModel.file_trace_id == "pg-source-trace-1"
            ).delete()
            db.commit()
    finally:
        db.close()
