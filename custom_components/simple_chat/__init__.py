"""The Simple Chat integration - internal chat between all HA users."""
from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CARD_FILENAME, DOMAIN, FRONTEND_URL_BASE
from .storage import ChatStore
from .websocket_api import async_register_websocket_commands

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Simple Chat from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    store = ChatStore(hass)
    await store.async_load()
    hass.data[DOMAIN]["store"] = store

    async_register_websocket_commands(hass)

    await _async_register_frontend(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data.pop(DOMAIN, None)
    return True


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Serve simple-chat-card.js and auto-register it as a Lovelace resource."""
    www_path = Path(__file__).parent / "frontend"

    try:
        from homeassistant.components.http import StaticPathConfig

        await hass.http.async_register_static_paths(
            [StaticPathConfig(FRONTEND_URL_BASE, str(www_path), cache_headers=False)]
        )
    except ImportError:
        # Older HA Core versions
        hass.http.register_static_path(FRONTEND_URL_BASE, str(www_path), cache_headers=False)

    card_url = f"{FRONTEND_URL_BASE}/{CARD_FILENAME}"

    add_extra_js = hass.data.setdefault("frontend_extra_module_url", set())
    if hasattr(add_extra_js, "add"):
        add_extra_js.add(card_url)
    else:
        # Fallback for HA versions exposing this via frontend.add_extra_js_url
        try:
            from homeassistant.components.frontend import add_extra_js_url

            add_extra_js_url(hass, card_url, es5=False)
        except Exception:  # noqa: BLE001
            _LOGGER.warning(
                "Simple Chat card served at %s - add it manually as a Lovelace resource "
                "(Settings > Dashboards > Resources) if it doesn't load automatically.",
                card_url,
            )
