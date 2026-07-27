"""Define constants for the Eetlijst integration."""

from homeassistant.const import Platform

DOMAIN = "eetlijst"
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.CALENDAR,
    Platform.TODO,
    Platform.BUTTON,
]

# Config
CONF_GROUP_ID = "group_id"
CONF_PREVIOUS_DAYS = "previous_days"
CONF_LIMIT = "limit"
CONF_UPDATE_INTERVAL = "update_interval"

# Defaults
DEFAULT_UPDATE_INTERVAL = 60  # in minutes
DEFAULT_PREVIOUS_DAYS = 7  # 0 means "all time"
DEFAULT_LIMIT = 50  # 0 or <=0 means no limit
