"""UCT 2026 course-load equivalence."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class UCTCourseLoadFramework:
    """Preserve UCT's legacy semester-course-equivalent suffix convention."""

    framework_id: str = "uct-course-load-2026"
    institution_id: str = "uct"

    _suffix_weights = {
        "F": 1.0,
        "S": 1.0,
        "FS": 1.0,
        "SF": 1.0,
        "H": 1.0,
        "W": 2.0,
        "P": 1.0,
        "U": 1.0,
        "L": 1.0,
        "Z": 1.0,
    }

    def load_equivalent(self, item: Any) -> float:
        code = item if isinstance(item, str) else getattr(item, "code", "")
        match = re.search(r"\d(\D+)$", str(code).strip().upper())
        if not match:
            return 1.0
        return self._suffix_weights.get(match.group(1), 1.0)

