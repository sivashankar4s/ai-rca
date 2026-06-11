from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from ..db.models import CaseActivity, CaseFailureRecord, CaseStatus, RcaCase
from ..models.schemas import FailureGroup


def create_case_from_group(
    db: Session, project_id: uuid.UUID, group: FailureGroup
) -> RcaCase:
    case = RcaCase(
        project_id=project_id,
        status=CaseStatus.ANALYZED,
        component_name=group.component,
        error_pattern=group.error_pattern,
        root_cause=group.root_cause,
        failure_category=group.failure_category,
        immediate_action=group.immediate_action,
        likely_fix=group.likely_fix,
        affected_files=group.affected_files,
        escalation_path=group.escalation_path,
        impact_count=group.impact_count,
        cw_log_url=group.cw_log_url,
    )
    db.add(case)
    db.flush()
    return case


def link_failure_records(
    db: Session, case_id: uuid.UUID, failure_record_ids: list[uuid.UUID]
) -> None:
    for failure_record_id in failure_record_ids:
        db.add(CaseFailureRecord(case_id=case_id, failure_record_id=failure_record_id))
    db.flush()


def add_activity(
    db: Session,
    case_id: uuid.UUID,
    activity_type: str,
    payload: dict | None = None,
    created_by: str | None = None,
) -> CaseActivity:
    activity = CaseActivity(
        case_id=case_id,
        activity_type=activity_type,
        payload=payload,
        created_by=created_by,
    )
    db.add(activity)
    db.flush()
    return activity


def reopen_as_recurring(db: Session, case: RcaCase) -> None:
    """Mark a previously resolved case as recurring after a new signature match."""
    if case.status == CaseStatus.RESOLVED:
        case.status = CaseStatus.RECURRING
        db.flush()
