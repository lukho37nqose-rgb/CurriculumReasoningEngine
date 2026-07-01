"""Stable product metadata and decision-oriented interface configuration."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

PRODUCT_NAME = "CurriculumAdvisor"
PRODUCT_VERSION = "11.0"
ACADEMIC_YEAR = 2026

DECISION_LENSES = (
    {
        "key": "position",
        "title": "Where am I now?",
        "description": "A programme-scoped account of completed credit, represented requirements, majors and academic standing.",
    },
    {
        "key": "blockers",
        "title": "What is blocking me?",
        "description": "Outstanding requirements, failed attempts, prerequisite barriers and questions that require institutional confirmation.",
    },
    {
        "key": "next",
        "title": "What can I do next?",
        "description": "Courses visible to the selected route, clearly separated from live timetable, capacity and discretionary approval.",
    },
)

TRUST_BOUNDARIES = (
    "The selected faculty, programme and pathway define the only curriculum scope used for analysis.",
    "Handbook rules and transcript facts remain separate from live timetable and course-offering data.",
    "Concessions, substitutions, clinical evidence and Faculty or Senate discretion are never inferred from marks.",
    "A complete represented rule can still require verification when the source or authority is provisional.",
)


def bootstrap_payload(faculties: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "product": {
            "name": PRODUCT_NAME,
            "version": PRODUCT_VERSION,
            "academic_year": ACADEMIC_YEAR,
            "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        },
        "decision_lenses": list(DECISION_LENSES),
        "trust_boundaries": list(TRUST_BOUNDARIES),
        "faculties": faculties,
        "capabilities": {
            "transcript_pdf": True,
            "programme_scoping": True,
            "major_reasoning": True,
            "course_visibility": True,
            "scenario_simulation": True,
            "live_timetable": False,
            "institutional_case_management": False,
            "automatic_concessions": False,
        },
    }
