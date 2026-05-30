"""Data coordinators for the Sentrymo integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntryAuthFailed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SentrymoApiClient, SentrymoApiError, SentrymoAuthError, SentrymoInvalidAuth
from .const import DEFAULT_POLL_INTERVAL, DOMAIN, MIN_POLL_INTERVAL

_LOGGER = logging.getLogger(__name__)


class SentrymoDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate Sentrymo snapshot updates."""

    def __init__(self, hass: HomeAssistant, client: SentrymoApiClient) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_POLL_INTERVAL,
        )
        self.client = client

    @property
    def vehicles(self) -> list[dict[str, Any]]:
        """Return vehicles from the last snapshot."""
        data = self.data or {}
        vehicles = data.get("vehicles", [])
        return vehicles if isinstance(vehicles, list) else []

    def vehicle_by_id(self, vehicle_id: str | int) -> dict[str, Any] | None:
        """Find a vehicle by id."""
        target = str(vehicle_id)
        return next((vehicle for vehicle in self.vehicles if str(vehicle.get("vehicle_id")) == target), None)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch fresh data from the Sentrymo API."""
        try:
            snapshot = await self.client.async_get_snapshot()
        except (SentrymoInvalidAuth, SentrymoAuthError) as err:
            raise ConfigEntryAuthFailed from err
        except SentrymoApiError as err:
            raise UpdateFailed(str(err)) from err

        self.update_interval = self._parse_update_interval(snapshot)
        return snapshot

    def _parse_update_interval(self, snapshot: dict[str, Any]) -> timedelta:
        """Resolve polling interval from snapshot data."""
        polling = snapshot.get("polling", {})
        seconds = None
        if isinstance(polling, dict):
            fast = polling.get("fast")
            if isinstance(fast, int) and fast > 0:
                seconds = fast

        if seconds is None:
            return DEFAULT_POLL_INTERVAL

        return timedelta(
            seconds=max(
                int(MIN_POLL_INTERVAL.total_seconds()),
                seconds,
            )
        )
