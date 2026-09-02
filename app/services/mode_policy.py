from __future__ import annotations

from dataclasses import dataclass

from app.database.models import ChatSettings, TelegramBusinessConnection
from app.permissions.service import BusinessPermissions


@dataclass(frozen=True, slots=True)
class AutopilotDecision:
    allowed: bool
    reason: str


def can_autopilot(
    settings: ChatSettings,
    connection: TelegramBusinessConnection,
    *,
    ai_automation_enabled: bool,
    autopilot_enabled: bool,
) -> AutopilotDecision:
    if not ai_automation_enabled:
        return AutopilotDecision(False, "global_ai_automation_disabled")
    if not autopilot_enabled:
        return AutopilotDecision(False, "global_autopilot_disabled")
    if not connection.active:
        return AutopilotDecision(False, "business_connection_inactive")
    if settings.mode != "autopilot":
        return AutopilotDecision(False, "chat_not_in_autopilot_mode")
    if not settings.enabled or settings.blocked:
        return AutopilotDecision(False, "chat_disabled_or_blocked")
    if not settings.auto_reply:
        return AutopilotDecision(False, "chat_auto_reply_disabled")
    if settings.requires_approval:
        return AutopilotDecision(False, "chat_requires_approval")
    if not BusinessPermissions.from_rights(connection.rights).can_reply:
        return AutopilotDecision(False, "telegram_can_reply_missing")
    return AutopilotDecision(True, "allowed")
