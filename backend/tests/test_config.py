"""Settings defaults — verifies Constitution Principle V (Explicit Configuration)."""

from backend.config import Settings, settings


def test_defaults_boot_without_env() -> None:
    """App must start with no .env present; local_file is the default data source."""
    s = Settings(_env_file=None)
    assert s.data_source_provider == "local_file"
    assert s.local_data_file == "./sample_failures.json"
    assert s.log_analysis_provider == "cloudwatch"
    assert s.llm_provider == "navify"
    assert "postgresql" in s.database_url


def test_module_level_singleton_exists() -> None:
    """The module-level ``settings`` singleton must be a ``Settings`` instance."""
    assert isinstance(settings, Settings)


def test_overridable_via_env(monkeypatch) -> None:
    """Environment variables override defaults (pydantic-settings contract)."""
    monkeypatch.setenv("DATA_SOURCE_PROVIDER", "athena")
    monkeypatch.setenv("LOCAL_DATA_FILE", "/tmp/custom.json")
    s = Settings()
    assert s.data_source_provider == "athena"
    assert s.local_data_file == "/tmp/custom.json"
