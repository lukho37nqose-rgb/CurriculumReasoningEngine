"""Institution-owned academic-period ordering contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class AcademicPeriodScheme(Protocol):
    """Opaque period semantics supplied by an institution release."""

    scheme_id: str

    def validate(self, period_key: str) -> None: ...

    def order(self, period_key: str) -> int: ...

    def cycle_key(self, period_key: str) -> str: ...

    def period_key_for_year(self, academic_year: int) -> str: ...


@dataclass(frozen=True, slots=True)
class ExplicitAcademicPeriodScheme:
    """A release-owned table; no ordering is inferred from key spelling."""

    periods: tuple[tuple[str, str, int], ...]
    scheme_id: str = "explicit"

    def __post_init__(self) -> None:
        keys = [key for key, _, _ in self.periods]
        if len(keys) != len(set(keys)):
            raise ValueError("Academic period keys must be unique.")
        if len({order for _, _, order in self.periods}) != len(self.periods):
            raise ValueError("Academic period order values must be unique.")

    def validate(self, period_key: str) -> None:
        if period_key not in {key for key, _, _ in self.periods}:
            raise ValueError(f"Unknown academic period {period_key!r} for {self.scheme_id}.")

    def order(self, period_key: str) -> int:
        self.validate(period_key)
        return next(order for key, _, order in self.periods if key == period_key)

    def cycle_key(self, period_key: str) -> str:
        self.validate(period_key)
        return next(cycle for key, cycle, _ in self.periods if key == period_key)

    def period_key_for_year(self, academic_year: int) -> str:
        candidates = [
            (order, key)
            for key, cycle, order in self.periods
            if str(academic_year) in {key, cycle}
        ]
        if not candidates:
            raise ValueError(f"No academic period compatibility mapping for year {academic_year}.")
        return min(candidates)[1]

    def latest_period(self, period_keys: list[str]) -> str | None:
        known = [key for key in period_keys if key]
        for key in known:
            self.validate(key)
        return max(known, key=self.order) if known else None

    def latest_cycle(self, period_keys: list[str]) -> str | None:
        latest = self.latest_period(period_keys)
        return self.cycle_key(latest) if latest else None


@dataclass(frozen=True, slots=True)
class LegacyAcademicYearPeriodScheme:
    """Compatibility scheme for year-only UCT records."""

    scheme_id: str = "legacy-academic-year"

    def validate(self, period_key: str) -> None:
        try:
            int(period_key)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Unknown legacy academic period {period_key!r}.") from exc

    def order(self, period_key: str) -> int:
        self.validate(period_key)
        return int(period_key)

    def cycle_key(self, period_key: str) -> str:
        self.validate(period_key)
        return period_key

    def period_key_for_year(self, academic_year: int) -> str:
        return str(academic_year)

