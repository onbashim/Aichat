from __future__ import annotations

from dataclasses import dataclass

from app.core.rate_limit import SlidingWindowRateLimiter
from app.core.security import is_admin


@dataclass(frozen=True, slots=True)
class OwnerAuthResult:
    allowed: bool
    reason: str


class OwnerAuthenticationMiddleware:
    def __init__(
        self,
        *,
        owner_id: int | None,
        admin_ids: set[int] | None = None,
        rate_limiter: SlidingWindowRateLimiter,
    ) -> None:
        self.owner_id = owner_id
        self.admin_ids = admin_ids or set()
        self.rate_limiter = rate_limiter

    async def authorize(self, user_id: int | None) -> OwnerAuthResult:
        if not is_admin(user_id, self.owner_id, self.admin_ids):
            return OwnerAuthResult(False, "not_admin")
        if not await self.rate_limiter.allow(f"admin:{int(user_id)}"):
            return OwnerAuthResult(False, "rate_limited")
        return OwnerAuthResult(True, "allowed")
