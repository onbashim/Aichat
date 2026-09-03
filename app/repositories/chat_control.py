from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import selectinload

from app.database.models import Chat, TelegramBusinessConnection
from app.repositories.core import CoreRepository


async def resolve_chat_for_owner(
    repo: CoreRepository,
    *,
    telegram_chat_id: int,
    owner_telegram_user_id: int,
) -> Chat | None:
    """Resolve the chat on the Owner's active Business Connection, creating it if unseen."""
    connection = await repo.session.scalar(
        select(TelegramBusinessConnection)
        .where(
            TelegramBusinessConnection.owner_telegram_user_id == owner_telegram_user_id,
            TelegramBusinessConnection.active.is_(True),
        )
        .order_by(
            desc(TelegramBusinessConnection.updated_at),
            desc(TelegramBusinessConnection.connected_at),
        )
        .limit(1)
    )
    if connection is None:
        return None

    chat = await repo.session.scalar(
        select(Chat)
        .options(selectinload(Chat.settings))
        .where(
            Chat.business_connection_id == connection.id,
            Chat.telegram_chat_id == telegram_chat_id,
        )
        .limit(1)
    )
    if chat is not None:
        return chat

    return await repo.ensure_chat(
        connection.id,
        {
            "id": telegram_chat_id,
            "type": "private",
        },
    )
