"""Button platform for Sentrymo."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import SentrymoDataUpdateCoordinator
from .entity import SentrymoEntity

REFRESH_DESCRIPTION = ButtonEntityDescription(
    key="refresh_data",
    translation_key="refresh_data",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up Sentrymo buttons."""
    coordinator: SentrymoDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    known_vehicle_ids: set[str] = set()

    def _build_entities() -> list[SentrymoRefreshButton]:
        entities: list[SentrymoRefreshButton] = []
        for vehicle in coordinator.vehicles:
            vehicle_id = vehicle.get("vehicle_id")
            if vehicle_id is None:
                continue
            vehicle_id_str = str(vehicle_id)
            if vehicle_id_str in known_vehicle_ids:
                continue
            known_vehicle_ids.add(vehicle_id_str)
            entities.append(SentrymoRefreshButton(coordinator, vehicle_id_str))
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


class SentrymoRefreshButton(SentrymoEntity, ButtonEntity):
    """Refresh vehicle data on demand."""

    entity_description = REFRESH_DESCRIPTION
    _attr_has_entity_name = True

    def __init__(self, coordinator: SentrymoDataUpdateCoordinator, vehicle_id: str) -> None:
        """Initialize the button."""
        super().__init__(coordinator, vehicle_id, REFRESH_DESCRIPTION.key)
        self._attr_translation_key = REFRESH_DESCRIPTION.translation_key

    async def async_press(self) -> None:
        """Force refresh the coordinator snapshot."""
        await self.coordinator.async_force_refresh()
