import httpx
import pytest

from app.telegram.client import TelegramBotAPI


class FakeHTTPClient:
    async def post(self, url, json):
        request = httpx.Request("POST", url)
        return httpx.Response(
            400,
            request=request,
            json={"ok": False, "error_code": 400, "description": "Bad Request: message is not modified"},
        )

    async def aclose(self):
        return None


@pytest.mark.asyncio
async def test_telegram_api_error_does_not_expose_bot_token():
    client = TelegramBotAPI("super-secret-token")
    await client._client.aclose()
    client._client = FakeHTTPClient()  # type: ignore[assignment]

    with pytest.raises(RuntimeError) as exc_info:
        await client.call("editMessageText", {"chat_id": 1, "message_id": 2, "text": "x"})

    message = str(exc_info.value)
    assert "super-secret-token" not in message
    assert "message is not modified" in message
