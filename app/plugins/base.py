from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from typing import Any

from app.events.bus import EventHandler


@dataclass(frozen=True, slots=True)
class PluginMetadata:
    plugin_id: str
    name: str
    description: str
    version: str
    dependencies: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()


class BasePlugin(ABC):
    metadata: PluginMetadata

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        self.enabled = True

    def subscriptions(self) -> dict[str, EventHandler]:
        return {}

    def commands(self) -> tuple[str, ...]:
        return ()

    async def initialize(self) -> None:
        return None

    async def shutdown(self) -> None:
        return None
