"""Persists RCA analysis results to the CRM tables (CRM_PLAN.md Phase 1).

Called by the /api/analyze route after RCAOrchestrator.analyze_records()
returns. Does not change the API response shape — persistence is a
side effect for the case queue / knowledge base.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from ..db.models import FailureRecord as FailureRecordModel
from ..models.schemas import AnalyzeResponse, FailureRecord, FailuresResponse
from ..repositories import case_repo, failure_repo, project_repo, signature_repo
from .signature_service import compute_signature_hash, match_or_create_signature

logger = logging.getLogger(__name__)


def persist_fetched_records(db: Session, response: FailuresResponse) -> int:
    """Persist Step-1 fetched failure records to `failure_records`.

    Records already stored for this project (matched by `file_trace_id`,
    i.e. `custom_key1`) are skipped so re-fetching the same time range
    doesn't create duplicates. Records without a `custom_key1` are always
    inserted, since there's nothing to dedupe on.
    """
    project = project_repo.get_or_create_default_project(db)

    trace_ids = [r.custom_key1 for r in response.records if r.custom_key1]
    existing = failure_repo.get_existing_trace_ids(db, project.id, trace_ids)

    new_records = [
        r for r in response.records if not (r.custom_key1 and r.custom_key1 in existing)
    ]

    if new_records:
        failure_repo.bulk_create_failure_records(db, project.id, new_records)
        db.commit()

    logger.info(
        "Persisted fetched failure records: project=%s new=%d skipped=%d",
        project.name,
        len(new_records),
        len(response.records) - len(new_records),
    )
    return len(new_records)


def persist_analysis(db: Session, response: AnalyzeResponse) -> None:
    """Persist failure records, RCA cases, activity, and signature matches."""
    project = project_repo.get_or_create_default_project(db)

    # Pre-load rows already persisted by Step 1 (/api/failures), keyed by file_trace_id,
    # so we link to them instead of inserting duplicates.
    trace_ids = [
        record.custom_key1
        for group in response.failure_groups
        for record in group.records
        if record.custom_key1
    ]
    persisted: dict[str, FailureRecordModel] = failure_repo.get_by_trace_ids(
        db, project.id, trace_ids
    )

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
