"""Institution-owned achievement value and comparison contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _compare_ordered(index: dict[str, int], left: Any, right: Any) -> int | None:
    if not isinstance(left, str) or not isinstance(right, str):
        return None
    if left not in index or right not in index:
        return None
    return (index[left] > index[right]) - (index[left] < index[right])


@dataclass(frozen=True, slots=True)
class NumericAchievementScheme:
    """Validate and compare numeric achievement values on one release scale."""

    minimum: float
    maximum: float
    scheme_id: str
    institution_id: str

    def validate(self, value: Any) -> bool:
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and self.minimum <= float(value) <= self.maximum
        )

    def compare(self, left: Any, right: Any) -> int | None:
        if not self.validate(left) or not self.validate(right):
            return None
        return (float(left) > float(right)) - (float(left) < float(right))

    def meets(self, value: Any, comparator: str, threshold: Any) -> bool | None:
        ordering = self.compare(value, threshold)
        if ordering is None:
            return None
        if comparator == "gte":
            return ordering >= 0
        if comparator == "gt":
            return ordering > 0
        return None


@dataclass(frozen=True, slots=True)
class SymbolicAchievementScheme:
    """Release-owned ordering for opaque, exact symbolic achievements."""

    values: tuple[str, ...]
    scheme_id: str
    institution_id: str

    def __post_init__(self) -> None:
        values = tuple(self.values)
        if not values or any(not isinstance(value, str) or not value for value in values):
            raise ValueError("A symbolic achievement scheme requires non-empty symbols.")
        if len(values) != len(set(values)):
            raise ValueError("Symbolic achievement values must be unique.")
        object.__setattr__(self, "values", values)

    @property
    def _index(self) -> dict[str, int]:
        return {value: position for position, value in enumerate(self.values)}

    def validate(self, value: Any) -> bool:
        return isinstance(value, str) and value in self._index

    def compare(self, left: Any, right: Any) -> int | None:
        if not self.validate(left) or not self.validate(right):
            return None
        return _compare_ordered(self._index, left, right)

    def meets(self, value: Any, comparator: str, threshold: Any) -> bool | None:
        ordering = self.compare(value, threshold)
        if ordering is None:
            return None
        if comparator == "gte":
            return ordering >= 0
        if comparator == "gt":
            return ordering > 0
        return None


@dataclass(frozen=True, slots=True)
class ExternalQualificationSystem:
    """Release-owned configuration for one accepted external result system."""

    qualification_system_id: str
    label: str
    achievement_scheme: NumericAchievementScheme | SymbolicAchievementScheme
    subject_ids: frozenset[str] = frozenset()
    verification_status: str = "unverified"
    source_reference: str = ""
    qualification_ids: frozenset[str] = frozenset()

    def accepts_subject(self, subject_id: str) -> bool:
        return not self.subject_ids or subject_id in self.subject_ids

    def accepts_qualification(self, qualification_id: str) -> bool:
        return not self.qualification_ids or qualification_id in self.qualification_ids
