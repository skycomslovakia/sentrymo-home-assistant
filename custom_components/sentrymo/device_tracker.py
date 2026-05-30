"""Device tracker platform for Sentrymo."""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import SentrymoDataUpdateCoordinator
from .entity import SentrymoEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up Sentrymo device trackers."""
    coordinator: SentrymoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    known_vehicle_ids: set[str] = set()

    def _build_entities() -> list[SentrymoTrackerEntity]:
        entities: list[SentrymoTrackerEntity] = []
        for vehicle in coordinator.vehicles:
            vehicle_id = str(vehicle.get("vehicle_id"))
            if vehicle_id in known_vehicle_ids:
                continue
            known_vehicle_ids.add(vehicle_id)
            entities.append(SentrymoTrackerEntity(coordinator, vehicle_id))
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


class SentrymoTrackerEntity(SentrymoEntity, TrackerEntity):
    """Represent a Sentrymo vehicle tracker."""

    _attr_has_entity_name = True
    _attr_translation_key = "location"

    def __init__(self, coordinator: SentrymoDataUpdateCoordinator, vehicle_id: str) -> None:
        """Initialize the tracker."""
        super().__init__(coordinator, vehicle_id, "location")

    @property
    def source_type(self) -> SourceType:
        """Return tracker source type."""
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        """Return latitude."""
        value = self.vehicle_location.get("lat")
        return float(value) if isinstance(value, (int, float)) else None

    @property
    def longitude(self) -> float | None:
        """Return longitude."""
        value = self.vehicle_location.get("lon")
        return float(value) if isinstance(value, (int, float)) else None

    @property
    def location_accuracy(self) -> int:
        """Return location accuracy."""
        value = self.vehicle_location.get("accuracy")
        if isinstance(value, (int, float)):
            return int(value)
        return 0

    @property
    def battery_level(self) -> int | None:
        """Return battery or fuel level if available."""
        for key in ("fuel_level_percent", "fuel_level"):
            value = self.vehicle_state.get(key)
            if isinstance(value, (int, float)):
                return max(0, min(100, int(value)))
        return None

    @property
    def available(self) -> bool:
        """Tracker is available only with coordinates."""
        return super().available and self.latitude is not None and self.longitude is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra tracker attributes."""
        return {
            "vehicle_id": self.vehicle_id,
            "speed": self.vehicle_state.get("speed_kmh"),
            "heading": self.vehicle_location.get("heading"),
            "last_update": self.vehicle.get("updated_at"),
            "ignition": self.vehicle_state.get("ignition"),
            "moving": self.vehicle_state.get("moving"),
            "alarm_active": self.vehicle_state.get("alarm_active"),
            "protection_active": self.vehicle_state.get("protection_active"),
        }
