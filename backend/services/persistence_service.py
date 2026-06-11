"""Persists RCA analysis results to the CRM tables (CRM_PLAN.md Phase 1).

Called by the /api/analyze route after RCAOrchestrator.analyze_records()
returns. Does not change the API response shape — persistence is a
side effect for the case queue / knowledge base.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from ..db.models import FailureRecord as FailureRecordModel
from ..models.schemas import AnalyzeResponse, FailureRecord
from ..repositories import case_repo, failure_repo, project_repo, signature_repo
from .signature_service import compute_signature_hash, match_or_create_signature

logger = logging.getLogger(__name__)


def persist_analysis(db: Session, response: AnalyzeResponse) -> None:
    """Persist failure records, RCA cases, activity, and signature matches."""
    project = project_repo.get_or_create_default_project(db)

    # Track failure records already persisted in this call (by file_trace_id) to
    # avoid duplicating rows shared across multiple groups.
    persisted: dict[str, FailureRecordModel] = {}

    for group in response.failure_groups:
        failure_rows = []
        for record in group.records:
            key = record.custom_key1 or f"{record.component_name}:{record.event_created_timestamp}"
            row = persisted.get(key)
            if row is None:
                row = failure_repo.create_failure_record(db, project.id, record)
                persisted[key] = row
            failure_rows.append(row)

        case = case_repo.create_case_from_group(db, project.id, group)
        if failure_rows:
            case_repo.link_failure_records(db, case.id, [r.id for r in failure_rows])

        case_repo.add_activity(
            db,
            case.id,
            activity_type="analysis_run",
            payload={"summary": response.summary, "impact_count": group.impact_count},
        )

        signature_hash = compute_signature_hash(
            group.component, _dominant_error_code(group.records), _dominant_stage(group.records)
        )
        signature, is_new = match_or_create_signature(
            db,
            project_id=project.id,
            signature_hash=signature_hash,
            component_name=group.component,
            error_code=_dominant_error_code(group.records),
            stage=_dominant_stage(group.records),
            root_cause=group.root_cause,
            failure_category=group.failure_category,
        )
        signature_repo.link_case_to_signature(db, case.id, signature.id)
        case_repo.add_activity(
            db,
            case.id,
            activity_type="signature_match",
            payload={"signature_hash": signature_hash, "is_new": is_new},
        )

    db.commit()
    logger.info(
        "Persisted RCA analysis: project=%s groups=%d failure_records=%d",
        project.name,
        len(response.failure_groups),
        len(persisted),
    )


def _dominant_error_code(records: list[FailureRecord]) -> str | None:
    codes = [r.event_data.error_code for r in records if r.event_data and r.event_data.error_code]
    return _most_common(codes)


def _dominant_stage(records: list[FailureRecord]) -> str | None:
    stages = [r.event_data.stage for r in records if r.event_data and r.event_data.stage]
    return _most_common(stages)


def _most_common(values: list[str]) -> str | None:
    if not values:
        return None
    return max(set(values), key=values.count)
