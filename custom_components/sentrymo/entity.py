"""Shared entity helpers for Sentrymo."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SentrymoDataUpdateCoordinator


class SentrymoEntity(CoordinatorEntity[SentrymoDataUpdateCoordinator]):
    """Base coordinator entity for Sentrymo vehicles."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SentrymoDataUpdateCoordinator,
        vehicle_id: str,
        entity_key: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.vehicle_id = str(vehicle_id)
        self.entity_key = entity_key

    @property
    def vehicle(self) -> dict[str, Any]:
        """Return current vehicle data."""
        return self.coordinator.vehicle_by_id(self.vehicle_id) or {}

    @property
    def vehicle_state(self) -> dict[str, Any]:
        """Return current vehicle state."""
        state = self.vehicle.get("state", {})
        return state if isinstance(state, dict) else {}

    @property
    def vehicle_location(self) -> dict[str, Any]:
        """Return current vehicle location."""
        location = self.vehicle.get("location", {})
        return location if isinstance(location, dict) else {}

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return self.coordinator.last_update_success and bool(self.vehicle)

    @property
    def unique_id(self) -> str:
        """Return unique id."""
        return f"sentrymo_{self.vehicle_id}_{self.entity_key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the vehicle."""
        package = self.vehicle.get("package")
        model = package.title() if isinstance(package, str) and package else "Vehicle"
        return DeviceInfo(
            identifiers={(DOMAIN, self.vehicle_id)},
            manufacturer="Sentrymo",
            name=str(self.vehicle.get("name") or f"Vehicle {self.vehicle_id}"),
            model=model,
        )
