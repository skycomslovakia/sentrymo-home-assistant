"""Constants for the Sentrymo integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "sentrymo"

CONF_API_URL = "api_url"
CONF_SETUP_KEY = "setup_key"
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_CPIN = "cpin"
CONF_TOKEN_EXPIRES_AT = "access_token_expires_at"

DEFAULT_PROD_API_URL = "https://api.prod.sentrymo.eu/ha-api/v1"
DEFAULT_QA_API_URL = "https://api.qa.sentrymo.eu/ha-api/v1"

DEFAULT_POLL_INTERVAL = timedelta(seconds=60)
MIN_POLL_INTERVAL = timedelta(seconds=30)

DATA_CLIENT = "client"
DATA_COORDINATOR = "coordinator"
DATA_SERVICES_REGISTERED = "services_registered"

ATTR_ENTRY_ID = "entry_id"

SERVICE_REFRESH = "refresh"

API_AUTH_EXCHANGE = "/auth/exchange"
API_AUTH_REFRESH = "/auth/refresh"
API_PROFILE = "/profile"
API_VEHICLES = "/vehicles"
API_STATE_FAST = "/state/fast"
API_STATE_TELEMETRY = "/state/telemetry"
API_STATE_SLOW = "/state/slow"
API_STATE_CONFIG = "/state/config"

DEFAULT_EXCHANGE_PAYLOAD: dict[str, int] = {
    "fast": 60,
    "telemetry": 60,
    "slow": 300,
    "config": 3600,
}

DEFAULT_ENTRY_TITLE = "Sentrymo"
DEFAULT_CLIENT_NAME = "Home Assistant"
DEFAULT_SOURCE = "home_assistant"

PLATFORMS = [
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
]
