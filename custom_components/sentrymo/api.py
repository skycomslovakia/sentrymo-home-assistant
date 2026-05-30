"""API client for the Sentrymo integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, timedelta
import logging
from typing import Any

import async_timeout
from aiohttp import ClientError, ClientResponse, ClientSession

from homeassistant.util import dt as dt_util

from .const import (
    API_AUTH_EXCHANGE,
    API_AUTH_REFRESH,
    API_PROFILE,
    API_STATE_CONFIG,
    API_STATE_FAST,
    API_STATE_SLOW,
    API_STATE_TELEMETRY,
    API_VEHICLES,
    COMMAND_PROTECTION_ACTIVATE,
    COMMAND_PROTECTION_AUTO,
    COMMAND_PROTECTION_DEACTIVATE,
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
    CONF_TOKEN_EXPIRES_AT,
    DEFAULT_EXCHANGE_PAYLOAD,
    DEFAULT_PROD_API_URL,
    DEFAULT_SOURCE,
    PROTECTION_MODE_AUTOMATIC,
    PROTECTION_MODE_DISABLED,
    PROTECTION_MODE_MANUAL,
)

_LOGGER = logging.getLogger(__name__)

TokenUpdateCallback = Callable[[dict[str, str]], Awaitable[None]]


class SentrymoApiError(Exception):
    """Base exception for Sentrymo API errors."""


class SentrymoCannotConnect(SentrymoApiError):
    """Raised when the API cannot be reached."""


class SentrymoAuthError(SentrymoApiError):
    """Raised when authentication fails."""


class SentrymoInvalidAuth(SentrymoAuthError):
    """Raised when credentials are invalid."""


class SentrymoPackageUnavailable(SentrymoApiError):
    """Raised when the user package does not support the integration."""


class SentrymoRateLimited(SentrymoApiError):
    """Raised when a segment is polled too frequently."""


class SentrymoCommandError(SentrymoApiError):
    """Raised when a command request fails."""

    def __init__(self, message: str, *, code: str | None = None) -> None:
        """Initialize the exception."""
        super().__init__(message)
        self.code = code


class SentrymoApiClient:
    """Async Sentrymo API client."""

    def __init__(
        self,
        session: ClientSession,
        api_url: str = DEFAULT_PROD_API_URL,
        access_token: str | None = None,
        refresh_token: str | None = None,
        token_expires_at: str | None = None,
        cpin: str | None = None,
        *,
        token_update_callback: TokenUpdateCallback | None = None,
    ) -> None:
        """Initialize the API client."""
        self._session = session
        self.api_url = self.normalize_api_url(api_url)
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_expires_at = token_expires_at
        self.cpin = cpin
        self._token_update_callback = token_update_callback
        self._segment_cache: dict[str, dict[str, Any]] = {}
        self._segment_next_refresh: dict[str, Any] = {}

    @staticmethod
    def normalize_api_url(api_url: str | None) -> str:
        """Normalize API URL input to `/ha-api/v1` base."""
        base_url = (api_url or DEFAULT_PROD_API_URL).strip().rstrip("/")
        lowered = base_url.lower()

        if lowered.endswith("/ha-api/v1"):
            return base_url
        if lowered.endswith("/ha-api"):
            return f"{base_url}/v1"
        if "/ha-api/" in lowered:
            return base_url

        return f"{base_url}/ha-api/v1"

    def clear_segment_cache(self) -> None:
        """Clear cached state segments."""
        self._segment_cache.clear()
        self._segment_next_refresh.clear()

    def set_tokens(
        self,
        *,
        access_token: str | None = None,
        refresh_token: str | None = None,
        token_expires_at: str | None = None,
        access_token_expires_at: str | None = None,
    ) -> None:
        """Update in-memory tokens."""
        if access_token:
            self.access_token = access_token
        if refresh_token:
            self.refresh_token = refresh_token

        resolved_expires_at = token_expires_at or access_token_expires_at
        if resolved_expires_at:
            self.token_expires_at = resolved_expires_at

    async def async_exchange_setup_key(
        self,
        api_url: str,
        setup_key: str,
        cpin: str,
        *,
        client_name: str | None = None,
        ha_instance_id: str | None = None,
    ) -> dict[str, Any]:
        """Exchange a setup key for tokens."""
        self.api_url = self.normalize_api_url(api_url)
        self.cpin = cpin

        response = await self._request(
            "post",
            API_AUTH_EXCHANGE,
            json_payload={
                "setup_key": setup_key,
                "cpin": cpin,
                "client_name": client_name,
                "ha_instance_id": ha_instance_id,
                "requested_polling": DEFAULT_EXCHANGE_PAYLOAD,
            },
            require_auth=False,
            allow_refresh=False,
        )

        tokens = self._extract_tokens(response)
        self.set_tokens(**tokens)

        return response

    async def async_refresh_token(self) -> dict[str, Any]:
        """Refresh access token."""
        if not self.refresh_token:
            raise SentrymoAuthError("Refresh token missing")

        response = await self._request(
            "post",
            API_AUTH_REFRESH,
            json_payload={CONF_REFRESH_TOKEN: self.refresh_token},
            require_auth=False,
            allow_refresh=False,
        )

        tokens = self._extract_tokens(response, refresh_token=self.refresh_token)
        self.set_tokens(**tokens)

        if self._token_update_callback is not None:
            await self._token_update_callback(tokens)

        return response

    async def async_get_profile(self) -> dict[str, Any]:
        """Fetch profile payload."""
        return await self._request("get", API_PROFILE)

    async def async_get_vehicles(self) -> dict[str, Any]:
        """Fetch vehicles payload."""
        return await self._request("get", API_VEHICLES)

    async def async_get_snapshot(self, *, force: bool = False) -> dict[str, Any]:
        """Fetch and merge profile, vehicles and optional state segments into one snapshot."""
        polling: dict[str, int] = {}
        merged: dict[str, dict[str, Any]] = {}
        server_time: str | None = None
        account: dict[str, Any] = {}
        capabilities: dict[str, Any] = {}

        if force:
            self.clear_segment_cache()

        try:
            profile = await self.async_get_profile()
        except SentrymoApiError as err:
            _LOGGER.warning("Sentrymo profile endpoint failed: %s", err)
            profile = {}

        if isinstance(profile, Mapping):
            profile_polling = profile.get("polling")
            if isinstance(profile_polling, Mapping):
                for key, value in profile_polling.items():
                    if isinstance(value, int):
                        polling[str(key)] = value

            profile_account = profile.get("account")
            if isinstance(profile_account, Mapping):
                account = dict(profile_account)

            profile_capabilities = profile.get("capabilities")
            if isinstance(profile_capabilities, Mapping):
                capabilities = dict(profile_capabilities)

            profile_server = profile.get("server")
            if isinstance(profile_server, Mapping):
                maybe_server_time = profile_server.get("server_time")
                if isinstance(maybe_server_time, str):
                    server_time = maybe_server_time

        try:
            vehicles_response = await self.async_get_vehicles()
        except SentrymoApiError as err:
            _LOGGER.warning("Sentrymo vehicles endpoint failed: %s", err)
            vehicles_response = {}

        vehicles = vehicles_response.get("vehicles") if isinstance(vehicles_response, Mapping) else []
        if isinstance(vehicles, list):
            for vehicle in vehicles:
                if not isinstance(vehicle, Mapping):
                    continue

                vehicle_id = self._coerce_vehicle_id(vehicle)
                if vehicle_id is None:
                    continue

                merged.setdefault(vehicle_id, {"vehicle_id": vehicle_id})
                self._merge_vehicle_segment(merged[vehicle_id], dict(vehicle))

        segment_paths = {
            "fast": API_STATE_FAST,
            "telemetry": API_STATE_TELEMETRY,
            "slow": API_STATE_SLOW,
            "config": API_STATE_CONFIG,
        }

        for segment, path in segment_paths.items():
            try:
                response = await self._get_segment(segment, path, force=force)
            except SentrymoRateLimited as err:
                _LOGGER.debug(
                    "Skipping Sentrymo segment %s because backend asked us to wait: %s",
                    segment,
                    err,
                )
                cached = self._segment_cache.get(segment)
                if cached is None:
                    continue
                response = cached
            except SentrymoApiError as err:
                _LOGGER.warning(
                    "Skipping Sentrymo segment %s because it failed: %s",
                    segment,
                    err,
                )
                continue

            maybe_server_time = response.get("server_time")
            if isinstance(maybe_server_time, str):
                server_time = maybe_server_time

            recommended = response.get("recommended_poll_seconds")
            if isinstance(recommended, int):
                polling[segment] = recommended

            segment_vehicles = response.get("vehicles")
            if not isinstance(segment_vehicles, list):
                continue

            for vehicle in segment_vehicles:
                if not isinstance(vehicle, Mapping):
                    continue

                vehicle_id = self._coerce_vehicle_id(vehicle)
                if vehicle_id is None:
                    continue

                merged.setdefault(vehicle_id, {"vehicle_id": vehicle_id})
                self._merge_vehicle_segment(merged[vehicle_id], dict(vehicle))

        return {
            "server_time": server_time,
            "polling": polling,
            "account": account,
            "capabilities": capabilities,
            "vehicles": sorted(
                merged.values(),
                key=lambda item: str(item.get("name", item.get("vehicle_id", ""))),
            ),
        }

    async def async_send_command(
        self,
        vehicle_id: int | str,
        command: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a vehicle command."""
        command_payload = {"source": DEFAULT_SOURCE}
        if payload:
            command_payload.update(payload)

        headers: dict[str, str] = {}
        if self.cpin:
            headers["X-Sentrymo-CPIN"] = self.cpin

        return await self._request(
            "post",
            f"/vehicles/{vehicle_id}/commands/{command}",
            json_payload=command_payload,
            headers=headers,
        )

    async def async_set_protection_mode(
        self,
        vehicle_id: int | str,
        mode: str,
    ) -> dict[str, Any]:
        """Set vehicle protection mode through backend-supported commands."""
        command = {
            PROTECTION_MODE_DISABLED: COMMAND_PROTECTION_DEACTIVATE,
            PROTECTION_MODE_MANUAL: COMMAND_PROTECTION_ACTIVATE,
            PROTECTION_MODE_AUTOMATIC: COMMAND_PROTECTION_AUTO,
        }.get(mode)

        if command is None:
            raise SentrymoCommandError(f"Unsupported protection mode: {mode}")

        return await self.async_send_command(vehicle_id, command, {"mode": mode})

    async def _get_segment(self, segment: str, path: str, *, force: bool = False) -> dict[str, Any]:
        """Fetch a state segment with cache windows based on backend polling."""
        now = dt_util.utcnow()
        next_refresh = self._segment_next_refresh.get(segment)

        if not force and segment in self._segment_cache and next_refresh is not None and now < next_refresh:
            return self._segment_cache[segment]

        headers = {"X-Sentrymo-Force-Refresh": "1"} if force else None
        request_path = f"{path}?force=1" if force and "?" not in path else path

        response = await self._request("get", request_path, headers=headers)
        self._segment_cache[segment] = response

        recommended = response.get("recommended_poll_seconds")
        seconds = (
            recommended
            if isinstance(recommended, int) and recommended > 0
            else DEFAULT_EXCHANGE_PAYLOAD.get(segment, 60)
        )
        self._segment_next_refresh[segment] = now + timedelta(seconds=seconds)

        return response

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        require_auth: bool = True,
        allow_refresh: bool = True,
    ) -> dict[str, Any]:
        """Execute an HTTP request."""
        url = f"{self.api_url}{path if path.startswith('/') else f'/{path}'}"

        request_headers = {"Accept": "application/json"}
        if headers:
            request_headers.update(headers)

        if require_auth and self.access_token:
            request_headers["Authorization"] = f"Bearer {self.access_token}"

        try:
            async with async_timeout.timeout(20):
                response = await self._session.request(
                    method.upper(),
                    url,
                    json=json_payload,
                    headers=request_headers,
                )
        except TimeoutError as err:
            raise SentrymoCannotConnect("Request timed out") from err
        except ClientError as err:
            raise SentrymoCannotConnect("Request failed") from err

        if response.status == 401 and allow_refresh and require_auth and self.refresh_token:
            _LOGGER.debug("Received 401 from Sentrymo API, attempting token refresh")
            try:
                await self.async_refresh_token()
            except SentrymoApiError as err:
                raise SentrymoAuthError("Authentication refresh failed") from err

            return await self._request(
                method,
                path,
                json_payload=json_payload,
                headers=headers,
                require_auth=require_auth,
                allow_refresh=False,
            )

        body = await self._decode_json(response)
        self._raise_for_status(response, body, path)

        return body

    async def _decode_json(self, response: ClientResponse) -> dict[str, Any]:
        """Decode a JSON response safely."""
        try:
            payload = await response.json(content_type=None)
        except ValueError:
            payload = {}

        return payload if isinstance(payload, dict) else {}

    def _raise_for_status(
        self,
        response: ClientResponse,
        body: Mapping[str, Any],
        path: str,
    ) -> None:
        """Convert HTTP failures to domain exceptions."""
        if response.status < 400:
            return

        code = str(body.get("code") or "")
        message = str(body.get("message") or f"Unexpected API error for {path}")
        lower_message = message.lower()

        if response.status == 404 and path in {API_AUTH_EXCHANGE, API_AUTH_REFRESH}:
            raise SentrymoCannotConnect(
                "Home Assistant API endpoint was not found. Check API URL."
            )

        if response.status == 422 and path == API_AUTH_EXCHANGE:
            raise SentrymoInvalidAuth(message)

        if response.status == 429 or "polling too frequently" in lower_message:
            raise SentrymoRateLimited(message or "Polling too frequently.")

        if response.status in (401, 403):
            if code == "package_required":
                raise SentrymoPackageUnavailable(message)

            if code in {
                "invalid_setup_key",
                "setup_key_expired",
                "integration_revoked",
                "invalid_refresh_token",
                "refresh_token_expired",
                "invalid_token",
            }:
                raise SentrymoInvalidAuth(message)

            raise SentrymoAuthError(message)

        if "/commands/" in path:
            raise SentrymoCommandError(message, code=code)

        raise SentrymoApiError(message)

    def _extract_tokens(
        self,
        payload: Mapping[str, Any],
        *,
        refresh_token: str | None = None,
    ) -> dict[str, str]:
        """Extract normalized token fields from a response payload."""
        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise SentrymoInvalidAuth("Access token missing in response")

        resolved_refresh = payload.get("refresh_token")
        if not isinstance(resolved_refresh, str) or not resolved_refresh:
            resolved_refresh = refresh_token or self.refresh_token

        if not resolved_refresh:
            raise SentrymoInvalidAuth("Refresh token missing in response")

        expires_at_value = payload.get("access_token_expires_at") or payload.get("expires_at")
        expires_at = self._normalize_expires_at(expires_at_value, payload.get("expires_in"))

        return {
            CONF_ACCESS_TOKEN: access_token,
            CONF_REFRESH_TOKEN: resolved_refresh,
            CONF_TOKEN_EXPIRES_AT: expires_at,
        }

    def _normalize_expires_at(self, expires_at: Any, expires_in: Any) -> str:
        """Normalize expiry values to an ISO UTC timestamp."""
        if isinstance(expires_at, str) and expires_at:
            parsed = dt_util.parse_datetime(expires_at)
            if parsed is not None:
                return parsed.astimezone(UTC).isoformat()

        if isinstance(expires_in, (int, float)) and expires_in > 0:
            return (dt_util.utcnow() + timedelta(seconds=int(expires_in))).isoformat()

        return (dt_util.utcnow() + timedelta(hours=12)).isoformat()

    def _merge_vehicle_segment(self, target: dict[str, Any], vehicle: dict[str, Any]) -> None:
        """Merge a segment payload into a unified vehicle structure."""
        vehicle_id = self._coerce_vehicle_id(vehicle)
        if vehicle_id is None:
            return

        target["vehicle_id"] = vehicle_id
        target["updated_at"] = vehicle.get("updated_at", target.get("updated_at"))

        name = vehicle.get("name")
        if isinstance(name, str) and name:
            target["name"] = name

        package = vehicle.get("package")
        if isinstance(package, str) and package:
            target["package"] = package

        capabilities = vehicle.get("capabilities")
        if isinstance(capabilities, Mapping):
            target.setdefault("capabilities", {})
            target["capabilities"].update(dict(capabilities))

        location = vehicle.get("location")
        if isinstance(location, Mapping):
            target.setdefault("location", {})
            target["location"].update(dict(location))

        state = vehicle.get("state")
        if isinstance(state, Mapping):
            target.setdefault("state", {})
            state_dict = dict(state)

            nested_capabilities = state_dict.pop("capabilities", None)
            if isinstance(nested_capabilities, Mapping):
                target.setdefault("capabilities", {})
                target["capabilities"].update(dict(nested_capabilities))

            nested_can = state_dict.get("can")
            if isinstance(nested_can, Mapping):
                state_dict.update(dict(nested_can))

            nested_name = state_dict.get("name")
            if isinstance(nested_name, str) and nested_name:
                target["name"] = nested_name

            nested_package = state_dict.get("package")
            if isinstance(nested_package, str) and nested_package:
                target["package"] = nested_package

            target["state"].update(state_dict)

        for nested_key in ("fast", "telemetry", "slow"):
            nested = vehicle.get(nested_key)
            if isinstance(nested, Mapping):
                target.setdefault("state", {})
                target["state"].update(dict(nested))

        gps = vehicle.get("gps")
        if isinstance(gps, Mapping):
            target.setdefault("location", {})
            target["location"].update(dict(gps))

    def _coerce_vehicle_id(self, vehicle: Mapping[str, Any]) -> str | None:
        """Get vehicle id from different backend payload variants."""
        value = vehicle.get("vehicle_id", vehicle.get("id"))

        if value is None:
            state = vehicle.get("state")
            if isinstance(state, Mapping):
                value = state.get("id")

        if value is None:
            return None

        return str(value)
