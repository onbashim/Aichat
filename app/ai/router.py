from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Intent = Literal[
    "status",
    "approve_action",
    "reject_action",
    "set_mode",
    "set_autoreply",
    "recent_summary",
    "contact_query",
    "help",
    "ask_ai",
]


@dataclass(slots=True)
class RoutedCommand:
    intent: Intent
    argument: str | None = None
    chat_id: int | None = None
    mode: str | None = None
    enabled: bool | None = None


class AICommandRouter:
    MODE_RE = re.compile(
        r"(?:حالت|mode).*?(?P<chat>-?\d+).*?(?P<mode>ghost|copilot|autopilot)", re.I
    )
    AUTO_RE = re.compile(
        r"(?:auto\s*reply|اتو\s*ریپلای|پاسخ\s*خودکار).*?(?P<chat>-?\d+).*?(?P<state>روشن|خاموش|on|off)",
        re.I,
    )

    def route(self, text: str) -> RoutedCommand:
        cleaned = text.strip()
        lower = cleaned.casefold()
        if lower in {"status", "/status", "وضعیت", "وضعیت ربات"}:
            return RoutedCommand("status")
        if lower in {"start", "/start", "help", "/help", "راهنما", "کمک"}:
            return RoutedCommand("help")
        for prefix, intent in (
            ("تایید ", "approve_action"),
            ("approve ", "approve_action"),
            ("رد ", "reject_action"),
            ("reject ", "reject_action"),
        ):
            if lower.startswith(prefix):
                return RoutedCommand(intent, argument=cleaned[len(prefix) :].strip())
        match = self.MODE_RE.search(cleaned)
        if match:
            return RoutedCommand(
                "set_mode", chat_id=int(match.group("chat")), mode=match.group("mode").lower()
            )
        match = self.AUTO_RE.search(cleaned)
        if match:
            return RoutedCommand(
                "set_autoreply",
                chat_id=int(match.group("chat")),
                enabled=match.group("state").casefold() in {"روشن", "on"},
            )
        if any(
            p in lower for p in ("پیام‌های جدید", "پیام های جدید", "آخرین پیام", "recent messages")
        ):
            return RoutedCommand("recent_summary")
        if "چی گفته" in lower or "what did" in lower:
            return RoutedCommand("contact_query", argument=cleaned)
        return RoutedCommand("ask_ai", argument=cleaned)
