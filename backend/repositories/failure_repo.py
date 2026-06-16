"""Failure record repository — upsert-based persistence with dedup.

Repositories are the ONLY place ORM queries live (Constitution Principle III).
No raw SQL, no business logic — pure persistence operations.
"""

import logging
import uuid

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from backend.db.models import FailureRecord as FailureRecordORM
from backend.models.schemas import FailureRecord as FailureRecordSchema

logger = logging.getLogger(__name__)


def upsert_failure_records(
    db: Session,
    project_id: uuid.UUID,
    records: list[FailureRecordSchema],
) -> list[FailureRecordORM]:
    """Upsert a batch of FailureRecord schemas into the DB for a given project.

    Records are deduplicated by (project_id, file_trace_id).  If a row with the
    same composite key already exists, its mutable columns are updated in-place.
    Records with file_trace_id=None bypass the upsert key and always insert as
    new rows (NULL != NULL in the unique constraint).

    Args:
        db: Active SQLAlchemy session (from the FastAPI dependency or test fixture).
        project_id: UUID of the owning project — FK to projects.id.
        records: List of Pydantic FailureRecord DTOs to persist.

    Returns:
        List of persisted FailureRecord ORM instances in input order.
    """
    if not records:
        return []

    results: list[FailureRecordORM] = []

    for schema in records:
        values: dict = {
            "id": uuid.uuid4(),
            "project_id": project_id,
            "application_name": schema.application_name,
            "component_name": schema.component_name,
            "organization": schema.organization,
            "file_trace_id": schema.file_trace_id,
            "file_name": schema.file_name,
            "device_id": schema.device_id,
            "error_code": schema.error_code,
            "stage": schema.stage,
            "event_created_ts": schema.event_created_ts,
            "event_inserted_ts": schema.event_inserted_ts,
            "raw_payload": schema.raw_payload,
            "signature_hash": schema.signature_hash,
        }

        update_values: dict = {
            k: v for k, v in values.items() if k not in ("id", "project_id", "file_trace_id")
        }

        if schema.file_trace_id is not None:
            # Upsert path: conflict on (project_id, file_trace_id) → update mutable cols
            stmt = (
                insert(FailureRecordORM)
                .values(**values)
                .on_conflict_do_update(
                    constraint="uq_failure_project_trace",
                    set_=update_values,
                )
                .returning(FailureRecordORM)
            )
            orm_obj = db.execute(stmt).scalars().one()
        else:
            # NULL file_trace_id — always insert a new row (NULL != NULL in unique constraint)
            orm_obj = FailureRecordORM(**values)
            db.add(orm_obj)
            db.flush()

        results.append(orm_obj)
        logger.debug(
            "upserted failure_record id=%s project_id=%s file_trace_id=%s",
            orm_obj.id,
            project_id,
            schema.file_trace_id,
        )

    logger.info(
        "upsert_failure_records: persisted %d records for project_id=%s",
        len(results),
        project_id,
    )
    return results
