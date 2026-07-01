"""Tests for plugin_registry — factory functions for strategy resolution."""

from unittest.mock import patch

import pytest

from backend.plugin_registry import describe_providers, get_data_source, get_llm, get_log_backend
from backend.providers.data_source.athena import AthenaDataSource
from backend.providers.data_source.cloudwatch import CloudWatchDataSource
from backend.providers.data_source.local_file import LocalFileDataSource
from backend.providers.data_source.postgres import PostgresDataSource
from backend.providers.llm.navify import NavifyLLMProvider
from backend.strategies.data_source import DataSourceStrategy


class TestGetDataSource:
    def test_local_file_returns_local_file_data_source(self) -> None:
        ds = get_data_source("local_file")
        assert isinstance(ds, LocalFileDataSource)
        assert isinstance(ds, DataSourceStrategy)

    def test_athena_returns_athena_data_source(self) -> None:
        ds = get_data_source("athena")
        assert isinstance(ds, AthenaDataSource)
        assert isinstance(ds, DataSourceStrategy)

    def test_none_uses_settings_provider(self) -> None:
        with patch("backend.plugin_registry.settings") as mock_settings:
            mock_settings.data_source_provider = "local_file"
            mock_settings.local_data_file = "./sample_failures.json"
            ds = get_data_source()
        assert isinstance(ds, LocalFileDataSource)

    def test_postgres_returns_postgres_data_source(self) -> None:
        ds = get_data_source("postgres")
        assert isinstance(ds, PostgresDataSource)
        assert isinstance(ds, DataSourceStrategy)

    def test_cloudwatch_returns_cloudwatch_data_source(self) -> None:
        ds = get_data_source("cloudwatch")
        assert isinstance(ds, CloudWatchDataSource)
        assert isinstance(ds, DataSourceStrategy)

    def test_cloudwatch_forwards_db_aws_credentials(self) -> None:
        from types import SimpleNamespace
        from unittest.mock import MagicMock

        row = SimpleNamespace(
            cloudwatch_config={"log_groups": ["/aws/lambda/x"], "query_timeout": 30},
            aws_config={
                "access_key_id": "DB_KEY",
                "secret_access_key": "DB_SECRET",
                "region": "ap-south-1",
            },
        )
        with (
            patch("backend.plugin_registry.config_repo.get_app_config", return_value=row),
            patch("backend.providers.data_source.cloudwatch.boto3.client") as mock_client,
        ):
            ds = get_data_source("cloudwatch", db=MagicMock())
        assert ds._log_groups == ["/aws/lambda/x"]
        _, kwargs = mock_client.call_args
        assert kwargs["aws_access_key_id"] == "DB_KEY"
        assert kwargs["aws_secret_access_key"] == "DB_SECRET"
        assert kwargs["region_name"] == "ap-south-1"

    def test_cloudwatch_without_db_creds_falls_back(self) -> None:
        from types import SimpleNamespace
        from unittest.mock import MagicMock

        row = SimpleNamespace(
            cloudwatch_config={"log_groups": ["/aws/lambda/x"]},
            aws_config=None,
        )
        with (
            patch("backend.plugin_registry.config_repo.get_app_config", return_value=row),
            patch("backend.providers.data_source.cloudwatch.boto3.client") as mock_client,
            patch("backend.providers.data_source.cloudwatch.settings") as mock_settings,
        ):
            mock_settings.aws_region = "eu-west-1"
            mock_settings.aws_access_key_id = "ENV_KEY"
            mock_settings.aws_secret_access_key = "ENV_SECRET"
            mock_settings.aws_session_token = ""
            get_data_source("cloudwatch", db=MagicMock())
        _, kwargs = mock_client.call_args
        assert kwargs["aws_access_key_id"] == "ENV_KEY"
        assert kwargs["region_name"] == "eu-west-1"

    def test_unknown_provider_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown data_source_provider"):
            get_data_source("mysql")

    def test_local_file_path_comes_from_settings(self) -> None:
        with patch("backend.plugin_registry.settings") as mock_settings:
            mock_settings.data_source_provider = "local_file"
            mock_settings.local_data_file = "/custom/path/failures.json"
            ds = get_data_source("local_file")
        assert isinstance(ds, LocalFileDataSource)
        assert ds._path == "/custom/path/failures.json"


class TestGetLlm:
    def test_navify_provider_returns_navify_instance(self) -> None:
        with patch("backend.plugin_registry.settings") as mock_settings:
            mock_settings.llm_provider = "navify"
            mock_settings.llm_base_url = "http://llm.example.com"
            result = get_llm()
        assert isinstance(result, NavifyLLMProvider)

    def test_openai_provider_returns_navify_instance(self) -> None:
        with patch("backend.plugin_registry.settings") as mock_settings:
            mock_settings.llm_provider = "openai"
            mock_settings.llm_base_url = "http://llm.example.com"
            result = get_llm()
        assert isinstance(result, NavifyLLMProvider)

    def test_unknown_provider_raises_value_error(self) -> None:
        with patch("backend.plugin_registry.settings") as mock_settings:
            mock_settings.llm_provider = "gpt-unknown"
            with pytest.raises(ValueError, match="Unknown llm_provider"):
                get_llm()
class TestGetLogBackend:
    def test_cloudwatch_returns_cloudwatch_backend(self) -> None:
        from backend.providers.log_backend.cloudwatch import CloudWatchLogBackend
        from backend.strategies.log_analysis import LogAnalysisStrategy

        lb = get_log_backend("cloudwatch")
        assert isinstance(lb, CloudWatchLogBackend)
        assert isinstance(lb, LogAnalysisStrategy)

    def test_grafana_loki_returns_grafana_loki_backend(self) -> None:
        from backend.providers.log_backend.grafana_loki import GrafanaLokiLogBackend
        from backend.strategies.log_analysis import LogAnalysisStrategy

        lb = get_log_backend("grafana_loki")
        assert isinstance(lb, GrafanaLokiLogBackend)
        assert isinstance(lb, LogAnalysisStrategy)

    def test_none_uses_settings_log_analysis_provider(self) -> None:
        from backend.providers.log_backend.cloudwatch import CloudWatchLogBackend

        with patch("backend.plugin_registry.settings") as mock_settings:
            mock_settings.log_analysis_provider = "cloudwatch"
            lb = get_log_backend()
        assert isinstance(lb, CloudWatchLogBackend)

    def test_unknown_backend_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown log_analysis_provider"):
            get_log_backend("splunk")


class TestDescribeProviders:
    def test_returns_providers_response_shape(self) -> None:
        result = describe_providers()
        assert len(result.data_sources) == 3
        assert len(result.log_backends) == 2

    def test_exactly_one_data_source_default(self) -> None:
        with patch("backend.plugin_registry.settings") as mock_settings:
            mock_settings.data_source_provider = "athena"
            mock_settings.log_analysis_provider = "cloudwatch"
            result = describe_providers()
        defaults = [ds for ds in result.data_sources if ds.is_default]
        assert len(defaults) == 1
        assert defaults[0].id == "athena"

    def test_postgres_default_when_configured(self) -> None:
        with patch("backend.plugin_registry.settings") as mock_settings:
            mock_settings.data_source_provider = "postgres"
            mock_settings.log_analysis_provider = "cloudwatch"
            result = describe_providers()
        postgres = next(ds for ds in result.data_sources if ds.id == "postgres")
        assert postgres.is_default is True

    def test_local_file_mode_maps_to_athena_default(self) -> None:
        with patch("backend.plugin_registry.settings") as mock_settings:
            mock_settings.data_source_provider = "local_file"
            mock_settings.log_analysis_provider = "cloudwatch"
            result = describe_providers()
        athena = next(ds for ds in result.data_sources if ds.id == "athena")
        assert athena.is_default is True

    def test_log_backend_default_reflects_settings(self) -> None:
        with patch("backend.plugin_registry.settings") as mock_settings:
            mock_settings.data_source_provider = "athena"
            mock_settings.log_analysis_provider = "grafana_loki"
            result = describe_providers()
        loki = next(lb for lb in result.log_backends if lb.id == "grafana_loki")
        assert loki.is_default is True
        cw = next(lb for lb in result.log_backends if lb.id == "cloudwatch")
        assert cw.is_default is False

    def test_provider_ids_and_labels_present(self) -> None:
        result = describe_providers()
        ids = {ds.id for ds in result.data_sources}
        assert ids == {"athena", "postgres", "cloudwatch"}
        lb_ids = {lb.id for lb in result.log_backends}
        assert lb_ids == {"cloudwatch", "grafana_loki"}
