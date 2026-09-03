from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

UpdateKind = Literal[
    "message",
    "business_connection",
    "business_message",
    "edited_business_message",
    "deleted_business_messages",
    "callback_query",
    "unknown",
]


@dataclass(slots=True)
class ParsedUpdate:
    update_id: int
    kind: UpdateKind
    payload: dict[str, Any]


class TelegramUpdateParser:
    SUPPORTED = (
        "business_connection",
        "business_message",
        "edited_business_message",
        "deleted_business_messages",
        "callback_query",
        "message",
    )

    def parse(self, update: dict[str, Any]) -> ParsedUpdate:
        update_id = int(update["update_id"])
        for key in self.SUPPORTED:
            if key in update:
                return ParsedUpdate(update_id, key, update[key])
        return ParsedUpdate(update_id, "unknown", update)
