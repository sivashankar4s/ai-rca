"""Tests for plugin_registry — factory functions for strategy resolution."""

from unittest.mock import patch

import pytest

from backend.plugin_registry import get_data_source, get_llm
from backend.providers.data_source.athena import AthenaDataSource
from backend.providers.data_source.local_file import LocalFileDataSource
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

    def test_unknown_provider_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown data_source_provider"):
            get_data_source("postgres")

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
