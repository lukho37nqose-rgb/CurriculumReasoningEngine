"""Institution-neutral structured course-completion prerequisites."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from curriculum_reasoning_engine.institutions.achievement import (
    ExternalQualificationSystem,
    NumericAchievementScheme,
)
from curriculum_reasoning_engine.institutions.coding import CourseCodeScheme
from curriculum_reasoning_engine.institutions.course_load import CourseLoadFramework
from curriculum_reasoning_engine.institutions.credit_framework import (
    AcademicCreditFramework,
)
from curriculum_reasoning_engine.institutions.grading import GradingScheme

from .completion import CourseCompletionRecognitionInput, CourseCompletionResolver
from .models import (
    AcademicRecordCoverageEvidence,
    Catalogue,
    CourseAttemptCoverageEvidence,
    CourseFact,
    ExternalSubjectAchievementCoverage,
    ExternalSubjectAchievementEvidence,
    PriorQualificationCoverage,
    PriorQualificationEvidence,
    StudentRecord,
)

_STATUS_RANK = {
    "conflict": 0,
    "unsupported": 0,
    "unverified": 1,
    "provisional": 1,
    "discretionary": 1,
    "verified": 2,
}


def _weaker_status(*statuses: str) -> str:
    values = [str(value or "unverified").strip().lower() for value in statuses]
    if "conflict" in values:
        return "conflict"
    return min(values or ["unverified"], key=lambda value: _STATUS_RANK.get(value, 1))


def _strongest_witness_status(results: list[PrerequisiteConditionResult]) -> str:
    return max(
        (result.status for result in results),
        key=lambda value: _STATUS_RANK.get(value, 1),
        default="unverified",
    )


@dataclass(frozen=True)
class ProjectedCourseCompletions:
    """Planning-only assumptions; never academic-result evidence."""

    course_codes: tuple[str, ...] = ()
    status: str = "provisional"


@dataclass(frozen=True)
class PrerequisiteConditionResult:
    outcome: str
    assessment_complete: bool
    status: str
    detail: str
    witness_course_codes: tuple[str, ...] = ()
    child_results: tuple[PrerequisiteConditionResult, ...] = field(default_factory=tuple)


class AcademicConditionEvaluator:
    """Shared current-evidence academic leaves and shallow composition.

    Course prerequisite presentation, legacy matching and projections live in
    the compatibility subclass, not in programme-entry evaluation.
    """

    def __init__(
        self,
        student: StudentRecord,
        catalogue: Catalogue,
        grading_scheme: GradingScheme | None = None,
        credit_framework: AcademicCreditFramework | None = None,
        course_code_scheme: CourseCodeScheme | None = None,
        course_load_framework: CourseLoadFramework | None = None,
        academic_record_coverage_evidence: list[AcademicRecordCoverageEvidence] | None = None,
        projected_course_completions: ProjectedCourseCompletions | None = None,
        completion_recognition: CourseCompletionRecognitionInput | None = None,
        achievement_scheme: NumericAchievementScheme | None = None,
        course_attempt_coverage_evidence: list[CourseAttemptCoverageEvidence] | None = None,
        external_qualification_systems: tuple[ExternalQualificationSystem, ...] = (),
        external_subject_achievement_evidence: list[ExternalSubjectAchievementEvidence] | None = None,
        external_subject_achievement_coverage: list[ExternalSubjectAchievementCoverage] | None = None,
        prior_qualification_evidence: list[PriorQualificationEvidence] | None = None,
        prior_qualification_coverage: list[PriorQualificationCoverage] | None = None,
    ) -> None:
        self.student = student
        self.catalogue = catalogue
        self.grading_scheme = grading_scheme
        self.coverage_evidence = academic_record_coverage_evidence
        self.projections = projected_course_completions or ProjectedCourseCompletions()
        self.achievement_scheme = achievement_scheme
        self.attempt_coverage = course_attempt_coverage_evidence
        self.external_systems = {item.qualification_system_id: item for item in external_qualification_systems}
        self.external_evidence = external_subject_achievement_evidence or []
        self.external_coverage = external_subject_achievement_coverage or []
        self.prior_qualifications = prior_qualification_evidence or []
        self.prior_qualification_coverage = prior_qualification_coverage or []
        self.projected_codes = {
            str(code).strip().upper() for code in self.projections.course_codes if str(code).strip()
        }
        self.completion = CourseCompletionResolver(
            student,
            catalogue,
            grading_scheme,
            completion_recognition,
        )

    def evaluate(self, expression: dict[str, Any]) -> PrerequisiteConditionResult:
        if not isinstance(expression, dict):
            return self._unsupported("Prerequisite expression must be an object.")
        authority = str(expression.get("verification_status", "unverified"))
        result = self._evaluate_node(expression, operator_depth=0)
        return PrerequisiteConditionResult(
            result.outcome,
            result.assessment_complete,
            _weaker_status(authority, result.status),
            result.detail,
            result.witness_course_codes,
            result.child_results,
        )

    def _evaluate_node(self, expression: dict[str, Any], operator_depth: int) -> PrerequisiteConditionResult:
        node_type = str(expression.get("type", "")).strip().lower()
        if node_type == "course_completed":
            return self._course_leaf(expression)
        if node_type == "course_achievement":
            return self._achievement_leaf(expression)
        if node_type == "external_subject_achievement":
            return self._external_achievement_leaf(expression)
        if node_type == "qualification_held":
            return self._qualification_held_leaf(expression)
        if node_type not in {"all_of", "one_of"}:
            return self._unsupported(f"Unsupported prerequisite type {node_type!r}.")
        if operator_depth >= 2:
            return self._unsupported("Prerequisite expression exceeds maximum depth.")
        conditions = expression.get("conditions")
        if not isinstance(conditions, list) or not conditions:
            return self._unsupported(f"{node_type} prerequisite requires a non-empty conditions list.")
        children = tuple(
            self._evaluate_node(child, operator_depth + 1)
            if isinstance(child, dict)
            else self._unsupported("Prerequisite child must be an object.")
            for child in conditions
        )
        if operator_depth == 1 and any(child.child_results for child in children):
            return self._unsupported("Prerequisite expression exceeds maximum depth.")
        return self._all_of(children) if node_type == "all_of" else self._one_of(children)

    def _course_leaf(self, expression: dict[str, Any]) -> PrerequisiteConditionResult:
        code = str(expression.get("course_code", "")).strip().upper()
        if not code:
            return self._unsupported("course_completed requires course_code.")
        actual = self.completion.resolve(code, self.coverage_evidence)
        return PrerequisiteConditionResult(
            actual.outcome, actual.assessment_complete, actual.status, actual.detail,
            (code,) if actual.outcome == "satisfied" else (),
        )

    def _achievement_leaf(self, expression: dict[str, Any]) -> PrerequisiteConditionResult:
        code = str(expression.get("course_code", "")).strip().upper()
        comparator = str(expression.get("comparator", "")).strip().lower()
        selection = str(expression.get("attempt_selection", "")).strip().lower()
        threshold = expression.get("threshold")
        if not code or comparator not in {"gte", "gt"} or selection != "any_qualifying_attempt":
            return self._unsupported("course_achievement requires an exact code, supported comparator, and explicit attempt_selection.")
        if self.achievement_scheme is None:
            return self._unsupported("No achievement scheme is available for this release.")
        if not self.achievement_scheme.validate(threshold):
            return self._unsupported("Achievement threshold is outside the governed scale.")
        relevant = [result for result in self.student.results if result.code.upper() == code]
        qualifying = []
        unknown_attempt = False
        for result in relevant:
            explicit_value = getattr(result, "achievement_value", None)
            if explicit_value is None and self.grading_scheme is not None and self.grading_scheme.is_pending(result):
                unknown_attempt = True
                continue
            value = explicit_value
            if value is None:
                value = getattr(result, "mark", None)
            if value is None or not self.achievement_scheme.validate(value):
                unknown_attempt = True
                continue
            meets = self.achievement_scheme.meets(value, comparator, threshold)
            if meets:
                qualifying.append(result)
        if qualifying:
            return PrerequisiteConditionResult(
                "satisfied", True, "verified",
                f"{code} has a qualifying achievement witness.", (code,),
            )
        covered = [evidence for evidence in (self.attempt_coverage or ())
                   if code in {item.upper() for item in evidence.course_codes}
                   and evidence.coverage_state == "complete"]
        if not covered:
            return PrerequisiteConditionResult(
                "unresolved", False, "unverified",
                f"No complete attempt coverage establishes that {code} lacks a qualifying achievement.",
            )
        if unknown_attempt:
            return PrerequisiteConditionResult(
                "unresolved", False, "unverified", f"{code} has pending or non-comparable achievement evidence."
            )
        status = _weaker_status(*(item.verification_status for item in covered))
        return PrerequisiteConditionResult(
            "conflict" if status == "conflict" else "not_satisfied", status != "conflict", status,
            f"No {code} achievement meets the governed threshold.",
        )

    def _external_achievement_leaf(self, expression: dict[str, Any]) -> PrerequisiteConditionResult:
        system_id = str(expression.get("qualification_system_id", "")).strip()
        subject_id = str(expression.get("subject_id", "")).strip()
        comparator = str(expression.get("comparator", "")).strip().lower()
        threshold = expression.get("threshold")
        system = self.external_systems.get(system_id)
        if not system or not subject_id or not system.accepts_subject(subject_id) or comparator not in {"gte", "gt"}:
            return self._unsupported("external_subject_achievement has an unknown system/subject or unsupported comparator.")
        if not system.achievement_scheme.validate(threshold):
            return self._unsupported("External achievement threshold is outside the governed scale.")
        matches = [
            item for item in self.external_evidence
            if item.student_id == self.student.student_id
            and item.qualification_system_id == system_id
            and item.subject_id == subject_id
        ]
        if (system.verification_status == "conflict"
                or any(item.verification_status == "conflict" for item in matches)
                or len({str(item.achievement_value) for item in matches}) > 1):
            return PrerequisiteConditionResult("conflict", False, "conflict", f"Conflicting external results exist for {system_id}/{subject_id}.")
        if any(not system.achievement_scheme.validate(item.achievement_value) for item in matches):
            return PrerequisiteConditionResult("unresolved", False, "unverified", "External achievement evidence is not comparable on the governed scale.")
        for item in matches:
            meets = system.achievement_scheme.meets(item.achievement_value, comparator, threshold)
            if meets:
                return PrerequisiteConditionResult("satisfied", True, _weaker_status(system.verification_status, item.verification_status), f"External {system_id}/{subject_id} achievement satisfies the threshold.", (subject_id,))
        covered = [item for item in self.external_coverage
            if item.student_id == self.student.student_id
            and item.qualification_system_id == system_id
            and subject_id in item.subject_ids
            and item.coverage_state == "complete"
        ]
        if not covered:
            return PrerequisiteConditionResult("unresolved", False, _weaker_status(system.verification_status), f"External {system_id}/{subject_id} achievement is not established with complete result coverage.")
        status = _weaker_status(system.verification_status, *(item.verification_status for item in matches + covered))
        return PrerequisiteConditionResult("conflict" if status == "conflict" else "not_satisfied", status != "conflict", status, f"No external {system_id}/{subject_id} achievement meets the threshold.")

    def _qualification_held_leaf(self, expression: dict[str, Any]) -> PrerequisiteConditionResult:
        system_id = str(expression.get("qualification_system_id", "")).strip()
        qualification_id = str(expression.get("qualification_id", "")).strip()
        system = self.external_systems.get(system_id)
        if not system or not qualification_id or not system.accepts_qualification(qualification_id):
            return self._unsupported("qualification_held has an unknown qualification system or qualification.")
        matches = [
            item for item in self.prior_qualifications
            if item.student_id == self.student.student_id
            and item.qualification_system_id == system_id
            and item.qualification_id == qualification_id
        ]
        if system.verification_status == "conflict" or any(item.verification_status == "conflict" for item in matches):
            return PrerequisiteConditionResult("conflict", False, "conflict", f"Conflicting attainment evidence exists for {system_id}/{qualification_id}.")
        if matches:
            witness_status = max((item.verification_status for item in matches), key=lambda value: _STATUS_RANK.get(value, 1))
            return PrerequisiteConditionResult("satisfied", True, _weaker_status(system.verification_status, witness_status), f"Prior qualification {system_id}/{qualification_id} is evidenced as attained.")
        covered = [item for item in self.prior_qualification_coverage
            if item.student_id == self.student.student_id
            and item.qualification_system_id == system_id
            and qualification_id in item.qualification_ids
            and item.coverage_state == "complete"
        ]
        if covered:
            status = _weaker_status(system.verification_status, *(item.verification_status for item in covered))
            return PrerequisiteConditionResult("conflict" if status == "conflict" else "not_satisfied", status != "conflict", status, f"No attainment evidence exists for {system_id}/{qualification_id} in the complete covered set.")
        return PrerequisiteConditionResult("unresolved", False, _weaker_status(system.verification_status), f"Attainment of {system_id}/{qualification_id} is not established.")

    def _all_of(self, children: tuple[PrerequisiteConditionResult, ...]) -> PrerequisiteConditionResult:
        complete = all(child.assessment_complete for child in children)
        if any(child.outcome == "unsupported" for child in children):
            outcome, relied = "unsupported", [c for c in children if c.outcome == "unsupported"]
        elif any(child.outcome == "conflict" for child in children):
            outcome, relied = "conflict", [c for c in children if c.outcome == "conflict"]
        elif any(child.outcome == "not_satisfied" for child in children):
            outcome, relied = "not_satisfied", [c for c in children if c.outcome == "not_satisfied"]
        elif any(child.outcome == "unresolved" for child in children):
            outcome, relied = "unresolved", [c for c in children if c.outcome == "unresolved"]
        else:
            outcome, relied = "satisfied", list(children)
        witnesses = tuple(dict.fromkeys(code for child in children for code in child.witness_course_codes))
        return PrerequisiteConditionResult(
            outcome,
            complete,
            _weaker_status(*(child.status for child in relied)),
            "All prerequisite conditions assessed: " + "; ".join(child.detail for child in children),
            witnesses if outcome == "satisfied" else (),
            children,
        )

    def _one_of(self, children: tuple[PrerequisiteConditionResult, ...]) -> PrerequisiteConditionResult:
        complete = all(child.assessment_complete for child in children)
        satisfied = [child for child in children if child.outcome == "satisfied"]
        if satisfied:
            witnesses = tuple(
                dict.fromkeys(code for child in satisfied for code in child.witness_course_codes)
            )
            return PrerequisiteConditionResult(
                "satisfied",
                complete,
                _strongest_witness_status(satisfied),
                "Prerequisite satisfied by: " + ", ".join(witnesses) + ".",
                witnesses,
                children,
            )
        if any(child.outcome == "unsupported" for child in children):
            outcome, relied = "unsupported", [c for c in children if c.outcome == "unsupported"]
        elif any(child.outcome == "unresolved" for child in children):
            outcome, relied = "unresolved", [c for c in children if c.outcome == "unresolved"]
        elif any(child.outcome == "conflict" for child in children):
            outcome, relied = "conflict", [c for c in children if c.outcome == "conflict"]
        else:
            outcome, relied = "not_satisfied", list(children)
        return PrerequisiteConditionResult(
            outcome,
            complete,
            _weaker_status(*(child.status for child in relied)),
            "No prerequisite alternative is established: " + "; ".join(child.detail for child in children),
            (),
            children,
        )

    @staticmethod
    def _unsupported(detail: str) -> PrerequisiteConditionResult:
        return PrerequisiteConditionResult("unsupported", False, "unverified", detail)


# Preserve the existing result/API vocabulary while exposing its neutral role.
AcademicConditionResult = PrerequisiteConditionResult


class PrerequisiteEvaluator(AcademicConditionEvaluator):
    """Course-specific compatibility and planning over shared academic truth."""

    def evaluate_for_course(self, course: CourseFact) -> PrerequisiteConditionResult:
        if course.prerequisite_expression is not None:
            return self.evaluate(course.prerequisite_expression)
        return self._evaluate_legacy(course)

    def _course_leaf(self, expression: dict[str, Any]) -> PrerequisiteConditionResult:
        actual = super()._course_leaf(expression)
        code = str(expression.get("course_code", "")).strip().upper()
        if actual.outcome not in {"satisfied", "conflict", "unsupported"} and code in self.projected_codes:
            return PrerequisiteConditionResult(
                "satisfied", True, self.projections.status,
                f"{code} is assumed completed for this planning branch.", (code,),
            )
        return actual

    def _evaluate_legacy(self, course: CourseFact) -> PrerequisiteConditionResult:
        if not course.prerequisites_verified:
            return PrerequisiteConditionResult(
                "unresolved", False, "unverified", "Legacy prerequisites are unverified."
            )
        actual_passed = self.student.passed_codes(self.grading_scheme)
        children = []
        for code in course.prerequisites:
            if legacy_prerequisite_satisfied(code, actual_passed):
                children.append(PrerequisiteConditionResult(
                    "satisfied", True, "verified", f"Legacy prerequisite {code} completed.", (code,)
                ))
            else:
                # Only local transcript compatibility uses stem matching. Recognition is exact.
                children.append(self._course_leaf({"course_code": code}))
        if not children:
            return PrerequisiteConditionResult(
                "satisfied", True, "verified", "No recorded prerequisites."
            )
        return self._all_of(tuple(children))


def legacy_prerequisite_satisfied(prerequisite: str, passed: set[str]) -> bool:
    """Compatibility-only UCT stem matching for legacy flat prerequisite lists."""

    prerequisite = prerequisite.strip().upper()
    if prerequisite in passed:
        return True
    match = re.fullmatch(r"([A-Z]{2,4}\d{4})([A-Z]{0,2})", prerequisite)
    if not match or match.group(2):
        return False
    return any(code.startswith(match.group(1)) for code in passed)


def legacy_prereqs_met(course: CourseFact, passed: set[str]) -> bool:
    if not course.prerequisites_verified:
        return False
    return all(legacy_prerequisite_satisfied(item, passed) for item in course.prerequisites)
