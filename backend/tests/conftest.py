"""Shared pytest fixtures for the backend test suite."""

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.main import app

TEST_DB_URL = "postgresql+psycopg2://postgres:root@localhost:5432/airca_test"


@pytest.fixture(scope="session")
def _apply_migrations() -> None:
    """Apply Alembic migrations to the test database once per session."""
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", TEST_DB_URL)
    command.upgrade(cfg, "head")


@pytest.fixture
def db_session(_apply_migrations: None) -> Session:
    """Yield a real DB session that rolls back after each test (no side effects)."""
    engine = create_engine(TEST_DB_URL)
    connection = engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection)
    session = session_factory()

    yield session

    session.close()
    transaction.rollback()
    connection.close()
    engine.dispose()


@pytest.fixture
def client() -> TestClient:
    """A FastAPI ``TestClient`` bound to the application instance."""
    return TestClient(app)
