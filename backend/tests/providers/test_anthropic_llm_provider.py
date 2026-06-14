from unittest.mock import MagicMock, patch

import pytest

from backend.config import settings
from backend.providers.llm.anthropic_provider import AnthropicLLMProvider


def test_invoke_requires_api_key():
    original = settings.anthropic_api_key
    try:
        settings.anthropic_api_key = ""
        provider = AnthropicLLMProvider()
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            provider.invoke("hello")
    finally:
        settings.anthropic_api_key = original


def test_invoke_success():
    original = settings.anthropic_api_key
    try:
        settings.anthropic_api_key = "fake-key"
        provider = AnthropicLLMProvider()

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "content": [{"type": "text", "text": "root cause: timeout"}],
            "stop_reason": "end_turn",
        }
        mock_resp.raise_for_status.return_value = None

        with patch("backend.providers.llm.anthropic_provider.requests.post", return_value=mock_resp) as mock_post:
            result = provider.invoke("what happened?", max_tokens=512)

        assert result == "root cause: timeout"
        _, kwargs = mock_post.call_args
        assert kwargs["headers"]["x-api-key"] == "fake-key"
        assert kwargs["headers"]["anthropic-version"] == "2023-06-01"
        assert kwargs["json"]["messages"] == [{"role": "user", "content": "what happened?"}]
        assert kwargs["json"]["max_tokens"] == 512
    finally:
        settings.anthropic_api_key = original
