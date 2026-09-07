"""Explicit programme/pathway registration-history evidence."""

from __future__ import annotations

from dataclasses import dataclass

from curriculum_reasoning_engine.institutions.periods import AcademicPeriodScheme

_STATES = {"active", "interrupted"}


@dataclass(frozen=True, slots=True)
class RegistrationHistoryEvidence:
    evidence_id: str
    student_id: str
    institution_id: str
    release_id: str
    academic_period_key: str
    programme_key: str
    pathway_key: str = ""
    registration_state: str = "active"
    authority: str = ""
    verification_status: str = "unverified"
    source_reference: str = ""

    def validate(self, period_scheme: AcademicPeriodScheme) -> None:
        if not self.evidence_id or not self.student_id or not self.institution_id or not self.release_id:
            raise ValueError("Registration history requires identity and release binding.")
        if not self.programme_key or self.registration_state not in _STATES:
            raise ValueError("Registration history has unsupported programme or state.")
        if self.verification_status not in {"verified", "provisional", "unverified", "conflict"}:
            raise ValueError("Unsupported registration-history verification status.")
        period_scheme.validate(self.academic_period_key)


@dataclass(frozen=True, slots=True)
class RegistrationHistoryCoverage:
    student_id: str
    institution_id: str
    release_id: str
    academic_period_keys: tuple[str, ...]
    authority: str
    source_reference: str
    coverage_state: str = "complete"
    verification_status: str = "unverified"
    programme_key: str = ""
    pathway_key: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "academic_period_keys", tuple(self.academic_period_keys))

    def validate(self, period_scheme: AcademicPeriodScheme) -> None:
        if not self.student_id or not self.institution_id or not self.release_id:
            raise ValueError("Registration coverage requires student and release binding.")
        if self.coverage_state not in {"complete", "partial", "conflict"}:
            raise ValueError("Unsupported registration coverage state.")
        for key in self.academic_period_keys:
            period_scheme.validate(key)


@dataclass(frozen=True, slots=True)
class RegistrationDurationResult:
    outcome: str
    value: int
    status: str
    assessment_complete: bool
    basis: str
    detail: str


def evaluate_registration_duration(
    entries: tuple[RegistrationHistoryEvidence, ...],
    coverage: tuple[RegistrationHistoryCoverage, ...],
    *,
    student_id: str,
    institution_id: str,
    release_id: str,
    period_scheme: AcademicPeriodScheme,
    programme_key: str,
    pathway_key: str = "",
    count_basis: str = "active_academic_cycles",
) -> RegistrationDurationResult:
    for entry in entries:
        entry.validate(period_scheme)
        if (entry.student_id, entry.institution_id, entry.release_id) != (
            student_id,
            institution_id,
            release_id,
        ):
            raise ValueError("Registration history is bound to a different student or release.")
    applicable = tuple(
        entry
        for entry in entries
        if entry.programme_key == programme_key
        and (not pathway_key or not entry.pathway_key or entry.pathway_key == pathway_key)
    )
    relevant_keys = {entry.academic_period_key for entry in applicable}
    if count_basis == "active_academic_cycles":
        relevant_keys = {
            entry.academic_period_key for entry in applicable if entry.registration_state == "active"
        }
    elif count_basis != "elapsed_academic_cycles":
        raise ValueError(f"Unsupported registration duration basis {count_basis!r}.")

    matching_coverage = tuple(
        item
        for item in coverage
        if (item.student_id, item.institution_id, item.release_id) == (student_id, institution_id, release_id)
        and (not item.programme_key or item.programme_key == programme_key)
        and (not item.pathway_key or item.pathway_key == pathway_key)
    )
    for item in matching_coverage:
        item.validate(period_scheme)
    complete = any(item.coverage_state == "complete" for item in matching_coverage)
    status = (
        "verified"
        if complete and all(entry.verification_status == "verified" for entry in applicable)
        else "unverified"
    )
    if not complete:
        return RegistrationDurationResult(
            "unresolved",
            len(relevant_keys),
            status,
            False,
            count_basis,
            "Registration history coverage is incomplete; duration is a lower bound only.",
        )
    if any(entry.verification_status == "conflict" for entry in applicable) or any(
        item.coverage_state == "conflict" for item in matching_coverage
    ):
        return RegistrationDurationResult(
            "conflict", len(relevant_keys), "conflict", True, count_basis, "Registration history conflicts."
        )
    if count_basis == "elapsed_academic_cycles" and relevant_keys:
        cycles = {period_scheme.cycle_key(key) for key in relevant_keys}
        value = len(cycles)
    else:
        value = len({period_scheme.cycle_key(key) for key in relevant_keys})
    return RegistrationDurationResult(
        "known", value, status, True, count_basis, "Registration duration is established by explicit history."
    )
