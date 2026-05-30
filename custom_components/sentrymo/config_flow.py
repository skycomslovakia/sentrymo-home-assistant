"""Config flow for Sentrymo."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME

from .const import CONF_API_URL, CONF_CPIN, DEFAULT_PROD_API_URL, DOMAIN


class SentrymoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sentrymo."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # TODO: Exchange setup key via /ha-api/v1/auth/exchange.
            # Store access_token, refresh_token and optional CPIN.
            await self.async_set_unique_id("sentrymo")
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=user_input.get(CONF_NAME, "Sentrymo"),
                data=user_input,
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="Sentrymo"): str,
                vol.Required(CONF_API_URL, default=DEFAULT_PROD_API_URL): str,
                vol.Required("setup_key"): str,
                vol.Optional(CONF_CPIN): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )