import pytest

from app.telegram.middleware import OwnerAuthenticationMiddleware


class Limiter:
    def __init__(self, allowed: bool) -> None:
        self.allowed = allowed
        self.calls = 0

    async def allow(self, key: str) -> bool:
        self.calls += 1
        return self.allowed


@pytest.mark.asyncio
async def test_owner_middleware_rejects_non_owner_without_consuming_rate_limit():
    limiter = Limiter(True)
    middleware = OwnerAuthenticationMiddleware(owner_id=100, rate_limiter=limiter)
    result = await middleware.authorize(101)
    assert result.allowed is False
    assert result.reason == "not_owner"
    assert limiter.calls == 0


@pytest.mark.asyncio
async def test_owner_middleware_rate_limits_owner():
    result = await OwnerAuthenticationMiddleware(
        owner_id=100, rate_limiter=Limiter(False)
    ).authorize(100)
    assert result.allowed is False
    assert result.reason == "rate_limited"
