"""Constants for the Sentrymo integration."""

DOMAIN = "sentrymo"

CONF_API_URL = "api_url"
CONF_SETUP_KEY = "setup_key"
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_CPIN = "cpin"

DEFAULT_PROD_API_URL = "https://api.prod.sentrymo.eu/ha-api/v1"
DEFAULT_QA_API_URL = "https://api.qa.sentrymo.eu/ha-api/v1"

PLATFORMS = ["device_tracker", "sensor", "binary_sensor", "button"]
