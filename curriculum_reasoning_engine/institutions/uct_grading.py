"""UCT 2026 grading and result-status interpretation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .grading import ResultState


@dataclass(frozen=True, slots=True)
class UCTGradingScheme:
    """Preserve current UCT 2026 pass/fail/pending semantics."""

    scheme_id: str = "uct-2026"
    institution_id: str = "uct"

    pass_mark: int = 50
    pass_grades: frozenset[str] = frozenset(
        {"1", "2+", "2-", "3", "P", "PA", "UP", "SP"}
    )
    fail_grades: frozenset[str] = frozenset(
        {
            "F",
            "FS",
            "SF",
            "A/SF",
            "AB",
            "DPR",
            "INC",
            "EXA",
            "UF",
            "UF SM",
            "OSS",
        }
    )
    pending_grades: frozenset[str] = frozenset({"DE", "ATT", "GIP", "LOA", "OS", ""})

    def classify(self, result: Any) -> ResultState:
        mark = getattr(result, "mark", None)
        if mark is not None:
            return ResultState.PASSED if mark >= self.pass_mark else ResultState.FAILED

        grade = self.normalise_grade(getattr(result, "grade", None))
        if grade in self.pass_grades:
            return ResultState.PASSED
        if grade in self.fail_grades:
            return ResultState.FAILED
        return ResultState.PENDING

    def is_passed(self, result: Any) -> bool:
        return self.classify(result) == ResultState.PASSED

    def is_failed(self, result: Any) -> bool:
        return self.classify(result) == ResultState.FAILED

    def is_pending(self, result: Any) -> bool:
        return self.classify(result) == ResultState.PENDING

    @staticmethod
    def normalise_grade(value: object) -> str:
        return " ".join(str(value or "").strip().upper().split())
