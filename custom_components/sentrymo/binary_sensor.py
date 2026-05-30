"""Binary sensor platform for Sentrymo."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity, BinarySensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import SentrymoDataUpdateCoordinator
from .entity import SentrymoEntity


@dataclass(frozen=True, kw_only=True)
class SentrymoBinarySensorDescription(BinarySensorEntityDescription):
    """Description for a Sentrymo binary sensor."""

    value_fn: Callable[[dict[str, Any]], Any]


BINARY_SENSOR_DESCRIPTIONS: tuple[SentrymoBinarySensorDescription, ...] = (
    SentrymoBinarySensorDescription(
        key="moving",
        translation_key="moving",
        value_fn=lambda vehicle: vehicle.get("state", {}).get("moving"),
    ),
    SentrymoBinarySensorDescription(
        key="ignition",
        translation_key="ignition",
        device_class=BinarySensorDeviceClass.POWER,
        value_fn=lambda vehicle: vehicle.get("state", {}).get("ignition"),
    ),
    SentrymoBinarySensorDescription(
        key="protection_active",
        translation_key="protection_active",
        device_class=BinarySensorDeviceClass.SAFETY,
        value_fn=lambda vehicle: vehicle.get("state", {}).get("protection_active"),
    ),
    SentrymoBinarySensorDescription(
        key="alarm_active",
        translation_key="alarm_active",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda vehicle: vehicle.get("state", {}).get("alarm_active"),
    ),
    SentrymoBinarySensorDescription(
        key="online",
        translation_key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda vehicle: vehicle.get("state", {}).get("online"),
    ),
    SentrymoBinarySensorDescription(
        key="charging",
        translation_key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=lambda vehicle: vehicle.get("state", {}).get("charging"),
    ),
    SentrymoBinarySensorDescription(
        key="crash_detected",
        translation_key="crash_detected",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=lambda vehicle: vehicle.get("state", {}).get("crash_detected"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up Sentrymo binary sensors."""
    coordinator: SentrymoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    known_entity_keys: set[tuple[str, str]] = set()

    def _build_entities() -> list[SentrymoBinarySensor]:
        entities: list[SentrymoBinarySensor] = []
        for vehicle in coordinator.vehicles:
            vehicle_id = str(vehicle.get("vehicle_id"))
            for description in BINARY_SENSOR_DESCRIPTIONS:
                marker = (vehicle_id, description.key)
                if marker in known_entity_keys:
                    continue
                known_entity_keys.add(marker)
                entities.append(SentrymoBinarySensor(coordinator, vehicle_id, description))
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


class SentrymoBinarySensor(SentrymoEntity, BinarySensorEntity):
    """Represent a Sentrymo binary sensor."""

    entity_description: SentrymoBinarySensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SentrymoDataUpdateCoordinator,
        vehicle_id: str,
        description: SentrymoBinarySensorDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, vehicle_id, description.key)
        self.entity_description = description
        self._attr_translation_key = description.translation_key

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        value = self.entity_description.value_fn(self.vehicle)
        return None if value is None else bool(value)
