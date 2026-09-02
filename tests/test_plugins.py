import pytest

from app.events.bus import EventBus
from app.plugins.base import BasePlugin, PluginMetadata
from app.plugins.manager import PluginManager


class PluginA(BasePlugin):
    metadata = PluginMetadata("a", "A", "base", "1.0.0")


class PluginB(BasePlugin):
    metadata = PluginMetadata("b", "B", "dependent", "1.0.0", dependencies=("a",))


@pytest.mark.asyncio
async def test_plugin_manager_resolves_dependencies():
    manager = PluginManager(EventBus())
    manager.register(PluginB())
    manager.register(PluginA())
    assert [p.metadata.plugin_id for p in manager._resolve_order()] == ["a", "b"]
    await manager.start()
    await manager.stop()


def test_plugin_manager_rejects_missing_dependency():
    manager = PluginManager(EventBus())
    manager.register(PluginB())
    with pytest.raises(ValueError, match="Missing plugin dependency"):
        manager._resolve_order()


@pytest.mark.asyncio
async def test_enabling_plugin_enables_dependencies_first():
    manager = PluginManager(EventBus())
    a = PluginA()
    b = PluginB()
    a.enabled = False
    b.enabled = False
    manager.register(b)
    manager.register(a)
    await manager.enable("b")
    assert a.enabled and b.enabled


@pytest.mark.asyncio
async def test_disabling_dependency_with_enabled_dependent_is_rejected():
    manager = PluginManager(EventBus())
    a = PluginA()
    b = PluginB()
    manager.register(a)
    manager.register(b)
    with pytest.raises(ValueError, match="enabled dependents"):
        await manager.disable("a")
