"""Sensor platform for Sentrymo."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfElectricPotential, UnitOfLength, UnitOfSpeed
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import SentrymoDataUpdateCoordinator
from .entity import SentrymoEntity


@dataclass(frozen=True, kw_only=True)
class SentrymoSensorDescription(SensorEntityDescription):
    """Description for a Sentrymo sensor."""

    value_fn: Callable[[dict[str, Any]], Any]


SENSOR_DESCRIPTIONS: tuple[SentrymoSensorDescription, ...] = (
    SentrymoSensorDescription(
        key="speed",
        translation_key="speed",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda vehicle: vehicle.get("state", {}).get("speed_kmh"),
    ),
    SentrymoSensorDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda vehicle: vehicle.get("state", {}).get("battery_voltage"),
    ),
    SentrymoSensorDescription(
        key="external_voltage",
        translation_key="external_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda vehicle: vehicle.get("state", {}).get("external_voltage"),
    ),
    SentrymoSensorDescription(
        key="fuel_level",
        translation_key="fuel_level",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda vehicle: vehicle.get("state", {}).get("fuel_level_percent") or vehicle.get("state", {}).get("fuel_level"),
    ),
    SentrymoSensorDescription(
        key="gsm_signal",
        translation_key="gsm_signal",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda vehicle: _scale_gsm_signal(vehicle.get("state", {}).get("gsm_signal")),
    ),
    SentrymoSensorDescription(
        key="odometer",
        translation_key="odometer",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda vehicle: vehicle.get("state", {}).get("odometer_km"),
    ),
    SentrymoSensorDescription(
        key="last_update",
        translation_key="last_update",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda vehicle: _parse_datetime(vehicle.get("updated_at") or vehicle.get("state", {}).get("last_seen_at")),
    ),
    SentrymoSensorDescription(
        key="ignition_state",
        translation_key="ignition_state",
        value_fn=lambda vehicle: _bool_to_text(vehicle.get("state", {}).get("ignition")),
    ),
    SentrymoSensorDescription(
        key="vehicle_status",
        translation_key="vehicle_status",
        value_fn=_vehicle_status,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up Sentrymo sensors."""
    coordinator: SentrymoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    known_entity_keys: set[tuple[str, str]] = set()

    def _build_entities() -> list[SentrymoSensor]:
        entities: list[SentrymoSensor] = []
        for vehicle in coordinator.vehicles:
            vehicle_id = str(vehicle.get("vehicle_id"))
            for description in SENSOR_DESCRIPTIONS:
                marker = (vehicle_id, description.key)
                if marker in known_entity_keys:
                    continue
                known_entity_keys.add(marker)
                entities.append(SentrymoSensor(coordinator, vehicle_id, description))
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


class SentrymoSensor(SentrymoEntity, SensorEntity):
    """Represent a Sentrymo sensor."""

    entity_description: SentrymoSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SentrymoDataUpdateCoordinator,
        vehicle_id: str,
        description: SentrymoSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, vehicle_id, description.key)
        self.entity_description = description
        self._attr_translation_key = description.translation_key

    @property
    def native_value(self) -> Any:
        """Return native value."""
        return self.entity_description.value_fn(self.vehicle)


def _parse_datetime(value: Any) -> datetime | None:
    """Parse datetime values safely."""
    if isinstance(value, str):
        return dt_util.parse_datetime(value)
    return value if isinstance(value, datetime) else None


def _scale_gsm_signal(value: Any) -> int | None:
    """Scale backend GSM signal strength to percentage."""
    if not isinstance(value, (int, float)):
        return None
    if value <= 5:
        return max(0, min(100, int(round((float(value) / 5) * 100))))
    return max(0, min(100, int(value)))


def _bool_to_text(value: Any) -> str | None:
    """Convert boolean values to text."""
    if value is None:
        return None
    return "on" if bool(value) else "off"


def _vehicle_status(vehicle: dict[str, Any]) -> str:
    """Build a compact text status."""
    state = vehicle.get("state", {})
    if state.get("alarm_active"):
        return "alarm"
    if state.get("crash_detected"):
        return "crash"
    if state.get("moving"):
        return "moving"
    if state.get("ignition"):
        return "ignition_on"
    if state.get("online") is False:
        return "offline"
    return "idle"
