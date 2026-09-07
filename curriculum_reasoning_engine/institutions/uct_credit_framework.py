"""UCT 2026 NQF academic credit and level framework."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class UCTCreditFramework:
    """Preserve current UCT/NQF credit, level, and senior-level semantics."""

    framework_id: str = "uct-nqf-2026"
    institution_id: str = "uct"
    senior_level_floor: int = 6

    def credit_value(self, item: Any) -> int:
        return int(getattr(item, "nqf_credits", 0) or 0)

    def academic_level(self, item: Any) -> int:
        return int(getattr(item, "nqf_level", 0) or 0)

    def is_senior_level(self, item: Any) -> bool:
        return self.academic_level(item) >= self.senior_level_floor

    def is_level(self, item: Any, level: int) -> bool:
        return self.academic_level(item) == int(level)
