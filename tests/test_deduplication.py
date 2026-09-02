import pytest

from app.core.config import Settings
from app.telegram.middleware import OwnerAuthenticationMiddleware
from app.telegram.parser import ParsedUpdate
from app.telegram.service import TelegramUpdateService


class FakeRepo:
    def __init__(self): self.calls = 0
    async def claim_update(self, update_id): self.calls += 1; return False

class NeverCalled:
    def __getattr__(self, name):
        async def fail(*args, **kwargs): raise AssertionError(f"{name} should not be called for duplicate update")
        return fail

@pytest.mark.asyncio
async def test_duplicate_update_is_not_processed():
    service = TelegramUpdateService(settings=Settings(telegram_owner_id=1), telegram=NeverCalled(), event_bus=NeverCalled(), orchestrator=NeverCalled(), command_center=NeverCalled(), owner_auth=OwnerAuthenticationMiddleware(owner_id=1, rate_limiter=NeverCalled()))
    repo = FakeRepo(); await service.process(repo, ParsedUpdate(99, "message", {"text":"hello"})); assert repo.calls == 1
