from app.ai.engine import AIEngine
from app.ai.models import AIResult
from app.events.bus import EventBus


class CapturingProvider:
    def __init__(self) -> None:
        self.messages = None

    async def generate(self, messages, *, trace_id):
        self.messages = messages
        return AIResult(text="ok", model="test-model")


async def test_draft_reply_includes_response_length_and_context():
    provider = CapturingProvider()
    engine = AIEngine(provider, EventBus())

    await engine.draft_reply(
        "سلام",
        trace_id="trace-1",
        tone="friendly",
        language="fa",
        custom_prompt="قیمت را دقیق بگو",
        memory_context="نام مشتری: علی",
        response_length="short",
        creativity="high",
    )

    assert provider.messages is not None
    user = provider.messages[1].content
    assert "Tone: friendly" in user
    assert "Language: fa" in user
    assert "Response length: short" in user
    assert "Creativity: high" in user
    assert "قیمت را دقیق بگو" in user
    assert "نام مشتری: علی" in user
