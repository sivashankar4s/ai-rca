"""LLMStrategy ABC — Constitution Principle III."""

from abc import ABC, abstractmethod
from typing import Any


class LLMStrategy(ABC):
    """Abstract interface for LLM providers used in the RCA pipeline."""

    @abstractmethod
    def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        """Send a chat-completion request and return the assistant text response."""
