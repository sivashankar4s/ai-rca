from abc import ABC, abstractmethod


class LogAnalysisStrategy(ABC):
    """Executes a structured log query on any observability backend."""

    @abstractmethod
    def execute_query(
        self,
        query: str,
        time_range: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[str]:
        """Return a list of matching log line strings."""
        ...

    @abstractmethod
    def build_deep_link(
        self,
        region: str,
        log_group: str,
        component: str,
        time_range: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> str:
        """Return a browser-ready deep link into the observability UI."""
        ...
