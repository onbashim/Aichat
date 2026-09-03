from app.database.models import Chat, ChatSettings
from app.repositories.core import CoreRepository


class FakeSession:
    def __init__(self, chat: Chat) -> None:
        self.chat = chat
        self.statement = None

    async def scalar(self, statement):
        self.statement = statement
        return self.chat

    async def flush(self) -> None:
        return None


async def test_ensure_chat_eager_loads_settings_for_existing_chat():
    chat = Chat(
        id=1,
        business_connection_id="business-1",
        telegram_chat_id=123456,
        chat_type="private",
    )
    chat.settings = ChatSettings(chat_id=1)

    session = FakeSession(chat)
    repo = CoreRepository(session)  # type: ignore[arg-type]

    result = await repo.ensure_chat(
        "business-1",
        {"id": 123456, "type": "private", "first_name": "Customer"},
    )

    assert result is chat
    assert session.statement is not None
    assert session.statement._with_options
    assert result.settings is chat.settings
