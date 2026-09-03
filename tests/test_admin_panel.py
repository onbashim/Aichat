from app.core.config import Settings
from app.services.admin_panel import AdminPanel


class DummyTelegram:
    pass


def test_admin_panel_home_is_persian_inline_menu():
    panel = AdminPanel(Settings(), DummyTelegram())  # type: ignore[arg-type]
    text, markup = panel.home()

    assert "پنل مدیریت" in text
    buttons = [button for row in markup["inline_keyboard"] for button in row]
    callbacks = {button["callback_data"] for button in buttons}
    assert "admin:chats" in callbacks
    assert "admin:status" in callbacks
    assert "admin:channels" in callbacks
    assert "admin:ai" in callbacks
    assert "admin:prompt" in callbacks
    assert "admin:reports" in callbacks
    assert "admin:audit" in callbacks
