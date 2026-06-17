"""Plugin registry — resolves provider names to concrete strategy instances."""

from backend.config import settings
from backend.models.schemas import ProviderOption, ProvidersResponse
from backend.providers.data_source.athena import AthenaDataSource
from backend.providers.data_source.local_file import LocalFileDataSource
from backend.providers.data_source.postgres import PostgresDataSource
from backend.strategies.data_source import DataSourceStrategy
from backend.strategies.llm import LLMStrategy
from backend.strategies.log_analysis import LogAnalysisStrategy

_DATA_SOURCE_CATALOGUE: list[tuple[str, str]] = [
    ("athena", "Amazon Athena"),
    ("postgres", "Stored history (Postgres)"),
]

_LOG_BACKEND_CATALOGUE: list[tuple[str, str]] = [
    ("cloudwatch", "CloudWatch Logs Insights"),
    ("grafana_loki", "Grafana Loki"),
]


def get_data_source(provider: str | None = None) -> DataSourceStrategy:
    """Return a DataSourceStrategy for the given provider name (defaults to settings)."""
    if provider is None:
        provider = settings.data_source_provider
    if provider == "local_file":
        return LocalFileDataSource(settings.local_data_file)
    if provider == "athena":
        return AthenaDataSource()
    if provider == "postgres":
        return PostgresDataSource()
    raise ValueError(f"Unknown data_source_provider: {provider!r}")


def get_log_backend(override: str | None = None) -> LogAnalysisStrategy:
    """Return a LogAnalysisStrategy for the given backend name (defaults to settings)."""
    provider = override or settings.log_analysis_provider
    if provider == "cloudwatch":
        from backend.providers.log_backend.cloudwatch import CloudWatchLogBackend

        return CloudWatchLogBackend()
    if provider == "grafana_loki":
        from backend.providers.log_backend.grafana_loki import GrafanaLokiLogBackend

        return GrafanaLokiLogBackend()
    raise ValueError(f"Unknown log_analysis_provider: {provider!r}")


def get_llm() -> LLMStrategy:
    """Return an LLMStrategy for the configured provider."""
    provider = settings.llm_provider
    if provider in ("navify", "openai"):
        from backend.providers.llm.navify import NavifyLLMProvider

        return NavifyLLMProvider()
    raise ValueError(f"Unknown llm_provider: {provider!r}")


def describe_providers() -> ProvidersResponse:
    """Report available data sources and log backends with their defaults (FR-005)."""
    effective_ds = settings.data_source_provider
    if effective_ds == "local_file":
        effective_ds = "athena"

    data_sources = [
        ProviderOption(id=pid, label=label, is_default=(pid == effective_ds))
        for pid, label in _DATA_SOURCE_CATALOGUE
    ]
    log_backends = [
        ProviderOption(id=pid, label=label, is_default=(pid == settings.log_analysis_provider))
        for pid, label in _LOG_BACKEND_CATALOGUE
    ]
    return ProvidersResponse(data_sources=data_sources, log_backends=log_backends)
