"""Switch platform for Sentrymo."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_CLIENT, DATA_COORDINATOR, DOMAIN
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
    """Return true when the backend says protection commands can be used."""
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
    """Set up Sentrymo switches."""
    coordinator: SentrymoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    client = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
    known_vehicle_ids: set[str] = set()

    def _build_entities() -> list[SentrymoProtectionSwitch]:
        entities: list[SentrymoProtectionSwitch] = []
        for vehicle in coordinator.vehicles:
            vehicle_id = vehicle.get("vehicle_id")
            if vehicle_id is None:
                continue
            vehicle_id_str = str(vehicle_id)
            if vehicle_id_str in known_vehicle_ids:
                continue
            known_vehicle_ids.add(vehicle_id_str)
            entities.append(SentrymoProtectionSwitch(coordinator, client, vehicle_id_str))
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


class SentrymoProtectionSwitch(SentrymoEntity, SwitchEntity):
    """Switch vehicle protection on/off."""

    _attr_has_entity_name = True
    _attr_translation_key = "protection"

    def __init__(
        self,
        coordinator: SentrymoDataUpdateCoordinator,
        client: Any,
        vehicle_id: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, vehicle_id, "protection")
        self.client = client

    @property
    def is_on(self) -> bool | None:
        """Return true if protection is active."""
        value = _state(self.vehicle).get("protection_active")
        return None if value is None else bool(value)

    @property
    def available(self) -> bool:
        """Return switch availability."""
        return super().available and _supports_protection_commands(self.vehicle)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable protection."""
        await self.client.async_set_protection_active(self.vehicle_id, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable protection."""
        await self.client.async_set_protection_active(self.vehicle_id, False)
        await self.coordinator.async_request_refresh()
