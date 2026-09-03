from __future__ import annotations

import logging
from uuid import uuid4

from app.ai.engine import AIEngine
from app.core.config import Settings
from app.core.rate_limit import SlidingWindowRateLimiter
from app.database.models import ActionStatus, ChatMode
from app.events.bus import EventBus
from app.events.types import Event, EventNames
from app.memory.service import MemoryService
from app.permissions.service import BusinessPermissions
from app.repositories.core import CoreRepository
from app.services.mode_policy import can_autopilot
from app.telegram.client import TelegramBotAPI

logger = logging.getLogger(__name__)


class ConversationOrchestrator:
    def __init__(
        self,
        *,
        settings: Settings,
        ai: AIEngine,
        telegram: TelegramBotAPI,
        event_bus: EventBus,
        rate_limiter: SlidingWindowRateLimiter,
    ) -> None:
        self.settings = settings
        self.ai = ai
        self.telegram = telegram
        self.event_bus = event_bus
        self.rate_limiter = rate_limiter

    async def handle_business_message(
        self, repo: CoreRepository, payload: dict, *, edited: bool = False
    ) -> None:
        trace_id = str(uuid4())
        connection_id = str(payload.get("business_connection_id", ""))
        connection = await repo.get_connection(connection_id)
        if connection is None or not connection.active:
            await repo.add_audit(
                trace_id=trace_id,
                action="business_message_ignored",
                result="ignored",
                details={
                    "reason": "unknown_or_inactive_connection",
                    "connection_id": connection_id,
                },
            )
            return
        chat = await repo.ensure_chat(connection_id, payload["chat"])
        settings = chat.settings
        sender = payload.get("from") or {}
        is_outgoing = bool(payload.get("sender_business_bot")) or int(sender.get("id", 0)) == int(
            connection.owner_telegram_user_id
        )
        direction = "outgoing" if is_outgoing else "incoming"
        if edited:
            await repo.mark_message_edited(payload)
            await self.event_bus.publish(
                Event(EventNames.TELEGRAM_MESSAGE_EDITED, payload, trace_id)
            )
            return
        await repo.save_message(chat, payload, direction=direction)
        await self.event_bus.publish(Event(EventNames.TELEGRAM_MESSAGE_RECEIVED, payload, trace_id))
        if (
            is_outgoing
            or payload.get("sender_business_bot")
            or not settings.enabled
            or settings.blocked
        ):
            return
        text = payload.get("text") or payload.get("caption")
        if not text:
            return
        if not await self.rate_limiter.allow(f"chat:{chat.id}"):
            await repo.add_audit(
                trace_id=trace_id,
                chat_id=chat.id,
                mode=settings.mode,
                action="ai_rate_limited",
                result="blocked",
            )
            return
        memory = MemoryService(repo, self.event_bus)
        memory_context = await memory.context_for_chat(chat.id) if settings.memory_enabled else ""

        get_system_setting = getattr(repo, "get_system_setting", None)
        if get_system_setting is None:
            global_tone = "natural"
            global_language = "auto"
            response_length = "medium"
            global_prompt_enabled = True
            global_prompt = ""
            ai_automation_enabled = self.settings.ai_automation_enabled
            autopilot_enabled = self.settings.autopilot_enabled
        else:
            global_tone = await get_system_setting("ai_tone", "natural")
            global_language = await get_system_setting("ai_language", "auto")
            response_length = await get_system_setting("ai_length", "medium")
            global_prompt_enabled = await get_system_setting("global_prompt_enabled", True)
            global_prompt = (
                await get_system_setting("global_prompt", "")
                if global_prompt_enabled
                else ""
            )
            ai_automation_enabled = await get_system_setting(
                "ai_automation_enabled", self.settings.ai_automation_enabled
            )
            autopilot_enabled = await get_system_setting(
                "autopilot_enabled", self.settings.autopilot_enabled
            )
        effective_tone = settings.tone if settings.tone != "natural" else str(global_tone)
        effective_language = (
            settings.language if settings.language != "auto" else str(global_language)
        )
        prompts = [item for item in (global_prompt, settings.custom_prompt) if item]
        effective_prompt = "\n\n".join(str(item) for item in prompts) or None
        try:
            if settings.mode == ChatMode.MANUAL.value:
                await repo.add_audit(
                    trace_id=trace_id,
                    chat_id=chat.id,
                    mode=settings.mode,
                    action="manual_message_stored",
                    result="success",
                )
                return
            if settings.mode == ChatMode.GHOST.value:
                result = await self.ai.analyze_message(text, trace_id=trace_id)
                await repo.add_ai_request(
                    trace_id=trace_id,
                    chat_id=chat.id,
                    kind="ghost_analysis",
                    model=result.model,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                )
                await repo.add_audit(
                    trace_id=trace_id,
                    chat_id=chat.id,
                    mode=settings.mode,
                    action="ghost_analysis",
                    result="success",
                    details={"analysis": result.text[:4000]},
                )
                return
            result = await self.ai.draft_reply(
                text,
                trace_id=trace_id,
                tone=effective_tone,
                language=effective_language,
                custom_prompt=effective_prompt,
                memory_context=memory_context,
                response_length=str(response_length),
            )
            await repo.add_ai_request(
                trace_id=trace_id,
                chat_id=chat.id,
                kind="reply_draft",
                model=result.model,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
            )
            if settings.mode == ChatMode.COPILOT.value:
                action = await repo.create_action(
                    trace_id=trace_id,
                    chat_id=chat.id,
                    action_type="send_business_message",
                    mode=settings.mode,
                    payload={
                        "business_connection_id": connection.id,
                        "telegram_chat_id": chat.telegram_chat_id,
                        "reply_to_message_id": int(payload["message_id"]),
                        "text": result.text,
                    },
                )
                can_reply = BusinessPermissions.from_rights(connection.rights).can_reply
                notice = (
                    f"🤖 پیشنهاد پاسخ AI\n\n{result.text}\n\n"
                    f"Chat ID: {chat.telegram_chat_id}\n"
                    f"مجوز ارسال: {'✅' if can_reply else '❌'}"
                )
                if self.settings.telegram_owner_id:
                    markup = {
                        "inline_keyboard": [
                            [
                                {
                                    "text": "✅ ارسال",
                                    "callback_data": f"action:approve:{action.id}",
                                },
                                {
                                    "text": "✏️ ویرایش",
                                    "callback_data": f"action:edit:{action.id}",
                                },
                                {
                                    "text": "❌ رد",
                                    "callback_data": f"action:reject:{action.id}",
                                },
                            ]
                        ]
                    }
                    try:
                        await self.telegram.send_bot_message(
                            self.settings.telegram_owner_id,
                            notice,
                            reply_markup=markup,
                        )
                    except TypeError:
                        # Backward-compatible adapter path for legacy Telegram clients.
                        await self.telegram.send_bot_message(
                            self.settings.telegram_owner_id,
                            notice,
                        )
                await repo.add_audit(
                    trace_id=trace_id,
                    chat_id=chat.id,
                    mode=settings.mode,
                    action="copilot_draft_created",
                    result="pending_approval",
                    details={"action_id": str(action.id)},
                )
                return
            if settings.mode == ChatMode.AUTOPILOT.value:
                decision = can_autopilot(
                    settings,
                    connection,
                    ai_automation_enabled=bool(ai_automation_enabled),
                    autopilot_enabled=bool(autopilot_enabled),
                )
                if not decision.allowed:
                    await repo.add_audit(
                        trace_id=trace_id,
                        chat_id=chat.id,
                        mode=settings.mode,
                        action="autopilot_send",
                        result="blocked",
                        details={"reason": decision.reason},
                    )
                    return
                sent = await self.telegram.send_business_message(
                    business_connection_id=connection.id,
                    chat_id=chat.telegram_chat_id,
                    text=result.text,
                    reply_to_message_id=int(payload["message_id"]),
                )
                await repo.create_action(
                    trace_id=trace_id,
                    chat_id=chat.id,
                    action_type="send_business_message",
                    mode=settings.mode,
                    status=ActionStatus.EXECUTED.value,
                    payload={"telegram_message_id": sent.get("message_id"), "text": result.text},
                )
                await self.event_bus.publish(
                    Event(EventNames.AUTOMATION_TRIGGERED, {"chat_id": chat.id}, trace_id)
                )
                await repo.add_audit(
                    trace_id=trace_id,
                    chat_id=chat.id,
                    mode=settings.mode,
                    action="autopilot_send",
                    result="success",
                    details={"telegram_message_id": sent.get("message_id")},
                )
        except Exception as exc:
            logger.exception("business AI processing failed")
            await repo.add_audit(
                trace_id=trace_id,
                chat_id=chat.id,
                mode=settings.mode,
                action="ai_processing",
                result="failed",
                error=str(exc),
            )
