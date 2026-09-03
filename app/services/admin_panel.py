from __future__ import annotations

from typing import Any

from app.core.config import Settings
from app.database.models import ChatMode
from app.repositories.core import CoreRepository
from app.telegram.client import TelegramBotAPI


def _button(text: str, data: str) -> dict[str, str]:
    return {"text": text, "callback_data": data}


def _keyboard(rows: list[list[dict[str, str]]]) -> dict[str, Any]:
    return {"inline_keyboard": rows}


class AdminPanel:
    def __init__(self, settings: Settings, telegram: TelegramBotAPI) -> None:
        self.settings = settings
        self.telegram = telegram

    def home(self) -> tuple[str, dict[str, Any]]:
        text = (
            "⚙️ پنل مدیریت Telegram AI OS\n\n"
            "مدیریت هوش مصنوعی، چت‌ها، گزارش‌ها و تنظیمات سیستم از همین بخش انجام می‌شود."
        )
        markup = _keyboard(
            [
                [_button("🤖 وضعیت سیستم", "admin:status")],
                [_button("💬 مدیریت چت‌ها", "admin:chats")],
                [_button("🧠 تنظیمات AI", "admin:ai")],
                [_button("📢 مدیریت کانال‌ها", "admin:channels")],
                [_button("📊 گزارش‌ها", "admin:reports")],
                [_button("🔐 امنیت", "admin:security")],
            ]
        )
        return text, markup

    def status(self) -> tuple[str, dict[str, Any]]:
        text = (
            "🤖 وضعیت سیستم\n\n"
            f"AI Automation: {'🟢 فعال' if self.settings.ai_automation_enabled else '🔴 خاموش'}\n"
            f"Autopilot Global: {'🟢 فعال' if self.settings.autopilot_enabled else '🔴 خاموش'}\n"
            f"Runtime: {'🟢 آماده' if self.settings.runtime_ready else '🟠 ناقص'}\n"
            f"Model: {self.settings.openai_model}"
        )
        return text, _keyboard([[_button("⬅️ بازگشت", "admin:home")]])

    async def chats(self, repo: CoreRepository) -> tuple[str, dict[str, Any]]:
        chats = await repo.list_chats(limit=20)
        if not chats:
            text = "💬 مدیریت چت‌ها\n\nهنوز هیچ Chat ثبت‌شده‌ای وجود ندارد."
            rows = [[_button("⬅️ بازگشت", "admin:home")]]
            return text, _keyboard(rows)

        rows: list[list[dict[str, str]]] = []
        for chat in chats:
            settings = chat.settings
            state = "🟢" if settings and settings.enabled else "🔴"
            name = chat.title or chat.first_name or chat.username or str(chat.telegram_chat_id)
            rows.append([_button(f"{state} {name}", f"admin:chat:{chat.id}")])
        rows.append([_button("⬅️ بازگشت", "admin:home")])
        return (
            f"💬 مدیریت چت‌ها\n\n{len(chats)} چت اخیر نمایش داده شده است.",
            _keyboard(rows),
        )

    async def chat_detail(
        self, repo: CoreRepository, chat_id: int
    ) -> tuple[str, dict[str, Any]]:
        chat = await repo.get_chat_with_settings(chat_id)
        if chat is None or chat.settings is None:
            return "Chat پیدا نشد.", _keyboard([[_button("⬅️ بازگشت", "admin:chats")]])

        settings = chat.settings
        name = chat.title or chat.first_name or chat.username or "بدون نام"
        text = (
            "💬 تنظیمات Chat\n\n"
            f"نام: {name}\n"
            f"ID: {chat.telegram_chat_id}\n"
            f"وضعیت: {'🟢 فعال' if settings.enabled else '🔴 خاموش'}\n"
            f"حالت: {settings.mode}\n"
            f"پاسخ خودکار: {'فعال' if settings.auto_reply else 'غیرفعال'}\n"
            f"حافظه: {'فعال' if settings.memory_enabled else 'غیرفعال'}"
        )
        rows = [
            [
                _button("Ghost", f"admin:mode:{chat.id}:ghost"),
                _button("Copilot", f"admin:mode:{chat.id}:copilot"),
                _button("Autopilot", f"admin:mode:{chat.id}:autopilot"),
            ],
            [
                _button(
                    "🔁 Auto Reply روشن" if not settings.auto_reply else "⛔ Auto Reply خاموش",
                    f"admin:autoreply:{chat.id}:{'on' if not settings.auto_reply else 'off'}",
                )
            ],
            [
                _button(
                    "🧠 Memory روشن" if not settings.memory_enabled else "🧠 Memory خاموش",
                    f"admin:memory:{chat.id}:{'on' if not settings.memory_enabled else 'off'}",
                )
            ],
            [
                _button(
                    "🔴 غیرفعال کردن" if settings.enabled else "🟢 فعال کردن",
                    f"admin:enabled:{chat.id}:{'off' if settings.enabled else 'on'}",
                )
            ],
            [_button("⬅️ لیست چت‌ها", "admin:chats")],
        ]
        return text, _keyboard(rows)

    async def mutate_chat(
        self, repo: CoreRepository, data: str
    ) -> tuple[str, dict[str, Any]]:
        parts = data.split(":")
        if len(parts) != 4:
            return self.home()

        action, raw_chat_id, value = parts[1], parts[2], parts[3]
        try:
            chat_id = int(raw_chat_id)
        except ValueError:
            return self.home()

        chat = await repo.get_chat_with_settings(chat_id)
        if chat is None or chat.settings is None:
            return "Chat پیدا نشد.", _keyboard([[_button("⬅️ بازگشت", "admin:chats")]])

        settings = chat.settings
        if action == "mode":
            if value not in {mode.value for mode in ChatMode}:
                return await self.chat_detail(repo, chat_id)
            settings.mode = value
            if value != ChatMode.AUTOPILOT.value:
                settings.auto_reply = False
                settings.requires_approval = True
        elif action == "autoreply":
            enabled = value == "on"
            if enabled and settings.mode != ChatMode.AUTOPILOT.value:
                settings.mode = ChatMode.AUTOPILOT.value
            settings.auto_reply = enabled
            settings.requires_approval = not enabled
        elif action == "memory":
            settings.memory_enabled = value == "on"
        elif action == "enabled":
            settings.enabled = value == "on"

        await repo.session.flush()
        await repo.add_audit(
            trace_id=f"admin-panel:{chat.id}",
            chat_id=chat.id,
            mode=settings.mode,
            action=f"admin_chat_{action}",
            result="success",
            details={"value": value},
        )
        return await self.chat_detail(repo, chat_id)

    async def render_callback(
        self, repo: CoreRepository, data: str
    ) -> tuple[str, dict[str, Any]]:
        if data == "admin:home":
            return self.home()
        if data == "admin:status":
            return self.status()
        if data == "admin:chats":
            return await self.chats(repo)
        if data.startswith("admin:chat:"):
            try:
                return await self.chat_detail(repo, int(data.rsplit(":", 1)[1]))
            except ValueError:
                return self.home()
        if data.startswith(("admin:mode:", "admin:autoreply:", "admin:memory:", "admin:enabled:")):
            return await self.mutate_chat(repo, data)
        if data == "admin:ai":
            return (
                "🧠 تنظیمات AI\n\nمدل و کلیدهای اصلی از تنظیمات امن سرور خوانده می‌شوند. "
                "کنترل‌های Tone، Language و Prompt اختصاصی در مرحله بعد اضافه می‌شوند.",
                _keyboard([[_button("⬅️ بازگشت", "admin:home")]]),
            )
        if data == "admin:channels":
            return (
                "📢 مدیریت کانال‌ها\n\nاین ماژول هنوز در نسخه فعلی فعال نشده است.",
                _keyboard([[_button("⬅️ بازگشت", "admin:home")]]),
            )
        if data == "admin:reports":
            return (
                "📊 گزارش‌ها\n\nزیرساخت Audit و AI Request فعال است. داشبورد آماری در مرحله بعد متصل می‌شود.",
                _keyboard([[_button("⬅️ بازگشت", "admin:home")]]),
            )
        if data == "admin:security":
            return (
                "🔐 امنیت\n\nدسترسی پنل فقط از مسیر احراز هویت Owner انجام می‌شود.",
                _keyboard([[_button("⬅️ بازگشت", "admin:home")]]),
            )
        return self.home()
