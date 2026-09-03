from __future__ import annotations

from typing import Any

import httpx


class TelegramBotAPI:
    def __init__(self, token: str, *, timeout_seconds: float = 20.0) -> None:
        self.base_url = f"https://api.telegram.org/bot{token}"
        self._client = httpx.AsyncClient(timeout=timeout_seconds)

    async def close(self) -> None:
        await self._client.aclose()

    async def call(self, method: str, payload: dict[str, Any] | None = None) -> Any:
        response = await self._client.post(f"{self.base_url}/{method}", json=payload or {})
        response.raise_for_status()
        body = response.json()
        if not body.get("ok"):
            raise RuntimeError(f"Telegram API error: {body}")
        return body.get("result")

    async def get_me(self) -> dict[str, Any]:
        return await self.call("getMe")

    async def set_webhook(self, url: str, secret_token: str) -> bool:
        allowed_updates = [
            "message",
            "business_connection",
            "business_message",
            "edited_business_message",
            "deleted_business_messages",
            "callback_query",
        ]
        return bool(
            await self.call(
                "setWebhook",
                {
                    "url": url,
                    "secret_token": secret_token,
                    "allowed_updates": allowed_updates,
                    "drop_pending_updates": False,
                },
            )
        )

    async def send_bot_message(
        self,
        chat_id: int,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        return await self.call("sendMessage", payload)

    async def edit_bot_message(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        return await self.call("editMessageText", payload)

    async def answer_callback_query(
        self,
        callback_query_id: str,
        *,
        text: str | None = None,
        show_alert: bool = False,
    ) -> bool:
        payload: dict[str, Any] = {
            "callback_query_id": callback_query_id,
            "show_alert": show_alert,
        }
        if text:
            payload["text"] = text
        return bool(await self.call("answerCallbackQuery", payload))

    async def send_business_message(
        self,
        *,
        business_connection_id: str,
        chat_id: int,
        text: str,
        reply_to_message_id: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "business_connection_id": business_connection_id,
            "chat_id": chat_id,
            "text": text,
        }
        if reply_to_message_id is not None:
            payload["reply_parameters"] = {"message_id": reply_to_message_id}
        return await self.call("sendMessage", payload)
