# app/llm/client.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Dict, Optional

from openai import OpenAI

from app.config import get_settings


class LLMClient(ABC):
    """
    Simple abstraction so we can swap providers if needed.
    """

    @abstractmethod
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        model: Optional[str] = None,
    ) -> str:
        """
        messages: list of {"role": "system"|"user"|"assistant", "content": "..."}
        returns: assistant content as a string
        """
        ...


class OpenAILLMClient(LLMClient):
    """
    OpenAI implementation using the official Python client.
    """

    def __init__(self, model: Optional[str] = None):
        settings = get_settings()
        if not settings.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set in environment (.env)."
            )

        # The OpenAI() client will pick up api_key automatically from env if not passed,
        # but we pass it explicitly for clarity.
        self.client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
        self.default_model = model or settings.llm_model

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        model: Optional[str] = None,
    ) -> str:
        completion = self.client.chat.completions.create(
            model=model or self.default_model,
            messages=messages,
            temperature=temperature,
        )
        content = completion.choices[0].message.content
        return content or ""
