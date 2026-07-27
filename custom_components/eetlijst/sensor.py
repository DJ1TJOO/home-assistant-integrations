"""Sensor platform for Eetlijst integration."""

from typing import Any

from eetlijst_py.services.events.transformers import Event
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import EetlijstConfigEntry, EetlijstCoordinator
from .device import EetlijstBaseEntity
from .helpers import get_today_event, parse_attendance_info


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: EetlijstConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Eetlijst sensor platform."""
    coordinator = entry.runtime_data
    group_id = entry.data["group_id"]

    entities: list[SensorEntity] = [
        EetlijstGroupSensor(coordinator, group_id),
        EetlijstEventTodaySensor(coordinator, group_id),
    ]

    # Dynamically instantiate member sensors for each user in the group
    if coordinator.data and coordinator.data.group and coordinator.data.group.users:
        for user in coordinator.data.group.users:
            entities.append(EetlijstMemberSensor(coordinator, group_id, user))

    async_add_entities(entities)


class EetlijstGroupSensor(EetlijstBaseEntity, SensorEntity):
    """Sensor for group metadata and noticeboard."""

    _attr_name = "Group"
    _attr_icon = "mdi:home-group"

    def __init__(self, coordinator: EetlijstCoordinator, group_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, group_id)
        self._attr_unique_id = f"eetlijst_{group_id}_info"

    @property
    def native_value(self) -> str | None:
        """Return group name."""
        if self.coordinator.data and self.coordinator.data.group:
            return self.coordinator.data.group.name
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return group extra attributes."""
        if not (self.coordinator.data and self.coordinator.data.group):
            return {}

        group = self.coordinator.data.group
        return {
            "id": group.id,
            "description": group.description,
            "default_close_time": group.default_close_time,
            "created_at": group.created_at.isoformat() if group.created_at else None,
            "created_at_eetlijst": (
                group.created_at_eetlijst.isoformat()
                if getattr(group, "created_at_eetlijst", None)
                else None
            ),
            "statistics_start_date": (
                group.statistics_start_date.isoformat()
                if group.statistics_start_date
                else None
            ),
            "statistics_end_date": (
                group.statistics_end_date.isoformat()
                if group.statistics_end_date
                else None
            ),
        }


class EetlijstEventTodaySensor(EetlijstBaseEntity, SensorEntity):
    """Sensor indicating today's headcount and meal summary."""

    _attr_name = "Today Event"
    _attr_icon = "mdi:pot-steam"

    def __init__(self, coordinator: EetlijstCoordinator, group_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, group_id)
        self._attr_unique_id = f"eetlijst_{group_id}_today_event"

    @property
    def _today_event(self) -> Event | None:
        """Find today's event from coordinator data."""
        return get_today_event(
            self.coordinator.data.events if self.coordinator.data else None
        )

    @property
    def native_value(self) -> int:
        """Return total headcount for dinner today."""
        event = self._today_event
        if not event:
            return 0
        return parse_attendance_info(event)["total_attendees"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return event details and formatted attendee list."""
        event = self._today_event
        if not event:
            return {"has_event": False, "attendees": []}

        return {
            "has_event": True,
            "event_id": str(event.id),
            "name": event.name,
            "description": event.description,
            "open": event.open,
            "start_date": event.start_date.isoformat(),
            "signup_deadline": (
                event.signup_deadline.isoformat() if event.signup_deadline else None
            ),
            "closed_by": event.closed_by,
            "changed_signup_time": (
                event.changed_signup_time.isoformat()
                if getattr(event, "changed_signup_time", None)
                else None
            ),
            "created_at": event.created_at.isoformat() if event.created_at else None,
            "updated_at": (
                event.updated_at.isoformat()
                if getattr(event, "updated_at", None)
                else None
            ),
            **parse_attendance_info(event),
        }


class EetlijstMemberSensor(EetlijstBaseEntity, SensorEntity):
    """Sensor representing an individual group member's status for today's event."""

    def __init__(
        self, coordinator: EetlijstCoordinator, group_id: str, user: Any
    ) -> None:
        """Initialize member sensor."""
        super().__init__(coordinator, group_id)
        self._user = user
        self._attr_name = user.name
        self._attr_unique_id = f"eetlijst_{group_id}_member_{user.id}"

    @property
    def _today_attendance(self) -> Any | None:
        """Cross-reference member ID with today's event attendees."""
        event = get_today_event(
            self.coordinator.data.events if self.coordinator.data else None
        )
        if not event or not event.attendees:
            return None

        for att in event.attendees:
            att_id = att.user.id if att.user else None
            att_user_id = att.user.user.id if (att.user and att.user.user) else None
            if att_id == self._user.id or att_user_id == self._user.id:
                return att
        return None

    @property
    def native_value(self) -> str:
        """Return attendance status string or UNSET."""
        att = self._today_attendance
        if att is None:
            return "UNSET"
        status = att.status.value if hasattr(att.status, "value") else str(att.status)
        return str(status).upper()

    @property
    def icon(self) -> str:
        """Dynamic icon based on status."""
        status = self.native_value
        if status in ("EATING", "COOK", "GOT_GROCERIES", "EAT_ONLY"):
            return "mdi:silverware-fork-knife"
        if status in ("NOT_EATING", "NOT_ATTENDING"):
            return "mdi:close-circle-outline"
        return "mdi:help-circle-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra user attendance attributes."""
        att = self._today_attendance
        return {
            "user_id": self._user.id,
            "name": self._user.name,
            "number_guests": att.number_guests if att else 0,
            "comment": att.comment if att else None,
            "order": getattr(self._user, "order", None),
        }
