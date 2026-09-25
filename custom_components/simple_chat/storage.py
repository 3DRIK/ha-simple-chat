"""Persistent storage for Simple Chat messages."""
from __future__ import annotations

import time
import uuid
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import MAX_MESSAGES_STORED, STORAGE_KEY, STORAGE_VERSION


class ChatStore:
    """Wraps a HA Store to persist chat messages to disk (.storage/simple_chat.messages)."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._messages: list[dict[str, Any]] = []
        self._loaded = False

    async def async_load(self) -> None:
        """Load messages from disk."""
        data = await self._store.async_load()
        self._messages = (data or {}).get("messages", [])
        self._loaded = True

    async def _async_save(self) -> None:
        await self._store.async_save({"messages": self._messages})

    def get_messages(self, limit: int | None = None, before: str | None = None) -> list[dict[str, Any]]:
        """Return messages, newest last. `before` paginates older history by message id."""
        messages = self._messages
        if before:
            idx = next((i for i, m in enumerate(messages) if m["id"] == before), None)
            if idx is not None:
                messages = messages[:idx]
        if limit:
            messages = messages[-limit:]
        return messages

    def get_message(self, message_id: str) -> dict[str, Any] | None:
        return next((m for m in self._messages if m["id"] == message_id), None)

    async def async_add_message(
        self,
        user_id: str,
        user_name: str,
        text: str,
        color: str | None = None,
    ) -> dict[str, Any]:
        """Add and persist a new message."""
        message = {
            "id": uuid.uuid4().hex,
            "user_id": user_id,
            "user_name": user_name,
            "color": color,
            "text": text,
            "timestamp": time.time(),
            "edited": False,
            "read_by": [user_id],
            "reactions": {},
        }
        self._messages.append(message)
        if len(self._messages) > MAX_MESSAGES_STORED:
            self._messages = self._messages[-MAX_MESSAGES_STORED:]
        await self._async_save()
        return message

    async def async_edit_message(self, message_id: str, user_id: str, text: str) -> dict[str, Any] | None:
        message = self.get_message(message_id)
        if not message or message["user_id"] != user_id:
            return None
        message["text"] = text
        message["edited"] = True
        await self._async_save()
        return message

    async def async_delete_message(self, message_id: str, user_id: str, is_admin: bool) -> bool:
        message = self.get_message(message_id)
        if not message:
            return False
        if message["user_id"] != user_id and not is_admin:
            return False
        self._messages.remove(message)
        await self._async_save()
        return True

    async def async_mark_read(self, message_ids: list[str], user_id: str) -> list[str]:
        """Mark messages as read by user_id, return ids actually updated."""
        updated = []
        for message_id in message_ids:
            message = self.get_message(message_id)
            if message and user_id not in message["read_by"]:
                message["read_by"].append(user_id)
                updated.append(message_id)
        if updated:
            await self._async_save()
        return updated

    async def async_toggle_reaction(self, message_id: str, user_id: str, emoji: str) -> dict[str, Any] | None:
        message = self.get_message(message_id)
        if not message:
            return None
        reactions = message.setdefault("reactions", {})
        users = reactions.setdefault(emoji, [])
        if user_id in users:
            users.remove(user_id)
            if not users:
                del reactions[emoji]
        else:
            users.append(user_id)
        await self._async_save()
        return message

    def unread_count_for(self, user_id: str) -> int:
        return sum(1 for m in self._messages if user_id not in m["read_by"])
