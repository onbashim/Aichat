from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


class EventNames:
    TELEGRAM_MESSAGE_RECEIVED = "telegram.message.received"
    TELEGRAM_MESSAGE_SENT = "telegram.message.sent"
    TELEGRAM_BUSINESS_CONNECTED = "telegram.business.connected"
    TELEGRAM_BUSINESS_DISCONNECTED = "telegram.business.disconnected"
    TELEGRAM_MESSAGE_EDITED = "telegram.message.edited"
    TELEGRAM_MESSAGES_DELETED = "telegram.messages.deleted"
    AI_REQUEST_STARTED = "ai.request.started"
    AI_RESPONSE_GENERATED = "ai.response.generated"
    AI_ACTION_REQUESTED = "ai.action.requested"
    MEMORY_CREATED = "memory.created"
    MEMORY_UPDATED = "memory.updated"
    PLUGIN_ENABLED = "plugin.enabled"
    PLUGIN_DISABLED = "plugin.disabled"
    AUTOMATION_TRIGGERED = "automation.triggered"


@dataclass(slots=True)
class Event:
    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
