"""Config flow for Simple Chat - single instance, no options needed."""
from __future__ import annotations

from homeassistant import config_entries

from .const import DOMAIN


class SimpleChatConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Simple Chat."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Single confirmation step - one instance is enough for the whole household."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title="Simple Chat", data={})

        return self.async_show_form(step_id="user")
