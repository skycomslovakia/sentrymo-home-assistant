"""URL normalization for the dedicated Sentrymo Home Assistant API."""

from __future__ import annotations

from urllib.parse import urlsplit

LEGACY_API_HOSTS: dict[str, str] = {
    "api.sentrymo.eu": "ha-api.sentrymo.eu",
    "api.prod.sentrymo.eu": "ha-api.sentrymo.eu",
    "api.qa.sentrymo.eu": "ha-api.qa.sentrymo.eu",
    "ha.sentrymo.eu": "ha-api.sentrymo.eu",
    "ha.qa.sentrymo.eu": "ha-api.qa.sentrymo.eu",
}


def normalize_api_url(api_url: str | None, default_url: str) -> str:
    """Return a dedicated HA API URL ending in /api/v1."""
    base_url = (api_url or default_url).strip().rstrip("/")
    parsed = urlsplit(base_url)
    legacy_host = (parsed.hostname or "").lower()
    if replacement_host := LEGACY_API_HOSTS.get(legacy_host):
        replacement_netloc = replacement_host
        if parsed.port is not None:
            replacement_netloc = f"{replacement_host}:{parsed.port}"
        base_url = parsed._replace(netloc=replacement_netloc).geturl()

    lowered = base_url.lower()
    if lowered.endswith("/api/v1"):
        return base_url
    if lowered.endswith("/api"):
        return f"{base_url}/v1"
    if lowered.endswith(("/ha-api/v1", "/ha-api")):
        return base_url[: lowered.rfind("/ha-api")] + "/api/v1"
    return f"{base_url}/api/v1"
