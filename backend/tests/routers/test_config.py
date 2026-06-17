"""Router tests for /api/config endpoints — TestClient with mocked config_repo."""

from datetime import UTC, datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.db.models import AppConfig
from backend.main import app
from backend.models.schemas import MASK_SENTINEL

_CLIENT = TestClient(app)

_NOW = datetime(2026, 6, 16, 10, 0, 0, tzinfo=UTC)


def _make_row(
    aws: dict | None = None,
    github: dict | None = None,
    updated_at: datetime = _NOW,
) -> AppConfig:
    row = AppConfig()
    row.id = 1
    row.aws_config = aws
    row.github_mcp_config = github
    row.updated_at = updated_at
    return row


class TestGetConfig:
    def test_returns_not_configured_when_db_empty(self) -> None:
        with (
            patch("backend.routers.config.config_repo.get_app_config", return_value=None),
            patch("backend.routers.config.settings") as mock_settings,
        ):
            mock_settings.aws_access_key_id = ""
            mock_settings.aws_secret_access_key = ""
            mock_settings.aws_region = ""
            mock_settings.github_repo = ""
            mock_settings.github_token = ""
            resp = _CLIENT.get("/api/config")
        assert resp.status_code == 200
        body = resp.json()
        assert body["aws"]["configured"] is False
        assert body["github_mcp"]["configured"] is False

    def test_aws_secret_is_masked_when_configured(self) -> None:
        row = _make_row(aws={"access_key_id": "AK", "secret_access_key": "real_secret"})
        with patch("backend.routers.config.config_repo.get_app_config", return_value=row):
            resp = _CLIENT.get("/api/config")
        body = resp.json()
        assert body["aws"]["configured"] is True
        assert body["aws"]["secret_access_key"] == MASK_SENTINEL
        assert body["aws"]["access_key_id"] == "AK"

    def test_github_token_is_masked_when_configured(self) -> None:
        row = _make_row(github={"repo": "o/r", "token": "ghp_real"})
        with patch("backend.routers.config.config_repo.get_app_config", return_value=row):
            resp = _CLIENT.get("/api/config")
        body = resp.json()
        assert body["github_mcp"]["configured"] is True
        assert body["github_mcp"]["token"] == MASK_SENTINEL
        assert body["github_mcp"]["repo"] == "o/r"

    def test_secrets_null_when_not_configured(self) -> None:
        with (
            patch("backend.routers.config.config_repo.get_app_config", return_value=None),
            patch("backend.routers.config.settings") as mock_settings,
        ):
            mock_settings.aws_access_key_id = ""
            mock_settings.aws_secret_access_key = ""
            mock_settings.aws_region = ""
            mock_settings.github_repo = ""
            mock_settings.github_token = ""
            resp = _CLIENT.get("/api/config")
        body = resp.json()
        assert body["aws"]["secret_access_key"] is None
        assert body["github_mcp"]["token"] is None

    def test_aws_not_configured_when_only_key_id_present(self) -> None:
        # DB row exists but secret is empty — should be not configured (no env-var fallback)
        row = _make_row(aws={"access_key_id": "AK", "secret_access_key": None})
        with patch("backend.routers.config.config_repo.get_app_config", return_value=row):
            resp = _CLIENT.get("/api/config")
        body = resp.json()
        assert body["aws"]["configured"] is False

    def test_env_var_fallback_for_aws(self) -> None:
        with (
            patch("backend.routers.config.config_repo.get_app_config", return_value=None),
            patch("backend.routers.config.settings") as mock_settings,
        ):
            mock_settings.aws_access_key_id = "ENV_AK"
            mock_settings.aws_secret_access_key = "ENV_SK"
            mock_settings.aws_region = "us-east-1"
            mock_settings.github_repo = ""
            mock_settings.github_token = ""
            resp = _CLIENT.get("/api/config")
        body = resp.json()
        assert body["aws"]["configured"] is True
        assert body["aws"]["access_key_id"] == "ENV_AK"
        assert body["aws"]["secret_access_key"] == MASK_SENTINEL

    def test_env_var_not_configured_when_both_empty(self) -> None:
        with (
            patch("backend.routers.config.config_repo.get_app_config", return_value=None),
            patch("backend.routers.config.settings") as mock_settings,
        ):
            mock_settings.aws_access_key_id = ""
            mock_settings.aws_secret_access_key = ""
            mock_settings.aws_region = "us-east-1"
            mock_settings.github_repo = ""
            mock_settings.github_token = ""
            resp = _CLIENT.get("/api/config")
        body = resp.json()
        assert body["aws"]["configured"] is False

    def test_env_var_fallback_for_github_mcp(self) -> None:
        with (
            patch("backend.routers.config.config_repo.get_app_config", return_value=None),
            patch("backend.routers.config.settings") as mock_settings,
        ):
            mock_settings.aws_access_key_id = ""
            mock_settings.aws_secret_access_key = ""
            mock_settings.aws_region = ""
            mock_settings.github_repo = "owner/repo"
            mock_settings.github_token = "ghp_envtoken"
            resp = _CLIENT.get("/api/config")
        body = resp.json()
        assert body["github_mcp"]["configured"] is True
        assert body["github_mcp"]["repo"] == "owner/repo"
        assert body["github_mcp"]["token"] == MASK_SENTINEL


class TestPatchAwsConfig:
    def test_returns_success_with_valid_payload(self) -> None:
        row = _make_row(
            aws={"access_key_id": "AK", "secret_access_key": "SK"},
            updated_at=_NOW,
        )
        with patch("backend.routers.config.config_repo.upsert_aws_config", return_value=row):
            resp = _CLIENT.patch(
                "/api/config/aws",
                json={"access_key_id": "AK", "secret_access_key": "SK"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "AWS" in body["message"]

    def test_422_when_access_key_id_empty(self) -> None:
        resp = _CLIENT.patch(
            "/api/config/aws",
            json={"access_key_id": "", "secret_access_key": "SK"},
        )
        assert resp.status_code == 422

    def test_422_when_secret_empty_and_not_sentinel(self) -> None:
        resp = _CLIENT.patch(
            "/api/config/aws",
            json={"access_key_id": "AK", "secret_access_key": ""},
        )
        assert resp.status_code == 422

    def test_sentinel_accepted_for_secret(self) -> None:
        row = _make_row(aws={"access_key_id": "AK", "secret_access_key": "orig"})
        with patch("backend.routers.config.config_repo.upsert_aws_config", return_value=row):
            resp = _CLIENT.patch(
                "/api/config/aws",
                json={"access_key_id": "AK", "secret_access_key": MASK_SENTINEL},
            )
        assert resp.status_code == 200

    def test_get_after_save_returns_configured_true(self) -> None:
        row = _make_row(aws={"access_key_id": "AK", "secret_access_key": "SK"})
        with patch("backend.routers.config.config_repo.get_app_config", return_value=row):
            resp = _CLIENT.get("/api/config")
        assert resp.json()["aws"]["configured"] is True


class TestPatchGithubMcpConfig:
    def test_returns_success_with_valid_payload(self) -> None:
        row = _make_row(github={"repo": "o/r", "token": "ghp_t"}, updated_at=_NOW)
        with patch(
            "backend.routers.config.config_repo.upsert_github_mcp_config", return_value=row
        ):
            resp = _CLIENT.patch(
                "/api/config/github-mcp",
                json={"repo": "o/r", "token": "ghp_t"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "GitHub" in body["message"]

    def test_422_when_repo_not_owner_slash_repo(self) -> None:
        resp = _CLIENT.patch(
            "/api/config/github-mcp",
            json={"repo": "noslash", "token": "ghp_t"},
        )
        assert resp.status_code == 422

    def test_422_when_repo_is_whitespace_only(self) -> None:
        resp = _CLIENT.patch(
            "/api/config/github-mcp",
            json={"repo": "   ", "token": "ghp_t"},
        )
        assert resp.status_code == 422

    def test_422_when_token_empty(self) -> None:
        resp = _CLIENT.patch(
            "/api/config/github-mcp",
            json={"repo": "o/r", "token": ""},
        )
        assert resp.status_code == 422

    def test_sentinel_accepted_for_token(self) -> None:
        row = _make_row(github={"repo": "o/r", "token": "orig"})
        with patch(
            "backend.routers.config.config_repo.upsert_github_mcp_config", return_value=row
        ):
            resp = _CLIENT.patch(
                "/api/config/github-mcp",
                json={"repo": "o/r", "token": MASK_SENTINEL},
            )
        assert resp.status_code == 200
