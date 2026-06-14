import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select

from ...db.models import FailureRecord as FailureRecordModel
from ...db.session import SessionLocal
from ...repositories import project_repo
from ...strategies.data_source import DataSourceStrategy

logger = logging.getLogger(__name__)

_INTERVAL_MAP = {
    "1h": timedelta(hours=1),
    "1d": timedelta(days=1),
    "1w": timedelta(weeks=1),
}


class PostgresDataSource(DataSourceStrategy):
    """Reads failure records back out of the local CRM database (`failure_records`).

    Records are populated there by /api/failures (Step 1) regardless of which
    upstream data source originally produced them — this lets the UI re-browse
    previously-fetched failures without re-querying Athena.
    """

    def fetch_records(
        self,
        time_range: str,
        component: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        failure_only: bool = True,
    ) -> list[dict]:
        if start_date and end_date:
            start = datetime.fromisoformat(start_date)
            end = datetime.fromisoformat(end_date)
        else:
            end = datetime.now(UTC).replace(tzinfo=None)
            start = end - _INTERVAL_MAP.get(time_range, timedelta(hours=1))

        with SessionLocal() as db:
            project = project_repo.get_or_create_default_project(db)

            query = (
                select(FailureRecordModel)
                .where(FailureRecordModel.project_id == project.id)
                .where(FailureRecordModel.event_inserted_ts.between(start, end))
            )

            if component:
                like = f"%{component}%"
                query = query.where(
                    or_(
                        FailureRecordModel.component_name.ilike(like),
                        FailureRecordModel.file_name.ilike(like),
                        FailureRecordModel.device_id.ilike(like),
                        FailureRecordModel.file_trace_id.ilike(like),
                    )
                )

            query = query.order_by(FailureRecordModel.event_inserted_ts.desc()).limit(200)
            rows = db.execute(query).scalars().all()

        # raw_payload is the original FailureRecord.model_dump(mode="json") —
        # already in the shape FailuresResponse expects.
        records = [row.raw_payload for row in rows]
        if failure_only:
            records = [r for r in records if r.get("status") == "FAILED"]

        logger.info(
            "PostgresDataSource returned %d record(s)  start=%s  end=%s  component=%s",
            len(records), start, end, component or "<all>",
        )
        return records
