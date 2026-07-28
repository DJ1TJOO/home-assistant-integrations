"""Helpers for parsing and converting Eetlijst models into HA attribute dicts."""

from datetime import datetime, timezone
from typing import Any, TypedDict

from eetlijst_py.services.event_attendance.types import Attendance, AttendanceStatus
from eetlijst_py.services.events.types import Event
from eetlijst_py.services.group_users.types import UserInGroup
from eetlijst_py.services.groups.types import Group
from eetlijst_py.services.users.types import User
from homeassistant.util import dt as dt_util

# ==========================================
# TypedDict Definitions
# ==========================================


class DefaultScheduleDict(TypedDict):
    """Structured weekly attendance schedule."""

    monday: str | None
    tuesday: str | None
    wednesday: str | None
    thursday: str | None
    friday: str | None
    saturday: str | None
    sunday: str | None


class GroupUserDict(TypedDict):
    """Structured group-specific user metadata and schedule."""

    active: bool | None
    order: int | None
    on_holiday: bool
    holiday_start: str | None
    holiday_end: str | None
    default_schedule: DefaultScheduleDict


class UserDict(TypedDict):
    """Structured user profile and cook points metadata."""

    id: str | None
    name: str | None
    origin: str | None
    email: str | None
    allergies: list[str]
    birthday: str | None
    profile_image: str | None
    profile_image_url: str | None
    order_of_buttom_bar: list[str] | None
    wants_to_recieve_notifications: bool
    funnel_lead: list[str] | None
    cook_points: float
    cook_points_imports: list[dict[str, Any]]


class GroupDict(TypedDict):
    """Structured group metadata."""

    id: str | None
    description: str | None
    default_close_time: str | None
    created_at: str | None
    created_at_eetlijst: str | None
    statistics_start_date: str | None
    statistics_end_date: str | None


class AttendanceDict(TypedDict):
    """Structured attendance details for an individual attendee."""

    user_id: str | None
    username: str | None
    event_id: str | None
    event_name: str | None
    status: str
    number_guests: int
    comment: str | None
    created_at: str | None
    updated_at: str | None


class AttendanceSummary(TypedDict):
    """Structured attendance summary for an event."""

    attending_count: int
    member_count: int
    guest_count: int
    has_cook: bool
    cooks: list[str]
    grocery_buyers: list[str]
    attendees: list[AttendanceDict]
    attending_names: list[str]


class EventDict(AttendanceSummary):
    """Structured event details and attendance summary."""

    has_event: bool
    event_id: str | None
    name: str | None
    description: str | None
    open: bool | None
    start_date: str | None
    signup_deadline: str | None
    closed_by: str | None
    changed_signup_time: bool | None
    created_at: str | None
    updated_at: str | None


# ==========================================
# Converter Functions
# ==========================================


def parse_default_schedule(group_user: UserInGroup | None) -> DefaultScheduleDict:
    """Parse weekly attendance schedule into a TypedDict of string status values."""
    if not group_user:
        return {
            "monday": None,
            "tuesday": None,
            "wednesday": None,
            "thursday": None,
            "friday": None,
            "saturday": None,
            "sunday": None,
        }

    return {
        "monday": group_user.monday.value if group_user.monday else None,
        "tuesday": group_user.tuesday.value if group_user.tuesday else None,
        "wednesday": group_user.wednesday.value if group_user.wednesday else None,
        "thursday": group_user.thursday.value if group_user.thursday else None,
        "friday": group_user.friday.value if group_user.friday else None,
        "saturday": group_user.saturday.value if group_user.saturday else None,
        "sunday": group_user.sunday.value if group_user.sunday else None,
    }


def is_user_on_holiday(group_user: UserInGroup | None) -> bool:
    """Determine whether a group user is currently on holiday."""
    if not group_user or not group_user.start_holliday or not group_user.end_holliday:
        return False

    current_time = datetime.now(timezone.utc)
    start_dt = (
        group_user.start_holliday
        if group_user.start_holliday.tzinfo
        else group_user.start_holliday.replace(tzinfo=timezone.utc)
    )
    end_dt = (
        group_user.end_holliday
        if group_user.end_holliday.tzinfo
        else group_user.end_holliday.replace(tzinfo=timezone.utc)
    )

    return start_dt <= current_time <= end_dt


def convert_user_in_group_to_dict(
    group_user: UserInGroup | None,
) -> GroupUserDict:
    """Convert a UserInGroup domain model into a typed dictionary."""
    if not group_user:
        return {
            "active": None,
            "order": None,
            "on_holiday": False,
            "holiday_start": None,
            "holiday_end": None,
            "default_schedule": parse_default_schedule(None),
        }

    return {
        "active": group_user.active,
        "order": group_user.order,
        "on_holiday": is_user_on_holiday(group_user),
        "holiday_start": (
            group_user.start_holliday.isoformat() if group_user.start_holliday else None
        ),
        "holiday_end": (
            group_user.end_holliday.isoformat() if group_user.end_holliday else None
        ),
        "default_schedule": parse_default_schedule(group_user),
    }


def convert_user_to_dict(user: User | None) -> UserDict:
    """Convert a User domain model into a typed dictionary."""
    if not user:
        return {
            "id": None,
            "name": None,
            "origin": None,
            "email": None,
            "allergies": [],
            "birthday": None,
            "profile_image": None,
            "profile_image_url": None,
            "order_of_buttom_bar": None,
            "wants_to_recieve_notifications": False,
            "funnel_lead": None,
            "cook_points": 0.0,
            "cook_points_imports": [],
        }

    total_cook_points = sum(cp.cook_points for cp in user.cook_points_imports)

    return {
        "id": user.id,
        "name": user.name,
        "origin": user.origin,
        "email": user.email,
        "allergies": user.allergies,
        "birthday": user.birthday.isoformat() if user.birthday else None,
        "profile_image": user.profile_image,
        "profile_image_url": user.profile_image_url,
        "order_of_buttom_bar": user.order_of_buttom_bar,
        "wants_to_recieve_notifications": user.wants_to_recieve_notifications,
        "funnel_lead": user.funnel_lead,
        "cook_points": total_cook_points,
        "cook_points_imports": [
            cp.model_dump(mode="json") for cp in user.cook_points_imports
        ],
    }


def convert_group_to_dict(group: Group | None) -> GroupDict:
    """Convert a Group metadata object into a typed dictionary."""
    if not group:
        return {
            "id": None,
            "description": None,
            "default_close_time": None,
            "created_at": None,
            "created_at_eetlijst": None,
            "statistics_start_date": None,
            "statistics_end_date": None,
        }

    return {
        "id": group.id,
        "description": group.description,
        "default_close_time": (
            group.default_close_time.isoformat()
            if isinstance(group.default_close_time, datetime)
            else str(group.default_close_time) if group.default_close_time else None
        ),
        "created_at": group.created_at.isoformat() if group.created_at else None,
        "created_at_eetlijst": (
            group.created_at_eetlijst.isoformat() if group.created_at_eetlijst else None
        ),
        "statistics_start_date": (
            group.statistics_start_date.isoformat()
            if group.statistics_start_date
            else None
        ),
        "statistics_end_date": (
            group.statistics_end_date.isoformat() if group.statistics_end_date else None
        ),
    }


def convert_attendance_to_dict(
    attendance: Attendance | None,
) -> AttendanceDict | None:
    """Convert an Attendance domain model into a typed dictionary."""
    if not attendance:
        return None

    user_id: str | None = None
    username: str | None = None
    if attendance.user and attendance.user.user:
        user_id = attendance.user.user.id
        username = attendance.user.user.name

    event_id: str | None = None
    event_name: str | None = None
    if attendance.event:
        event_id = attendance.event.id
        event_name = attendance.event.name

    return AttendanceDict(
        user_id=user_id,
        username=username,
        event_id=event_id,
        event_name=event_name,
        status=attendance.status.value,
        number_guests=attendance.number_guests,
        comment=attendance.comment,
        created_at=(
            attendance.created_at.isoformat() if attendance.created_at else None
        ),
        updated_at=(
            attendance.updated_at.isoformat() if attendance.updated_at else None
        ),
    )


def convert_event_to_dict(event: Event | None) -> EventDict:
    """Convert an Event domain model into a typed dictionary."""
    if not event:
        return {
            "has_event": False,
            "event_id": None,
            "name": None,
            "description": None,
            "open": None,
            "start_date": None,
            "signup_deadline": None,
            "closed_by": None,
            "changed_signup_time": None,
            "created_at": None,
            "updated_at": None,
            "attending_count": 0,
            "member_count": 0,
            "guest_count": 0,
            "has_cook": False,
            "cooks": [],
            "grocery_buyers": [],
            "attendees": [],
            "attending_names": [],
        }

    summary = parse_attendance_info(event)

    return {
        "has_event": True,
        "event_id": str(event.id),
        "name": event.name,
        "description": event.description,
        "open": event.open,
        "start_date": event.start_date.isoformat() if event.start_date else None,
        "signup_deadline": (
            event.signup_deadline.isoformat() if event.signup_deadline else None
        ),
        "closed_by": event.closed_by,
        "changed_signup_time": event.changed_signup_time,
        "created_at": event.created_at.isoformat() if event.created_at else None,
        "updated_at": event.updated_at.isoformat() if event.updated_at else None,
        **summary,
    }


# ==========================================
# Event Search & Parsing Helpers
# ==========================================


def get_today_event(events: list[Event] | None) -> Event | None:
    """Find today's event from a list of events."""
    if not events:
        return None

    today = dt_util.now().date()
    for event in events:
        if dt_util.as_local(event.start_date).date() == today:
            return event
    return None


def parse_attendance_info(event: Event) -> AttendanceSummary:
    """Extract structured attendance summary attributes from an Event."""
    attendees: list[AttendanceDict] = []
    cooks: list[str] = []
    grocery_buyers: list[str] = []
    attending_names: list[str] = []

    for attendee in event.attendees or []:
        att_dict = convert_attendance_to_dict(attendee)
        if not att_dict:
            continue

        username = att_dict["username"] or "Unknown"
        status = attendee.status

        if status == AttendanceStatus.COOK:
            cooks.append(username)

        if status == AttendanceStatus.GOT_GROCERIES:
            grocery_buyers.append(username)

        if status not in (
            AttendanceStatus.NOT_ATTENDING,
            AttendanceStatus.DONT_KNOW_YET,
        ):
            attending_names.append(username)

        attendees.append(att_dict)

    attending_count = len(attending_names)
    guest_count = sum(a["number_guests"] for a in attendees)

    return {
        "attending_count": attending_count + guest_count,
        "member_count": attending_count,
        "guest_count": guest_count,
        "has_cook": len(cooks) > 0,
        "cooks": cooks,
        "grocery_buyers": grocery_buyers,
        "attendees": attendees,
        "attending_names": attending_names,
    }


def extract_cooks_from_description(description: str) -> list[str]:
    """Extract cook names from a formatted event description string."""
    for line in description.splitlines():
        if line.startswith("Cook assigned:"):
            parts = line.split(":", 1)
            if len(parts) > 1 and parts[1].strip() not in ("No", "None", ""):
                return [c.strip() for c in parts[1].split(",")]
    return []


def extract_attendees_from_description(description: str) -> list[str]:
    """Extract attendee usernames from a formatted event description string."""
    names: list[str] = []
    in_attendee_section = False

    for line in description.splitlines():
        if line.strip() == "Attendees:":
            in_attendee_section = True
            continue

        if in_attendee_section:
            if line.startswith("• "):
                name_part = line[2:].split("[")[0].split("(+")[0].strip()
                if name_part:
                    names.append(name_part)
            elif not line.strip():
                break

    return names
