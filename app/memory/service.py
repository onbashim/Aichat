from __future__ import annotations

from uuid import UUID

from app.events.bus import EventBus
from app.events.types import Event, EventNames
from app.repositories.core import CoreRepository


class MemoryService:
    def __init__(self, repository: CoreRepository, event_bus: EventBus) -> None:
        self.repository = repository; self.event_bus = event_bus

    async def context_for_chat(self, chat_id: int) -> str:
        memories = await self.repository.list_memories(chat_id)
        return "\n".join(f"- {m.memory_type}/{m.key}: {m.value}" for m in memories)

    async def create(self, *, chat_id: int | None, memory_type: str, key: str, value: str, importance: int = 0):
        memory = await self.repository.create_memory(chat_id=chat_id, memory_type=memory_type, key=key, value=value, importance=importance)
        await self.event_bus.publish(Event(EventNames.MEMORY_CREATED, {"memory_id": str(memory.id)}))
        return memory

    async def delete(self, memory_id: UUID) -> bool:
        return await self.repository.delete_memory(memory_id)
