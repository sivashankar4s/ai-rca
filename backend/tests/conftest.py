"""Shared pytest fixtures for the backend test suite."""

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client() -> TestClient:
    """A FastAPI ``TestClient`` bound to the application instance."""
    return TestClient(app)
