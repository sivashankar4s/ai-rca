"""PostgresDataSource — reads stored failure records from the failure_records table."""

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import FailureRecord as FailureRecordORM
from backend.db.session import SessionLocal
from backend.models.schemas import FailureRecord as FailureRecordSchema
from backend.strategies.data_source import DataSourceStrategy

logger = logging.getLogger(__name__)


def _to_schema(row: FailureRecordORM) -> FailureRecordSchema:
    return FailureRecordSchema(
        file_trace_id=row.file_trace_id,
        application_name=row.application_name,
        component_name=row.component_name,
        organization=row.organization,
        file_name=row.file_name,
        device_id=row.device_id,
        error_code=row.error_code,
        stage=row.stage,
        event_created_ts=row.event_created_ts,
        event_inserted_ts=row.event_inserted_ts,
        raw_payload=row.raw_payload,
        signature_hash=row.signature_hash,
    )


class PostgresDataSource(DataSourceStrategy):
    """Returns failure records already stored in the failure_records table (FR-004)."""

    def __init__(self, session_factory=None) -> None:
        self._session_factory = session_factory or SessionLocal

    def fetch_records(
        self,
        start: datetime,
        end: datetime,
        component: str | None = None,
    ) -> list[FailureRecordSchema]:
        db: Session = self._session_factory()
        try:
            stmt = select(FailureRecordORM).where(
                FailureRecordORM.event_created_ts >= start,
                FailureRecordORM.event_created_ts <= end,
            )
            if component is not None:
                stmt = stmt.where(FailureRecordORM.component_name == component)

            rows = db.scalars(stmt).all()
            logger.info(
                "PostgresDataSource: returned %d records (component=%s)",
                len(rows),
                component or "<all>",
            )
            return [_to_schema(r) for r in rows]
        finally:
            db.close()
