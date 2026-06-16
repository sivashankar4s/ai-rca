from abc import ABC, abstractmethod


class DataSourceStrategy(ABC):
    """Fetches raw failure/event records from any monitoring store."""

    @abstractmethod
    def fetch_records(
        self,
        time_range: str,
        component: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        failure_only: bool = True,
    ) -> list[dict]:
        """Return a list of raw record dicts."""
        ...
