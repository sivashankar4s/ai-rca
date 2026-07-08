"""Plugin registry — resolves provider names to concrete strategy instances."""

from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from backend.models.schemas import HealthServiceType
    from backend.strategies.health_check import HealthCheckStrategy

from backend.config import settings
from backend.models.schemas import ProviderOption, ProvidersResponse
from backend.providers.data_source.athena import AthenaDataSource
from backend.providers.data_source.cloudwatch import CloudWatchDataSource
from backend.providers.data_source.local_file import LocalFileDataSource
from backend.providers.data_source.postgres import PostgresDataSource
from backend.repositories import config_repo
from backend.strategies.data_source import DataSourceStrategy
from backend.strategies.llm import LLMStrategy
from backend.strategies.log_analysis import LogAnalysisStrategy

_DATA_SOURCE_CATALOGUE: list[tuple[str, str]] = [
    ("athena", "Amazon Athena"),
    ("postgres", "Stored history (Postgres)"),
    ("cloudwatch", "CloudWatch (Lambda logs)"),
]

_LOG_BACKEND_CATALOGUE: list[tuple[str, str]] = [
    ("cloudwatch", "CloudWatch Logs Insights"),
    ("grafana_loki", "Grafana Loki"),
]


def _build_athena_source(db: Session | None) -> AthenaDataSource:
    """Build AthenaDataSource from the DB config (app_config), env as fallback."""
    database: str | None = None
    table: str | None = None
    if db is not None:
        row = config_repo.get_app_config(db)
        cfg = (row.athena_config or {}) if row else None
        if cfg and cfg.get("database") and cfg.get("table"):
            database = cfg["database"]
            table = cfg["table"]
    return AthenaDataSource(database=database, table=table)


def _build_cloudwatch_source(db: Session | None) -> CloudWatchDataSource:
    """Build CloudWatchDataSource from the DB config (app_config), env as fallback.

    Log groups/timeout come from ``cloudwatch_config`` and AWS credentials from
    ``aws_config`` — both saved on the Config page. Either falls back to env
    settings when the DB row is absent or incomplete.
    """
    log_groups: list[str] | None = None
    query_timeout: int | None = None
    aws_credentials: dict | None = None
    if db is not None:
        row = config_repo.get_app_config(db)
        cfg = (row.cloudwatch_config or {}) if row else None
        if cfg and cfg.get("log_groups"):
            log_groups = cfg["log_groups"]
            query_timeout = cfg.get("query_timeout")
        aws_cfg = (row.aws_config or {}) if row else None
        if aws_cfg and aws_cfg.get("access_key_id") and aws_cfg.get("secret_access_key"):
            aws_credentials = {
                "access_key_id": aws_cfg.get("access_key_id"),
                "secret_access_key": aws_cfg.get("secret_access_key"),
                "session_token": aws_cfg.get("session_token"),
                "region": aws_cfg.get("region"),
            }
    return CloudWatchDataSource(
        log_groups=log_groups,
        query_timeout=query_timeout,
        aws_credentials=aws_credentials,
    )


def get_data_source(provider: str | None = None, db: Session | None = None) -> DataSourceStrategy:
    """Return a DataSourceStrategy for the given provider name (defaults to settings).

    ``db`` is used by the CloudWatch and Athena sources to read their config
    from the config page (app_config), falling back to env settings when absent.
    """
    if provider is None:
        provider = settings.data_source_provider
    if provider == "local_file":
        return LocalFileDataSource(settings.local_data_file)
    if provider == "athena":
        return _build_athena_source(db)
    if provider == "postgres":
        return PostgresDataSource()
    if provider == "cloudwatch":
        return _build_cloudwatch_source(db)
    raise ValueError(f"Unknown data_source_provider: {provider!r}")


def get_cloudwatch_source(
    db: Session | None, log_groups: list[str] | None = None
) -> CloudWatchDataSource:
    """Build a CloudWatch data source scoped to specific ``log_groups``.

    Used for per-resource failure drill-down (e.g. a Lambda's own ``/aws/lambda/<name>``
    log group). AWS credentials come from ``app_config`` (env fallback), as elsewhere.
    """
    return CloudWatchDataSource(
        log_groups=log_groups, aws_credentials=_aws_credentials_from_db(db)
    )


def _aws_credentials_from_db(db: Session | None) -> dict | None:
    """Read AWS credentials from app_config (aws_config), or None to fall back to env."""
    if db is None:
        return None
    row = config_repo.get_app_config(db)
    aws_cfg = (row.aws_config or {}) if row else None
    if aws_cfg and aws_cfg.get("access_key_id") and aws_cfg.get("secret_access_key"):
        return {
            "access_key_id": aws_cfg.get("access_key_id"),
            "secret_access_key": aws_cfg.get("secret_access_key"),
            "session_token": aws_cfg.get("session_token"),
            "region": aws_cfg.get("region"),
        }
    return None


def get_health_checkers(
    db: Session | None = None,
) -> "dict[HealthServiceType, HealthCheckStrategy]":
    """Return one health-check provider per service type, keyed by service type.

    AWS credentials come from the Config page (app_config ``aws_config``) when present,
    falling back to env settings otherwise — the single-source pattern used across the app.
    """
    from backend.models.schemas import HealthServiceType
    from backend.providers.health_check.datasync import DataSyncHealthCheck
    from backend.providers.health_check.glue_job import GlueJobHealthCheck
    from backend.providers.health_check.glue_workflow import GlueWorkflowHealthCheck
    from backend.providers.health_check.lambda_fn import LambdaHealthCheck

    creds = _aws_credentials_from_db(db)
    return {
        HealthServiceType.GLUE_JOB: GlueJobHealthCheck(aws_credentials=creds),
        HealthServiceType.GLUE_WORKFLOW: GlueWorkflowHealthCheck(aws_credentials=creds),
        HealthServiceType.LAMBDA_FUNCTION: LambdaHealthCheck(aws_credentials=creds),
        HealthServiceType.DATASYNC_TASK: DataSyncHealthCheck(aws_credentials=creds),
    }


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
    if provider == "anthropic":
        from backend.providers.llm.anthropic_provider import AnthropicLLMProvider

        return AnthropicLLMProvider()
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
