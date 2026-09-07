"""Generic result-status interpretation contracts."""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Any, Protocol, runtime_checkable


class ResultState(StrEnum):
    """Institutional interpretation of raw course-result evidence."""

    PASSED = "passed"
    FAILED = "failed"
    PENDING = "pending"


@runtime_checkable
class GradingScheme(Protocol):
    """Classify raw CourseResult evidence for one institutional release."""

    scheme_id: str
    institution_id: str

    def classify(self, result: Any) -> ResultState:
        """Return the institution-specific interpretation of a course result."""

    def is_passed(self, result: Any) -> bool:
        """Return whether the result is interpreted as passed."""

    def is_failed(self, result: Any) -> bool:
        """Return whether the result is interpreted as failed."""

    def is_pending(self, result: Any) -> bool:
        """Return whether the result is interpreted as pending or unresolved."""


@lru_cache(maxsize=1)
def legacy_default_grading_scheme() -> GradingScheme:
    """Return the immutable compatibility grading scheme for legacy callers."""
    from .uct_grading import UCTGradingScheme

    return UCTGradingScheme()
