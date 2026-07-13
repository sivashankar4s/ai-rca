"""Tests for AnthropicLLMProvider — anthropic SDK client mocked at the boundary."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import anthropic
import httpx
import pytest

from backend.providers.llm.anthropic_provider import AnthropicLLMProvider


def _text_block(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


class _StreamCM:
    """Stand-in for the ``messages.stream(...)`` context manager."""

    def __init__(self, chunks: list[str]) -> None:
        self._chunks = chunks

    def __enter__(self):
        stream = MagicMock()
        stream.text_stream = iter(self._chunks)
        return stream

    def __exit__(self, *exc) -> bool:
        return False


def _provider_with_client() -> tuple[AnthropicLLMProvider, MagicMock]:
    client = MagicMock()
    with patch("backend.providers.llm.anthropic_provider.anthropic.Anthropic", return_value=client):
        provider = AnthropicLLMProvider()
    return provider, client


def _conn_error() -> anthropic.APIConnectionError:
    return anthropic.APIConnectionError(message="boom", request=httpx.Request("POST", "http://x"))


class TestInvoke:
    def test_returns_joined_text(self) -> None:
        provider, client = _provider_with_client()
        client.messages.create.return_value = SimpleNamespace(
            content=[_text_block("Hello "), _text_block("world")]
        )
        assert provider.invoke("hi") == "Hello world"

    def test_skips_non_text_blocks(self) -> None:
        provider, client = _provider_with_client()
        client.messages.create.return_value = SimpleNamespace(
            content=[SimpleNamespace(type="thinking", text="x"), _text_block("ok")]
        )
        assert provider.invoke("hi") == "ok"

    def test_wraps_api_error(self) -> None:
        provider, client = _provider_with_client()
        client.messages.create.side_effect = _conn_error()
        with pytest.raises(RuntimeError, match="LLM request failed"):
            provider.invoke("hi")


class TestInvokeStream:
    def test_yields_text_chunks(self) -> None:
        provider, client = _provider_with_client()
        client.messages.stream.return_value = _StreamCM(["root ", "cause"])
        assert "".join(provider.invoke_stream("hi")) == "root cause"

    def test_wraps_api_error(self) -> None:
        provider, client = _provider_with_client()
        client.messages.stream.side_effect = _conn_error()
        with pytest.raises(RuntimeError, match="LLM request failed"):
            list(provider.invoke_stream("hi"))
