"""Anthropic LLM provider — calls Claude via the official ``anthropic`` SDK.

Honours ``LLM_BASE_URL`` when set (e.g. an internal Anthropic-compatible gateway),
otherwise talks to the default Anthropic API. Credentials come from ``LLM_API_KEY``.
"""

import logging
from collections.abc import Iterator

import anthropic

from ...config import settings
from ...strategies.llm import LLMStrategy

logger = logging.getLogger(__name__)


class AnthropicLLMProvider(LLMStrategy):
    """Claude access through the Anthropic Messages API (streaming + non-streaming)."""

    def __init__(self) -> None:
        self._model = settings.llm_model
        self._client = anthropic.Anthropic(
            api_key=settings.llm_api_key or None,
            base_url=settings.llm_base_url or None,
        )

    def invoke(self, prompt: str, max_tokens: int = 4096) -> str:
        try:
            message = self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.APIError as exc:
            raise RuntimeError(f"LLM request failed: {exc}") from exc
        return "".join(block.text for block in message.content if block.type == "text")

    def invoke_stream(self, prompt: str, max_tokens: int = 4096) -> Iterator[str]:
        try:
            with self._client.messages.stream(
                model=self._model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                yield from stream.text_stream
        except anthropic.APIError as exc:
            raise RuntimeError(f"LLM request failed: {exc}") from exc
