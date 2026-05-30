"""Sentrymo Home Assistant integration."""

from __future__ import annotations

from collections.abc import Iterable

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import SentrymoApiClient
from .const import (
    ATTR_ENTRY_ID,
    ATTR_MODE,
    ATTR_VEHICLE_ID,
    CONF_ACCESS_TOKEN,
    CONF_API_URL,
    CONF_CPIN,
    CONF_REFRESH_TOKEN,
    CONF_SETUP_KEY,
    CONF_TOKEN_EXPIRES_AT,
    DATA_CLIENT,
    DATA_COORDINATOR,
    DATA_SERVICES_REGISTERED,
    DOMAIN,
    PLATFORMS,
    PROTECTION_MODE_OPTIONS,
    SERVICE_REFRESH,
    SERVICE_SET_PROTECTION_MODE,
)
from .coordinator import SentrymoDataUpdateCoordinator


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration domain."""
    del config
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sentrymo from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    async def _async_update_tokens(tokens: dict[str, str]) -> None:
        data = dict(entry.data)
        data.update(tokens)
        hass.config_entries.async_update_entry(entry, data=data)

    client = SentrymoApiClient(
        async_get_clientsession(hass),
        api_url=entry.options.get(CONF_API_URL, entry.data[CONF_API_URL]),
        access_token=entry.data.get(CONF_ACCESS_TOKEN),
        refresh_token=entry.data.get(CONF_REFRESH_TOKEN),
        token_expires_at=entry.data.get(CONF_TOKEN_EXPIRES_AT),
        cpin=entry.data.get(CONF_CPIN),
        token_update_callback=_async_update_tokens,
    )
    await _async_restore_tokens(entry, client, hass)
    coordinator = SentrymoDataUpdateCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_CLIENT: client,
        DATA_COORDINATOR: coordinator,
    }

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await _async_register_services(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Sentrymo config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not [key for key in hass.data[DOMAIN] if key != DATA_SERVICES_REGISTERED]:
            await _async_unregister_services(hass)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload a config entry when options or tokens change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_restore_tokens(
    entry: ConfigEntry,
    client: SentrymoApiClient,
    hass: HomeAssistant,
) -> None:
    """Restore missing tokens for legacy entries before the first refresh."""
    if client.access_token:
        return

    if client.refresh_token:
        await client.async_refresh_token()
        return

    setup_key = entry.data.get(CONF_SETUP_KEY)
    if not isinstance(setup_key, str) or not setup_key:
        return

    await client.async_exchange_setup_key(
        entry.options.get(CONF_API_URL, entry.data[CONF_API_URL]),
        setup_key,
        str(entry.data.get(CONF_CPIN) or ""),
        client_name=str(entry.title or "Sentrymo"),
    )

    data = dict(entry.data)
    data.update(
        {
            CONF_API_URL: client.api_url,
            CONF_ACCESS_TOKEN: client.access_token,
            CONF_REFRESH_TOKEN: client.refresh_token,
            CONF_TOKEN_EXPIRES_AT: client.token_expires_at,
        }
    )
    hass.config_entries.async_update_entry(entry, data=data)


async def _async_register_services(hass: HomeAssistant) -> None:
    """Register services once per domain."""
    if hass.data[DOMAIN].get(DATA_SERVICES_REGISTERED):
        return

    async def async_handle_refresh(call: ServiceCall) -> None:
        for coordinator in _iter_coordinators(hass, call.data.get(ATTR_ENTRY_ID)):
            await coordinator.async_force_refresh()

    async def async_handle_set_protection_mode(call: ServiceCall) -> None:
        vehicle_id = str(call.data[ATTR_VEHICLE_ID])
        mode = str(call.data[ATTR_MODE])
        for data in _iter_entry_data(hass, call.data.get(ATTR_ENTRY_ID)):
            coordinator = data[DATA_COORDINATOR]
            if coordinator.vehicle_by_id(vehicle_id) is None:
                continue
            await data[DATA_CLIENT].async_set_protection_mode(vehicle_id, mode)
            await coordinator.async_force_refresh()
            return

    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH,
        async_handle_refresh,
        schema=vol.Schema({vol.Optional(ATTR_ENTRY_ID): str}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_PROTECTION_MODE,
        async_handle_set_protection_mode,
        schema=vol.Schema(
            {
                vol.Required(ATTR_VEHICLE_ID): vol.Coerce(str),
                vol.Required(ATTR_MODE): vol.In(PROTECTION_MODE_OPTIONS),
                vol.Optional(ATTR_ENTRY_ID): str,
            }
        ),
    )
    hass.data[DOMAIN][DATA_SERVICES_REGISTERED] = True


async def _async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister services when no entries remain."""
    for service in (SERVICE_REFRESH, SERVICE_SET_PROTECTION_MODE):
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)
    hass.data[DOMAIN].pop(DATA_SERVICES_REGISTERED, None)


def _iter_coordinators(
    hass: HomeAssistant,
    target_entry_id: str | None = None,
) -> Iterable[SentrymoDataUpdateCoordinator]:
    """Yield coordinators for configured entries."""
    for data in _iter_entry_data(hass, target_entry_id):
        coordinator = data.get(DATA_COORDINATOR)
        if isinstance(coordinator, SentrymoDataUpdateCoordinator):
            yield coordinator


def _iter_entry_data(
    hass: HomeAssistant,
    target_entry_id: str | None = None,
) -> Iterable[dict]:
    """Yield stored entry data for configured entries."""
    for entry_id, data in hass.data.get(DOMAIN, {}).items():
        if entry_id == DATA_SERVICES_REGISTERED:
            continue
        if target_entry_id is not None and entry_id != target_entry_id:
            continue
        if isinstance(data, dict):
            yield data
