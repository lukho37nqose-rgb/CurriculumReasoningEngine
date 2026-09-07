"""UCT 2026 course-code interpretation."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UCTCourseCodeScheme:
    """Preserve UCT's legacy course-code level conventions."""

    scheme_id: str = "uct-course-codes-2026"
    institution_id: str = "uct"

    def infer_academic_level(self, code: str) -> int:
        for ch in code.strip().upper():
            if ch.isdigit():
                return {1: 5, 2: 6, 3: 7, 4: 8}.get(int(ch), 0)
        return 0

    def infer_year_level(self, code: str) -> int:
        match = re.match(r"^[A-Z]+([1-9])", code.strip().upper())
        return int(match.group(1)) if match else 0

    def infer_department(self, code: str) -> str:
        match = re.match(r"^[A-Z]+", code.strip().upper())
        return match.group(0) if match else ""
