from __future__ import annotations

from dataclasses import dataclass

from app.core.rate_limit import SlidingWindowRateLimiter
from app.core.security import is_owner


@dataclass(frozen=True, slots=True)
class OwnerAuthResult:
    allowed: bool
    reason: str


class OwnerAuthenticationMiddleware:
    def __init__(self, *, owner_id: int | None, rate_limiter: SlidingWindowRateLimiter) -> None:
        self.owner_id = owner_id
        self.rate_limiter = rate_limiter

    async def authorize(self, user_id: int | None) -> OwnerAuthResult:
        if not is_owner(user_id, self.owner_id):
            return OwnerAuthResult(False, "not_owner")
        if not await self.rate_limiter.allow(f"owner:{int(user_id)}"):
            return OwnerAuthResult(False, "rate_limited")
        return OwnerAuthResult(True, "allowed")
