from __future__ import annotations

import re
from uuid import uuid4

from app.ai.engine import AIEngine
from app.ai.router import AICommandRouter
from app.core.config import Settings
from app.database.models import ActionStatus
from app.permissions.service import BusinessPermissions
from app.repositories.core import CoreRepository
from app.telegram.client import TelegramBotAPI


class CommandCenter:
    def __init__(self, settings: Settings, ai: AIEngine, telegram: TelegramBotAPI) -> None:
        self.settings = settings
        self.ai = ai
        self.telegram = telegram
        self.router = AICommandRouter()

    async def handle(self, repo: CoreRepository, text: str) -> str:
        command = self.router.route(text)
        if command.intent == "status":
            return (
                "Telegram AI OS v0.1.0\n"
                f"AI automation: {'ON' if self.settings.ai_automation_enabled else 'OFF'}\n"
                f"Global autopilot: {'ON' if self.settings.autopilot_enabled else 'OFF'}\n"
                f"Runtime configured: {'YES' if self.settings.runtime_ready else 'NO'}"
            )
        if command.intent == "help":
            return (
                "Telegram AI OS آماده است.\n\n"
                "دستورهای مدیریت:\n"
                "وضعیت\n"
                "حالت 123456 ghost\n"
                "حالت 123456 copilot\n"
                "حالت 123456 autopilot\n"
                "اتو ریپلای 123456 روشن\n"
                "پیام‌های جدیدم رو بررسی کن\n"
                "تایید <action-id> / رد <action-id>"
            )
        if command.intent in {"approve_action", "reject_action"}:
            return await self._handle_action(
                repo, command.argument or "", approve=command.intent == "approve_action"
            )
        if command.intent == "set_mode":
            chat = await repo.get_chat_by_telegram_id(int(command.chat_id or 0))
            if chat is None:
                return "این Chat هنوز در دیتابیس دیده نشده است."
            if command.mode not in {"ghost", "copilot", "autopilot"}:
                return "Mode نامعتبر است."
            chat.settings.mode = command.mode
            if command.mode != "autopilot":
                chat.settings.auto_reply = False
                chat.settings.requires_approval = True
            await repo.session.flush()
            return f"Mode چت {chat.telegram_chat_id} روی {command.mode} تنظیم شد."
        if command.intent == "set_autoreply":
            chat = await repo.get_chat_by_telegram_id(int(command.chat_id or 0))
            if chat is None:
                return "این Chat هنوز در دیتابیس دیده نشده است."
            if command.enabled and chat.settings.mode != "autopilot":
                return "برای Auto Reply ابتدا Mode چت را روی autopilot قرار بده."
            chat.settings.auto_reply = bool(command.enabled)
            chat.settings.requires_approval = not bool(command.enabled)
            await repo.session.flush()
            return f"Auto Reply چت {chat.telegram_chat_id} {'روشن' if command.enabled else 'خاموش'} شد."

        if command.intent in {"recent_summary", "contact_query", "ask_ai"} and not self.settings.openai_api_key:
            return "بخش AI هنوز فعال نشده است؛ OPENAI_API_KEY باید در تنظیمات سرور ثبت شود."

        if command.intent == "recent_summary":
            messages = await repo.recent_messages(limit=30)
            context = self._format_messages(messages)
            if not context:
                return "هنوز پیامی ذخیره نشده است."
            result = await self.ai.answer_command(text, context, trace_id=str(uuid4()))
            return result.text
        if command.intent == "contact_query":
            token = self._guess_contact_token(text)
            messages = (
                await repo.search_contact_messages(token, limit=30)
                if token
                else await repo.recent_messages(30)
            )
            context = self._format_messages(messages)
            result = await self.ai.answer_command(
                text, context or "No matching messages.", trace_id=str(uuid4())
            )
            return result.text
        messages = await repo.recent_messages(limit=20)
        result = await self.ai.answer_command(
            text, self._format_messages(messages), trace_id=str(uuid4())
        )
        return result.text

    async def _handle_action(self, repo: CoreRepository, action_id: str, *, approve: bool) -> str:
        action = await repo.get_action(action_id)
        if action is None:
            return "Action پیدا نشد."
        if action.status != ActionStatus.PENDING.value:
            return f"این Action در وضعیت {action.status} است."
        if not approve:
            await repo.set_action_status(action, ActionStatus.REJECTED.value)
            return "Action رد شد."
        payload = action.payload
        connection = await repo.get_connection(str(payload.get("business_connection_id", "")))
        if connection is None or not connection.active:
            await repo.set_action_status(action, ActionStatus.FAILED.value, "inactive connection")
            return "Business Connection فعال نیست؛ ارسال انجام نشد."
        if not BusinessPermissions.from_rights(connection.rights).can_reply:
            await repo.set_action_status(action, ActionStatus.FAILED.value, "can_reply missing")
            return "مجوز Telegram برای ارسال (can_reply) وجود ندارد؛ ارسال انجام نشد."
        try:
            await repo.set_action_status(action, ActionStatus.APPROVED.value)
            sent = await self.telegram.send_business_message(
                business_connection_id=connection.id,
                chat_id=int(payload["telegram_chat_id"]),
                text=str(payload["text"]),
                reply_to_message_id=payload.get("reply_to_message_id"),
            )
            action.payload = {**payload, "sent_message_id": sent.get("message_id")}
            await repo.set_action_status(action, ActionStatus.EXECUTED.value)
            return "پیام تأیید و ارسال شد."
        except Exception as exc:
            await repo.set_action_status(action, ActionStatus.FAILED.value, str(exc))
            return f"ارسال ناموفق بود: {exc}"

    @staticmethod
    def _format_messages(messages) -> str:
        lines = []
        for message in reversed(messages):
            if not message.text:
                continue
            lines.append(
                f"[{message.telegram_date.isoformat()}] chat={message.telegram_chat_id} "
                f"direction={message.direction}: {message.text}"
            )
        return "\n".join(lines)

    @staticmethod
    def _guess_contact_token(text: str) -> str:
        cleaned = re.sub(r"(چی گفته|چه گفته|what did|say|گفته)", " ", text, flags=re.I)
        tokens = [t for t in cleaned.split() if len(t) >= 2]
        return tokens[0] if tokens else ""
