from __future__ import annotations

from app.plugins.base import BasePlugin, PluginMetadata


class PlaceholderPlugin(BasePlugin):
    def __init__(self, plugin_id: str, name: str, description: str, version: str = "0.1.0") -> None:
        self.metadata = PluginMetadata(plugin_id, name, description, version)
        super().__init__()
        self.enabled = False


def future_plugins() -> tuple[PlaceholderPlugin, ...]:
    specs = (
        ("smart_inbox", "Smart Inbox", "Priority and inbox intelligence"),
        ("translator", "Translator", "Per-chat translation workflows"),
        ("summaries", "Summaries", "Conversation and digest summaries"),
        ("reminders", "Reminders", "Reminder and follow-up automation"),
        ("voice_ai", "Voice AI", "Voice transcription and voice response workflows"),
        ("web_search", "Web Search", "Web search and research integration"),
        ("file_analyzer", "File Analyzer", "Document and file analysis"),
        ("calendar", "Calendar", "Calendar integration"),
        ("task_manager", "Task Manager", "Task lifecycle and assignments"),
    )
    return tuple(PlaceholderPlugin(*spec) for spec in specs)
