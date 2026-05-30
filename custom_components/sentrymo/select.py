"""Select platform for Sentrymo."""

from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DATA_CLIENT,
    DATA_COORDINATOR,
    DOMAIN,
    PROTECTION_MODE_OPTIONS,
)
from .coordinator import SentrymoDataUpdateCoordinator
from .entity import SentrymoEntity


def _capabilities(vehicle: dict[str, Any]) -> dict[str, Any]:
    """Return vehicle capabilities safely."""
    capabilities = vehicle.get("capabilities", {})
    return capabilities if isinstance(capabilities, dict) else {}


def _state(vehicle: dict[str, Any]) -> dict[str, Any]:
    """Return vehicle state safely."""
    state = vehicle.get("state", {})
    return state if isinstance(state, dict) else {}


def _supports_protection_commands(vehicle: dict[str, Any]) -> bool:
    """Return true when the backend says protection mode can be changed."""
    capabilities = _capabilities(vehicle)
    return bool(
        capabilities.get("protection_commands")
        or capabilities.get("commands_enabled")
        or capabilities.get("commands")
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up Sentrymo selects."""
    coordinator: SentrymoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    client = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
    known_vehicle_ids: set[str] = set()

    def _build_entities() -> list[SentrymoProtectionModeSelect]:
        entities: list[SentrymoProtectionModeSelect] = []
        for vehicle in coordinator.vehicles:
            vehicle_id = vehicle.get("vehicle_id")
            if vehicle_id is None:
                continue
            vehicle_id_str = str(vehicle_id)
            if vehicle_id_str in known_vehicle_ids:
                continue
            known_vehicle_ids.add(vehicle_id_str)
            entities.append(SentrymoProtectionModeSelect(coordinator, client, vehicle_id_str))
        return entities

    entities = _build_entities()
    if entities:
        async_add_entities(entities)

    @callback
    def _handle_coordinator_update() -> None:
        new_entities = _build_entities()
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_handle_coordinator_update))
    return True


class SentrymoProtectionModeSelect(SentrymoEntity, SelectEntity):
    """Select vehicle protection mode."""

    _attr_has_entity_name = True
    _attr_translation_key = "protection_mode_control"
    _attr_options = PROTECTION_MODE_OPTIONS

    def __init__(
        self,
        coordinator: SentrymoDataUpdateCoordinator,
        client: Any,
        vehicle_id: str,
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator, vehicle_id, "protection_mode_control")
        self.client = client

    @property
    def current_option(self) -> str | None:
        """Return current protection mode."""
        value = _state(self.vehicle).get("protection_mode")
        if isinstance(value, str) and value in PROTECTION_MODE_OPTIONS:
            return value

        if _state(self.vehicle).get("protection_active") is True:
            return "manual"

        if _state(self.vehicle).get("protection_active") is False:
            return "disabled"

        return None

    @property
    def available(self) -> bool:
        """Return select availability."""
        return super().available and _supports_protection_commands(self.vehicle)

    async def async_select_option(self, option: str) -> None:
        """Set protection mode."""
        if option not in PROTECTION_MODE_OPTIONS:
            return

        await self.client.async_set_protection_mode(self.vehicle_id, option)
        await self.coordinator.async_force_refresh()
