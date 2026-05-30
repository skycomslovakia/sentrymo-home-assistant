"""Config flow for Sentrymo."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    SentrymoApiClient,
    SentrymoCannotConnect,
    SentrymoInvalidAuth,
    SentrymoPackageUnavailable,
)
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_API_URL,
    CONF_CPIN,
    CONF_REFRESH_TOKEN,
    CONF_SETUP_KEY,
    CONF_TOKEN_EXPIRES_AT,
    DEFAULT_PROD_API_URL,
    DOMAIN,
)


class SentrymoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sentrymo."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id("sentrymo")
            self._abort_if_unique_id_configured()

            cpin = (user_input.get(CONF_CPIN) or "").strip()
            if cpin and (not cpin.isdigit() or len(cpin) != 4):
                errors["base"] = "invalid_cpin"
            else:
                try:
                    client = SentrymoApiClient(async_get_clientsession(self.hass))
                    await client.async_exchange_setup_key(
                        user_input[CONF_API_URL],
                        user_input[CONF_SETUP_KEY],
                        cpin,
                        client_name=user_input.get(CONF_NAME),
                    )
                except SentrymoPackageUnavailable:
                    errors["base"] = "package_unavailable"
                except SentrymoCannotConnect:
                    errors["base"] = "cannot_connect"
                except SentrymoInvalidAuth as err:
                    if "no longer valid" in str(err).lower() or "expired" in str(err).lower():
                        errors["base"] = "setup_key_expired"
                    else:
                        errors["base"] = "invalid_auth"
                except Exception:
                    errors["base"] = "unknown"
                else:
                    data = {
                        CONF_NAME: user_input.get(CONF_NAME, "Sentrymo"),
                        CONF_API_URL: client.api_url,
                        CONF_ACCESS_TOKEN: client.access_token,
                        CONF_REFRESH_TOKEN: client.refresh_token,
                        CONF_TOKEN_EXPIRES_AT: client.token_expires_at,
                    }
                    if cpin:
                        data[CONF_CPIN] = cpin

                    return self.async_create_entry(
                        title=user_input.get(CONF_NAME, "Sentrymo"),
                        data=data,
                    )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="Sentrymo"): str,
                vol.Required(CONF_API_URL, default=DEFAULT_PROD_API_URL): str,
                vol.Required(CONF_SETUP_KEY): str,
                vol.Optional(CONF_CPIN): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )
