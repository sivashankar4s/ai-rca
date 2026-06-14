import logging

import requests

from ...config import settings
from ...strategies.llm import LLMStrategy

logger = logging.getLogger(__name__)

_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"


class AnthropicLLMProvider(LLMStrategy):
    """Calls Anthropic's Messages API directly using the user's Anthropic API key."""

    def __init__(self):
        if not settings.anthropic_api_key:
            logger.warning(
                "ANTHROPIC_API_KEY is not set — set it in .env before making LLM calls"
            )
        logger.debug("Anthropic LLM client initialised  model=%s", settings.llm_model)

    def invoke(self, prompt: str, max_tokens: int = 4096) -> str:
        if not settings.anthropic_api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not configured. Set it in .env and restart the server."
            )

        logger.info(
            "Invoking Anthropic LLM  model=%s  prompt_chars=%d  max_tokens=%d",
            settings.llm_model,
            len(prompt),
            max_tokens,
        )

        headers = {
            "Content-Type": "application/json",
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
        }
        payload = {
            "model": settings.llm_model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }

        try:
            resp = requests.post(
                _MESSAGES_URL,
                json=payload,
                headers=headers,
                timeout=120,
            )
            resp.raise_for_status()
            result = resp.json()
            text = "".join(
                block.get("text", "")
                for block in result.get("content", [])
                if block.get("type") == "text"
            )
            logger.info(
                "Anthropic LLM response received  model=%s  response_chars=%d  stop_reason=%s",
                settings.llm_model,
                len(text),
                result.get("stop_reason", "unknown"),
            )
            logger.info("LLM response content:\n%s", text[:1000])
            return text

        except requests.exceptions.HTTPError as e:
            logger.error(
                "Anthropic LLM HTTP error  status=%d  body=%s",
                e.response.status_code,
                e.response.text[:500],
                exc_info=True,
            )
            raise RuntimeError(
                f"LLM request failed with HTTP {e.response.status_code}: {e.response.text[:200]}"
            ) from e

        except requests.exceptions.ConnectionError as e:
            logger.error("Anthropic LLM connection error  error=%s", e, exc_info=True)
            raise RuntimeError(f"Cannot connect to Anthropic endpoint ({_MESSAGES_URL}): {e}") from e

        except Exception as e:
            logger.error("Anthropic LLM invocation failed  error=%s", e, exc_info=True)
            raise
