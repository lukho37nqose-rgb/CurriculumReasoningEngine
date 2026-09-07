"""Generic course-load equivalence contracts."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class CourseLoadFramework(Protocol):
    """Institution-owned course-load/equivalent interpretation."""

    framework_id: str
    institution_id: str

    def load_equivalent(self, item: Any) -> float:
        """Return the course-load equivalent for a represented course."""

