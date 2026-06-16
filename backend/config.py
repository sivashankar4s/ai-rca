"""Runtime configuration (Constitution Principle V — Explicit Configuration).

All configuration flows through this module via ``pydantic-settings``. Defaults are
chosen so the application boots with no ``.env`` present: the local-file data source
reads ``./sample_failures.json`` and no AWS/LLM credentials are required to start.
Reading ``os.environ`` directly anywhere else in the codebase is prohibited.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global settings loaded from environment variables / ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Provider selection (Strategy Pattern) — resolved via plugin_registry.py.
    data_source_provider: str = "local_file"
    log_analysis_provider: str = "cloudwatch"
    llm_provider: str = "navify"

    # Local-file data source: when set, the app reads failures from this JSON file
    # and skips Athena/AWS entirely (useful for local dev and CI).
    local_data_file: str = "./sample_failures.json"

    # CRM persistence (PostgreSQL via SQLAlchemy + Alembic).
    database_url: str = "postgresql+psycopg2://postgres:root@localhost:5432/airca"

    # GitHub MCP (related code changes) — optional; empty means the feature is off.
    github_repo: str = ""
    github_token: str = ""


settings = Settings()
