"""Validation for term-specific course offerings and timetable data.

Operational data is intentionally separate from curriculum rules. Validation
here cannot grant curriculum credit, waive prerequisites, or alter a programme.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import time
from typing import Any

ALLOWED_TERMS = {"first_semester", "second_semester", "full_year", "summer", "winter"}
ALLOWED_STATUSES = {"scheduled", "provisional", "cancelled", "not_offered", "unknown"}
ALLOWED_VERIFICATION = {"verified", "provisional", "unverified", "conflict"}
ALLOWED_DAYS = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}


class OperationalDataError(ValueError):
    """Raised when timetable/offering data is structurally unsafe."""


def _require_string(record: dict[str, Any], key: str, context: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise OperationalDataError(f"{context}.{key} must be a non-empty string")
    return value.strip()


def _parse_clock(value: str, context: str) -> time:
    try:
        hour_text, minute_text = value.split(":", 1)
        return time(hour=int(hour_text), minute=int(minute_text))
    except (ValueError, TypeError) as exc:
        raise OperationalDataError(f"{context} must use HH:MM 24-hour time") from exc


def validate_offerings_payload(payload: dict[str, Any]) -> list[str]:
    """Validate and return non-blocking warnings.

    Raises OperationalDataError for invalid or ambiguous records. Duplicate
    offering identities are rejected because silent replacement could mislead a
    student about actual delivery.
    """
    if not isinstance(payload, dict):
        raise OperationalDataError("Operational payload must be an object")
    if payload.get("schema_version") != 1:
        raise OperationalDataError("schema_version must be 1")
    academic_year = payload.get("academic_year")
    if not isinstance(academic_year, int) or not 2000 <= academic_year <= 2200:
        raise OperationalDataError("academic_year must be an integer between 2000 and 2200")
    term = payload.get("term")
    if term not in ALLOWED_TERMS:
        raise OperationalDataError(f"term must be one of: {', '.join(sorted(ALLOWED_TERMS))}")
    _require_string(payload, "source", "payload")
    verification = payload.get("verification_status")
    if verification not in ALLOWED_VERIFICATION:
        raise OperationalDataError(
            f"verification_status must be one of: {', '.join(sorted(ALLOWED_VERIFICATION))}"
        )
    offerings = payload.get("offerings")
    if not isinstance(offerings, list):
        raise OperationalDataError("offerings must be a list")

    identities: set[tuple[str, str, str]] = set()
    warnings: list[str] = []
    slots_by_offering: dict[tuple[str, str, str], list[tuple[str, time, time, str]]] = defaultdict(list)

    for index, offering in enumerate(offerings):
        context = f"offerings[{index}]"
        if not isinstance(offering, dict):
            raise OperationalDataError(f"{context} must be an object")
        course_code = _require_string(offering, "course_code", context).upper()
        campus = _require_string(offering, "campus", context)
        section = str(offering.get("section", "default")).strip() or "default"
        status = offering.get("status")
        if status not in ALLOWED_STATUSES:
            raise OperationalDataError(
                f"{context}.status must be one of: {', '.join(sorted(ALLOWED_STATUSES))}"
            )
        identity = (course_code, campus.casefold(), section.casefold())
        if identity in identities:
            raise OperationalDataError(
                f"Duplicate offering identity for {course_code}, campus {campus}, section {section}"
            )
        identities.add(identity)

        meetings = offering.get("meetings", [])
        if not isinstance(meetings, list):
            raise OperationalDataError(f"{context}.meetings must be a list")
        if status == "scheduled" and not meetings:
            warnings.append(f"{course_code} is scheduled but has no meeting times")
        if status in {"cancelled", "not_offered"} and meetings:
            raise OperationalDataError(
                f"{course_code} is {status} but still contains meeting times"
            )

        for meeting_index, meeting in enumerate(meetings):
            meeting_context = f"{context}.meetings[{meeting_index}]"
            if not isinstance(meeting, dict):
                raise OperationalDataError(f"{meeting_context} must be an object")
            day = _require_string(meeting, "day", meeting_context).casefold()
            if day not in ALLOWED_DAYS:
                raise OperationalDataError(
                    f"{meeting_context}.day must be one of: {', '.join(sorted(ALLOWED_DAYS))}"
                )
            start = _parse_clock(_require_string(meeting, "start", meeting_context), f"{meeting_context}.start")
            end = _parse_clock(_require_string(meeting, "end", meeting_context), f"{meeting_context}.end")
            if end <= start:
                raise OperationalDataError(f"{meeting_context}.end must be after start")
            meeting_type = _require_string(meeting, "type", meeting_context)
            slots_by_offering[identity].append((day, start, end, meeting_type))

        slots = slots_by_offering[identity]
        for left_index, left in enumerate(slots):
            for right in slots[left_index + 1 :]:
                if left[0] == right[0] and left[1] < right[2] and right[1] < left[2]:
                    warnings.append(
                        f"{course_code} has overlapping {left[3]} and {right[3]} meetings on {left[0]}"
                    )

    return warnings
