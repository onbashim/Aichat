from __future__ import annotations

from abc import ABC, abstractmethod

from app.ai.models import AIMessage, AIResult


class AIProvider(ABC):
    @abstractmethod
    async def generate(self, messages: list[AIMessage], *, trace_id: str) -> AIResult:
        raise NotImplementedError


class OpenAIProvider(AIProvider):
    def __init__(self, api_key: str, model: str, timeout_seconds: float = 30.0, max_retries: int = 2) -> None:
        from openai import AsyncOpenAI

        self.model = model
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=max_retries)

    async def generate(self, messages: list[AIMessage], *, trace_id: str) -> AIResult:
        response = await self._client.responses.create(
            model=self.model,
            input=[{"role": item.role, "content": item.content} for item in messages],
            metadata={"trace_id": trace_id},
        )
        usage = getattr(response, "usage", None)
        return AIResult(
            text=response.output_text,
            model=self.model,
            input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
            metadata={"response_id": getattr(response, "id", None)},
        )


class UnavailableAIProvider(AIProvider):
    def __init__(self, reason: str = "OPENAI_API_KEY is not configured") -> None:
        self.reason = reason

    async def generate(self, messages: list[AIMessage], *, trace_id: str) -> AIResult:
        raise RuntimeError(self.reason)
