import logging

import requests

from ...config import settings
from ...strategies.llm import LLMStrategy

logger = logging.getLogger(__name__)

_COMPLETIONS_PATH = "/v1/chat/completions"


class NavifyLLMProvider(LLMStrategy):
    """Thin wrapper around the custom OpenAI-compatible Navify LLM endpoint."""

    def __init__(self):
        base = settings.llm_base_url.rstrip("/")
        self._url = f"{base}{_COMPLETIONS_PATH}"
        if not settings.llm_api_key:
            logger.warning(
                "LLM_API_KEY is not set — set it in .env before making LLM calls"
            )
        logger.debug(
            "LLM client initialised  url=%s  model=%s",
            self._url,
            settings.llm_model,
        )

    def invoke(self, prompt: str, max_tokens: int = 4096) -> str:
        if not settings.llm_api_key:
            raise RuntimeError(
                "LLM_API_KEY is not configured. Set it in .env and restart the server."
            )

        logger.info(
            "Invoking LLM  url=%s  model=%s  prompt_chars=%d  max_tokens=%d",
            self._url,
            settings.llm_model,
            len(prompt),
            max_tokens,
        )

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {settings.llm_api_key}",
        }
        payload = {
            "model": settings.llm_model,
            "user": "onedbm-golden-griffins",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }

        try:
            resp = requests.post(
                self._url,
                json=payload,
                headers=headers,
                timeout=120,
            )
            resp.raise_for_status()
            result = resp.json()
            text = result["choices"][0]["message"]["content"]
            logger.info(
                "LLM response received  model=%s  response_chars=%d  finish_reason=%s",
                settings.llm_model,
                len(text),
                result["choices"][0].get("finish_reason", "unknown"),
            )
            logger.info("LLM response content:\n%s", text[:1000])
            return text

        except requests.exceptions.HTTPError as e:
            logger.error(
                "LLM HTTP error  status=%d  url=%s  body=%s",
                e.response.status_code,
                self._url,
                e.response.text[:500],
                exc_info=True,
            )
            raise RuntimeError(
                f"LLM request failed with HTTP {e.response.status_code}: {e.response.text[:200]}"
            ) from e

        except requests.exceptions.ConnectionError as e:
            logger.error("LLM connection error  url=%s  error=%s", self._url, e, exc_info=True)
            raise RuntimeError(f"Cannot connect to LLM endpoint ({self._url}): {e}") from e

        except Exception as e:
            logger.error("LLM invocation failed  error=%s", e, exc_info=True)
            raise
