"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod
from typing import Generator


class BaseLLM(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def chat(self, messages: list[dict]) -> str:
        """
        Send messages to the LLM and get a response.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.

        Returns:
            The assistant's response text.
        """
        pass

    @abstractmethod
    def chat_stream(self, messages: list[dict]) -> Generator[str, None, None]:
        """
        Send messages to the LLM and stream the response.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.

        Yields:
            Chunks of the response text.
        """
        pass
