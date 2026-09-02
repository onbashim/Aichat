from types import SimpleNamespace

import pytest

from app.ai.models import AIResult
from app.core.config import Settings
from app.events.bus import EventBus
from app.services.orchestrator import ConversationOrchestrator


class FakeAI:
    def __init__(self):
        self.analysis_calls = 0
        self.reply_calls = 0

    async def analyze_message(self, text, *, trace_id):
        self.analysis_calls += 1
        return AIResult("internal analysis", "fake-model", 10, 5)

    async def draft_reply(self, text, **kwargs):
        self.reply_calls += 1
        return AIResult("draft reply", "fake-model", 10, 5)


class FakeTelegram:
    def __init__(self):
        self.bot_messages = []
        self.business_messages = []

    async def send_bot_message(self, chat_id, text):
        self.bot_messages.append((chat_id, text))
        return {"message_id": 1}

    async def send_business_message(self, **payload):
        self.business_messages.append(payload)
        return {"message_id": 2}


class AllowAllLimiter:
    async def allow(self, key):
        return True


class FakeRepo:
    def __init__(self, mode):
        self.connection = SimpleNamespace(
            id="biz-1", owner_telegram_user_id=1, active=True, rights={"can_reply": True}
        )
        settings = SimpleNamespace(
            mode=mode,
            enabled=True,
            blocked=False,
            auto_reply=mode == "autopilot",
            requires_approval=False if mode == "autopilot" else True,
            memory_enabled=False,
            tone="natural",
            language="auto",
            custom_prompt=None,
        )
        self.chat = SimpleNamespace(id=5, telegram_chat_id=200, settings=settings)
        self.actions = []

    async def get_connection(self, connection_id):
        return self.connection

    async def ensure_chat(self, connection_id, payload):
        return self.chat

    async def save_message(self, chat, payload, direction):
        return None

    async def list_memories(self, chat_id, limit=20):
        return []

    async def add_ai_request(self, **kwargs):
        return None

    async def add_audit(self, **kwargs):
        return None

    async def create_action(self, **kwargs):
        action = SimpleNamespace(id="action-1", **kwargs)
        self.actions.append(action)
        return action


PAYLOAD = {
    "business_connection_id": "biz-1",
    "message_id": 10,
    "date": 1700000000,
    "from": {"id": 999},
    "chat": {"id": 200, "type": "private"},
    "text": "hello",
}


@pytest.mark.asyncio
async def test_ghost_mode_never_sends_message():
    ai = FakeAI()
    tg = FakeTelegram()
    service = ConversationOrchestrator(
        settings=Settings(telegram_owner_id=1),
        ai=ai,
        telegram=tg,
        event_bus=EventBus(),
        rate_limiter=AllowAllLimiter(),
    )
    await service.handle_business_message(FakeRepo("ghost"), PAYLOAD)
    assert ai.analysis_calls == 1
    assert tg.business_messages == []


@pytest.mark.asyncio
async def test_copilot_creates_draft_but_does_not_send_business_message():
    ai = FakeAI()
    tg = FakeTelegram()
    repo = FakeRepo("copilot")
    service = ConversationOrchestrator(
        settings=Settings(telegram_owner_id=1),
        ai=ai,
        telegram=tg,
        event_bus=EventBus(),
        rate_limiter=AllowAllLimiter(),
    )
    await service.handle_business_message(repo, PAYLOAD)
    assert ai.reply_calls == 1
    assert len(repo.actions) == 1
    assert tg.business_messages == []
    assert len(tg.bot_messages) == 1


@pytest.mark.asyncio
async def test_autopilot_default_global_guard_blocks_send():
    ai = FakeAI()
    tg = FakeTelegram()
    service = ConversationOrchestrator(
        settings=Settings(telegram_owner_id=1, autopilot_enabled=False),
        ai=ai,
        telegram=tg,
        event_bus=EventBus(),
        rate_limiter=AllowAllLimiter(),
    )
    await service.handle_business_message(FakeRepo("autopilot"), PAYLOAD)
    assert tg.business_messages == []
