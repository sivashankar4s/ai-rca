"""Navify / OpenAI-compatible LLM provider."""

import json
import logging
from collections.abc import Iterator

import requests

from ...config import settings
from ...strategies.llm import LLMStrategy

logger = logging.getLogger(__name__)

_COMPLETIONS_PATH = "/v1/chat/completions"


class NavifyLLMProvider(LLMStrategy):
    """Thin wrapper around the custom OpenAI-compatible Navify LLM endpoint."""

    def __init__(self) -> None:
        base = (settings.llm_base_url or "").rstrip("/")
        self._url = f"{base}{_COMPLETIONS_PATH}"

    def invoke(self, prompt: str, max_tokens: int = 4096) -> str:
        if not settings.llm_api_key:
            raise RuntimeError("LLM_API_KEY is not configured.")
        if not settings.llm_base_url:
            raise RuntimeError("LLM_BASE_URL is not configured.")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.llm_api_key}",
        }
        payload = {
            "model": settings.llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }
        try:
            resp = requests.post(self._url, json=payload, headers=headers, timeout=120)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except requests.exceptions.HTTPError as exc:
            raise RuntimeError(
                f"LLM request failed with HTTP {exc.response.status_code}"
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(f"Cannot connect to LLM endpoint ({self._url})") from exc

    def invoke_stream(self, prompt: str, max_tokens: int = 4096) -> Iterator[str]:
        if not settings.llm_api_key:
            raise RuntimeError("LLM_API_KEY is not configured.")
        if not settings.llm_base_url:
            raise RuntimeError("LLM_BASE_URL is not configured.")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.llm_api_key}",
        }
        payload = {
            "model": settings.llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "stream": True,
        }
        try:
            resp = requests.post(
                self._url, json=payload, headers=headers, stream=True, timeout=120
            )
            resp.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            raise RuntimeError(
                f"LLM request failed with HTTP {exc.response.status_code}"
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(f"Cannot connect to LLM endpoint ({self._url})") from exc

        for raw in resp.iter_lines():
            if not raw:
                continue
            line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            if not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue
            delta = (chunk.get("choices") or [{}])[0].get("delta", {}).get("content")
            if delta:
                yield delta
