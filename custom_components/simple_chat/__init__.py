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
    """Serve simple-chat-card.js and try to auto-register it as a Lovelace resource."""
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
    _LOGGER.info("Simple Chat: karta sa servíruje na %s", card_url)

    registered = False
    try:
        # Only works for storage-mode dashboards, and only on HA versions that
        # expose the resource collection this way - wrapped so a failure here
        # never breaks integration setup.
        resources = hass.data.get("lovelace", {}).get("resources")
        if resources is not None:
            if hasattr(resources, "async_items") and not getattr(resources, "loaded", True):
                await resources.async_load()
            existing_urls = {item.get("url") for item in resources.async_items()}
            if card_url not in existing_urls:
                await resources.async_create_item({"res_type": "module", "url": card_url})
            registered = True
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Simple Chat: auto-registrácia resource zlyhala: %s", err)

    if registered:
        _LOGGER.info("Simple Chat: karta bola automaticky pridaná medzi Lovelace resources.")
    else:
        _LOGGER.warning(
            "Simple Chat: karta sa nedala automaticky pridať medzi Lovelace resources "
            "(bežné pri YAML dashboardoch alebo starších/novších verziách HA). "
            "Pridaj ju ručne: Nastavenia > Dashboardy > tri bodky vpravo hore > "
            "Resources > Add Resource > URL '%s', typ JavaScript Module. "
            "Po pridaní urob hard refresh prehliadača (Ctrl+Shift+R).",
            card_url,
        )
