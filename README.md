# Sentrymo Home Assistant Integration

Custom Home Assistant integration for Sentrymo vehicle security, tracking and alerts.

## Features

- UI-based config flow for pairing through Home Assistant
- Automatic access-token refresh with reauth fallback
- Vehicle location via `device_tracker`
- Telemetry and status sensors
- Binary sensors for ignition, movement, protection, alarm, connectivity and crash state
- On-demand refresh button per vehicle

## Installation

### HACS custom repository

1. Open HACS.
2. Add this repository as a custom repository.
3. Select category `Integration`.
4. Install `Sentrymo`.
5. Restart Home Assistant.
6. Go to Settings -> Devices & services -> Add integration -> Sentrymo.

## Setup

Generate Home Assistant credentials in the Sentrymo mobile app:

1. Open Sentrymo and generate Home Assistant access.
2. Note the API URL, setup key and 4-digit CPIN.
3. In Home Assistant, add the `Sentrymo` integration.
4. Enter:
   - `Name`
   - `API URL` such as `https://api.prod.sentrymo.eu/ha-api/v1`
   - `Setup key`
   - `CPIN`

The integration exchanges the setup key for access and refresh tokens and stores only:

- API URL
- access token
- refresh token
- access token expiry
- integration name

The setup key and CPIN are not written to the config entry.

## Entities

The integration creates a device per vehicle and typically exposes:

- `device_tracker`: vehicle location
- `sensor`: speed, battery voltage, external voltage, fuel level, GSM signal, odometer, last update, ignition text, vehicle status
- `binary_sensor`: moving, ignition, protection active, alarm active, online, charging, crash detected
- `button`: refresh snapshot

## Token handling

- Requests use the stored access token.
- If the API returns `401`, the integration refreshes the token once and retries the original request.
- If refresh fails, Home Assistant starts the reauthentication flow.

## Troubleshooting

- `Invalid authentication`: the setup key is invalid, expired, or already used.
- `Refresh token expired`: start reauthentication from the integration card.
- `Package unavailable`: the account does not currently have a Rider or Legend package for an eligible vehicle.
- `No vehicles`: reload the integration after vehicle or package changes if the backend account has no eligible vehicles yet.
- `Commands disabled`: the current backend command API requires CPIN on each command request, so this integration currently exposes refresh-only actions to avoid storing CPIN in Home Assistant automations.

## Status

This integration is HACS-ready and under active development.
