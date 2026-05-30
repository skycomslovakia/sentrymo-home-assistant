"""Button platform for Sentrymo."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import SentrymoDataUpdateCoordinator
from .entity import SentrymoEntity

# The backend currently requires a runtime CPIN header for protection commands.
# We intentionally expose only refresh actions until commands can be invoked
# without persisting CPIN in Home Assistant configuration or automations.
REFRESH_DESCRIPTION = ButtonEntityDescription(
    key="refresh_snapshot",
    translation_key="refresh_snapshot",
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
            vehicle_id = str(vehicle.get("vehicle_id"))
            if vehicle_id in known_vehicle_ids:
                continue
            known_vehicle_ids.add(vehicle_id)
            entities.append(SentrymoRefreshButton(coordinator, vehicle_id))
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
    """Refresh a vehicle snapshot on demand."""

    entity_description = REFRESH_DESCRIPTION
    _attr_has_entity_name = True

    def __init__(self, coordinator: SentrymoDataUpdateCoordinator, vehicle_id: str) -> None:
        """Initialize the button."""
        super().__init__(coordinator, vehicle_id, REFRESH_DESCRIPTION.key)
        self._attr_translation_key = REFRESH_DESCRIPTION.translation_key

    async def async_press(self) -> None:
        """Refresh the coordinator snapshot."""
        await self.coordinator.async_request_refresh()
