"""Device tracker platform for Sentrymo."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.core import callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import SentrymoDataUpdateCoordinator
from .entity import SentrymoEntity


def _location(vehicle: dict[str, Any]) -> dict[str, Any]:
    """Return vehicle location safely."""
    location = vehicle.get("location", {})
    return location if isinstance(location, dict) else {}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up Sentrymo device trackers."""
    coordinator: SentrymoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    known_vehicle_ids: set[str] = set()

    def _build_entities() -> list[SentrymoDeviceTracker]:
        entities: list[SentrymoDeviceTracker] = []
        for vehicle in coordinator.vehicles:
            vehicle_id = vehicle.get("vehicle_id")
            if vehicle_id is None:
                continue

            vehicle_id_str = str(vehicle_id)
            if vehicle_id_str in known_vehicle_ids:
                continue

            known_vehicle_ids.add(vehicle_id_str)
            entities.append(SentrymoDeviceTracker(coordinator, vehicle_id_str))
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


class SentrymoDeviceTracker(SentrymoEntity, TrackerEntity):
    """Represent the latest vehicle location."""

    _attr_has_entity_name = True
    _attr_translation_key = "location"

    def __init__(self, coordinator: SentrymoDataUpdateCoordinator, vehicle_id: str) -> None:
        """Initialize the device tracker."""
        super().__init__(coordinator, vehicle_id, "location")

    @property
    def latitude(self) -> float | None:
        """Return latitude."""
        value = _location(self.vehicle).get("lat")
        return float(value) if isinstance(value, (int, float)) else None

    @property
    def longitude(self) -> float | None:
        """Return longitude."""
        value = _location(self.vehicle).get("lon")
        return float(value) if isinstance(value, (int, float)) else None

    @property
    def location_accuracy(self) -> int:
        """Return location accuracy in meters when available."""
        value = _location(self.vehicle).get("accuracy")
        return int(value) if isinstance(value, (int, float)) else 0

    @property
    def source_type(self) -> SourceType:
        """Return the source type."""
        return SourceType.GPS

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra location-related attributes."""
        location = _location(self.vehicle)
        attributes: dict[str, Any] = {}
        for key in ("heading", "address", "places"):
            value = location.get(key)
            if value is not None:
                attributes[key] = value
        return attributes
