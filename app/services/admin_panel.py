from __future__ import annotations

from typing import Any

from app.core.config import Settings
from app.database.models import ChatMode
from app.repositories.chat_control import resolve_chat_for_owner
from app.repositories.core import CoreRepository
from app.telegram.client import TelegramBotAPI


def _button(text: str, data: str) -> dict[str, str]:
    return {"text": text, "callback_data": data}


def _keyboard(rows: list[list[dict[str, str]]]) -> dict[str, Any]:
    return {"inline_keyboard": rows}


def _on(value: Any) -> bool:
    return bool(value)


class AdminPanel:
    def __init__(self, settings: Settings, telegram: TelegramBotAPI) -> None:
        self.settings = settings
        self.telegram = telegram

    def home(self) -> tuple[str, dict[str, Any]]:
        return (
            "⚙️ پنل مدیریت Telegram AI OS\n\n"
            "تمام کنترل‌های اصلی دستیار از همین پنل انجام می‌شود.",
            _keyboard(
                [
                    [_button("🤖 وضعیت سیستم", "admin:status")],
                    [_button("💬 مدیریت چت‌ها", "admin:chats")],
                    [_button("👥 مدیریت کاربران", "admin:users")],
                    [_button("📢 مدیریت کانال‌ها", "admin:channels")],
                    [_button("🧠 تنظیمات AI", "admin:ai")],
                    [_button("📝 Prompt اصلی", "admin:prompt")],
                    [_button("📊 گزارش‌ها", "admin:reports")],
                    [_button("🧾 Audit Log", "admin:audit")],
                    [_button("🔔 اعلان‌ها", "admin:notifications")],
                    [_button("⚙️ تنظیمات پیشرفته", "admin:advanced")],
                    [_button("🔐 امنیت", "admin:security")],
                ]
            ),
        )

    async def status(self, repo: CoreRepository) -> tuple[str, dict[str, Any]]:
        ai_enabled = await repo.get_system_setting(
            "ai_automation_enabled", self.settings.ai_automation_enabled
        )
        autopilot_enabled = await repo.get_system_setting(
            "autopilot_enabled", self.settings.autopilot_enabled
        )
        stats = await repo.dashboard_stats()
        text = (
            "🤖 وضعیت سیستم\n\n"
            f"AI Automation: {'🟢 فعال' if ai_enabled else '🔴 خاموش'}\n"
            f"Autopilot Global: {'🟢 فعال' if autopilot_enabled else '🔴 خاموش'}\n"
            f"Runtime: {'🟢 آماده' if self.settings.runtime_ready else '🟠 ناقص'}\n"
            f"Model: {self.settings.openai_model}\n\n"
            f"چت فعال: {stats['active_chats']}\n"
            f"پیام امروز: {stats['messages_today']}\n"
            f"پاسخ/درخواست AI امروز: {stats['ai_today']}\n"
            f"خطا/مسدودی امروز: {stats['errors_today']}"
        )
        return text, _keyboard(
            [
                [
                    _button(
                        "⛔ AI خاموش" if ai_enabled else "🟢 AI روشن",
                        f"admin:global:ai:{'off' if ai_enabled else 'on'}",
                    )
                ],
                [
                    _button(
                        "⛔ Autopilot خاموش" if autopilot_enabled else "🟢 Autopilot روشن",
                        f"admin:global:autopilot:{'off' if autopilot_enabled else 'on'}",
                    )
                ],
                [_button("🔄 بروزرسانی", "admin:status")],
                [_button("⬅️ بازگشت", "admin:home")],
            ]
        )

    async def chats(self, repo: CoreRepository) -> tuple[str, dict[str, Any]]:
        chats = await repo.list_chats(limit=30)
        rows: list[list[dict[str, str]]] = [
            [
                _button("➕ افزودن Chat", "admin:add_chat"),
                _button("🔍 جستجوی Chat", "admin:search_chat"),
            ]
        ]
        for chat in chats:
            settings = chat.settings
            state = "🟢" if settings and settings.enabled else "🔴"
            name = chat.title or chat.first_name or chat.username or str(chat.telegram_chat_id)
            rows.append([_button(f"{state} {name}", f"admin:chat:{chat.id}")])
        rows.append([_button("⬅️ بازگشت", "admin:home")])
        text = (
            "💬 مدیریت چت‌ها\n\n"
            f"تعداد نمایش داده‌شده: {len(chats)}"
            if chats
            else "💬 مدیریت چت‌ها\n\nهنوز Chat ثبت‌شده‌ای وجود ندارد."
        )
        return text, _keyboard(rows)

    async def chat_detail(
        self, repo: CoreRepository, chat_id: int
    ) -> tuple[str, dict[str, Any]]:
        chat = await repo.get_chat_with_settings(chat_id)
        if chat is None or chat.settings is None:
            return "Chat پیدا نشد.", _keyboard([[_button("⬅️ بازگشت", "admin:chats")]])

        s = chat.settings
        name = chat.title or chat.first_name or chat.username or "بدون نام"
        text = (
            "💬 تنظیمات Chat\n\n"
            f"نام: {name}\n"
            f"ID: {chat.telegram_chat_id}\n"
            f"وضعیت: {'🟢 فعال' if s.enabled else '🔴 خاموش'}\n"
            f"Mode: {s.mode}\n"
            f"Auto Reply: {'فعال' if s.auto_reply else 'غیرفعال'}\n"
            f"Memory: {'فعال' if s.memory_enabled else 'غیرفعال'}\n"
            f"Tone: {s.tone}\n"
            f"Language: {s.language}\n"
            f"Prompt اختصاصی: {'تنظیم شده' if s.custom_prompt else 'ندارد'}"
        )
        return text, _keyboard(
            [
                [
                    _button("Manual", f"admin:mode:{chat.id}:manual"),
                    _button("Copilot", f"admin:mode:{chat.id}:copilot"),
                    _button("Autopilot", f"admin:mode:{chat.id}:autopilot"),
                ],
                [
                    _button(
                        "⛔ Auto Reply خاموش" if s.auto_reply else "🟢 Auto Reply روشن",
                        f"admin:autoreply:{chat.id}:{'off' if s.auto_reply else 'on'}",
                    )
                ],
                [
                    _button(
                        "🧠 Memory خاموش" if s.memory_enabled else "🧠 Memory روشن",
                        f"admin:memory:{chat.id}:{'off' if s.memory_enabled else 'on'}",
                    )
                ],
                [
                    _button("رسمی", f"admin:tone:{chat.id}:formal"),
                    _button("دوستانه", f"admin:tone:{chat.id}:friendly"),
                    _button("فروش", f"admin:tone:{chat.id}:sales"),
                ],
                [
                    _button("فارسی", f"admin:lang:{chat.id}:fa"),
                    _button("English", f"admin:lang:{chat.id}:en"),
                    _button("Auto", f"admin:lang:{chat.id}:auto"),
                ],
                [_button("📝 Prompt اختصاصی", f"admin:chatprompt:{chat.id}")],
                [
                    _button(
                        "🔴 غیرفعال کردن" if s.enabled else "🟢 فعال کردن",
                        f"admin:enabled:{chat.id}:{'off' if s.enabled else 'on'}",
                    )
                ],
                [_button("❌ حذف Chat", f"admin:chat_delete_confirm:{chat.id}")],
                [_button("⬅️ لیست چت‌ها", "admin:chats")],
            ]
        )

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

        s = chat.settings
        if action == "mode" and value in {mode.value for mode in ChatMode}:
            s.mode = value
            if value != ChatMode.AUTOPILOT.value:
                s.auto_reply = False
                s.requires_approval = True
        elif action == "autoreply":
            enabled = value == "on"
            if enabled:
                s.mode = ChatMode.AUTOPILOT.value
            s.auto_reply = enabled
            s.requires_approval = not enabled
        elif action == "memory":
            s.memory_enabled = value == "on"
        elif action == "enabled":
            s.enabled = value == "on"
        elif action == "tone" and value in {"formal", "friendly", "sales", "support", "natural"}:
            s.tone = value
        elif action == "lang" and value in {"fa", "en", "auto"}:
            s.language = value
        else:
            return await self.chat_detail(repo, chat_id)

        await repo.session.flush()
        await repo.add_audit(
            trace_id=f"admin-panel:{chat.id}",
            chat_id=chat.id,
            mode=s.mode,
            action=f"admin_chat_{action}",
            result="success",
            details={"value": value},
        )
        return await self.chat_detail(repo, chat_id)

    async def ai_menu(self, repo: CoreRepository) -> tuple[str, dict[str, Any]]:
        tone = await repo.get_system_setting("ai_tone", "natural")
        language = await repo.get_system_setting("ai_language", "auto")
        length = await repo.get_system_setting("ai_length", "medium")
        creativity = await repo.get_system_setting("ai_creativity", "medium")
        return (
            "🧠 تنظیمات AI\n\n"
            f"مدل: {self.settings.openai_model}\n"
            f"لحن پیش‌فرض: {tone}\n"
            f"زبان پیش‌فرض: {language}\n"
            f"طول پاسخ: {length}\n"
            f"خلاقیت: {creativity}",
            _keyboard(
                [
                    [
                        _button("رسمی", "admin:aiset:tone:formal"),
                        _button("دوستانه", "admin:aiset:tone:friendly"),
                        _button("فروش", "admin:aiset:tone:sales"),
                    ],
                    [
                        _button("فارسی", "admin:aiset:language:fa"),
                        _button("English", "admin:aiset:language:en"),
                        _button("Auto", "admin:aiset:language:auto"),
                    ],
                    [
                        _button("کوتاه", "admin:aiset:length:short"),
                        _button("متوسط", "admin:aiset:length:medium"),
                        _button("کامل", "admin:aiset:length:full"),
                    ],
                    [
                        _button("خلاقیت کم", "admin:aiset:creativity:low"),
                        _button("متوسط", "admin:aiset:creativity:medium"),
                        _button("زیاد", "admin:aiset:creativity:high"),
                    ],
                    [_button("📝 Prompt اصلی", "admin:prompt")],
                    [_button("⬅️ بازگشت", "admin:home")],
                ]
            ),
        )

    async def prompt_menu(self, repo: CoreRepository) -> tuple[str, dict[str, Any]]:
        prompt = await repo.get_system_setting("global_prompt", "")
        enabled = await repo.get_system_setting("global_prompt_enabled", True)
        preview = str(prompt)[:800] if prompt else "هنوز Prompt اصلی تنظیم نشده است."
        return (
            "📝 Prompt اصلی\n\n"
            f"وضعیت: {'🟢 فعال' if enabled else '🔴 خاموش'}\n\n{preview}",
            _keyboard(
                [
                    [_button("✏️ ویرایش Prompt", "admin:prompt_edit")],
                    [
                        _button(
                            "🔴 غیرفعال کردن" if enabled else "🟢 فعال کردن",
                            f"admin:prompt_toggle:{'off' if enabled else 'on'}",
                        )
                    ],
                    [_button("⬅️ بازگشت", "admin:home")],
                ]
            ),
        )

    async def reports(self, repo: CoreRepository) -> tuple[str, dict[str, Any]]:
        stats = await repo.dashboard_stats()
        return (
            "📊 گزارش سیستم\n\n"
            f"پیام امروز: {stats['messages_today']}\n"
            f"درخواست/پاسخ AI امروز: {stats['ai_today']}\n"
            f"خطا یا Block امروز: {stats['errors_today']}\n"
            f"Chat فعال: {stats['active_chats']}",
            _keyboard(
                [
                    [_button("🔄 بروزرسانی", "admin:reports")],
                    [_button("🧾 آخرین Audit", "admin:audit")],
                    [_button("⬅️ بازگشت", "admin:home")],
                ]
            ),
        )

    async def audit(self, repo: CoreRepository) -> tuple[str, dict[str, Any]]:
        audits = await repo.recent_audits(limit=10)
        if not audits:
            body = "هنوز Audit ثبت نشده است."
        else:
            lines = []
            for item in audits:
                when = item.created_at.strftime("%Y-%m-%d %H:%M")
                lines.append(f"• {when} | {item.action} | {item.result}")
            body = "\n".join(lines)
        return (
            "🧾 آخرین Audit Log\n\n" + body,
            _keyboard(
                [
                    [_button("🔄 بروزرسانی", "admin:audit")],
                    [_button("⬅️ بازگشت", "admin:home")],
                ]
            ),
        )

    async def channels(self, repo: CoreRepository) -> tuple[str, dict[str, Any]]:
        channels = await repo.list_channels()
        rows: list[list[dict[str, str]]] = [
            [_button("➕ افزودن کانال", "admin:add_channel")]
        ]
        for channel in channels:
            state = "🟢" if channel.enabled else "🔴"
            name = channel.title or str(channel.telegram_chat_id)
            rows.append([_button(f"{state} {name}", f"admin:channel:{channel.id}")])
        rows.append([_button("⬅️ بازگشت", "admin:home")])
        return (
            f"📢 مدیریت کانال‌ها\n\nتعداد کانال‌ها: {len(channels)}",
            _keyboard(rows),
        )

    async def channel_detail(
        self, repo: CoreRepository, channel_id: int
    ) -> tuple[str, dict[str, Any]]:
        channel = await repo.get_channel(channel_id)
        if channel is None:
            return "کانال پیدا نشد.", _keyboard([[_button("⬅️ بازگشت", "admin:channels")]])
        return (
            "📢 تنظیمات کانال\n\n"
            f"نام: {channel.title or 'بدون نام'}\n"
            f"ID: {channel.telegram_chat_id}\n"
            f"وضعیت: {'🟢 فعال' if channel.enabled else '🔴 خاموش'}\n"
            f"AI: {'🟢 فعال' if channel.ai_enabled else '🔴 خاموش'}",
            _keyboard(
                [
                    [
                        _button(
                            "🔴 خاموش کردن کانال" if channel.enabled else "🟢 فعال کردن کانال",
                            f"admin:channel_enabled:{channel.id}:{'off' if channel.enabled else 'on'}",
                        )
                    ],
                    [
                        _button(
                            "🔴 AI خاموش" if channel.ai_enabled else "🟢 AI روشن",
                            f"admin:channel_ai:{channel.id}:{'off' if channel.ai_enabled else 'on'}",
                        )
                    ],
                    [_button("✏️ ویرایش نام", f"admin:channel_title:{channel.id}")],
                    [_button("❌ حذف کانال", f"admin:channel_delete:{channel.id}:yes")],
                    [_button("⬅️ بازگشت", "admin:channels")],
                ]
            ),
        )


    async def users(self, repo: CoreRepository) -> tuple[str, dict[str, Any]]:
        users = await repo.list_users(limit=50)
        rows: list[list[dict[str, str]]] = []
        for user in users:
            name = " ".join(
                part for part in (user.first_name, user.last_name) if part
            ).strip()
            if not name:
                name = user.username or str(user.telegram_user_id)
            badge = "👑" if user.is_owner else "👤"
            rows.append([_button(f"{badge} {name}", f"admin:user:{user.id}")])
        rows.append([_button("⬅️ بازگشت", "admin:home")])
        return (
            f"👥 مدیریت کاربران\n\nتعداد کاربران ثبت‌شده: {len(users)}",
            _keyboard(rows),
        )

    async def user_detail(
        self, repo: CoreRepository, user_id: int
    ) -> tuple[str, dict[str, Any]]:
        user = await repo.get_user(user_id)
        if user is None:
            return "کاربر پیدا نشد.", _keyboard([[_button("⬅️ بازگشت", "admin:users")]])
        name = " ".join(
            part for part in (user.first_name, user.last_name) if part
        ).strip() or "بدون نام"
        return (
            "👤 اطلاعات کاربر\n\n"
            f"نام: {name}\n"
            f"Telegram ID: {user.telegram_user_id}\n"
            f"Username: @{user.username if user.username else '-'}\n"
            f"نقش: {'مالک اصلی' if user.is_owner else 'کاربر'}",
            _keyboard([[_button("⬅️ بازگشت", "admin:users")]]),
        )

    async def notifications(self, repo: CoreRepository) -> tuple[str, dict[str, Any]]:
        enabled = await repo.get_system_setting("error_notifications", True)
        return (
            "🔔 اعلان‌ها\n\n"
            f"اعلان خطاهای عملیاتی: {'🟢 فعال' if enabled else '🔴 خاموش'}\n"
            "خطاهای واقعی AI/Telegram برای Owner ارسال می‌شوند؛ "
            "خطاهای تنظیمات ناقص به Audit Log می‌روند.",
            _keyboard(
                [
                    [
                        _button(
                            "🔴 خاموش کردن" if enabled else "🟢 فعال کردن",
                            f"admin:notify_errors:{'off' if enabled else 'on'}",
                        )
                    ],
                    [_button("⬅️ بازگشت", "admin:home")],
                ]
            ),
        )

    async def advanced(self, repo: CoreRepository) -> tuple[str, dict[str, Any]]:
        ai_enabled = await repo.get_system_setting(
            "ai_automation_enabled", self.settings.ai_automation_enabled
        )
        autopilot_enabled = await repo.get_system_setting(
            "autopilot_enabled", self.settings.autopilot_enabled
        )
        memory_default = await repo.get_system_setting("memory_default", True)
        return (
            "⚙️ تنظیمات پیشرفته\n\n"
            f"AI Automation: {'فعال' if ai_enabled else 'خاموش'}\n"
            f"Autopilot Global: {'فعال' if autopilot_enabled else 'خاموش'}\n"
            f"Memory پیش‌فرض: {'فعال' if memory_default else 'خاموش'}",
            _keyboard(
                [
                    [
                        _button(
                            "Memory پیش‌فرض خاموش" if memory_default else "Memory پیش‌فرض روشن",
                            f"admin:memory_default:{'off' if memory_default else 'on'}",
                        )
                    ],
                    [_button("🤖 وضعیت و کلیدهای اصلی", "admin:status")],
                    [_button("⬅️ بازگشت", "admin:home")],
                ]
            ),
        )

    async def handle_input(
        self, repo: CoreRepository, telegram_user_id: int, text: str
    ) -> tuple[bool, str, dict[str, Any] | None]:
        session = await repo.get_admin_session(telegram_user_id)
        if session is None:
            return False, "", None

        value = text.strip()
        if value.casefold() in {"/cancel", "لغو", "cancel"}:
            await repo.clear_admin_session(telegram_user_id)
            home_text, markup = self.home()
            return True, home_text, markup

        if session.state == "awaiting_chat_id":
            try:
                telegram_chat_id = int(value)
            except ValueError:
                return True, "Chat ID معتبر نیست. فقط عدد ارسال کن یا «لغو» بفرست.", None
            chat = await resolve_chat_for_owner(
                repo,
                telegram_chat_id=telegram_chat_id,
                owner_telegram_user_id=int(self.settings.telegram_owner_id or 0),
            )
            if chat is None:
                await repo.clear_admin_session(telegram_user_id)
                return (
                    True,
                    "Business Connection فعال پیدا نشد. اتصال Telegram Business را بررسی کن.",
                    _keyboard([[_button("⬅️ بازگشت", "admin:chats")]]),
                )
            if chat.settings is not None:
                memory_default = await repo.get_system_setting("memory_default", True)
                chat.settings.enabled = True
                chat.settings.mode = ChatMode.AUTOPILOT.value
                chat.settings.auto_reply = True
                chat.settings.requires_approval = False
                chat.settings.memory_enabled = bool(memory_default)
                await repo.session.flush()
            await repo.clear_admin_session(telegram_user_id)
            await repo.add_audit(
                trace_id=f"admin-add-chat:{chat.id}",
                chat_id=chat.id,
                mode=chat.settings.mode if chat.settings else None,
                action="admin_chat_added",
                result="success",
                details={"telegram_chat_id": telegram_chat_id},
            )
            detail, markup = await self.chat_detail(repo, chat.id)
            return True, "Chat اضافه شد ✅\n\n" + detail, markup

        if session.state == "awaiting_chat_search":
            results = await repo.search_chats(value, limit=20)
            await repo.clear_admin_session(telegram_user_id)
            rows: list[list[dict[str, str]]] = []
            for chat in results:
                name = chat.title or chat.first_name or chat.username or str(chat.telegram_chat_id)
                rows.append([_button(name, f"admin:chat:{chat.id}")])
            rows.append([_button("⬅️ بازگشت", "admin:chats")])
            return (
                True,
                f"🔍 نتیجه جستجو\n\n{len(results)} Chat پیدا شد.",
                _keyboard(rows),
            )

        if session.state == "awaiting_chat_prompt":
            chat_id = int(session.payload.get("chat_id", 0))
            chat = await repo.get_chat_with_settings(chat_id)
            if chat is None or chat.settings is None:
                await repo.clear_admin_session(telegram_user_id)
                return True, "Chat پیدا نشد.", None
            chat.settings.custom_prompt = value if value != "-" else None
            await repo.session.flush()
            await repo.clear_admin_session(telegram_user_id)
            detail, markup = await self.chat_detail(repo, chat.id)
            return True, "Prompt اختصاصی ذخیره شد ✅\n\n" + detail, markup

        if session.state == "awaiting_global_prompt":
            await repo.set_system_setting("global_prompt", value)
            await repo.set_system_setting("global_prompt_enabled", True)
            await repo.clear_admin_session(telegram_user_id)
            prompt_text, markup = await self.prompt_menu(repo)
            return True, "Prompt اصلی ذخیره شد ✅\n\n" + prompt_text, markup

        if session.state == "awaiting_channel_title":
            channel_id = int(session.payload.get("channel_id", 0))
            channel = await repo.get_channel(channel_id)
            if channel is None:
                await repo.clear_admin_session(telegram_user_id)
                return True, "کانال پیدا نشد.", None
            channel.title = value[:255]
            await repo.session.flush()
            await repo.clear_admin_session(telegram_user_id)
            detail, markup = await self.channel_detail(repo, channel.id)
            return True, "نام کانال ذخیره شد ✅\n\n" + detail, markup

        if session.state == "awaiting_channel_id":
            try:
                telegram_chat_id = int(value)
            except ValueError:
                return True, "Channel ID معتبر نیست. فقط عدد ارسال کن یا «لغو» بفرست.", None
            channel = await repo.add_channel(telegram_chat_id)
            await repo.clear_admin_session(telegram_user_id)
            detail, markup = await self.channel_detail(repo, channel.id)
            return True, "کانال اضافه شد ✅\n\n" + detail, markup

        await repo.clear_admin_session(telegram_user_id)
        return False, "", None

    async def render_callback(
        self, repo: CoreRepository, data: str, *, owner_id: int
    ) -> tuple[str, dict[str, Any]]:
        navigation = {
            "admin:home",
            "admin:status",
            "admin:chats",
            "admin:channels",
            "admin:users",
            "admin:ai",
            "admin:prompt",
            "admin:reports",
            "admin:audit",
            "admin:notifications",
            "admin:advanced",
            "admin:security",
        }
        if data in navigation or data.startswith(("admin:chat:", "admin:channel:")):
            await repo.clear_admin_session(owner_id)

        if data == "admin:home":
            return self.home()
        if data == "admin:status":
            return await self.status(repo)
        if data == "admin:chats":
            return await self.chats(repo)
        if data == "admin:users":
            return await self.users(repo)
        if data.startswith("admin:user:"):
            try:
                return await self.user_detail(repo, int(data.rsplit(":", 1)[1]))
            except ValueError:
                return await self.users(repo)
        if data == "admin:add_chat":
            await repo.set_admin_session(owner_id, "awaiting_chat_id")
            return (
                "➕ افزودن Chat\n\nلطفاً Chat ID را ارسال کن.\nبرای لغو: «لغو»",
                _keyboard([[_button("⬅️ لغو", "admin:chats")]]),
            )
        if data == "admin:search_chat":
            await repo.set_admin_session(owner_id, "awaiting_chat_search")
            return (
                "🔍 جستجوی Chat\n\nنام، username یا Chat ID را ارسال کن.",
                _keyboard([[_button("⬅️ لغو", "admin:chats")]]),
            )
        if data.startswith("admin:chatprompt:"):
            try:
                chat_id = int(data.rsplit(":", 1)[1])
            except ValueError:
                return await self.chats(repo)
            await repo.set_admin_session(owner_id, "awaiting_chat_prompt", {"chat_id": chat_id})
            return (
                "📝 Prompt اختصاصی Chat\n\nPrompt جدید را ارسال کن.\nبرای پاک کردن Prompt فقط «-» بفرست.",
                _keyboard([[_button("⬅️ لغو", f"admin:chat:{chat_id}")]]),
            )
        if data.startswith("admin:chat_delete_confirm:"):
            try:
                chat_id = int(data.rsplit(":", 1)[1])
            except ValueError:
                return await self.chats(repo)
            chat = await repo.get_chat_with_settings(chat_id)
            if chat is None:
                return await self.chats(repo)
            name = chat.title or chat.first_name or chat.username or str(chat.telegram_chat_id)
            return (
                f"❌ حذف Chat\n\nآیا از حذف «{name}» مطمئنی؟\n"
                "پیام‌ها و تنظیمات وابسته این Chat نیز از دیتابیس حذف می‌شوند.",
                _keyboard(
                    [
                        [_button("✅ بله، حذف شود", f"admin:chat_delete:{chat_id}:yes")],
                        [_button("⬅️ انصراف", f"admin:chat:{chat_id}")],
                    ]
                ),
            )
        if data.startswith("admin:chat_delete:"):
            parts = data.split(":")
            if len(parts) == 4 and parts[3] == "yes":
                try:
                    chat_id = int(parts[2])
                except ValueError:
                    return await self.chats(repo)
                await repo.delete_chat(chat_id)
                await repo.add_audit(
                    trace_id=f"admin-delete-chat:{chat_id}",
                    action="admin_chat_deleted",
                    result="success",
                    details={"chat_id": chat_id},
                )
            return await self.chats(repo)
        if data.startswith("admin:chat:"):
            try:
                return await self.chat_detail(repo, int(data.rsplit(":", 1)[1]))
            except ValueError:
                return await self.chats(repo)
        if data.startswith(
            (
                "admin:mode:",
                "admin:autoreply:",
                "admin:memory:",
                "admin:enabled:",
                "admin:tone:",
                "admin:lang:",
            )
        ):
            return await self.mutate_chat(repo, data)

        if data == "admin:ai":
            return await self.ai_menu(repo)
        if data.startswith("admin:aiset:"):
            parts = data.split(":")
            if len(parts) == 4:
                kind, value = parts[2], parts[3]
                key = {
                    "tone": "ai_tone",
                    "language": "ai_language",
                    "length": "ai_length",
                    "creativity": "ai_creativity",
                }.get(kind)
                if key:
                    await repo.set_system_setting(key, value)
            return await self.ai_menu(repo)
        if data.startswith("admin:global:"):
            parts = data.split(":")
            if len(parts) == 4:
                key = (
                    "ai_automation_enabled"
                    if parts[2] == "ai"
                    else "autopilot_enabled"
                )
                await repo.set_system_setting(key, parts[3] == "on")
                await repo.add_audit(
                    trace_id=f"admin-global:{key}",
                    action=f"admin_{key}",
                    result="success",
                    details={"enabled": parts[3] == "on"},
                )
            return await self.status(repo)

        if data == "admin:prompt":
            return await self.prompt_menu(repo)
        if data == "admin:prompt_edit":
            await repo.set_admin_session(owner_id, "awaiting_global_prompt")
            return (
                "📝 ویرایش Prompt اصلی\n\nPrompt جدید را در یک پیام ارسال کن.\nبرای لغو: «لغو»",
                _keyboard([[_button("⬅️ لغو", "admin:prompt")]]),
            )
        if data.startswith("admin:prompt_toggle:"):
            await repo.set_system_setting("global_prompt_enabled", data.endswith(":on"))
            return await self.prompt_menu(repo)

        if data == "admin:reports":
            return await self.reports(repo)
        if data == "admin:audit":
            return await self.audit(repo)

        if data == "admin:channels":
            return await self.channels(repo)
        if data == "admin:add_channel":
            await repo.set_admin_session(owner_id, "awaiting_channel_id")
            return (
                "➕ افزودن کانال\n\nChannel ID را ارسال کن.\nبرای لغو: «لغو»",
                _keyboard([[_button("⬅️ لغو", "admin:channels")]]),
            )
        if data.startswith("admin:channel_title:"):
            try:
                channel_id = int(data.rsplit(":", 1)[1])
            except ValueError:
                return await self.channels(repo)
            await repo.set_admin_session(
                owner_id, "awaiting_channel_title", {"channel_id": channel_id}
            )
            return (
                "✏️ ویرایش نام کانال\n\nنام جدید را ارسال کن.",
                _keyboard([[_button("⬅️ لغو", f"admin:channel:{channel_id}")]]),
            )
        if data.startswith("admin:channel:"):
            try:
                return await self.channel_detail(repo, int(data.rsplit(":", 1)[1]))
            except ValueError:
                return await self.channels(repo)
        if data.startswith(("admin:channel_enabled:", "admin:channel_ai:", "admin:channel_delete:")):
            parts = data.split(":")
            if len(parts) == 4:
                action, raw_id, value = parts[1], parts[2], parts[3]
                try:
                    channel_id = int(raw_id)
                except ValueError:
                    return await self.channels(repo)
                channel = await repo.get_channel(channel_id)
                if channel is None:
                    return await self.channels(repo)
                if action == "channel_enabled":
                    channel.enabled = value == "on"
                elif action == "channel_ai":
                    channel.ai_enabled = value == "on"
                elif action == "channel_delete" and value == "yes":
                    await repo.delete_channel(channel_id)
                    return await self.channels(repo)
                await repo.session.flush()
                return await self.channel_detail(repo, channel_id)

        if data == "admin:notifications":
            return await self.notifications(repo)
        if data.startswith("admin:notify_errors:"):
            await repo.set_system_setting("error_notifications", data.endswith(":on"))
            return await self.notifications(repo)
        if data == "admin:advanced":
            return await self.advanced(repo)
        if data.startswith("admin:memory_default:"):
            await repo.set_system_setting("memory_default", data.endswith(":on"))
            return await self.advanced(repo)

        if data == "admin:security":
            return (
                "🔐 امنیت\n\n"
                "دسترسی پنل: فقط Owner اصلی\n"
                f"Owner ID: {self.settings.telegram_owner_id}\n"
                "Webhook Secret: فعال و مخفی\n"
                "Autopilot: Fail-Closed\n"
                "Business Permission: قبل از هر ارسال بررسی می‌شود.",
                _keyboard([[_button("⬅️ بازگشت", "admin:home")]]),
            )
        return self.home()
