"""API client for the Sentrymo integration."""

from __future__ import annotations


class SentrymoApiClient:
    """Minimal Sentrymo API client placeholder."""

    def __init__(self, api_url: str, access_token: str | None = None) -> None:
        """Initialize the API client."""
        self.api_url = api_url.rstrip("/")
        self.access_token = access_token
