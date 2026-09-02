from __future__ import annotations

from app.ai.models import AIMessage, AIResult
from app.ai.prompts import COMMAND_SYSTEM_PROMPT, GHOST_SYSTEM_PROMPT, REPLY_SYSTEM_PROMPT
from app.ai.provider import AIProvider
from app.events.bus import EventBus
from app.events.types import Event, EventNames


class AIEngine:
    def __init__(self, provider: AIProvider, event_bus: EventBus) -> None:
        self.provider = provider; self.event_bus = event_bus

    async def analyze_message(self, text: str, *, trace_id: str) -> AIResult:
        await self.event_bus.publish(Event(EventNames.AI_REQUEST_STARTED, {"kind": "analysis"}, trace_id))
        result = await self.provider.generate([AIMessage("system", GHOST_SYSTEM_PROMPT), AIMessage("user", text)], trace_id=trace_id)
        await self.event_bus.publish(Event(EventNames.AI_RESPONSE_GENERATED, {"kind": "analysis", "model": result.model}, trace_id))
        return result

    async def draft_reply(self, text: str, *, trace_id: str, tone: str = "natural", language: str = "auto", custom_prompt: str | None = None, memory_context: str | None = None) -> AIResult:
        context = [f"Tone: {tone}", f"Language: {language}"]
        if custom_prompt: context.append(f"Owner instruction: {custom_prompt}")
        if memory_context: context.append(f"Relevant memory:\n{memory_context}")
        user_content = "\n".join(context) + f"\n\nIncoming message:\n{text}"
        await self.event_bus.publish(Event(EventNames.AI_REQUEST_STARTED, {"kind": "reply"}, trace_id))
        result = await self.provider.generate([AIMessage("system", REPLY_SYSTEM_PROMPT), AIMessage("user", user_content)], trace_id=trace_id)
        await self.event_bus.publish(Event(EventNames.AI_RESPONSE_GENERATED, {"kind": "reply", "model": result.model}, trace_id))
        return result

    async def answer_command(self, query: str, context: str, *, trace_id: str) -> AIResult:
        return await self.provider.generate([AIMessage("system", COMMAND_SYSTEM_PROMPT), AIMessage("user", f"Context:\n{context}\n\nOwner request:\n{query}")], trace_id=trace_id)
