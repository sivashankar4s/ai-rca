"""Repository tests for project_repo — run against a real test DB (Constitution IV)."""

from sqlalchemy.orm import Session

from backend.repositories.project_repo import get_or_create_default_project


class TestGetOrCreateDefaultProject:
    def test_creates_project_on_first_call(self, db_session: Session) -> None:
        project = get_or_create_default_project(db_session)
        assert project.id is not None
        assert project.name == "default"
        assert project.is_active is True

    def test_returns_same_project_on_repeat_calls(self, db_session: Session) -> None:
        p1 = get_or_create_default_project(db_session)
        p2 = get_or_create_default_project(db_session)
        assert p1.id == p2.id

    def test_project_has_required_cfg_fields(self, db_session: Session) -> None:
        project = get_or_create_default_project(db_session)
        assert isinstance(project.data_source_cfg, dict)
        assert isinstance(project.log_backend_cfg, dict)
