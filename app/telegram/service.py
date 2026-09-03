from __future__ import annotations

import logging

from app.core.config import Settings
from app.events.bus import EventBus
from app.events.types import Event, EventNames
from app.permissions.service import BusinessPermissions
from app.repositories.core import CoreRepository
from app.services.admin_panel import AdminPanel
from app.services.command_center import CommandCenter
from app.services.orchestrator import ConversationOrchestrator
from app.telegram.client import TelegramBotAPI
from app.telegram.middleware import OwnerAuthenticationMiddleware
from app.telegram.parser import ParsedUpdate

logger = logging.getLogger(__name__)


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
        admin_panel: AdminPanel | None = None,
    ) -> None:
        self.settings = settings
        self.telegram = telegram
        self.event_bus = event_bus
        self.orchestrator = orchestrator
        self.command_center = command_center
        self.admin_panel = admin_panel or AdminPanel(settings, telegram)
        self.owner_auth = owner_auth

    async def process(self, repo: CoreRepository, update: ParsedUpdate) -> None:
        if not await repo.claim_update(update.update_id):
            return
        if update.kind == "business_connection":
            connection = await repo.upsert_business_connection(
                update.payload, expected_owner_id=int(self.settings.telegram_owner_id or 0)
            )
            permissions = BusinessPermissions.from_rights(connection.rights)
            logger.info(
                "telegram business connection updated active=%s can_reply=%s",
                connection.active,
                permissions.can_reply,
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
            logger.info("telegram business message received")
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
        if update.kind == "callback_query":
            await self._handle_callback_query(repo, update.payload)
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
        if text.strip().casefold() in {"/start", "start", "/menu", "menu", "پنل", "منو"}:
            await repo.clear_admin_session(int(sender_id))
            panel_text, markup = self.admin_panel.home()
            await self.telegram.send_bot_message(
                int(chat["id"]), panel_text, reply_markup=markup
            )
            return

        session = await repo.get_admin_session(int(sender_id))
        if session is not None and session.state == "awaiting_action_edit":
            action_id = str(session.payload.get("action_id", ""))
            action = await repo.get_action(action_id)
            if action is None:
                await repo.clear_admin_session(int(sender_id))
                await self.telegram.send_bot_message(int(chat["id"]), "Action پیدا نشد.")
                return
            if action.status != "pending":
                await repo.clear_admin_session(int(sender_id))
                await self.telegram.send_bot_message(
                    int(chat["id"]), f"این Action در وضعیت {action.status} است."
                )
                return
            action.payload = {**action.payload, "text": text.strip()}
            await repo.session.flush()
            await repo.clear_admin_session(int(sender_id))
            markup = {
                "inline_keyboard": [
                    [
                        {"text": "✅ ارسال", "callback_data": f"action:approve:{action.id}"},
                        {"text": "✏️ ویرایش", "callback_data": f"action:edit:{action.id}"},
                        {"text": "❌ رد", "callback_data": f"action:reject:{action.id}"},
                    ]
                ]
            }
            await self.telegram.send_bot_message(
                int(chat["id"]),
                f"پیشنهاد ویرایش‌شده AI:\n\n{text.strip()}",
                reply_markup=markup,
            )
            return

        handled, panel_text, markup = await self.admin_panel.handle_input(
            repo, int(sender_id), text
        )
        if handled:
            await self.telegram.send_bot_message(
                int(chat["id"]), panel_text, reply_markup=markup
            )
            return

        response = await self.command_center.handle(repo, text)
        await self.telegram.send_bot_message(int(chat["id"]), response)

    async def _handle_callback_query(self, repo: CoreRepository, payload: dict) -> None:
        callback_id = str(payload.get("id", ""))
        sender_id = (payload.get("from") or {}).get("id")
        auth = await self.owner_auth.authorize(sender_id)
        if not auth.allowed:
            if callback_id:
                await self.telegram.answer_callback_query(
                    callback_id, text="دسترسی ندارید.", show_alert=True
                )
            return

        message = payload.get("message") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        message_id = message.get("message_id")
        data = str(payload.get("data") or "admin:home")
        if chat_id is None or message_id is None:
            if callback_id:
                await self.telegram.answer_callback_query(callback_id)
            return

        if data.startswith("action:"):
            parts = data.split(":", 2)
            if len(parts) == 3:
                action_kind, action_id = parts[1], parts[2]
                if action_kind == "edit":
                    await repo.set_admin_session(
                        int(sender_id), "awaiting_action_edit", {"action_id": action_id}
                    )
                    text = "✏️ ویرایش پاسخ AI\n\nمتن جدید را ارسال کن.\nبرای لغو: «لغو»"
                    markup = {
                        "inline_keyboard": [
                            [{"text": "⬅️ بازگشت", "callback_data": "admin:home"}]
                        ]
                    }
                elif action_kind in {"approve", "reject"}:
                    command = ("تایید " if action_kind == "approve" else "رد ") + action_id
                    text = await self.command_center.handle(repo, command)
                    markup = {"inline_keyboard": [[{"text": "⬅️ پنل", "callback_data": "admin:home"}]]}
                else:
                    text, markup = self.admin_panel.home()
            else:
                text, markup = self.admin_panel.home()
        else:
            text, markup = await self.admin_panel.render_callback(
                repo, data, owner_id=int(sender_id)
            )
        if callback_id:
            await self.telegram.answer_callback_query(callback_id)
        try:
            await self.telegram.edit_bot_message(
                int(chat_id), int(message_id), text, reply_markup=markup
            )
        except Exception:
            logger.exception(
                "admin panel message edit failed callback=%s data=%s",
                callback_id,
                data,
            )
