from abc import ABC, abstractmethod


class LLMStrategy(ABC):
    """Runs a text prompt against any LLM backend."""

    @abstractmethod
    def invoke(self, prompt: str, max_tokens: int = 4096) -> str:
        """Return the model's text response."""
        ...
