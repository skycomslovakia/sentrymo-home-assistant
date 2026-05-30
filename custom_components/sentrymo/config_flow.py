"""Config flow for Sentrymo."""

from __future__ import annotations

from hashlib import sha256
import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.instance_id import async_get as async_get_instance_id

from .api import (
    SentrymoApiClient,
    SentrymoApiError,
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
    DEFAULT_CLIENT_NAME,
    DEFAULT_ENTRY_TITLE,
    DEFAULT_PROD_API_URL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
_CPIN_RE = re.compile(r"^\d{4}$")


def _normalize_api_url(api_url: str) -> str:
    """Normalize API URL for storage and requests."""
    return SentrymoApiClient.normalize_api_url(api_url)


async def _build_unique_id(client: SentrymoApiClient) -> str:
    """Build a stable unique id from profile and vehicles."""
    profile = await client.async_get_profile()
    vehicles = await client.async_get_vehicles()
    account = profile.get("account", {}) if isinstance(profile, dict) else {}
    vehicles_list = vehicles.get("vehicles", []) if isinstance(vehicles, dict) else []
    vehicle_ids = sorted(
        str(vehicle.get("id"))
        for vehicle in vehicles_list
        if isinstance(vehicle, dict) and vehicle.get("id") is not None
    )
    seed = "|".join(
        [
            client.api_url,
            str(account.get("name") or ""),
            str(account.get("package") or ""),
            ",".join(vehicle_ids),
        ]
    )
    return f"sentrymo_{sha256(seed.encode('utf-8')).hexdigest()[:16]}"


class SentrymoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sentrymo."""

    VERSION = 1
    reauth_entry: config_entries.ConfigEntry | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors, entry_payload, unique_id = await self._async_exchange(user_input)
            if not errors and entry_payload is not None and unique_id is not None:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=entry_payload[CONF_NAME],
                    data=entry_payload,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self._build_user_schema(user_input),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]):
        """Start reauth flow."""
        del entry_data
        entry_id = self.context.get("entry_id")
        self.reauth_entry = self.hass.config_entries.async_get_entry(entry_id) if entry_id else None
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None):
        """Handle the reauth confirmation step."""
        if self.reauth_entry is None:
            return self.async_abort(reason="unknown")

        errors: dict[str, str] = {}
        if user_input is not None:
            merged_input = {
                CONF_NAME: self.reauth_entry.title or self.reauth_entry.data.get(CONF_NAME, DEFAULT_ENTRY_TITLE),
                CONF_API_URL: user_input[CONF_API_URL],
                CONF_SETUP_KEY: user_input[CONF_SETUP_KEY],
                CONF_CPIN: user_input[CONF_CPIN],
            }
            errors, entry_payload, unique_id = await self._async_exchange(merged_input)
            if not errors and entry_payload is not None and unique_id is not None:
                self.hass.config_entries.async_update_entry(
                    self.reauth_entry,
                    title=entry_payload[CONF_NAME],
                    data=entry_payload,
                    unique_id=unique_id,
                )
                await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        current_url = self.reauth_entry.options.get(CONF_API_URL, self.reauth_entry.data.get(CONF_API_URL, DEFAULT_PROD_API_URL))
        schema = vol.Schema(
            {
                vol.Required(CONF_API_URL, default=current_url): str,
                vol.Required(CONF_SETUP_KEY): str,
                vol.Required(CONF_CPIN): str,
            }
        )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @config_entries.callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Get options flow."""
        return SentrymoOptionsFlow(config_entry)

    def _build_user_schema(self, user_input: dict[str, Any] | None) -> vol.Schema:
        """Build schema for the main config form."""
        data = user_input or {}
        return vol.Schema(
            {
                vol.Required(CONF_NAME, default=data.get(CONF_NAME, DEFAULT_ENTRY_TITLE)): str,
                vol.Required(CONF_API_URL, default=data.get(CONF_API_URL, DEFAULT_PROD_API_URL)): str,
                vol.Required(CONF_SETUP_KEY, default=data.get(CONF_SETUP_KEY, "")): str,
                vol.Required(CONF_CPIN, default=data.get(CONF_CPIN, "")): str,
            }
        )

    async def _async_exchange(
        self,
        user_input: dict[str, Any],
    ) -> tuple[dict[str, str], dict[str, Any] | None, str | None]:
        """Validate form input and exchange the setup key."""
        cpin = str(user_input.get(CONF_CPIN, "")).strip()
        if not _CPIN_RE.fullmatch(cpin):
            return {"base": "invalid_cpin"}, None, None

        api_url = _normalize_api_url(str(user_input[CONF_API_URL]))
        client = SentrymoApiClient(async_get_clientsession(self.hass), api_url=api_url)

        try:
            ha_instance_id = await async_get_instance_id(self.hass)

            await client.async_exchange_setup_key(
                api_url,
                str(user_input[CONF_SETUP_KEY]).strip(),
                cpin,
                client_name=str(user_input.get(CONF_NAME) or DEFAULT_CLIENT_NAME),
                ha_instance_id=ha_instance_id,
            )
            unique_id = await _build_unique_id(client)
        except SentrymoCannotConnect:
            return {"base": "cannot_connect"}, None, None
        except SentrymoPackageUnavailable:
            return {"base": "package_unavailable"}, None, None
        except SentrymoInvalidAuth as err:
            if "expired" in str(err).lower():
                return {"base": "setup_key_expired"}, None, None
            return {"base": "invalid_auth"}, None, None
        except SentrymoApiError:
            _LOGGER.exception("Unexpected Sentrymo API error during config flow")
            return {"base": "unknown"}, None, None
        except Exception:
            _LOGGER.exception("Unexpected error during Sentrymo config flow")
            return {"base": "unknown"}, None, None

        entry_payload = {
            CONF_NAME: str(user_input.get(CONF_NAME) or DEFAULT_ENTRY_TITLE),
            CONF_API_URL: api_url,
            CONF_ACCESS_TOKEN: client.access_token,
            CONF_REFRESH_TOKEN: client.refresh_token,
            CONF_TOKEN_EXPIRES_AT: client.token_expires_at,
        }
        return {}, entry_payload, unique_id


class SentrymoOptionsFlow(config_entries.OptionsFlow):
    """Sentrymo options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Manage integration options."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={CONF_API_URL: _normalize_api_url(str(user_input[CONF_API_URL]))},
            )

        current_url = self.config_entry.options.get(CONF_API_URL, self.config_entry.data.get(CONF_API_URL, DEFAULT_PROD_API_URL))
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({vol.Required(CONF_API_URL, default=current_url): str}),
        )
