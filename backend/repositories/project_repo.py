from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db.models import Project

DEFAULT_PROJECT_NAME = "default"


def get_or_create_default_project(db: Session) -> Project:
    """Return the single project seeded from today's .env (Athena/CloudWatch config).

    Phase 1 is single-project; multi-project CRUD lands in CRM_PLAN.md Phase 5.
    """
    project = db.execute(
        select(Project).where(Project.name == DEFAULT_PROJECT_NAME)
    ).scalar_one_or_none()
    if project is not None:
        return project

    project = Project(
        name=DEFAULT_PROJECT_NAME,
        description="Default project seeded from .env (Athena/CloudWatch configuration)",
        data_source_cfg={
            "provider": "athena",
            "database": settings.athena_database,
            "table": settings.athena_table,
        },
        log_backend_cfg={
            "provider": "cloudwatch",
            "log_group": settings.cloudwatch_log_group,
        },
    )
    db.add(project)
    db.flush()
    return project
