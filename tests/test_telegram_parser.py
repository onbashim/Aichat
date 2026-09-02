from app.telegram.parser import TelegramUpdateParser


def test_parse_business_connection_update():
    parsed = TelegramUpdateParser().parse(
        {"update_id": 1, "business_connection": {"id": "biz-1", "is_enabled": True}}
    )
    assert parsed.kind == "business_connection"
    assert parsed.payload["id"] == "biz-1"


def test_parse_business_message_update():
    parsed = TelegramUpdateParser().parse({"update_id": 2, "business_message": {"message_id": 10}})
    assert parsed.kind == "business_message"
