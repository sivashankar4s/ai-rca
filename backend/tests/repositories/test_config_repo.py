"""Repository tests for config_repo — run against a real test DB (Constitution IV)."""

import pytest
from sqlalchemy.orm import Session

from backend.models.schemas import HealthConfigUpdate, HealthProfileUpdate, HealthResource
from backend.repositories import config_repo
from backend.repositories.config_repo import ProfileNameConflict, ProfileNotFound


class TestGetAppConfig:
    def test_returns_none_when_table_empty(self, db_session: Session) -> None:
        result = config_repo.get_app_config(db_session)
        assert result is None

    def test_returns_row_after_upsert(self, db_session: Session) -> None:
        config_repo._upsert_app_config(
            db_session, aws_config={"access_key_id": "AK", "secret_access_key": "SK"}
        )
        result = config_repo.get_app_config(db_session)
        assert result is not None
        assert result.id == 1

    def test_second_upsert_updates_same_row(self, db_session: Session) -> None:
        config_repo._upsert_app_config(db_session, aws_config={"access_key_id": "AK1"})
        config_repo._upsert_app_config(db_session, aws_config={"access_key_id": "AK2"})
        result = config_repo.get_app_config(db_session)
        assert result is not None
        assert result.aws_config["access_key_id"] == "AK2"


class TestUpsertAwsConfig:
    def test_stores_access_key_id_and_secret(self, db_session: Session) -> None:
        from backend.models.schemas import AwsConfigUpdate

        data = AwsConfigUpdate(access_key_id="AKIATEST", secret_access_key="mysecret")
        config_repo.upsert_aws_config(db_session, data)
        row = config_repo.get_app_config(db_session)
        assert row is not None
        assert row.aws_config["access_key_id"] == "AKIATEST"
        assert row.aws_config["secret_access_key"] == "mysecret"

    def test_mask_sentinel_preserves_existing_secret(self, db_session: Session) -> None:
        from backend.models.schemas import MASK_SENTINEL, AwsConfigUpdate

        config_repo._upsert_app_config(
            db_session, aws_config={"access_key_id": "AK", "secret_access_key": "original"}
        )
        data = AwsConfigUpdate(access_key_id="AK", secret_access_key=MASK_SENTINEL)
        config_repo.upsert_aws_config(db_session, data)
        row = config_repo.get_app_config(db_session)
        assert row is not None
        assert row.aws_config["secret_access_key"] == "original"

    def test_mask_sentinel_is_never_stored(self, db_session: Session) -> None:
        from backend.models.schemas import MASK_SENTINEL, AwsConfigUpdate

        data = AwsConfigUpdate(access_key_id="AK", secret_access_key=MASK_SENTINEL)
        config_repo.upsert_aws_config(db_session, data)
        row = config_repo.get_app_config(db_session)
        assert row is not None
        assert row.aws_config.get("secret_access_key") is None

    def test_clearing_secret_stores_none(self, db_session: Session) -> None:
        from backend.models.schemas import AwsConfigUpdate

        config_repo._upsert_app_config(
            db_session, aws_config={"access_key_id": "AK", "secret_access_key": "s"}
        )
        data = AwsConfigUpdate(access_key_id="AK", secret_access_key="new_secret")
        data.secret_access_key = ""
        config_repo._upsert_app_config(
            db_session, aws_config={"access_key_id": "AK", "secret_access_key": None}
        )
        row = config_repo.get_app_config(db_session)
        assert row is not None
        assert row.aws_config.get("secret_access_key") is None

    def test_stores_session_token(self, db_session: Session) -> None:
        from backend.models.schemas import AwsConfigUpdate

        data = AwsConfigUpdate(
            access_key_id="ASIATEST", secret_access_key="SK", session_token="TOKEN123"
        )
        config_repo.upsert_aws_config(db_session, data)
        row = config_repo.get_app_config(db_session)
        assert row is not None
        assert row.aws_config["session_token"] == "TOKEN123"

    def test_session_token_none_when_absent(self, db_session: Session) -> None:
        from backend.models.schemas import AwsConfigUpdate

        data = AwsConfigUpdate(access_key_id="AK", secret_access_key="SK")
        config_repo.upsert_aws_config(db_session, data)
        row = config_repo.get_app_config(db_session)
        assert row is not None
        assert row.aws_config.get("session_token") is None

    def test_mask_sentinel_preserves_existing_session_token(self, db_session: Session) -> None:
        from backend.models.schemas import MASK_SENTINEL, AwsConfigUpdate

        config_repo._upsert_app_config(
            db_session,
            aws_config={"access_key_id": "AK", "secret_access_key": "s", "session_token": "orig"},
        )
        data = AwsConfigUpdate(
            access_key_id="AK", secret_access_key=MASK_SENTINEL, session_token=MASK_SENTINEL
        )
        config_repo.upsert_aws_config(db_session, data)
        row = config_repo.get_app_config(db_session)
        assert row is not None
        assert row.aws_config["session_token"] == "orig"

    def test_stores_region(self, db_session: Session) -> None:
        from backend.models.schemas import AwsConfigUpdate

        data = AwsConfigUpdate(access_key_id="AK", secret_access_key="SK", region="eu-west-1")
        config_repo.upsert_aws_config(db_session, data)
        row = config_repo.get_app_config(db_session)
        assert row is not None
        assert row.aws_config["region"] == "eu-west-1"


class TestUpsertGithubMcpConfig:
    def test_stores_repo_and_token(self, db_session: Session) -> None:
        from backend.models.schemas import GithubMcpConfigUpdate

        data = GithubMcpConfigUpdate(repo="owner/repo", token="ghp_test")
        config_repo.upsert_github_mcp_config(db_session, data)
        row = config_repo.get_app_config(db_session)
        assert row is not None
        assert row.github_mcp_config["repo"] == "owner/repo"
        assert row.github_mcp_config["token"] == "ghp_test"

    def test_mask_sentinel_preserves_existing_token(self, db_session: Session) -> None:
        from backend.models.schemas import MASK_SENTINEL, GithubMcpConfigUpdate

        config_repo._upsert_app_config(
            db_session, github_mcp_config={"repo": "o/r", "token": "original_token"}
        )
        data = GithubMcpConfigUpdate(repo="o/r", token=MASK_SENTINEL)
        config_repo.upsert_github_mcp_config(db_session, data)
        row = config_repo.get_app_config(db_session)
        assert row is not None
        assert row.github_mcp_config["token"] == "original_token"

    def test_mask_sentinel_not_stored_when_no_existing_token(self, db_session: Session) -> None:
        from backend.models.schemas import MASK_SENTINEL, GithubMcpConfigUpdate

        data = GithubMcpConfigUpdate(repo="o/r", token=MASK_SENTINEL)
        config_repo.upsert_github_mcp_config(db_session, data)
        row = config_repo.get_app_config(db_session)
        assert row is not None
        assert row.github_mcp_config.get("token") is None

    def test_stores_default_branch(self, db_session: Session) -> None:
        from backend.models.schemas import GithubMcpConfigUpdate

        data = GithubMcpConfigUpdate(repo="o/r", token="t", default_branch="develop")
        config_repo.upsert_github_mcp_config(db_session, data)
        row = config_repo.get_app_config(db_session)
        assert row is not None
        assert row.github_mcp_config["default_branch"] == "develop"


class TestUpsertCloudwatchConfig:
    def test_stores_log_groups(self, db_session: Session) -> None:
        from backend.models.schemas import CloudWatchConfigUpdate

        data = CloudWatchConfigUpdate(log_groups=["/aws/lambda/a", "/aws/lambda/b"])
        config_repo.upsert_cloudwatch_config(db_session, data)
        row = config_repo.get_app_config(db_session)
        assert row is not None
        assert row.cloudwatch_config["log_groups"] == ["/aws/lambda/a", "/aws/lambda/b"]
        assert "query_timeout" not in row.cloudwatch_config

    def test_stores_query_timeout(self, db_session: Session) -> None:
        from backend.models.schemas import CloudWatchConfigUpdate

        data = CloudWatchConfigUpdate(log_groups=["/aws/lambda/a"], query_timeout=120)
        config_repo.upsert_cloudwatch_config(db_session, data)
        row = config_repo.get_app_config(db_session)
        assert row is not None
        assert row.cloudwatch_config["query_timeout"] == 120


class TestUpsertAthenaConfig:
    def test_stores_database_and_table(self, db_session: Session) -> None:
        from backend.models.schemas import AthenaConfigUpdate

        data = AthenaConfigUpdate(database="mydb", table="mytable")
        config_repo.upsert_athena_config(db_session, data)
        row = config_repo.get_app_config(db_session)
        assert row is not None
        assert row.athena_config["database"] == "mydb"
        assert row.athena_config["table"] == "mytable"

    def test_trims_whitespace(self, db_session: Session) -> None:
        from backend.models.schemas import AthenaConfigUpdate

        data = AthenaConfigUpdate(database="  mydb  ", table="  mytable  ")
        config_repo.upsert_athena_config(db_session, data)
        row = config_repo.get_app_config(db_session)
        assert row is not None
        assert row.athena_config["database"] == "mydb"
        assert row.athena_config["table"] == "mytable"


class TestUpsertHealthConfig:
    def test_stores_all_four_lists(self, db_session: Session) -> None:
        from backend.models.schemas import HealthConfigUpdate, HealthResource

        data = HealthConfigUpdate(
            glue_jobs=["etl"],
            glue_workflows=["wf"],
            lambda_functions=["fn"],
            datasync_tasks=[HealthResource(id="arn:1", label="nightly")],
        )
        config_repo.upsert_health_config(db_session, data)
        row = config_repo.get_app_config(db_session)
        assert row is not None
        assert row.health_config["glue_jobs"] == ["etl"]
        assert row.health_config["glue_workflows"] == ["wf"]
        assert row.health_config["lambda_functions"] == ["fn"]
        assert row.health_config["datasync_tasks"] == [{"id": "arn:1", "label": "nightly"}]

    def test_empty_lists_allowed(self, db_session: Session) -> None:
        from backend.models.schemas import HealthConfigUpdate

        config_repo.upsert_health_config(db_session, HealthConfigUpdate())
        row = config_repo.get_app_config(db_session)
        assert row is not None
        assert row.health_config["glue_jobs"] == []
        assert row.health_config["datasync_tasks"] == []

    def test_resave_overwrites(self, db_session: Session) -> None:
        from backend.models.schemas import HealthConfigUpdate

        config_repo.upsert_health_config(db_session, HealthConfigUpdate(glue_jobs=["a"]))
        config_repo.upsert_health_config(db_session, HealthConfigUpdate(glue_jobs=["b"]))
        row = config_repo.get_app_config(db_session)
        assert row is not None
        assert row.health_config["glue_jobs"] == ["b"]


class TestHealthProfiles:
    def test_no_profiles_returns_empty(self, db_session: Session) -> None:
        config_repo._upsert_app_config(db_session, health_config=None, health_profiles=None)
        assert config_repo.get_profiles(db_session) == []

    def test_legacy_config_surfaces_as_default(self, db_session: Session) -> None:
        config_repo.upsert_health_config(db_session, HealthConfigUpdate(glue_jobs=["etl"]))
        profiles = config_repo.get_profiles(db_session)
        assert len(profiles) == 1
        assert profiles[0]["name"] == "Default"
        assert profiles[0]["glue_jobs"] == ["etl"]

    def test_managed_empty_list_wins_over_legacy(self, db_session: Session) -> None:
        config_repo.upsert_health_config(db_session, HealthConfigUpdate(glue_jobs=["etl"]))
        config_repo._persist_profiles(db_session, [])
        assert config_repo.get_profiles(db_session) == []

    def test_legacy_profile_list_in_health_config_is_returned(self, db_session: Session) -> None:
        row = config_repo._upsert_app_config(
            db_session,
            health_config=[{"name": "Prod", "glue_jobs": ["etl"], "datasync_tasks": []}],
        )
        db_session.commit()
        assert row.health_config == [{"name": "Prod", "glue_jobs": ["etl"], "datasync_tasks": []}]
        assert config_repo.get_profiles(db_session) == [
            {"name": "Prod", "glue_jobs": ["etl"], "datasync_tasks": []}
        ]

    def test_malformed_legacy_health_config_list_is_ignored(self, db_session: Session) -> None:
        row = config_repo._upsert_app_config(db_session, health_config=["bad-shape"])
        db_session.commit()
        assert row.health_config == ["bad-shape"]
        assert config_repo.get_profiles(db_session) == []

    def test_create_and_get_profile(self, db_session: Session) -> None:
        config_repo.create_profile(db_session, "Prod ETL")
        resources = config_repo.get_profile_resources(db_session, "Prod ETL")
        assert resources is not None
        assert resources["name"] == "Prod ETL"
        assert resources["glue_jobs"] == []

    def test_create_duplicate_name_is_case_insensitive_conflict(self, db_session: Session) -> None:
        config_repo.create_profile(db_session, "Prod")
        with pytest.raises(ProfileNameConflict):
            config_repo.create_profile(db_session, "  prod  ")

    def test_create_materializes_legacy_default(self, db_session: Session) -> None:
        config_repo.upsert_health_config(db_session, HealthConfigUpdate(glue_jobs=["etl"]))
        config_repo.create_profile(db_session, "New")
        names = {p["name"] for p in config_repo.get_profiles(db_session)}
        assert names == {"Default", "New"}

    def test_update_replaces_resources(self, db_session: Session) -> None:
        config_repo.create_profile(db_session, "P")
        config_repo.update_profile(
            db_session,
            HealthProfileUpdate(
                name="P",
                lambda_functions=["fn"],
                datasync_tasks=[HealthResource(id="arn:1", label="nightly")],
            ),
        )
        resources = config_repo.get_profile_resources(db_session, "P")
        assert resources["lambda_functions"] == ["fn"]
        assert resources["datasync_tasks"] == [{"id": "arn:1", "label": "nightly"}]

    def test_update_missing_raises_not_found(self, db_session: Session) -> None:
        with pytest.raises(ProfileNotFound):
            config_repo.update_profile(db_session, HealthProfileUpdate(name="ghost"))

    def test_rename_profile(self, db_session: Session) -> None:
        config_repo._upsert_app_config(db_session, health_config=None, health_profiles=None)
        config_repo.create_profile(db_session, "Old")
        config_repo.rename_profile(db_session, "Old", "New")
        names = {p["name"] for p in config_repo.get_profiles(db_session)}
        assert names == {"New"}

    def test_rename_to_existing_raises_conflict(self, db_session: Session) -> None:
        config_repo.create_profile(db_session, "A")
        config_repo.create_profile(db_session, "B")
        with pytest.raises(ProfileNameConflict):
            config_repo.rename_profile(db_session, "A", "b")

    def test_rename_missing_raises_not_found(self, db_session: Session) -> None:
        with pytest.raises(ProfileNotFound):
            config_repo.rename_profile(db_session, "ghost", "x")

    def test_delete_profile(self, db_session: Session) -> None:
        config_repo._upsert_app_config(db_session, health_config=None, health_profiles=None)
        config_repo.create_profile(db_session, "A")
        config_repo.create_profile(db_session, "B")
        config_repo.delete_profile(db_session, "A")
        names = {p["name"] for p in config_repo.get_profiles(db_session)}
        assert names == {"B"}

    def test_delete_missing_raises_not_found(self, db_session: Session) -> None:
        with pytest.raises(ProfileNotFound):
            config_repo.delete_profile(db_session, "ghost")

    def test_get_profile_resources_default_is_first(self, db_session: Session) -> None:
        config_repo._upsert_app_config(db_session, health_config=None, health_profiles=None)
        config_repo.create_profile(db_session, "First")
        config_repo.create_profile(db_session, "Second")
        assert config_repo.get_profile_resources(db_session)["name"] == "First"
