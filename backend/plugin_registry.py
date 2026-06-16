"""Plugin registry — resolves provider names to concrete strategy instances."""

from backend.config import settings
from backend.providers.data_source.athena import AthenaDataSource
from backend.providers.data_source.local_file import LocalFileDataSource
from backend.strategies.data_source import DataSourceStrategy


def get_data_source(provider: str | None = None) -> DataSourceStrategy:
    """Return a DataSourceStrategy for the given provider name (defaults to settings)."""
    if provider is None:
        provider = settings.data_source_provider
    if provider == "local_file":
        return LocalFileDataSource(settings.local_data_file)
    if provider == "athena":
        return AthenaDataSource()
    raise ValueError(f"Unknown data_source_provider: {provider!r}")
