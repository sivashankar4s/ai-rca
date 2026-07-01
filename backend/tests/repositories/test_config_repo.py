"""Repository tests for config_repo — run against a real test DB (Constitution IV)."""

from sqlalchemy.orm import Session

from backend.repositories import config_repo


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

        data = AwsConfigUpdate(
            access_key_id="AK", secret_access_key="SK", region="eu-west-1"
        )
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
