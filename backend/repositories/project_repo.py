"""Project repository — get or create the singleton default project."""

import logging

from sqlalchemy.orm import Session

from backend.db.models import Project

logger = logging.getLogger(__name__)


def get_or_create_default_project(db: Session) -> Project:
    """Return the singleton 'default' project, creating it if it doesn't exist."""
    project = db.query(Project).filter_by(name="default").first()
    if project is None:
        project = Project(
            name="default",
            data_source_cfg={},
            log_backend_cfg={},
            is_active=True,
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        logger.info("Created default project id=%s", project.id)
    return project
