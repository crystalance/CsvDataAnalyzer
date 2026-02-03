"""Qwen (通义千问) LLM implementation using DashScope."""

from typing import Generator

import dashscope
from dashscope import Generation

from config import Config
from .base import BaseLLM


class QwenLLM(BaseLLM):
    """Qwen LLM provider using DashScope API."""

    def __init__(self):
        dashscope.api_key = Config.DASHSCOPE_API_KEY
        self.model = Config.QWEN_MODEL

    def chat(self, messages: list[dict]) -> str:
        """Send messages to Qwen and get a response."""
        response = Generation.call(
            model=self.model,
            messages=messages,
            result_format="message",
        )

        if response.status_code == 200:
            return response.output.choices[0].message.content
        else:
            raise Exception(
                f"Qwen API error: {response.code} - {response.message}"
            )

    def chat_stream(self, messages: list[dict]) -> Generator[str, None, None]:
        """Send messages to Qwen and stream the response."""
        responses = Generation.call(
            model=self.model,
            messages=messages,
            result_format="message",
            stream=True,
            incremental_output=True,
        )

        for response in responses:
            if response.status_code == 200:
                content = response.output.choices[0].message.content
                if content:
                    yield content
            else:
                raise Exception(
                    f"Qwen API error: {response.code} - {response.message}"
                )
