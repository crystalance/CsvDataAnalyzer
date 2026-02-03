"""OpenAI LLM implementation."""

from typing import Generator

from openai import OpenAI

from config import Config
from .base import BaseLLM


class OpenAILLM(BaseLLM):
    """OpenAI LLM provider."""

    def __init__(self):
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.model = Config.OPENAI_MODEL

    def chat(self, messages: list[dict]) -> str:
        """Send messages to OpenAI and get a response."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        return response.choices[0].message.content or ""

    def chat_stream(self, messages: list[dict]) -> Generator[str, None, None]:
        """Send messages to OpenAI and stream the response."""
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True,
        )

        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
