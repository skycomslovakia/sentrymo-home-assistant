"""Data coordinators for the Sentrymo integration."""

from __future__ import annotations

import asyncio
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

    def async_apply_vehicle_state(self, vehicle_id: str | int, **state_updates: Any) -> None:
        """Apply a local optimistic state update for a vehicle."""
        current = self.data or {}
        vehicles = current.get("vehicles")
        if not isinstance(vehicles, list):
            return

        target = str(vehicle_id)
        updated_vehicles: list[dict[str, Any]] = []
        changed = False

        for vehicle in vehicles:
            if not isinstance(vehicle, dict):
                updated_vehicles.append(vehicle)
                continue

            if str(vehicle.get("vehicle_id")) != target:
                updated_vehicles.append(vehicle)
                continue

            updated_vehicle = dict(vehicle)
            state = updated_vehicle.get("state", {})
            updated_state = dict(state) if isinstance(state, dict) else {}
            updated_state.update(state_updates)
            updated_vehicle["state"] = updated_state
            updated_vehicles.append(updated_vehicle)
            changed = True

        if not changed:
            return

        snapshot = dict(current)
        snapshot["vehicles"] = updated_vehicles
        self.async_set_updated_data(snapshot)

    async def async_refresh_after_delay(self, delay_seconds: float) -> None:
        """Refresh after a short delay to reconcile optimistic updates."""
        await asyncio.sleep(delay_seconds)
        await self.async_force_refresh()

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

    async def async_force_refresh(self) -> None:
        """Force a manual refresh.

        This bypasses the local segment cache and asks the backend for a forced refresh.
        If the backend still rate-limits slow/config segments, cached data is reused.
        """
        try:
            snapshot = await self.client.async_get_snapshot(force=True)
        except (SentrymoInvalidAuth, SentrymoAuthError) as err:
            raise ConfigEntryAuthFailed from err
        except SentrymoApiError as err:
            raise UpdateFailed(str(err)) from err

        self.update_interval = self._parse_update_interval(snapshot)
        self.async_set_updated_data(snapshot)

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
