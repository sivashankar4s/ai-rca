"""Router tests for /api/config endpoints — TestClient with mocked config_repo."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

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
            mock_settings.athena_database = ""
            mock_settings.athena_table = ""
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

    def test_aws_session_token_masked_when_present(self) -> None:
        row = _make_row(
            aws={"access_key_id": "AK", "secret_access_key": "s", "session_token": "tok"}
        )
        with patch("backend.routers.config.config_repo.get_app_config", return_value=row):
            resp = _CLIENT.get("/api/config")
        assert resp.json()["aws"]["session_token"] == MASK_SENTINEL

    def test_aws_session_token_null_when_absent(self) -> None:
        row = _make_row(aws={"access_key_id": "AK", "secret_access_key": "s"})
        with patch("backend.routers.config.config_repo.get_app_config", return_value=row):
            resp = _CLIENT.get("/api/config")
        assert resp.json()["aws"]["session_token"] is None

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
            mock_settings.athena_database = ""
            mock_settings.athena_table = ""
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
            mock_settings.athena_database = ""
            mock_settings.athena_table = ""
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
            mock_settings.athena_database = ""
            mock_settings.athena_table = ""
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
            mock_settings.athena_database = ""
            mock_settings.athena_table = ""
            resp = _CLIENT.get("/api/config")
        body = resp.json()
        assert body["github_mcp"]["configured"] is True
        assert body["github_mcp"]["repo"] == "owner/repo"
        assert body["github_mcp"]["token"] == MASK_SENTINEL


class TestDiscoverCloudWatchLogGroups:
    def test_returns_log_groups_with_prefix(self) -> None:
        mock_ds = MagicMock()
        mock_ds.list_log_groups.return_value = ["/aws/lambda/a", "/aws/lambda/b"]
        with patch("backend.routers.config.get_data_source", return_value=mock_ds):
            resp = _CLIENT.get("/api/config/cloudwatch/log-groups?prefix=/aws/lambda/")
        assert resp.status_code == 200
        assert resp.json()["log_groups"] == ["/aws/lambda/a", "/aws/lambda/b"]
        mock_ds.list_log_groups.assert_called_once_with("/aws/lambda/")

    def test_no_prefix_passes_none(self) -> None:
        mock_ds = MagicMock()
        mock_ds.list_log_groups.return_value = []
        with patch("backend.routers.config.get_data_source", return_value=mock_ds):
            resp = _CLIENT.get("/api/config/cloudwatch/log-groups")
        assert resp.status_code == 200
        mock_ds.list_log_groups.assert_called_once_with(None)

    def test_runtime_error_returns_400(self) -> None:
        mock_ds = MagicMock()
        mock_ds.list_log_groups.side_effect = RuntimeError(
            "CloudWatch log group discovery failed: boom"
        )
        with patch("backend.routers.config.get_data_source", return_value=mock_ds):
            resp = _CLIENT.get("/api/config/cloudwatch/log-groups")
        assert resp.status_code == 400
        assert "discovery failed" in resp.json()["detail"]


class TestAthenaConfig:
    def test_configured_from_db_row(self) -> None:
        row = _make_row()
        row.athena_config = {"database": "mydb", "table": "mytable"}
        with patch("backend.routers.config.config_repo.get_app_config", return_value=row):
            resp = _CLIENT.get("/api/config")
        body = resp.json()
        assert body["athena"]["configured"] is True
        assert body["athena"]["database"] == "mydb"
        assert body["athena"]["table"] == "mytable"

    def test_not_configured_when_incomplete(self) -> None:
        row = _make_row()
        row.athena_config = {"database": "mydb"}
        with patch("backend.routers.config.config_repo.get_app_config", return_value=row):
            resp = _CLIENT.get("/api/config")
        assert resp.json()["athena"]["configured"] is False

    def test_patch_saves_config(self) -> None:
        row = _make_row(updated_at=_NOW)
        with patch("backend.routers.config.config_repo.upsert_athena_config", return_value=row):
            resp = _CLIENT.patch(
                "/api/config/athena", json={"database": "mydb", "table": "mytable"}
            )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_patch_422_when_database_empty(self) -> None:
        resp = _CLIENT.patch("/api/config/athena", json={"database": "", "table": "t"})
        assert resp.status_code == 422


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
        with patch("backend.routers.config.config_repo.upsert_github_mcp_config", return_value=row):
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
        with patch("backend.routers.config.config_repo.upsert_github_mcp_config", return_value=row):
            resp = _CLIENT.patch(
                "/api/config/github-mcp",
                json={"repo": "o/r", "token": MASK_SENTINEL},
            )
        assert resp.status_code == 200


class TestHealthDiscovery:
    def test_glue_jobs_discovery_returns_resources(self) -> None:
        from backend.models.schemas import HealthResource, HealthServiceType

        provider = MagicMock()
        provider.discover.return_value = [HealthResource(id="etl", label="etl")]
        checkers = {HealthServiceType.GLUE_JOB: provider}
        with patch("backend.routers.config.get_health_checkers", return_value=checkers):
            resp = _CLIENT.get("/api/config/health/glue-jobs")
        assert resp.status_code == 200
        assert resp.json()["resources"] == [{"id": "etl", "label": "etl"}]

    def test_datasync_discovery_uses_provider(self) -> None:
        from backend.models.schemas import HealthResource, HealthServiceType

        provider = MagicMock()
        provider.discover.return_value = [HealthResource(id="arn:1", label="nightly")]
        checkers = {HealthServiceType.DATASYNC_TASK: provider}
        with patch("backend.routers.config.get_health_checkers", return_value=checkers):
            resp = _CLIENT.get("/api/config/health/datasync-tasks")
        assert resp.status_code == 200
        assert resp.json()["resources"][0]["label"] == "nightly"

    def test_discovery_runtime_error_returns_400(self) -> None:
        from backend.models.schemas import HealthServiceType

        provider = MagicMock()
        provider.discover.side_effect = RuntimeError("Lambda discovery failed: boom")
        checkers = {HealthServiceType.LAMBDA_FUNCTION: provider}
        with patch("backend.routers.config.get_health_checkers", return_value=checkers):
            resp = _CLIENT.get("/api/config/health/lambda-functions")
        assert resp.status_code == 400
        assert "discovery failed" in resp.json()["detail"]


class TestHealthConfig:
    def test_get_config_reports_health_selection(self) -> None:
        row = _make_row()
        row.health_config = {
            "glue_jobs": ["etl"],
            "datasync_tasks": [{"id": "arn:1", "label": "nightly"}],
        }
        with patch("backend.routers.config.config_repo.get_app_config", return_value=row):
            resp = _CLIENT.get("/api/config")
        body = resp.json()
        assert body["health"]["configured"] is True
        assert body["health"]["glue_jobs"] == ["etl"]
        assert body["health"]["datasync_tasks"] == [{"id": "arn:1", "label": "nightly"}]

    def test_get_config_health_not_configured_when_empty(self) -> None:
        with (
            patch("backend.routers.config.config_repo.get_app_config", return_value=None),
            patch("backend.routers.config.settings") as mock_settings,
        ):
            mock_settings.aws_access_key_id = ""
            mock_settings.aws_secret_access_key = ""
            mock_settings.aws_region = ""
            mock_settings.github_repo = ""
            mock_settings.github_token = ""
            mock_settings.athena_database = ""
            mock_settings.athena_table = ""
            mock_settings.cloudwatch_log_groups = []
            resp = _CLIENT.get("/api/config")
        assert resp.json()["health"]["configured"] is False

    def test_patch_health_saves(self) -> None:
        row = _make_row(updated_at=_NOW)
        with patch("backend.routers.config.config_repo.upsert_health_config", return_value=row):
            resp = _CLIENT.patch(
                "/api/config/health",
                json={"glue_jobs": ["etl"], "datasync_tasks": [{"id": "a", "label": "b"}]},
            )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_patch_health_empty_body_ok(self) -> None:
        row = _make_row(updated_at=_NOW)
        with patch("backend.routers.config.config_repo.upsert_health_config", return_value=row):
            resp = _CLIENT.patch("/api/config/health", json={})
        assert resp.status_code == 200


class TestHealthProfiles:
    def test_list_profiles(self) -> None:
        profiles = [{"name": "Prod", "glue_jobs": ["j1"]}]
        with patch("backend.routers.config.config_repo.get_profiles", return_value=profiles):
            resp = _CLIENT.get("/api/config/health/profiles")
        assert resp.status_code == 200
        assert resp.json()["profiles"][0]["name"] == "Prod"

    def test_create_profile(self) -> None:
        created = {"name": "Prod", "glue_jobs": [], "glue_workflows": [],
                   "lambda_functions": [], "datasync_tasks": []}
        with patch("backend.routers.config.config_repo.create_profile", return_value=created):
            resp = _CLIENT.post("/api/config/health/profiles", json={"name": "Prod"})
        assert resp.status_code == 201
        assert resp.json()["name"] == "Prod"

    def test_create_duplicate_returns_409(self) -> None:
        from backend.repositories.config_repo import ProfileNameConflict

        with patch(
            "backend.routers.config.config_repo.create_profile",
            side_effect=ProfileNameConflict("Prod"),
        ):
            resp = _CLIENT.post("/api/config/health/profiles", json={"name": "Prod"})
        assert resp.status_code == 409

    def test_create_empty_name_returns_422(self) -> None:
        resp = _CLIENT.post("/api/config/health/profiles", json={"name": "   "})
        assert resp.status_code == 422

    def test_update_missing_returns_404(self) -> None:
        from backend.repositories.config_repo import ProfileNotFound

        with patch(
            "backend.routers.config.config_repo.update_profile",
            side_effect=ProfileNotFound("ghost"),
        ):
            resp = _CLIENT.patch(
                "/api/config/health/profiles", json={"name": "ghost", "glue_jobs": ["j"]}
            )
        assert resp.status_code == 404

    def test_rename_conflict_returns_409(self) -> None:
        from backend.repositories.config_repo import ProfileNameConflict

        with patch(
            "backend.routers.config.config_repo.rename_profile",
            side_effect=ProfileNameConflict("B"),
        ):
            resp = _CLIENT.post(
                "/api/config/health/profiles/rename", json={"name": "A", "new_name": "B"}
            )
        assert resp.status_code == 409

    def test_delete_missing_returns_404(self) -> None:
        from backend.repositories.config_repo import ProfileNotFound

        with patch(
            "backend.routers.config.config_repo.delete_profile",
            side_effect=ProfileNotFound("ghost"),
        ):
            resp = _CLIENT.delete("/api/config/health/profiles?name=ghost")
        assert resp.status_code == 404

    def test_delete_ok(self) -> None:
        with patch("backend.routers.config.config_repo.delete_profile", return_value=None):
            resp = _CLIENT.delete("/api/config/health/profiles?name=Prod")
        assert resp.status_code == 200
        assert resp.json()["success"] is True
