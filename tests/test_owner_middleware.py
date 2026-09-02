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
async def test_owner_middleware_allows_owner():
    result = await OwnerAuthenticationMiddleware(
        owner_id=100, admin_ids=set(), rate_limiter=Limiter(True)
    ).authorize(100)
    assert result.allowed is True


@pytest.mark.asyncio
async def test_owner_middleware_allows_admin_id():
    result = await OwnerAuthenticationMiddleware(
        owner_id=100, admin_ids={8210327011}, rate_limiter=Limiter(True)
    ).authorize(8210327011)
    assert result.allowed is True


@pytest.mark.asyncio
async def test_owner_middleware_denies_random_user():
    result = await OwnerAuthenticationMiddleware(
        owner_id=100, admin_ids={8210327011}, rate_limiter=Limiter(True)
    ).authorize(101)
    assert result.allowed is False
    assert result.reason == "not_admin"


@pytest.mark.asyncio
async def test_empty_admin_ids_keeps_owner_only_access():
    middleware = OwnerAuthenticationMiddleware(
        owner_id=100, admin_ids=set(), rate_limiter=Limiter(True)
    )
    assert (await middleware.authorize(100)).allowed is True
    assert (await middleware.authorize(8210327011)).allowed is False


@pytest.mark.asyncio
async def test_owner_middleware_rate_limits_admin():
    result = await OwnerAuthenticationMiddleware(
        owner_id=100, admin_ids={8210327011}, rate_limiter=Limiter(False)
    ).authorize(8210327011)
    assert result.allowed is False
    assert result.reason == "rate_limited"
