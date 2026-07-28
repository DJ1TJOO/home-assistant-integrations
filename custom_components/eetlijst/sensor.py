"""Sensor platform for Eetlijst integration."""

from typing import Any

from eetlijst_py.services.events.transformers import Attendance, Event
from eetlijst_py.services.groups.transformers import AttendanceStatus, UserInGroupResult
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import EetlijstConfigEntry, EetlijstCoordinator
from .device import EetlijstBaseEntity
from .helpers import (
    EventDict,
    GroupDict,
    convert_attendance_to_dict,
    convert_event_to_dict,
    convert_group_to_dict,
    convert_user_in_group_to_dict,
    convert_user_to_dict,
    get_today_event,
    parse_attendance_info,
)


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
    def extra_state_attributes(self) -> GroupDict:
        """Return group extra attributes."""
        group = self.coordinator.data.group if self.coordinator.data else None
        return convert_group_to_dict(group)


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
        return parse_attendance_info(event)["attending_count"]

    @property
    def extra_state_attributes(self) -> EventDict:
        """Return event details and formatted attendee list."""
        return convert_event_to_dict(self._today_event)


class EetlijstMemberSensor(EetlijstBaseEntity, SensorEntity):
    """Sensor representing an individual group member's status for today's event."""

    def __init__(
        self, coordinator: EetlijstCoordinator, group_id: str, user: UserInGroupResult
    ) -> None:
        """Initialize member sensor."""
        super().__init__(coordinator, group_id)
        self._user_id = user.user.id
        self._attr_name = user.user.name
        self._attr_unique_id = f"eetlijst_{group_id}_member_{self._user_id}"

    @property
    def group_user(self) -> UserInGroupResult | None:
        """Dynamically fetch latest member data from coordinator."""
        if not self.coordinator.data or not self.coordinator.data.group:
            return None

        for group_user_item in self.coordinator.data.group.users:
            if group_user_item.user.id == self._user_id:
                return group_user_item

        return None

    @property
    def entity_picture(self) -> str | None:
        """Return user avatar for UI cards when available."""
        group_user = self.group_user
        if not group_user:
            return None

        return group_user.user.profile_image_url

    @property
    def _today_attendance(self) -> Attendance | None:
        """Cross-reference member ID with today's event attendees."""
        if not self.coordinator.data:
            return None

        event = get_today_event(self.coordinator.data.events)
        if not event or not event.attendees:
            return None

        for attendee in event.attendees:
            if attendee.user and attendee.user.user.id == self._user_id:
                return attendee

        return None

    @property
    def native_value(self) -> str | None:
        """Return attendance status string or None."""
        attendance = self._today_attendance
        return attendance.status.value if attendance else None

    @property
    def icon(self) -> str:
        """Dynamic icon based on status."""
        status = self.native_value
        match status:
            case (
                AttendanceStatus.COOK.value
                | AttendanceStatus.GOT_GROCERIES.value
                | AttendanceStatus.EAT_ONLY.value
            ):
                return "mdi:silverware-fork-knife"

            case AttendanceStatus.NOT_ATTENDING.value:
                return "mdi:close-circle-outline"

            case AttendanceStatus.DONT_KNOW_YET.value | None:
                return "mdi:help-circle-outline"

            case _:
                return "mdi:account-outline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed user profile, preferences, and event status."""
        group_user = self.group_user
        user = group_user.user if group_user else None

        user_dict = convert_user_to_dict(user)
        if not user:
            user_dict["id"] = self._user_id
            user_dict["name"] = self._attr_name

        return {
            "today_attendance": convert_attendance_to_dict(self._today_attendance),
            **user_dict,
            "group_user": convert_user_in_group_to_dict(group_user),
        }
