from __future__ import annotations

import hmac


def is_owner(user_id: int | None, owner_id: int | None) -> bool:
    return user_id is not None and owner_id is not None and int(user_id) == int(owner_id)


def verify_webhook_secret(received: str | None, expected: str | None) -> bool:
    if not received or not expected:
        return False
    return hmac.compare_digest(received, expected)
