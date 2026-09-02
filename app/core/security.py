from __future__ import annotations

import hmac


def is_owner(user_id: int | None, owner_id: int | None) -> bool:
    return user_id is not None and owner_id is not None and int(user_id) == int(owner_id)


def is_admin(user_id: int | None, owner_id: int | None, admin_ids: set[int] | None = None) -> bool:
    if user_id is None:
        return False
    if is_owner(user_id, owner_id):
        return True
    return int(user_id) in (admin_ids or set())


def verify_webhook_secret(received: str | None, expected: str | None) -> bool:
    if not received or not expected:
        return False
    return hmac.compare_digest(received, expected)
