from app.telegram.parser import TelegramUpdateParser


def test_parser_supports_callback_query():
    update = {
        "update_id": 99,
        "callback_query": {
            "id": "cb-1",
            "from": {"id": 123},
            "data": "admin:home",
        },
    }
    parsed = TelegramUpdateParser().parse(update)
    assert parsed.kind == "callback_query"
    assert parsed.payload["data"] == "admin:home"
