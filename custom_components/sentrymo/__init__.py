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
    CONF_ACCESS_TOKEN,
    CONF_API_URL,
    CONF_REFRESH_TOKEN,
    CONF_TOKEN_EXPIRES_AT,
    DATA_CLIENT,
    DATA_COORDINATOR,
    DATA_SERVICES_REGISTERED,
    DOMAIN,
    PLATFORMS,
    SERVICE_REFRESH,
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
        token_update_callback=_async_update_tokens,
    )
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


async def _async_register_services(hass: HomeAssistant) -> None:
    """Register services once per domain."""
    if hass.data[DOMAIN].get(DATA_SERVICES_REGISTERED):
        return

    async def async_handle_refresh(call: ServiceCall) -> None:
        for coordinator in _iter_coordinators(hass, call.data.get(ATTR_ENTRY_ID)):
            await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH,
        async_handle_refresh,
        schema=vol.Schema({vol.Optional(ATTR_ENTRY_ID): str}),
    )
    hass.data[DOMAIN][DATA_SERVICES_REGISTERED] = True


async def _async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister services when no entries remain."""
    if hass.services.has_service(DOMAIN, SERVICE_REFRESH):
        hass.services.async_remove(DOMAIN, SERVICE_REFRESH)
    hass.data[DOMAIN].pop(DATA_SERVICES_REGISTERED, None)


def _iter_coordinators(
    hass: HomeAssistant,
    target_entry_id: str | None = None,
) -> Iterable[SentrymoDataUpdateCoordinator]:
    """Yield coordinators for configured entries."""
    for entry_id, data in hass.data.get(DOMAIN, {}).items():
        if entry_id == DATA_SERVICES_REGISTERED:
            continue
        if target_entry_id is not None and entry_id != target_entry_id:
            continue
        coordinator = data.get(DATA_COORDINATOR)
        if isinstance(coordinator, SentrymoDataUpdateCoordinator):
            yield coordinator
