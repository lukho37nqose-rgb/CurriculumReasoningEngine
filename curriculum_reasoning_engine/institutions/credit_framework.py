"""Generic academic credit and level interpretation contracts."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class AcademicCreditFramework(Protocol):
    """Interpret credit value and academic level for an institutional release."""

    framework_id: str
    institution_id: str

    def credit_value(self, item: Any) -> int:
        """Return the institutional credit value for a course fact or result."""

    def academic_level(self, item: Any) -> int:
        """Return a comparable institutional academic level for a course fact or result."""

    def is_senior_level(self, item: Any) -> bool:
        """Return whether the item is senior-level study under this framework."""

    def is_level(self, item: Any, level: int) -> bool:
        """Return whether the item belongs to the requested institutional level."""
