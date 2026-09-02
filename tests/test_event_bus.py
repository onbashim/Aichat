import pytest

from app.events.bus import EventBus
from app.events.types import Event


@pytest.mark.asyncio
async def test_event_bus_publishes_to_subscribers():
    bus = EventBus()
    seen = []

    async def handler(event):
        seen.append(event.payload["value"])

    bus.subscribe("test.event", handler)
    errors = await bus.publish(Event("test.event", {"value": 42}))
    assert errors == []
    assert seen == [42]
