from types import SimpleNamespace

import pytest

from app.repositories.chat_control import resolve_chat_for_owner


class FakeSession:
    def __init__(self, *results):
        self.results = list(results)
        self.scalar_calls = 0

    async def scalar(self, statement):
        self.scalar_calls += 1
        return self.results.pop(0)


class FakeRepo:
    def __init__(self, *scalar_results):
        self.session = FakeSession(*scalar_results)
        self.ensure_calls = []

    async def ensure_chat(self, connection_id, payload):
        self.ensure_calls.append((connection_id, payload))
        return SimpleNamespace(telegram_chat_id=payload["id"])


@pytest.mark.asyncio
async def test_resolver_returns_existing_chat_on_active_business_connection():
    connection = SimpleNamespace(id="biz-1")
    existing = SimpleNamespace(telegram_chat_id=8210327011)
    repo = FakeRepo(connection, existing)

    result = await resolve_chat_for_owner(
        repo,
        telegram_chat_id=8210327011,
        owner_telegram_user_id=100,
    )

    assert result is existing
    assert repo.session.scalar_calls == 2
    assert repo.ensure_calls == []


@pytest.mark.asyncio
async def test_resolver_creates_unseen_chat_on_active_business_connection():
    connection = SimpleNamespace(id="biz-1")
    repo = FakeRepo(connection, None)

    result = await resolve_chat_for_owner(
        repo,
        telegram_chat_id=8210327011,
        owner_telegram_user_id=100,
    )

    assert result.telegram_chat_id == 8210327011
    assert repo.ensure_calls == [
        ("biz-1", {"id": 8210327011, "type": "private"}),
    ]


@pytest.mark.asyncio
async def test_resolver_returns_none_without_active_business_connection():
    repo = FakeRepo(None)

    result = await resolve_chat_for_owner(
        repo,
        telegram_chat_id=8210327011,
        owner_telegram_user_id=100,
    )

    assert result is None
    assert repo.session.scalar_calls == 1
    assert repo.ensure_calls == []
