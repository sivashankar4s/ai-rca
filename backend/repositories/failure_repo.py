from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from ..db.models import FailureRecord as FailureRecordModel
from ..models.schemas import FailureRecord
from ..services.signature_service import compute_signature_hash


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def create_failure_record(
    db: Session, project_id: uuid.UUID, record: FailureRecord
) -> FailureRecordModel:
    """Persist a single normalized failure record, computing its signature hash."""
    event_data = record.event_data
    error_code = event_data.error_code if event_data else None
    stage = event_data.stage if event_data else None

    row = FailureRecordModel(
        project_id=project_id,
        application_name=record.application_name,
        component_name=record.component_name,
        organization=record.organization,
        file_trace_id=record.custom_key1,
        file_name=record.custom_key2,
        device_id=record.custom_key3,
        error_code=error_code,
        stage=stage,
        event_created_ts=_parse_ts(record.event_created_timestamp),
        event_inserted_ts=_parse_ts(record.event_inserted_timestamp),
        raw_payload=record.model_dump(mode="json"),
        signature_hash=compute_signature_hash(record.component_name, error_code, stage),
    )
    db.add(row)
    db.flush()
    return row


def bulk_create_failure_records(
    db: Session, project_id: uuid.UUID, records: list[FailureRecord]
) -> list[FailureRecordModel]:
    return [create_failure_record(db, project_id, record) for record in records]


def get_existing_trace_ids(
    db: Session, project_id: uuid.UUID, trace_ids: list[str]
) -> set[str]:
    """Return the subset of `trace_ids` (custom_key1) already stored for this project."""
    if not trace_ids:
        return set()
    rows = (
        db.query(FailureRecordModel.file_trace_id)
        .filter(
            FailureRecordModel.project_id == project_id,
            FailureRecordModel.file_trace_id.in_(trace_ids),
        )
        .all()
    )
    return {row[0] for row in rows}


def get_by_trace_ids(
    db: Session, project_id: uuid.UUID, trace_ids: list[str]
) -> dict[str, FailureRecordModel]:
    """Return existing failure_records rows for this project, keyed by `file_trace_id`."""
    if not trace_ids:
        return {}
    rows = (
        db.query(FailureRecordModel)
        .filter(
            FailureRecordModel.project_id == project_id,
            FailureRecordModel.file_trace_id.in_(trace_ids),
        )
        .all()
    )
    return {row.file_trace_id: row for row in rows}
