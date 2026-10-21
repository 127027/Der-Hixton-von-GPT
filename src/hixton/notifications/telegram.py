"""Small Telegram Bot API client. Never expose the token-bearing URL in errors."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


class DeliveryError(RuntimeError):
    def __init__(self, message: str, *, retry_after: int = 60) -> None:
        super().__init__(message)
        self.retry_after = min(3600, max(30, retry_after))


def validate_token(token: str) -> str:
    if not re.fullmatch(r"[0-9]{5,20}:[A-Za-z0-9_-]{20,128}", token):
        raise ValueError("Gültigen Telegram-Bot-Token von @BotFather eingeben.")
    return token


def validate_chat(chat: str) -> str:
    if not re.fullmatch(r"[1-9][0-9]{0,19}", chat):
        raise ValueError("Die numerische ID deines privaten Telegram-Chats eingeben.")
    return chat


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


class TelegramClient:
    def _call(self, token: str, method: str, payload: dict[str, object]) -> dict[str, Any]:
        validate_token(token)
        request = Request(
            f"https://api.telegram.org/bot{token}/{method}",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with build_opener(_NoRedirect()).open(request, timeout=8) as response:
                result = json.loads(response.read(65536))
        except HTTPError as error:
            code = error.code
            retry_after = 60
            if code == 429:
                try:
                    body = json.loads(error.read(8192))
                    retry_after = int(body.get("parameters", {}).get("retry_after", 60))
                except (ValueError, TypeError, AttributeError):
                    pass
            error.close()
            if code in {401, 403}:
                raise DeliveryError(
                    "Telegram lehnt den Zugang ab. Token, privaten Chat und /start prüfen.",
                    retry_after=3600,
                ) from None
            if code == 429:
                raise DeliveryError(
                    "Telegram begrenzt den Versand; erneuter Versuch folgt.",
                    retry_after=retry_after,
                ) from None
            raise DeliveryError(
                f"Telegram hat die Anfrage abgelehnt (HTTP {code}). Einstellungen prüfen."
            ) from None
        except (OSError, URLError, ValueError):
            raise DeliveryError(
                "Telegram-Antwort fehlt. Erneuter Versuch folgt; eine Doppelmeldung ist möglich."
            ) from None
        if not isinstance(result, dict) or result.get("ok") is not True:
            raise DeliveryError("Telegram hat die Anfrage nicht bestätigt.")
        return result

    def send(self, token: str, chat: str, title: str, body: str) -> str:
        validate_chat(chat)
        text = f"{title}\n\n{body}"
        if len(text) > 4096:
            raise DeliveryError("Meldung überschreitet Telegram-Limit; lokalen Bericht prüfen.")
        result = self._call(
            token,
            "sendMessage",
            {"chat_id": chat, "text": text},
        )
        message = result.get("result")
        if (
            not isinstance(message, dict)
            or not isinstance(message.get("chat"), dict)
            or str(message["chat"].get("id")) != chat
            or type(message.get("message_id")) is not int
            or message["message_id"] <= 0
        ):
            raise DeliveryError("Telegram hat den Versand nicht eindeutig bestätigt.")
        return str(message["message_id"])

    def discover(self, token: str) -> list[dict[str, str]]:
        result = self._call(token, "getUpdates", {"limit": 100, "timeout": 0})
        updates = result.get("result")
        if not isinstance(updates, list):
            raise DeliveryError("Telegram hat keine lesbare Chat-Liste geliefert.")
        chats: dict[str, dict[str, str]] = {}
        for update in updates:
            message = update.get("message") if isinstance(update, dict) else None
            chat = message.get("chat") if isinstance(message, dict) else None
            if not isinstance(chat, dict) or chat.get("type") != "private":
                continue
            chat_id = str(chat.get("id", ""))
            if not re.fullmatch(r"[1-9][0-9]{0,19}", chat_id):
                continue
            name = str(chat.get("first_name") or chat.get("username") or "Privater Chat")
            chats[chat_id] = {"id": chat_id, "label": name[:100]}
        return list(chats.values())
