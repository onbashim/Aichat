from __future__ import annotations

from collections import OrderedDict

from app.events.bus import EventBus
from app.events.types import Event, EventNames
from app.plugins.base import BasePlugin


class PluginManager:
    def __init__(self, event_bus: EventBus) -> None:
        self.event_bus = event_bus
        self._plugins: OrderedDict[str, BasePlugin] = OrderedDict()
        self._started = False

    def register(self, plugin: BasePlugin) -> None:
        plugin_id = plugin.metadata.plugin_id
        if plugin_id in self._plugins:
            raise ValueError(f"Duplicate plugin id: {plugin_id}")
        self._plugins[plugin_id] = plugin

    def get(self, plugin_id: str) -> BasePlugin | None:
        return self._plugins.get(plugin_id)

    def all(self) -> tuple[BasePlugin, ...]:
        return tuple(self._plugins.values())

    def _resolve_order(self) -> list[BasePlugin]:
        resolved: list[BasePlugin] = []
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(plugin_id: str) -> None:
            if plugin_id in visited:
                return
            if plugin_id in visiting:
                raise ValueError(f"Circular plugin dependency involving {plugin_id}")
            plugin = self._plugins.get(plugin_id)
            if plugin is None:
                raise ValueError(f"Missing plugin dependency: {plugin_id}")
            visiting.add(plugin_id)
            for dep in plugin.metadata.dependencies:
                visit(dep)
            visiting.remove(plugin_id)
            visited.add(plugin_id)
            resolved.append(plugin)

        for plugin_id in self._plugins:
            visit(plugin_id)
        return resolved

    async def start(self) -> None:
        if self._started:
            return
        for plugin in self._resolve_order():
            await plugin.initialize()
            if plugin.enabled:
                for event_name, handler in plugin.subscriptions().items():
                    self.event_bus.subscribe(event_name, handler)
        self._started = True

    async def stop(self) -> None:
        for plugin in reversed(self._resolve_order()):
            for event_name, handler in plugin.subscriptions().items():
                self.event_bus.unsubscribe(event_name, handler)
            await plugin.shutdown()
        self._started = False

    async def enable(self, plugin_id: str) -> None:
        plugin = self._plugins[plugin_id]
        if plugin.enabled:
            return
        for dependency_id in plugin.metadata.dependencies:
            dependency = self._plugins.get(dependency_id)
            if dependency is None:
                raise ValueError(f"Missing plugin dependency: {dependency_id}")
            if not dependency.enabled:
                await self.enable(dependency_id)
        plugin.enabled = True
        for event_name, handler in plugin.subscriptions().items():
            self.event_bus.subscribe(event_name, handler)
        await self.event_bus.publish(Event(EventNames.PLUGIN_ENABLED, {"plugin_id": plugin_id}))

    async def disable(self, plugin_id: str) -> None:
        plugin = self._plugins[plugin_id]
        if not plugin.enabled:
            return
        dependents = [
            item.metadata.plugin_id
            for item in self._plugins.values()
            if item.enabled and plugin_id in item.metadata.dependencies
        ]
        if dependents:
            raise ValueError(
                f"Cannot disable {plugin_id}; enabled dependents: {', '.join(sorted(dependents))}"
            )
        plugin.enabled = False
        for event_name, handler in plugin.subscriptions().items():
            self.event_bus.unsubscribe(event_name, handler)
        await self.event_bus.publish(Event(EventNames.PLUGIN_DISABLED, {"plugin_id": plugin_id}))
