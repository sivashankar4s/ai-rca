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
from backend.models.schemas import AnalyzeResponse
from backend.services import persistence_service
from backend.tests.conftest import make_failure_group


def _response(groups) -> AnalyzeResponse:
    return AnalyzeResponse(
        total_failures=sum(g.impact_count for g in groups),
        time_range="1h",
        analyzed_at=datetime.now(timezone.utc).isoformat(),
        failure_groups=groups,
        summary="Test summary",
    )


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
