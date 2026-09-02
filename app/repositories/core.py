from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import desc, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    Action,
    ActionStatus,
    AIRequest,
    AuditLog,
    Chat,
    ChatSettings,
    Memory,
    Message,
    ProcessedUpdate,
    TelegramBusinessConnection,
    User,
)


class CoreRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def claim_update(self, update_id: int) -> bool:
        self.session.add(ProcessedUpdate(update_id=update_id, received_at=datetime.now(UTC)))
        try:
            await self.session.flush()
            return True
        except IntegrityError:
            await self.session.rollback()
            return False

    async def upsert_user(self, payload: dict[str, Any], *, is_owner: bool = False) -> User:
        telegram_id = int(payload["id"])
        user = await self.session.scalar(select(User).where(User.telegram_user_id == telegram_id))
        if user is None:
            user = User(telegram_user_id=telegram_id)
            self.session.add(user)
        user.username = payload.get("username")
        user.first_name = payload.get("first_name")
        user.last_name = payload.get("last_name")
        user.is_owner = is_owner
        await self.session.flush()
        return user

    async def upsert_business_connection(
        self, payload: dict[str, Any], *, expected_owner_id: int
    ) -> TelegramBusinessConnection:
        connection_id = str(payload["id"])
        connection = await self.session.get(TelegramBusinessConnection, connection_id)
        owner_id = int(payload["user"]["id"])
        if connection is None:
            connection = TelegramBusinessConnection(
                id=connection_id,
                owner_telegram_user_id=owner_id,
                user_chat_id=int(payload["user_chat_id"]),
                connected_at=datetime.fromtimestamp(int(payload["date"]), tz=UTC),
            )
            self.session.add(connection)
        connection.owner_telegram_user_id = owner_id
        connection.user_chat_id = int(payload["user_chat_id"])
        connection.rights = payload.get("rights") or {}
        connection.active = bool(payload.get("is_enabled")) and owner_id == expected_owner_id
        await self.upsert_user(payload["user"], is_owner=owner_id == expected_owner_id)
        await self.session.flush()
        return connection

    async def get_connection(self, connection_id: str) -> TelegramBusinessConnection | None:
        return await self.session.get(TelegramBusinessConnection, connection_id)

    async def ensure_chat(self, connection_id: str, payload: dict[str, Any]) -> Chat:
        telegram_chat_id = int(payload["id"])
        chat = await self.session.scalar(
            select(Chat).where(
                Chat.business_connection_id == connection_id,
                Chat.telegram_chat_id == telegram_chat_id,
            )
        )
        if chat is None:
            chat = Chat(
                business_connection_id=connection_id,
                telegram_chat_id=telegram_chat_id,
                chat_type=payload.get("type", "private"),
            )
            self.session.add(chat)
            await self.session.flush()
            chat.settings = ChatSettings(chat_id=chat.id)
        chat.title = payload.get("title")
        chat.username = payload.get("username")
        chat.first_name = payload.get("first_name")
        chat.last_name = payload.get("last_name")
        await self.session.flush()
        return chat

    async def get_chat_by_telegram_id(self, telegram_chat_id: int) -> Chat | None:
        return await self.session.scalar(
            select(Chat)
            .where(Chat.telegram_chat_id == telegram_chat_id)
            .order_by(desc(Chat.updated_at))
            .limit(1)
        )

    async def save_message(self, chat: Chat, payload: dict[str, Any], *, direction: str) -> Message:
        existing = await self.session.scalar(
            select(Message).where(
                Message.business_connection_id == str(payload["business_connection_id"]),
                Message.telegram_chat_id == int(payload["chat"]["id"]),
                Message.telegram_message_id == int(payload["message_id"]),
            )
        )
        if existing is not None:
            return existing
        sender = payload.get("from") or {}
        message = Message(
            chat_id=chat.id,
            business_connection_id=str(payload["business_connection_id"]),
            telegram_chat_id=int(payload["chat"]["id"]),
            telegram_message_id=int(payload["message_id"]),
            sender_telegram_user_id=sender.get("id"),
            direction=direction,
            message_type=self._message_type(payload),
            text=payload.get("text") or payload.get("caption"),
            raw_payload=payload,
            telegram_date=datetime.fromtimestamp(int(payload["date"]), tz=UTC),
        )
        self.session.add(message)
        await self.session.flush()
        return message

    @staticmethod
    def _message_type(payload: dict[str, Any]) -> str:
        for key in (
            "text",
            "photo",
            "voice",
            "video",
            "document",
            "audio",
            "sticker",
            "contact",
            "location",
        ):
            if key in payload:
                return key
        return "other"

    async def mark_message_edited(self, payload: dict[str, Any]) -> None:
        await self.session.execute(
            update(Message)
            .where(
                Message.business_connection_id == str(payload["business_connection_id"]),
                Message.telegram_chat_id == int(payload["chat"]["id"]),
                Message.telegram_message_id == int(payload["message_id"]),
            )
            .values(
                text=payload.get("text") or payload.get("caption"),
                raw_payload=payload,
                edited_at=datetime.fromtimestamp(
                    int(payload.get("edit_date", payload["date"])), tz=UTC
                ),
            )
        )

    async def mark_messages_deleted(
        self, connection_id: str, chat_id: int, message_ids: list[int]
    ) -> None:
        if not message_ids:
            return
        await self.session.execute(
            update(Message)
            .where(
                Message.business_connection_id == connection_id,
                Message.telegram_chat_id == chat_id,
                Message.telegram_message_id.in_(message_ids),
            )
            .values(deleted=True)
        )

    async def add_ai_request(
        self,
        *,
        trace_id: str,
        chat_id: int | None,
        kind: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        success: bool = True,
        error: str | None = None,
    ) -> None:
        self.session.add(
            AIRequest(
                trace_id=trace_id,
                chat_id=chat_id,
                kind=kind,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                success=success,
                error=error,
            )
        )
        await self.session.flush()

    async def create_action(
        self,
        *,
        trace_id: str,
        chat_id: int,
        action_type: str,
        mode: str,
        payload: dict[str, Any],
        plugin_id: str | None = None,
        status: str = ActionStatus.PENDING.value,
    ) -> Action:
        action = Action(
            trace_id=trace_id,
            chat_id=chat_id,
            action_type=action_type,
            mode=mode,
            payload=payload,
            plugin_id=plugin_id,
            status=status,
        )
        self.session.add(action)
        await self.session.flush()
        return action

    async def get_action(self, action_id: str) -> Action | None:
        try:
            parsed = UUID(action_id)
        except ValueError:
            return None
        return await self.session.get(Action, parsed)

    async def set_action_status(
        self, action: Action, status: str, error: str | None = None
    ) -> None:
        action.status = status
        action.error = error
        await self.session.flush()

    async def add_audit(
        self,
        *,
        trace_id: str,
        action: str,
        result: str,
        chat_id: int | None = None,
        mode: str | None = None,
        plugin_id: str | None = None,
        error: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.session.add(
            AuditLog(
                trace_id=trace_id,
                chat_id=chat_id,
                plugin_id=plugin_id,
                mode=mode,
                action=action,
                result=result,
                error=error,
                details=details or {},
                created_at=datetime.now(UTC),
            )
        )
        await self.session.flush()

    async def recent_messages(self, limit: int = 30) -> list[Message]:
        return list(
            await self.session.scalars(
                select(Message)
                .where(Message.deleted.is_(False))
                .order_by(desc(Message.telegram_date))
                .limit(limit)
            )
        )

    async def search_contact_messages(self, query: str, limit: int = 30) -> list[Message]:
        pattern = f"%{query}%"
        return list(
            await self.session.scalars(
                select(Message)
                .join(Chat, Chat.id == Message.chat_id)
                .where(
                    Message.deleted.is_(False),
                    (
                        Chat.first_name.ilike(pattern)
                        | Chat.last_name.ilike(pattern)
                        | Chat.username.ilike(pattern)
                    ),
                )
                .order_by(desc(Message.telegram_date))
                .limit(limit)
            )
        )

    async def list_memories(self, chat_id: int, limit: int = 20) -> list[Memory]:
        return list(
            await self.session.scalars(
                select(Memory)
                .where(Memory.chat_id == chat_id)
                .order_by(desc(Memory.importance), desc(Memory.updated_at))
                .limit(limit)
            )
        )

    async def create_memory(
        self,
        *,
        chat_id: int | None,
        memory_type: str,
        key: str,
        value: str,
        importance: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> Memory:
        memory = Memory(
            chat_id=chat_id,
            memory_type=memory_type,
            key=key,
            value=value,
            importance=importance,
            metadata_json=metadata or {},
        )
        self.session.add(memory)
        await self.session.flush()
        return memory

    async def delete_memory(self, memory_id: UUID) -> bool:
        memory = await self.session.get(Memory, memory_id)
        if memory is None:
            return False
        await self.session.delete(memory)
        return True
