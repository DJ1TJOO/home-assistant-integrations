"""Helpers for parsing Eetlijst event data and attendance statuses."""

from typing import TypedDict

from eetlijst_py.generated import AttendanceStatus
from eetlijst_py.services.events.transformers import Event
from homeassistant.util import dt as dt_util


class AttendeeDetail(TypedDict):
    """Structured details for an individual attendee."""

    user_id: str | None
    username: str
    status: str
    number_guests: int
    comment: str | None


class AttendanceSummary(TypedDict):
    """Structured attendance summary for an event."""

    total_attendees: int
    member_count: int
    guest_count: int
    has_cook: bool
    cooks: list[str]
    grocery_buyers: list[str]
    attendees: list[AttendeeDetail]
    attendee_names: list[str]


def get_today_event(events: list[Event] | None) -> Event | None:
    """Find today's event from a list of events."""
    if not events:
        return None

    today = dt_util.now().date()
    for event in events:
        if event.start_date.date() == today:
            return event
    return None


def parse_attendance_info(event: Event) -> AttendanceSummary:
    """Extract structured attendance attributes from a typed Event."""
    attendees = event.attendees or []

    eating_members: list[AttendeeDetail] = []
    cooks: list[str] = []
    grocery_buyers: list[str] = []
    attendee_names: list[str] = []

    for attendee in attendees:
        # Extract user_id and username from the nested user model
        username = "Unknown"
        user_id = None
        if attendee.user and attendee.user.user:
            username = attendee.user.user.name
            user_id = str(attendee.user.user.id)

        status = attendee.status

        # Categorize cooks and grocery buyers
        if status == AttendanceStatus.cook:
            cooks.append(username)

        if status == AttendanceStatus.got_groceries:
            grocery_buyers.append(username)

        # Include everyone who is attending (cook, eat_only, got_groceries)
        if status != AttendanceStatus.not_attending:
            attendee_names.append(username)
            eating_members.append(
                {
                    "user_id": user_id,
                    "username": username,
                    "status": status.value,
                    "number_guests": attendee.number_guests,
                    "comment": attendee.comment,
                }
            )

    total_guests = sum(a["number_guests"] for a in eating_members)

    return {
        "total_attendees": len(eating_members) + total_guests,
        "member_count": len(eating_members),
        "guest_count": total_guests,
        "has_cook": len(cooks) > 0,
        "cooks": cooks,
        "grocery_buyers": grocery_buyers,
        "attendees": eating_members,
        "attendee_names": attendee_names,
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
                # Matches: "• Username (+Guests) [status] - 'comment'"
                name_part = line[2:].split("[")[0].split("(+")[0].strip()
                if name_part:
                    names.append(name_part)
            elif not line.strip():
                break

    return names
