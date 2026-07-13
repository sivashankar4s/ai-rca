"""LLMStrategy ABC — Constitution Principle III."""

from abc import ABC, abstractmethod
from collections.abc import Iterator


class LLMStrategy(ABC):
    """Abstract interface for LLM providers used in the code-review pipeline."""

    @abstractmethod
    def invoke(self, prompt: str, max_tokens: int = 4096) -> str:
        """Run a text prompt and return the model's text response."""

    def invoke_stream(self, prompt: str, max_tokens: int = 4096) -> Iterator[str]:
        """Run a text prompt and yield the response incrementally (token chunks)."""
        raise NotImplementedError
