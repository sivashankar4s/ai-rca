import logging

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_PLACEHOLDER_PATTERNS = ("your-bucket", "your_bucket", "change-me", "<", ">")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        frozen=False,          # allow in-memory mutation via the config API
        validate_assignment=False,  # skip re-validation on assignment for speed
    )

    # AWS
    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_session_token: str = ""

    # Athena
    athena_database: str = "default"
    athena_table: str = "monitoring_table"
    athena_output_bucket: str = ""

    # Local development — set LOCAL_DATA_FILE to skip Athena/S3 entirely
    local_data_file: str = ""
    # Directory where Athena result snapshots are saved (empty = disabled)
    snapshots_dir: str = "./snapshots"

    # CloudWatch
    cloudwatch_log_group: str = "/aws/application/logs"

    # Custom LLM (OpenAI-compatible)
    llm_base_url: str = "https://enrichment-dev-nightly.usw2.ds.platform.navify.com"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o"

    # CRM persistence (Postgres via SQLAlchemy + Alembic)
    database_url: str = "postgresql+psycopg2://airca:airca@localhost:5432/airca"

    # Provider selection (Strategy Pattern)
    data_source_provider: str = "athena"          # DATA_SOURCE_PROVIDER env var
    llm_provider: str = "navify"                  # LLM_PROVIDER env var
    log_analysis_provider: str = "cloudwatch"     # LOG_ANALYSIS_PROVIDER env var

    # Grafana / Loki (only needed when log_analysis_provider = "grafana_loki")
    grafana_loki_url: str = ""                    # GRAFANA_LOKI_URL
    grafana_api_key: str = ""                     # GRAFANA_API_KEY
    grafana_datasource_uid: str = ""              # GRAFANA_DATASOURCE_UID (for deep links)

    def validate_required(self) -> None:
        """Raise ValueError for missing or placeholder configuration values."""
        errors: list[str] = []

        # Skip S3 / Athena validation entirely when using local data
        if not self.local_data_file:
            if not self.athena_output_bucket:
                errors.append("ATHENA_OUTPUT_BUCKET is not set (must be an s3:// URI).")
            elif any(p in self.athena_output_bucket for p in _PLACEHOLDER_PATTERNS):
                errors.append(
                    f"ATHENA_OUTPUT_BUCKET still contains a placeholder value: "
                    f"'{self.athena_output_bucket}'. Set it to a real s3:// URI."
                )

        if self.athena_database == "default" and not self.local_data_file:
            logger.warning(
                "ATHENA_DATABASE is set to 'default'. "
                "Override with your actual database name if needed."
            )

        if errors:
            raise ValueError(
                "Invalid configuration — fix the following before starting:\n  • "
                + "\n  • ".join(errors)
            )


settings = Settings()


def get_boto3_kwargs() -> dict:
    """Returns credential kwargs for boto3 - falls back to IAM role if keys not set."""
    kwargs = {"region_name": settings.aws_region}
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
        if settings.aws_session_token:
            kwargs["aws_session_token"] = settings.aws_session_token
    return kwargs
