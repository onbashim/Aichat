from __future__ import annotations

import asyncio
import inspect
from collections import defaultdict
from collections.abc import Awaitable, Callable

from app.events.types import Event

EventHandler = Callable[[Event], Awaitable[None] | None]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        if handler not in self._subscribers[event_name]:
            self._subscribers[event_name].append(handler)

    def unsubscribe(self, event_name: str, handler: EventHandler) -> None:
        handlers = self._subscribers.get(event_name, [])
        if handler in handlers:
            handlers.remove(handler)

    async def publish(self, event: Event) -> list[BaseException]:
        errors: list[BaseException] = []

        async def invoke(handler: EventHandler) -> None:
            try:
                result = handler(event)
                if inspect.isawaitable(result):
                    await result
            except BaseException as exc:
                errors.append(exc)

        await asyncio.gather(*(invoke(h) for h in tuple(self._subscribers.get(event.name, []))))
        return errors

    def subscriber_count(self, event_name: str) -> int:
        return len(self._subscribers.get(event_name, []))
