"""Constants for Fan Smart Sync."""

from datetime import timedelta

DOMAIN = "fan_smart_sync"
MANUFACTURER = "Chungear"
MODEL = "Fan Smart Sync ceiling fan"
DEFAULT_NAME = "Ceiling fan"

# How often to read the fan, which picks up changes made with the wall remote or the phone app.
POLL_INTERVAL = timedelta(seconds=30)
