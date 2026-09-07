"""Generic course-code interpretation contracts."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class CourseCodeScheme(Protocol):
    """Institution-owned interpretation of academic meaning encoded in codes."""

    scheme_id: str
    institution_id: str

    def infer_academic_level(self, code: str) -> int:
        """Return an academic level inferred from a course code, or 0 if unknown."""

    def infer_year_level(self, code: str) -> int:
        """Return an institution-specific course year/stage, or 0 if unknown."""

    def infer_department(self, code: str) -> str:
        """Return a department-like code prefix, or an empty string if unknown."""
