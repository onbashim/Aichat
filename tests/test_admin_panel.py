from app.core.config import Settings
from app.services.admin_panel import AdminPanel


class DummyTelegram:
    pass


def test_admin_panel_home_is_persian_inline_menu():
    panel = AdminPanel(Settings(), DummyTelegram())  # type: ignore[arg-type]
    text, markup = panel.home()

    assert "پنل مدیریت" in text
    buttons = [button for row in markup["inline_keyboard"] for button in row]
    assert any(button["callback_data"] == "admin:chats" for button in buttons)
    assert any(button["callback_data"] == "admin:status" for button in buttons)
