"""Tests for log backend stubs — interface contract and NotImplementedError behaviour."""

from datetime import UTC, datetime

import pytest

from backend.providers.log_backend.cloudwatch import CloudWatchLogBackend
from backend.providers.log_backend.grafana_loki import GrafanaLokiLogBackend
from backend.strategies.log_analysis import LogAnalysisStrategy

_START = datetime(2026, 6, 1, tzinfo=UTC)
_END = datetime(2026, 6, 30, tzinfo=UTC)


class TestCloudWatchLogBackend:
    def test_implements_log_analysis_strategy(self) -> None:
        assert isinstance(CloudWatchLogBackend(), LogAnalysisStrategy)

    def test_query_logs_raises_not_implemented(self) -> None:
        lb = CloudWatchLogBackend()
        with pytest.raises(NotImplementedError):
            lb.query_logs("q", _START, _END)

    def test_query_logs_raises_with_log_group(self) -> None:
        lb = CloudWatchLogBackend()
        with pytest.raises(NotImplementedError):
            lb.query_logs("q", _START, _END, log_group="/aws/lambda/fn")


class TestGrafanaLokiLogBackend:
    def test_implements_log_analysis_strategy(self) -> None:
        assert isinstance(GrafanaLokiLogBackend(), LogAnalysisStrategy)

    def test_query_logs_raises_not_implemented(self) -> None:
        lb = GrafanaLokiLogBackend()
        with pytest.raises(NotImplementedError):
            lb.query_logs("q", _START, _END)

    def test_query_logs_raises_with_log_group(self) -> None:
        lb = GrafanaLokiLogBackend()
        with pytest.raises(NotImplementedError):
            lb.query_logs("q", _START, _END, log_group="my-bucket")
