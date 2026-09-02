from __future__ import annotations

from app.core.config import Settings
from app.events.bus import EventBus
from app.events.types import Event, EventNames
from app.repositories.core import CoreRepository
from app.services.command_center import CommandCenter
from app.services.orchestrator import ConversationOrchestrator
from app.telegram.client import TelegramBotAPI
from app.telegram.middleware import OwnerAuthenticationMiddleware
from app.telegram.parser import ParsedUpdate


class TelegramUpdateService:
    def __init__(
        self,
        *,
        settings: Settings,
        telegram: TelegramBotAPI,
        event_bus: EventBus,
        orchestrator: ConversationOrchestrator,
        command_center: CommandCenter,
        owner_auth: OwnerAuthenticationMiddleware,
    ) -> None:
        self.settings = settings
        self.telegram = telegram
        self.event_bus = event_bus
        self.orchestrator = orchestrator
        self.command_center = command_center
        self.owner_auth = owner_auth

    async def process(self, repo: CoreRepository, update: ParsedUpdate) -> None:
        if not await repo.claim_update(update.update_id):
            return
        if update.kind == "business_connection":
            connection = await repo.upsert_business_connection(
                update.payload, expected_owner_id=int(self.settings.telegram_owner_id or 0)
            )
            event_name = (
                EventNames.TELEGRAM_BUSINESS_CONNECTED
                if connection.active
                else EventNames.TELEGRAM_BUSINESS_DISCONNECTED
            )
            await self.event_bus.publish(
                Event(event_name, {"business_connection_id": connection.id})
            )
            return
        if update.kind == "business_message":
            await self.orchestrator.handle_business_message(repo, update.payload)
            return
        if update.kind == "edited_business_message":
            await self.orchestrator.handle_business_message(repo, update.payload, edited=True)
            return
        if update.kind == "deleted_business_messages":
            payload = update.payload
            await repo.mark_messages_deleted(
                str(payload["business_connection_id"]),
                int(payload["chat"]["id"]),
                [int(item) for item in payload.get("message_ids", [])],
            )
            await self.event_bus.publish(Event(EventNames.TELEGRAM_MESSAGES_DELETED, payload))
            return
        if update.kind == "message":
            await self._handle_bot_message(repo, update.payload)

    async def _handle_bot_message(self, repo: CoreRepository, payload: dict) -> None:
        sender_id = (payload.get("from") or {}).get("id")
        chat = payload.get("chat") or {}
        text = payload.get("text") or ""
        auth = await self.owner_auth.authorize(sender_id)
        if not auth.allowed:
            if chat.get("type") == "private":
                await self.telegram.send_bot_message(
                    int(chat["id"]),
                    "تعداد درخواست‌ها زیاد است؛ کمی بعد دوباره تلاش کن."
                    if auth.reason == "rate_limited"
                    else "این ربات خصوصی است.",
                )
            return
        response = await self.command_center.handle(repo, text)
        await self.telegram.send_bot_message(int(chat["id"]), response)
