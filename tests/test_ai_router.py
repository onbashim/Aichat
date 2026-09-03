from app.ai.router import AICommandRouter


def test_router_understands_status_in_persian():
    assert AICommandRouter().route("وضعیت").intent == "status"


def test_router_understands_mode_change():
    result = AICommandRouter().route("حالت 123456 autopilot")
    assert result.intent == "set_mode"
    assert result.chat_id == 123456
    assert result.mode == "autopilot"


def test_router_understands_recent_message_request():
    assert AICommandRouter().route("پیام‌های جدیدم رو بررسی کن").intent == "recent_summary"


def test_router_understands_manual_mode():
    result = AICommandRouter().route("حالت 123456 manual")
    assert result.intent == "set_mode"
    assert result.chat_id == 123456
    assert result.mode == "manual"
