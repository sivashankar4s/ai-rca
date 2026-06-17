"""Grafana Loki log backend (stub — log analysis not yet implemented)."""

from datetime import datetime

from backend.strategies.log_analysis import LogAnalysisStrategy


class GrafanaLokiLogBackend(LogAnalysisStrategy):
    """Stub Grafana Loki log backend — returns empty results until implemented."""

    def query_logs(
        self,
        query: str,
        start: datetime,
        end: datetime,
        log_group: str | None = None,
    ) -> tuple[list[str], str]:
        raise NotImplementedError("Grafana Loki log analysis is not yet implemented")
