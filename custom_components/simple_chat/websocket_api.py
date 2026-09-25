"""WebSocket API for Simple Chat."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import (
    DEFAULT_HISTORY_LIMIT,
    DOMAIN,
    EVENT_MESSAGE_DELETED,
    EVENT_MESSAGES_READ,
    EVENT_NEW_MESSAGE,
    EVENT_REACTION,
    EVENT_TYPING,
)
from .storage import ChatStore


def _store(hass: HomeAssistant) -> ChatStore:
    return hass.data[DOMAIN]["store"]


def _user_display(connection) -> tuple[str, str]:
    """Return (user_id, name) for the connected user."""
    user = connection.user
    name = user.name or "Neznámy užívateľ"
    return user.id, name


@callback
def async_register_websocket_commands(hass: HomeAssistant) -> None:
    """Register all simple_chat websocket commands."""
    websocket_api.async_register_command(hass, ws_get_messages)
    websocket_api.async_register_command(hass, ws_send_message)
    websocket_api.async_register_command(hass, ws_edit_message)
    websocket_api.async_register_command(hass, ws_delete_message)
    websocket_api.async_register_command(hass, ws_mark_read)
    websocket_api.async_register_command(hass, ws_toggle_reaction)
    websocket_api.async_register_command(hass, ws_typing)
    websocket_api.async_register_command(hass, ws_subscribe)


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------
@websocket_api.websocket_command(
    {
        vol.Required("type"): "simple_chat/get_messages",
        vol.Optional("limit", default=DEFAULT_HISTORY_LIMIT): int,
        vol.Optional("before"): str,
    }
)
@callback
def ws_get_messages(hass, connection, msg):
    messages = _store(hass).get_messages(limit=msg["limit"], before=msg.get("before"))
    connection.send_result(msg["id"], {"messages": messages})


# ---------------------------------------------------------------------------
# Send
# ---------------------------------------------------------------------------
@websocket_api.websocket_command(
    {
        vol.Required("type"): "simple_chat/send_message",
        vol.Required("text"): vol.All(str, vol.Length(min=1, max=4000)),
        vol.Optional("color"): str,
    }
)
@websocket_api.async_response
async def ws_send_message(hass, connection, msg):
    user_id, name = _user_display(connection)
    message = await _store(hass).async_add_message(
        user_id=user_id, user_name=name, text=msg["text"], color=msg.get("color")
    )
    connection.send_result(msg["id"], {"message": message})
    hass.bus.async_fire(EVENT_NEW_MESSAGE, message)


# ---------------------------------------------------------------------------
# Edit
# ---------------------------------------------------------------------------
@websocket_api.websocket_command(
    {
        vol.Required("type"): "simple_chat/edit_message",
        vol.Required("message_id"): str,
        vol.Required("text"): vol.All(str, vol.Length(min=1, max=4000)),
    }
)
@websocket_api.async_response
async def ws_edit_message(hass, connection, msg):
    user_id, _ = _user_display(connection)
    message = await _store(hass).async_edit_message(msg["message_id"], user_id, msg["text"])
    if message is None:
        connection.send_error(msg["id"], "not_allowed", "Môžeš upravovať iba svoje správy")
        return
    connection.send_result(msg["id"], {"message": message})
    hass.bus.async_fire(EVENT_NEW_MESSAGE, message)


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------
@websocket_api.websocket_command(
    {
        vol.Required("type"): "simple_chat/delete_message",
        vol.Required("message_id"): str,
    }
)
@websocket_api.async_response
async def ws_delete_message(hass, connection, msg):
    user_id, _ = _user_display(connection)
    is_admin = connection.user.is_admin
    ok = await _store(hass).async_delete_message(msg["message_id"], user_id, is_admin)
    if not ok:
        connection.send_error(msg["id"], "not_allowed", "Túto správu nemôžeš zmazať")
        return
    connection.send_result(msg["id"], {"deleted": True})
    hass.bus.async_fire(EVENT_MESSAGE_DELETED, {"id": msg["message_id"]})


# ---------------------------------------------------------------------------
# Read receipts
# ---------------------------------------------------------------------------
@websocket_api.websocket_command(
    {
        vol.Required("type"): "simple_chat/mark_read",
        vol.Required("message_ids"): [str],
    }
)
@websocket_api.async_response
async def ws_mark_read(hass, connection, msg):
    user_id, _ = _user_display(connection)
    updated = await _store(hass).async_mark_read(msg["message_ids"], user_id)
    connection.send_result(msg["id"], {"updated": updated})
    if updated:
        hass.bus.async_fire(EVENT_MESSAGES_READ, {"message_ids": updated, "user_id": user_id})


# ---------------------------------------------------------------------------
# Reactions
# ---------------------------------------------------------------------------
@websocket_api.websocket_command(
    {
        vol.Required("type"): "simple_chat/toggle_reaction",
        vol.Required("message_id"): str,
        vol.Required("emoji"): str,
    }
)
@websocket_api.async_response
async def ws_toggle_reaction(hass, connection, msg):
    user_id, _ = _user_display(connection)
    message = await _store(hass).async_toggle_reaction(msg["message_id"], user_id, msg["emoji"])
    if message is None:
        connection.send_error(msg["id"], "not_found", "Správa neexistuje")
        return
    connection.send_result(msg["id"], {"message": message})
    hass.bus.async_fire(EVENT_REACTION, message)


# ---------------------------------------------------------------------------
# Typing indicator (ephemeral, not persisted)
# ---------------------------------------------------------------------------
@websocket_api.websocket_command(
    {
        vol.Required("type"): "simple_chat/typing",
    }
)
@callback
def ws_typing(hass, connection, msg):
    user_id, name = _user_display(connection)
    connection.send_result(msg["id"])
    hass.bus.async_fire(EVENT_TYPING, {"user_id": user_id, "user_name": name})


# ---------------------------------------------------------------------------
# Live subscription - forwards all chat events to this connection
# ---------------------------------------------------------------------------
@websocket_api.websocket_command({vol.Required("type"): "simple_chat/subscribe"})
@callback
def ws_subscribe(hass, connection, msg):
    @callback
    def forward_event(event):
        connection.send_message(
            websocket_api.messages.event_message(
                msg["id"], {"event": event.event_type, "data": event.data}
            )
        )

    remove_listeners = [
        hass.bus.async_listen(EVENT_NEW_MESSAGE, forward_event),
        hass.bus.async_listen(EVENT_MESSAGE_DELETED, forward_event),
        hass.bus.async_listen(EVENT_MESSAGES_READ, forward_event),
        hass.bus.async_listen(EVENT_TYPING, forward_event),
        hass.bus.async_listen(EVENT_REACTION, forward_event),
    ]

    @callback
    def unsubscribe():
        for remove in remove_listeners:
            remove()

    connection.subscriptions[msg["id"]] = unsubscribe
    connection.send_result(msg["id"])
