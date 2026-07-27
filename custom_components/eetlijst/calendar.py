"""Calendar platform for Eetlijst integration."""

from datetime import datetime, timedelta

from eetlijst_py.services.events.transformers import Event
from homeassistant.components.calendar import CalendarEntity, CalendarEvent
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
    """Set up Eetlijst calendar platform."""
    coordinator = entry.runtime_data
    async_add_entities([EetlijstCalendarEntity(coordinator, entry.data["group_id"])])


class EetlijstCalendarEntity(CoordinatorEntity[EetlijstCoordinator], CalendarEntity):
    """Representation of an Eetlijst Calendar."""

    _attr_has_entity_name = True
    _attr_name = "Calendar"
    _attr_icon = "mdi:calendar-cutlery"

    def __init__(self, coordinator: EetlijstCoordinator, group_id: str) -> None:
        """Initialize calendar entity."""
        super().__init__(coordinator)
        self._group_id = group_id
        self._attr_unique_id = f"eetlijst_{group_id}_calendar"

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        if not self.coordinator.data or not self.coordinator.data.events:
            return None

        now = dt_util.now()
        for event in self.coordinator.data.events:
            event_end = event.start_date + timedelta(hours=1)
            if event_end >= now:
                return self._to_calendar_event(event)

        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        events: list[Event] = (
            self.coordinator.data.events if self.coordinator.data else []
        )

        return [
            self._to_calendar_event(evt)
            for evt in events
            if start_date <= evt.start_date <= end_date
        ]

    def _to_calendar_event(self, event: Event) -> CalendarEvent:
        """Convert an Eetlijst Event model into an HA CalendarEvent."""
        att_info = parse_attendance_info(event)

        cook_str = ", ".join(att_info["cooks"]) if att_info["has_cook"] else "No"
        summary_lines = [
            f"Total Attendees: {att_info['total_attendees']}",
            f"Cook assigned: {cook_str}",
            "\nAttendees:",
        ]

        for att in att_info["attendees"]:
            guests = f" (+{att['number_guests']})" if att["number_guests"] > 0 else ""
            comment = f" - '{att['comment']}'" if att["comment"] else ""
            summary_lines.append(
                f"• {att['username']}{guests} [{att['status']}]{comment}"
            )

        base_desc = event.description or ""
        description = f"{base_desc}\n\n" if base_desc else ""
        description += "\n".join(summary_lines)

        return CalendarEvent(
            summary=event.name,
            start=event.start_date,
            end=event.start_date + timedelta(hours=1),
            description=description.strip(),
            uid=str(event.id),
        )
