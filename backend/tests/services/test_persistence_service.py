from datetime import datetime, timezone

from sqlalchemy import select

from backend.db.models import (
    CaseActivity,
    CaseFailureRecord,
    CaseSignatureLink,
    FailureRecord as FailureRecordModel,
    RcaCase,
    RootCauseSignature,
)
from backend.models.schemas import AnalyzeResponse, FailuresResponse
from backend.services import persistence_service
from backend.tests.conftest import make_failure_group, make_failure_record


def _response(groups) -> AnalyzeResponse:
    return AnalyzeResponse(
        total_failures=sum(g.impact_count for g in groups),
        time_range="1h",
        analyzed_at=datetime.now(timezone.utc).isoformat(),
        failure_groups=groups,
        summary="Test summary",
    )


def test_persist_fetched_records_creates_failure_records(db_session):
    response = FailuresResponse(
        total=2,
        time_range="1h",
        records=[
            make_failure_record(custom_key1="trace-a"),
            make_failure_record(custom_key1="trace-b"),
        ],
    )

    created = persistence_service.persist_fetched_records(db_session, response)

    assert created == 2
    rows = db_session.execute(select(FailureRecordModel)).scalars().all()
    assert {r.file_trace_id for r in rows} == {"trace-a", "trace-b"}


def test_persist_fetched_records_skips_already_persisted(db_session):
    response = FailuresResponse(
        total=1, time_range="1h", records=[make_failure_record(custom_key1="trace-a")]
    )

    first = persistence_service.persist_fetched_records(db_session, response)
    second = persistence_service.persist_fetched_records(db_session, response)

    assert first == 1
    assert second == 0
    rows = db_session.execute(select(FailureRecordModel)).scalars().all()
    assert len(rows) == 1


def test_persist_analysis_links_to_already_fetched_record(db_session):
    record = make_failure_record(custom_key1="trace-shared")
    fetched = FailuresResponse(total=1, time_range="1h", records=[record])
    persistence_service.persist_fetched_records(db_session, fetched)

    group = make_failure_group(records=[record])
    persistence_service.persist_analysis(db_session, _response([group]))

    # Only one failure_records row should exist — analysis links to the
    # row already created by Step 1, instead of inserting a duplicate.
    rows = db_session.execute(select(FailureRecordModel)).scalars().all()
    assert len(rows) == 1

    link = db_session.execute(select(CaseFailureRecord)).scalar_one()
    assert link.failure_record_id == rows[0].id


def test_persist_analysis_creates_case_failure_and_signature(db_session):
    group = make_failure_group()
    response = _response([group])

    persistence_service.persist_analysis(db_session, response)

    case = db_session.execute(select(RcaCase)).scalar_one()
    assert case.component_name == group.component
    assert case.root_cause == group.root_cause
    assert case.impact_count == group.impact_count

    failure_row = db_session.execute(select(FailureRecordModel)).scalar_one()
    assert failure_row.component_name == group.component
    assert failure_row.error_code == "S3_PUT_FAILED"
    assert failure_row.stage == "lz-processor"

    link = db_session.execute(select(CaseFailureRecord)).scalar_one()
    assert link.case_id == case.id
    assert link.failure_record_id == failure_row.id

    activity_types = {
        a.activity_type for a in db_session.execute(select(CaseActivity)).scalars()
    }
    assert "analysis_run" in activity_types
    assert "signature_match" in activity_types

    signature = db_session.execute(select(RootCauseSignature)).scalar_one()
    assert signature.occurrence_count == 1

    sig_link = db_session.execute(select(CaseSignatureLink)).scalar_one()
    assert sig_link.case_id == case.id
    assert sig_link.signature_id == signature.id


def test_persist_analysis_recurring_failure_bumps_occurrence_count(db_session):
    group = make_failure_group()
    persistence_service.persist_analysis(db_session, _response([group]))

    # Same signature (component/error_code/stage) recurs in a second analysis run.
    group2 = make_failure_group(group_id="grp-2")
    persistence_service.persist_analysis(db_session, _response([group2]))

    cases = db_session.execute(select(RcaCase)).scalars().all()
    assert len(cases) == 2

    signature = db_session.execute(select(RootCauseSignature)).scalar_one()
    assert signature.occurrence_count == 2

    sig_links = db_session.execute(select(CaseSignatureLink)).scalars().all()
    assert {link.case_id for link in sig_links} == {c.id for c in cases}
