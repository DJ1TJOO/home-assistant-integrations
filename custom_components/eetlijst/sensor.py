"""Sensor platform for Eetlijst integration."""

from typing import Any

from eetlijst_py.services.events.transformers import Event
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .coordinator import EetlijstConfigEntry, EetlijstCoordinator
from .helpers import parse_attendance_info


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: EetlijstConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Eetlijst sensor platform."""
    coordinator = entry.runtime_data
    async_add_entities([EetlijstEventTodaySensor(coordinator, entry.data["group_id"])])


class EetlijstEventTodaySensor(CoordinatorEntity[EetlijstCoordinator], SensorEntity):
    """Sensor indicating today's meal event and detailed attendance."""

    _attr_has_entity_name = True
    _attr_name = "Event Today"
    _attr_icon = "mdi:silverware-fork-knife"

    def __init__(self, coordinator: EetlijstCoordinator, group_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._group_id = group_id
        self._attr_unique_id = f"{group_id}_event_today"

    @property
    def _today_event(self) -> Event | None:
        """Find today's event from coordinator data."""
        if not self.coordinator.data:
            return None

        today = dt_util.now().date()
        for event in self.coordinator.data:
            if event.start_date.date() == today:
                return event
        return None

    @property
    def native_value(self) -> str:
        """Return the event name or fallback status."""
        if event := self._today_event:
            return event.name
        return "No event today"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return attendance details as extra state attributes for automations."""
        event = self._today_event
        if not event:
            return {"has_event": False}

        attendance_data = parse_attendance_info(event)

        return {
            "has_event": True,
            "event_id": str(event.id),
            "open": event.open,
            "start_date": event.start_date.isoformat(),
            "signup_deadline": (
                event.signup_deadline.isoformat() if event.signup_deadline else None
            ),
            "closed_by": event.closed_by,
            "description": event.description,
            **attendance_data,
        }
