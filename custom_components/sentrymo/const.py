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
ATTR_VEHICLE_ID = "vehicle_id"
ATTR_ENABLED = "enabled"
ATTR_MODE = "mode"

SERVICE_REFRESH = "refresh"
SERVICE_SET_PROTECTION = "set_protection"
SERVICE_SET_PROTECTION_MODE = "set_protection_mode"

# These command identifiers must match the HA API command controller.
# If backend uses different names, change only these constants.
COMMAND_PROTECTION_SET_ACTIVE = "protection_set_active"
COMMAND_PROTECTION_SET_MODE = "protection_set_mode"

PROTECTION_MODE_DISABLED = "disabled"
PROTECTION_MODE_MANUAL = "manual"
PROTECTION_MODE_AUTOMATIC = "automatic"
PROTECTION_MODE_OPTIONS = [
    PROTECTION_MODE_DISABLED,
    PROTECTION_MODE_MANUAL,
    PROTECTION_MODE_AUTOMATIC,
]

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
    Platform.SWITCH,
    Platform.SELECT,
    Platform.BUTTON,
]
