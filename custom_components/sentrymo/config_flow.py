"""Config flow for Sentrymo."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import (
    SentrymoApiClient,
    SentrymoCannotConnect,
    SentrymoInvalidAuth,
    SentrymoPackageUnavailable,
)
from .const import (
    API_ENVIRONMENT_BETA,
    API_ENVIRONMENT_PRODUCTION,
    API_ENVIRONMENT_URLS,
    CONF_ACCESS_TOKEN,
    CONF_API_ENVIRONMENT,
    CONF_API_URL,
    CONF_CPIN,
    CONF_REFRESH_TOKEN,
    CONF_SETUP_KEY,
    CONF_TOKEN_EXPIRES_AT,
    DEFAULT_API_ENVIRONMENT,
    DOMAIN,
)

API_ENVIRONMENT_OPTIONS = [
    API_ENVIRONMENT_PRODUCTION,
    API_ENVIRONMENT_BETA,
]


def _api_environment_selector() -> SelectSelector:
    """Return the API environment selector."""
    return SelectSelector(
        SelectSelectorConfig(
            options=API_ENVIRONMENT_OPTIONS,
            mode=SelectSelectorMode.DROPDOWN,
            translation_key=CONF_API_ENVIRONMENT,
        )
    )


def _resolve_api_url(api_environment: str) -> str:
    """Resolve the selected environment to an internal API URL."""
    return API_ENVIRONMENT_URLS.get(api_environment, API_ENVIRONMENT_URLS[DEFAULT_API_ENVIRONMENT])


def _environment_from_api_url(api_url: str | None) -> str:
    """Infer the environment from a persisted API URL."""
    normalized_api_url = SentrymoApiClient.normalize_api_url(api_url)
    for environment, environment_url in API_ENVIRONMENT_URLS.items():
        if normalized_api_url == SentrymoApiClient.normalize_api_url(environment_url):
            return environment
    return DEFAULT_API_ENVIRONMENT


class SentrymoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sentrymo."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SentrymoOptionsFlow:
        """Create the options flow."""
        return SentrymoOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict | None = None):
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_url = _resolve_api_url(user_input[CONF_API_ENVIRONMENT])
            normalized_api_url = SentrymoApiClient.normalize_api_url(api_url)
            await self.async_set_unique_id(normalized_api_url.lower())
            self._abort_if_unique_id_configured()

            cpin = (user_input.get(CONF_CPIN) or "").strip()
            if cpin and (not cpin.isdigit() or len(cpin) != 4):
                errors["base"] = "invalid_cpin"
            else:
                try:
                    client = SentrymoApiClient(async_get_clientsession(self.hass))
                    await client.async_exchange_setup_key(
                        api_url,
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
                vol.Required(
                    CONF_API_ENVIRONMENT,
                    default=DEFAULT_API_ENVIRONMENT,
                ): _api_environment_selector(),
                vol.Required(CONF_SETUP_KEY): str,
                vol.Optional(CONF_CPIN): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )


class SentrymoOptionsFlow(config_entries.OptionsFlow):
    """Handle Sentrymo options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Manage integration options."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_API_URL: _resolve_api_url(user_input[CONF_API_ENVIRONMENT]),
                },
            )

        current_api_url = self.config_entry.options.get(
            CONF_API_URL,
            self.config_entry.data.get(CONF_API_URL),
        )
        current_environment = _environment_from_api_url(current_api_url)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_API_ENVIRONMENT,
                    default=current_environment,
                ): _api_environment_selector(),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )
