from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class BusinessPermissions:
    can_reply: bool = False
    can_read_messages: bool = False
    can_delete_sent_messages: bool = False
    can_delete_all_messages: bool = False

    @classmethod
    def from_rights(cls, rights: dict[str, Any] | None) -> BusinessPermissions:
        rights = rights or {}
        return cls(
            can_reply=bool(rights.get("can_reply")),
            can_read_messages=bool(rights.get("can_read_messages")),
            can_delete_sent_messages=bool(rights.get("can_delete_sent_messages")),
            can_delete_all_messages=bool(rights.get("can_delete_all_messages")),
        )
