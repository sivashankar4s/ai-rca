"""LLMStrategy ABC — Constitution Principle III."""

from abc import ABC, abstractmethod


class LLMStrategy(ABC):
    """Abstract interface for LLM providers used in the code-review pipeline."""

    @abstractmethod
    def invoke(self, prompt: str, max_tokens: int = 4096) -> str:
        """Run a text prompt and return the model's text response."""
