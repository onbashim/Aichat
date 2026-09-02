from types import SimpleNamespace

from app.services.mode_policy import can_autopilot


def settings(**overrides):
    base = dict(
        mode="autopilot", enabled=True, blocked=False, auto_reply=True, requires_approval=False
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def connection(**overrides):
    base = dict(active=True, rights={"can_reply": True})
    base.update(overrides)
    return SimpleNamespace(**base)


def test_autopilot_global_switch_is_fail_closed():
    result = can_autopilot(
        settings(), connection(), ai_automation_enabled=True, autopilot_enabled=False
    )
    assert not result.allowed
    assert result.reason == "global_autopilot_disabled"


def test_autopilot_requires_explicit_chat_auto_reply():
    assert not can_autopilot(
        settings(auto_reply=False), connection(), ai_automation_enabled=True, autopilot_enabled=True
    ).allowed


def test_autopilot_requires_telegram_can_reply_permission():
    result = can_autopilot(
        settings(), connection(rights={}), ai_automation_enabled=True, autopilot_enabled=True
    )
    assert not result.allowed
    assert result.reason == "telegram_can_reply_missing"


def test_autopilot_allows_only_when_all_guards_pass():
    assert can_autopilot(
        settings(), connection(), ai_automation_enabled=True, autopilot_enabled=True
    ).allowed
