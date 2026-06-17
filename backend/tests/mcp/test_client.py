"""Tests for backend.mcp.client.call_github_tool (the public synchronous API)."""

from unittest.mock import MagicMock, patch

import pytest

from backend.config import settings
from backend.mcp.client import call_github_tool


def test_call_github_tool_raises_when_no_token():
    original = settings.github_token
    try:
        settings.github_token = ""
        with pytest.raises(RuntimeError, match="GITHUB_TOKEN is not configured"):
            call_github_tool("any_tool", {})
    finally:
        settings.github_token = original


def test_call_github_tool_returns_executor_result():
    original = settings.github_token
    try:
        settings.github_token = "fake-token"
        mock_future = MagicMock()
        mock_future.result.return_value = {"key": "value"}

        mock_executor = MagicMock()
        mock_executor.__enter__ = MagicMock(return_value=mock_executor)
        mock_executor.__exit__ = MagicMock(return_value=False)
        mock_executor.submit.return_value = mock_future

        with patch("backend.mcp.client.concurrent.futures.ThreadPoolExecutor",
                   return_value=mock_executor):
            result = call_github_tool("some_tool", {"arg": "val"})

        assert result == {"key": "value"}
        mock_future.result.assert_called_once_with(timeout=30)
    finally:
        settings.github_token = original
