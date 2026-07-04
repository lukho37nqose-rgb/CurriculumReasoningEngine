from __future__ import annotations

import pytest

from catalogue_governance.operational import (
    OperationalDataError,
    validate_offerings_payload,
)


def _payload() -> dict:
    return {
        "schema_version": 1,
        "academic_year": 2027,
        "term": "first_semester",
        "source": "Official export",
        "verification_status": "verified",
        "last_updated": "2026-12-01T10:00:00+02:00",
        "offerings": [
            {
                "course_code": "POL1004F",
                "status": "scheduled",
                "campus": "Upper Campus",
                "section": "default",
                "meetings": [
                    {
                        "day": "monday",
                        "start": "10:00",
                        "end": "11:00",
                        "type": "lecture",
                    }
                ],
            }
        ],
    }


def test_valid_offering_is_accepted() -> None:
    assert validate_offerings_payload(_payload()) == []


def test_cancelled_course_cannot_keep_meeting_times() -> None:
    payload = _payload()
    payload["offerings"][0]["status"] = "cancelled"
    with pytest.raises(OperationalDataError):
        validate_offerings_payload(payload)


def test_duplicate_identity_is_rejected() -> None:
    payload = _payload()
    payload["offerings"].append(dict(payload["offerings"][0]))
    with pytest.raises(OperationalDataError):
        validate_offerings_payload(payload)


def test_internal_overlap_is_reported_as_warning() -> None:
    payload = _payload()
    payload["offerings"][0]["meetings"].append(
        {
            "day": "monday",
            "start": "10:30",
            "end": "11:30",
            "type": "tutorial",
        }
    )
    warnings = validate_offerings_payload(payload)
    assert len(warnings) == 1
    assert "overlapping" in warnings[0]
