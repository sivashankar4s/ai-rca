# Testing Patterns

## TDD is Mandatory

Write tests first, watch them fail (red), then implement (green), then refactor. Never write implementation before the failing test exists.

## Test Location

```
backend/tests/
  test_routers/     # FastAPI endpoint tests via TestClient
  test_services/    # Service unit tests (mock repositories)
  test_repositories/ # Repository integration tests (real DB)
  test_providers/   # Provider tests (mock external APIs)
  conftest.py       # Shared fixtures
```

## FastAPI Testing Pattern

```python
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_endpoint():
    response = client.get("/api/v1/resource/1")
    assert response.status_code == 200
    assert response.json()["id"] == 1
```

## Service Testing Pattern

```python
from unittest.mock import AsyncMock, patch

async def test_service_method():
    mock_repo = AsyncMock()
    mock_repo.get.return_value = SomeModel(id=1)
    
    service = SomeService(repo=mock_repo)
    result = await service.get_something(1)
    
    assert result.id == 1
    mock_repo.get.assert_called_once_with(1)
```

## Coverage Requirements

- ≥ 90% lines, branches, functions, statements
- `pytest --cov --cov-fail-under=90` is the enforcement command
- Exclude: `backend/tests/*`, `backend/db/migrations/*`
- Use `# pragma: no cover` only for truly untestable branches (e.g., `if TYPE_CHECKING:`)

## Fixtures

Shared fixtures live in `conftest.py`. Scope to the narrowest level needed: `function` > `module` > `session`.

## What Not to Mock

- Do not mock the database for repository tests — use a real test database
- Do mock external HTTP APIs (GitHub, AWS, LLM providers)
