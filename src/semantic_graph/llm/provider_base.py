"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod


class LLMProviderBase(ABC):
    """Base interface for all LLM providers."""

    @abstractmethod
    async def complete(self, prompt: str) -> str:
        """Send a prompt and return the completion text."""
        ...
