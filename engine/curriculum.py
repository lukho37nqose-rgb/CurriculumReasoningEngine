"""Composable curriculum-rule evaluation for structured Humanities routes.

The general BA/BSocSc degrees are expressed through majors and aggregate
thresholds.  Professional, performance, education, fine-art and music
qualifications instead prescribe curricula with streams, alternatives and
manual selection conditions.  This module evaluates a small handbook-grounded
rule language without turning discretionary institutional decisions into facts.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from typing import Any

from curriculum_reasoning_engine.institutions import (
    AcademicCreditFramework,
    CourseCodeScheme,
    CourseLoadFramework,
    GradingScheme,
    UCTCourseCodeScheme,
    UCTCourseLoadFramework,
)

from .completion import CourseCompletionRecognitionInput, CourseCompletionResolver
from .models import (
    AcademicRecordCoverageEvidence,
    Catalogue,
    CourseFact,
    CourseResult,
    RequirementRecognitionCoverage,
    RequirementRecognitionEvidence,
    StudentRecord,
)
from .recognition import provisional_open_credit_allocations, recognised_credited_pairs

_LEGACY_UCT_CODE_SCHEME = UCTCourseCodeScheme()
_LEGACY_UCT_LOAD_FRAMEWORK = UCTCourseLoadFramework()


@dataclass
class RuleEvaluation:
    id: str
    label: str
    complete: bool
    current: float
    required: float
    detail: str
    status: str = "verified"
    confidence: float = 1.0
    blocking: bool = True
    used_course_codes: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    source: dict[str, Any] = field(default_factory=dict)
    outcome_override: str | None = None
    assessment_complete_override: bool | None = None
    recognition_witness: str | None = None

    @property
    def assessment_complete(self) -> bool:
        if self.assessment_complete_override is not None:
            return self.assessment_complete_override
        return self.status in {"verified", "discretionary"}

    @property
    def outcome(self) -> str:
        if self.outcome_override is not None:
            return self.outcome_override
        if self.status == "conflict":
            return "conflict"
        if self.status == "unsupported":
            return "unsupported"
        if self.complete:
            return "satisfied"
        return "not_satisfied" if self.assessment_complete else "unresolved"


def _normalise_codes(values: Iterable[Any]) -> list[str]:
    return [str(value).strip().upper() for value in values if str(value).strip()]


def collect_rule_course_codes(
    rule: dict[str, Any], catalogue: Catalogue | None = None
) -> set[str]:
    """Collect every course that a rule may require or recommend."""
    codes = set(_normalise_codes(rule.get("course_codes", [])))
    code = str(rule.get("course_code", "")).strip().upper()
    if code:
        codes.add(code)
    for child in rule.get("children", []):
        if isinstance(child, dict):
            codes.update(collect_rule_course_codes(child, catalogue))
    filters = (
        rule.get("filters", {}) if isinstance(rule.get("filters", {}), dict) else {}
    )
    codes.update(_normalise_codes(filters.get("course_codes", [])))
    if catalogue and filters:
        candidates = codes or set(catalogue.courses)
        for course_code in list(candidates):
            fact = catalogue.courses.get(course_code)
            if fact is not None and _fact_matches_filters(course_code, fact, filters):
                codes.add(course_code)
    return codes


def collect_curriculum_course_codes(
    rules: Iterable[dict[str, Any]],
    catalogue: Catalogue | None = None,
) -> set[str]:
    codes: set[str] = set()
    for rule in rules:
        if isinstance(rule, dict):
            codes.update(collect_rule_course_codes(rule, catalogue))
    return codes


def _year_level(code: str) -> int:
    """Compatibility shim for legacy callers; UCT owns year-level inference."""
    return _LEGACY_UCT_CODE_SCHEME.infer_year_level(code)


def _fact_matches_filters(
    code: str,
    fact: CourseFact,
    filters: dict[str, Any],
    credit_framework: AcademicCreditFramework | None = None,
    course_code_scheme: CourseCodeScheme | None = None,
) -> bool:
    explicit = set(_normalise_codes(filters.get("course_codes", [])))
    if explicit and code not in explicit:
        return False
    prefixes = [
        str(p).strip().upper() for p in filters.get("prefixes", []) if str(p).strip()
    ]
    if prefixes and not any(code.startswith(prefix) for prefix in prefixes):
        return False
    excluded_prefixes = [
        str(p).strip().upper()
        for p in filters.get("exclude_prefixes", [])
        if str(p).strip()
    ]
    if excluded_prefixes and any(
        code.startswith(prefix) for prefix in excluded_prefixes
    ):
        return False
    levels = {int(value) for value in filters.get("nqf_levels", [])}
    academic_level = (
        credit_framework.academic_level(fact)
        if credit_framework is not None
        else fact.nqf_level
    )
    if levels and academic_level not in levels:
        return False
    credit_values = {
        int(value) for value in filters.get("credit_values", []) if str(value).strip()
    }
    credit_value = (
        credit_framework.credit_value(fact)
        if credit_framework is not None
        else fact.nqf_credits
    )
    if credit_values and credit_value not in credit_values:
        return False
    years = {int(value) for value in filters.get("year_levels", [])}
    code_scheme = course_code_scheme or _LEGACY_UCT_CODE_SCHEME
    if years and code_scheme.infer_year_level(code) not in years:
        return False
    if filters.get("senior") is True and not (
        credit_framework.is_senior_level(fact)
        if credit_framework is not None
        else fact.nqf_level >= 6
    ):
        return False
    if filters.get("humanities") is True and not fact.counts_as_humanities:
        return False
    if filters.get("science") is True and not fact.counts_as_science:
        return False
    if filters.get("general_elective") is True and not fact.general_elective:
        return False
    if filters.get("credit_bearing") is True and not fact.credit_bearing:
        return False
    if filters.get("departments"):
        departments = {str(value).strip().lower() for value in filters["departments"]}
        if fact.department.strip().lower() not in departments:
            return False
    return True


def _combine_status(statuses: list[str], fallback: str = "verified") -> str:
    if not statuses:
        return fallback
    order = {
        "conflict": 5,
        "discretionary": 4,
        "unverified": 3,
        "provisional": 2,
        "verified": 1,
    }
    return max(statuses, key=lambda value: order.get(value, 3))


def _weighting_basis(rule: dict[str, Any]) -> str:
    weighting = rule.get("weighting", {})
    if not isinstance(weighting, dict):
        return "credit_value"
    basis = str(weighting.get("basis", "credit_value")).strip().lower()
    return basis or "credit_value"


def _normalise_status_token(value: Any) -> str:
    return " ".join(str(value or "").strip().upper().split())


def _status_treatment(rule: dict[str, Any]) -> dict[str, str]:
    raw = rule.get("status_treatment", {})
    if not isinstance(raw, dict):
        return {}
    allowed = {"zero", "exclude", "requires_verification"}
    return {
        _normalise_status_token(token): action
        for token, action_raw in raw.items()
        if (action := str(action_raw).strip().lower()) in allowed
        and _normalise_status_token(token)
    }


class CurriculumEvaluator:
    def __init__(
        self,
        student: StudentRecord,
        catalogue: Catalogue,
        grading_scheme: GradingScheme | None = None,
        credit_framework: AcademicCreditFramework | None = None,
        course_code_scheme: CourseCodeScheme | None = None,
        course_load_framework: CourseLoadFramework | None = None,
        completion_recognition: CourseCompletionRecognitionInput | None = None,
        academic_record_coverage_evidence: list[AcademicRecordCoverageEvidence] | None = None,
        requirement_recognition_evidence: list[RequirementRecognitionEvidence] | None = None,
        requirement_recognition_coverage: list[RequirementRecognitionCoverage] | None = None,
        institution_id: str = "",
    ):
        self.student = student
        self.catalogue = catalogue
        self.grading_scheme = grading_scheme
        self.credit_framework = credit_framework
        self.course_code_scheme = course_code_scheme
        self.course_load_framework = course_load_framework
        self.academic_record_coverage_evidence = academic_record_coverage_evidence
        self.requirement_recognition_evidence = requirement_recognition_evidence or []
        self.requirement_recognition_coverage = requirement_recognition_coverage or []
        self.institution_id = institution_id or getattr(grading_scheme, "institution_id", "")
        self.completion = CourseCompletionResolver(student, catalogue, grading_scheme, completion_recognition)
        pairs, _ = recognised_credited_pairs(
            student, catalogue, grading_scheme, course_code_scheme
        )
        self.pairs = pairs
        self.fact_by_code = {fact.code: fact for _, fact in pairs}

        self.result_by_code: dict[str, CourseResult] = {}
        for result, _ in pairs:
            self.result_by_code[result.code] = result
        self.passed = set(self.result_by_code)
        # Zero-credit practical, project, skills and assessment courses may be
        # compulsory even though they do not contribute to credit totals.
        # Keep them available for course-completion rules without adding them
        # to the recognised credit maps.
        self.passed.update(
            result.code
            for result in student.credited_results(grading_scheme)
            if result.code in catalogue.courses
        )
        self.open_credit_allocations = provisional_open_credit_allocations(
            student, catalogue, grading_scheme, credit_framework
        )
        self.open_allocation_by_id = {
            allocation.rule_id: allocation
            for allocation in self.open_credit_allocations
        }
        self.provisional_results = [
            result
            for allocation in self.open_credit_allocations
            for result in allocation.results
        ]
        self.provisional_result_by_code = {
            result.code: result for result in self.provisional_results
        }
        self.provisional_codes = set(self.provisional_result_by_code)
        self.credits = sum(self.credit_value(fact) for _, fact in pairs) + sum(
            self.credit_value(result) for result in self.provisional_results
        )
        self.credits_by_level: dict[int, int] = {}
        for _, fact in pairs:
            level = self.academic_level(fact)
            self.credits_by_level[level] = (
                self.credits_by_level.get(level, 0) + self.credit_value(fact)
            )
        for result in self.provisional_results:
            level = self.academic_level(result)
            self.credits_by_level[level] = (
                self.credits_by_level.get(level, 0) + self.credit_value(result)
            )

    def _coverage_complete_for(self, codes: Iterable[str]) -> bool:
        if self.academic_record_coverage_evidence is None:
            return True
        wanted = {str(code).strip().upper() for code in codes if str(code).strip()}
        covered = {
            str(code).strip().upper()
            for evidence in self.academic_record_coverage_evidence
            if str(evidence.coverage_state).strip().lower() == "complete"
            for code in evidence.course_codes
        }
        return wanted <= covered

    def credit_value(self, item: CourseFact | CourseResult) -> int:
        return (
            self.credit_framework.credit_value(item)
            if self.credit_framework is not None
            else item.nqf_credits
        )

    def academic_level(self, item: CourseFact | CourseResult) -> int:
        return (
            self.credit_framework.academic_level(item)
            if self.credit_framework is not None
            else item.nqf_level
        )

    def department_for(self, code: str, fact: CourseFact | None = None) -> str:
        if fact is not None and fact.department.strip():
            return fact.department.strip()
        code_scheme = self.course_code_scheme or _LEGACY_UCT_CODE_SCHEME
        return code_scheme.infer_department(code)

    def load_equivalent(self, item: CourseFact | CourseResult | str) -> float:
        load_framework = self.course_load_framework or _LEGACY_UCT_LOAD_FRAMEWORK
        return load_framework.load_equivalent(item)

    def average_weight(self, item: CourseFact | CourseResult, basis: str) -> float:
        if basis == "equal":
            return 1.0
        if basis == "course_load_equivalent":
            return self.load_equivalent(item)
        if basis == "credit_value":
            return max(1, float(self.credit_value(item)))
        raise ValueError(f"Unsupported average weighting basis {basis!r}.")

    def evaluate_many(self, rules: Iterable[dict[str, Any]]) -> list[RuleEvaluation]:
        return [self._apply_requirement_recognition(rule, self.evaluate(rule)) for rule in rules if isinstance(rule, dict)]

    def _apply_requirement_recognition(
        self, rule: dict[str, Any], evaluation: RuleEvaluation
    ) -> RuleEvaluation:
        if not bool(rule.get("recognition_allowed", False)):
            return evaluation
        requirement_id = evaluation.id
        matches = [
            evidence
            for evidence in self.requirement_recognition_evidence
            if evidence.target_requirement_id == requirement_id
            and evidence.student_id == self.student.student_id
            and evidence.programme_key == (self.catalogue.programme_key or self.student.programme_key)
            and evidence.institution_id == self.institution_id
            and evidence.release_id == self.catalogue.recognition_release_id
            and (not evidence.pathway_key or evidence.pathway_key == self.catalogue.pathway_key)
        ]
        if len(matches) > 1 and len({evidence.recognition_id for evidence in matches}) != 1:
            return replace(
                evaluation,
                outcome_override="conflict",
                assessment_complete_override=False,
                status="conflict",
                detail=f"Conflicting requirement-recognition decisions target {requirement_id}.",
            )
        if matches:
            evidence = matches[0]
            return replace(
                evaluation,
                complete=True,
                current=max(1.0, evaluation.current),
                status=_combine_status([evaluation.status, evidence.verification_status]),
                outcome_override="satisfied",
                assessment_complete_override=True,
                recognition_witness=evidence.recognition_id,
                detail=(
                    f"Requirement {requirement_id} satisfied by institutional recognition "
                    f"decision {evidence.recognition_id}."
                ),
            )
        if evaluation.outcome == "satisfied":
            return evaluation
        covered = any(
            requirement_id in coverage.requirement_ids
            and coverage.student_id == self.student.student_id
            and coverage.programme_key == (self.catalogue.programme_key or self.student.programme_key)
            and coverage.institution_id == self.institution_id
            and coverage.release_id == self.catalogue.recognition_release_id
            and coverage.coverage_state == "complete"
            for coverage in self.requirement_recognition_coverage
        )
        if not covered:
            return replace(
                evaluation,
                outcome_override="unresolved",
                assessment_complete_override=False,
                status=_combine_status([evaluation.status, "unverified"]),
                detail=(
                    f"{evaluation.detail} Requirement-recognition decision coverage "
                    f"for {requirement_id} is incomplete."
                ),
            )
        return evaluation

    def evaluate(self, rule: dict[str, Any]) -> RuleEvaluation:
        rule_type = str(rule.get("type", "course")).strip().lower()
        rule_id = str(rule.get("id", rule.get("label", rule_type))).strip() or rule_type
        label = str(rule.get("label", rule_id)).strip()
        status = str(rule.get("verification_status", rule.get("status", "verified")))
        blocking = bool(rule.get("blocking", True))
        source = (
            rule.get("source", {}) if isinstance(rule.get("source", {}), dict) else {}
        )

        if rule_type == "manual":
            assumed_complete = bool(rule.get("assumed_complete", True))
            manual_status = str(rule.get("status", "discretionary"))
            note = str(
                rule.get(
                    "note",
                    "This condition requires confirmation by the relevant academic authority.",
                )
            )
            return RuleEvaluation(
                id=rule_id,
                label=label,
                complete=assumed_complete,
                current=1.0 if assumed_complete else 0.0,
                required=1.0,
                detail=note,
                status=manual_status,
                confidence=0.0,
                blocking=blocking,
                assumptions=[note],
                source=source,
            )

        if rule_type == "credits":
            required = float(rule.get("required", 0))
            current = float(self.credits)
            evaluation_status = "unverified" if self.provisional_codes else status
            if self.academic_record_coverage_evidence is not None and not self._coverage_complete_for(self.catalogue.courses):
                evaluation_status = _combine_status([evaluation_status, "unverified"])
            assumptions = []
            detail = f"{int(current)} of {int(required)} recognised or provisionally allocated NQF credits completed."
            if self.provisional_codes:
                assumptions.append(
                    "Includes transcript credits allocated to an approved/open elective pool whose faculty approval is not verified."
                )
                detail += (
                    " Provisional elective codes: "
                    + ", ".join(sorted(self.provisional_codes))
                    + "."
                )
            return RuleEvaluation(
                rule_id,
                label,
                current >= required,
                current,
                required,
                detail,
                evaluation_status,
                (
                    0.45
                    if self.provisional_codes
                    else (1.0 if status == "verified" else 0.7)
                ),
                blocking,
                used_course_codes=sorted(self.passed | self.provisional_codes),
                assumptions=assumptions,
                source=source,
                outcome_override=("unresolved" if current < required and evaluation_status == status else None),
                assessment_complete_override=(False if current < required and evaluation_status == status else None),
            )

        if rule_type == "level_credits":
            level = int(rule.get("nqf_level", 0))
            required = float(rule.get("required", 0))
            current = float(
                sum(
                    self.credit_value(fact)
                    for _, fact in self.pairs
                    if (
                        self.credit_framework.is_level(fact, level)
                        if self.credit_framework is not None
                        else fact.nqf_level == level
                    )
                )
                + sum(
                    self.credit_value(result)
                    for result in self.provisional_results
                    if (
                        self.credit_framework.is_level(result, level)
                        if self.credit_framework is not None
                        else result.nqf_level == level
                    )
                )
            )
            used = sorted(
                code
                for code, fact in self.fact_by_code.items()
                if (
                    self.credit_framework.is_level(fact, level)
                    if self.credit_framework is not None
                    else fact.nqf_level == level
                )
            )
            evaluation_status = status
            if self.academic_record_coverage_evidence is not None and not self._coverage_complete_for(self.catalogue.courses):
                evaluation_status = _combine_status([evaluation_status, "unverified"])
            return RuleEvaluation(
                rule_id,
                label,
                current >= required,
                current,
                required,
                f"{int(current)} of {int(required)} credits at NQF level {level} completed.",
                evaluation_status,
                1.0 if evaluation_status == "verified" else 0.7,
                blocking,
                used_course_codes=used,
                source=source,
                outcome_override=("unresolved" if current < required and evaluation_status == status else None),
                assessment_complete_override=(False if current < required and evaluation_status == status else None),
            )

        if rule_type == "minimum_mark":
            codes = _normalise_codes(rule.get("course_codes", []))
            threshold = int(rule.get("minimum_mark", rule.get("required", 0)))
            matched = [
                self.result_by_code[code]
                for code in codes
                if code in self.result_by_code
            ]
            if not matched:
                return RuleEvaluation(
                    rule_id,
                    label,
                    False,
                    0.0,
                    float(threshold),
                    f"No passing result was found for any of: {', '.join(codes)}.",
                    status,
                    1.0,
                    blocking,
                    source=source,
                )
            known_marks = [result.mark for result in matched if result.mark is not None]
            if not known_marks:
                note = "The course is passed, but the transcript does not expose a numeric mark for this threshold."
                return RuleEvaluation(
                    rule_id,
                    label,
                    True,
                    0.0,
                    float(threshold),
                    note,
                    "unverified",
                    0.0,
                    blocking,
                    used_course_codes=[result.code for result in matched],
                    assumptions=[note],
                    source=source,
                )
            current = float(max(known_marks))
            return RuleEvaluation(
                rule_id,
                label,
                current >= threshold,
                current,
                float(threshold),
                f"Best recorded mark is {int(current)}%; at least {threshold}% is required.",
                status,
                1.0,
                blocking,
                used_course_codes=[result.code for result in matched],
                source=source,
            )

        if rule_type in {"course", "choose_n"} and rule.get("children"):
            children = [
                self.evaluate(child)
                for child in rule.get("children", [])
                if isinstance(child, dict)
            ]
            required = int(
                rule.get("required", 1 if rule_type == "course" else len(children))
            )
            complete_children = [child for child in children if child.complete]
            unknown_children = [child for child in children if not child.complete and not child.assessment_complete]
            definite_children = [child for child in children if not child.complete and child.assessment_complete]
            used = sorted(
                {
                    code
                    for child in complete_children
                    for code in child.used_course_codes
                }
            )
            if len(complete_children) >= required:
                child_status = _combine_status([child.status for child in children if child.complete], status)
                if unknown_children:
                    child_status = _combine_status([child_status, "unverified"])
            elif len(complete_children) + len(unknown_children) < required:
                child_status = _combine_status([child.status for child in definite_children], status)
            else:
                child_status = _combine_status([status, "unverified"])
            bound_outcome = None
            bound_complete = None
            if len(complete_children) + len(unknown_children) < required:
                bound_outcome = "not_satisfied"
                bound_complete = not unknown_children
            return RuleEvaluation(
                rule_id,
                label,
                len(complete_children) >= required,
                float(len(complete_children)),
                float(required),
                f"{len(complete_children)} of {required} alternatives completed.",
                _combine_status([status, child_status]),
                min([child.confidence for child in complete_children] or [1.0]),
                blocking,
                used,
                source=source,
                outcome_override=bound_outcome,
                assessment_complete_override=bound_complete,
            )

        if rule_type in {"course", "choose_n", "all_courses"}:
            codes = _normalise_codes(rule.get("course_codes", []))
            if rule_type == "course":
                required = int(rule.get("required", 1))
            elif rule_type == "all_courses":
                required = len(codes)
            else:
                required = int(rule.get("required", 1))
            assessments = {
                code: self.completion.resolve(code, self.academic_record_coverage_evidence)
                for code in codes
            }
            completed = [code for code in codes if assessments[code].outcome == "satisfied"]
            missing = [code for code in codes if code not in completed]
            witnesses = sorted(completed, key=lambda c: {"verified": 0, "provisional": 1}.get(assessments[c].status, 2))[:required]
            if len(completed) >= required:
                status = _combine_status([status, *(assessments[c].status for c in witnesses)])
            elif any(a.outcome == "conflict" for a in assessments.values()):
                status = "conflict"
            elif len(completed) + sum(a.outcome in {"unresolved", "unsupported"} for a in assessments.values()) < required:
                status = _combine_status([status, *(a.status for a in assessments.values() if a.outcome == "not_satisfied")])
            else:
                status = _combine_status([status, "unverified"])
            if rule_type == "course" and required == 1:
                detail = (
                    assessments[witnesses[0]].detail
                    if completed
                    else "Complete one of: " + ", ".join(codes) + "."
                )
            else:
                detail = (
                    f"{len(completed)} of {required} required courses completed."
                    if rule_type == "all_courses"
                    else f"You need {required} course(s) from this represented group. CRE can confirm {len(completed)}. Represented options: {', '.join(codes)}."
                )
                if len(completed) < required and missing:
                    detail += (
                        (" Courses still represented as required include: " if rule_type == "all_courses" else " Remaining options include: ")
                        + ", ".join(missing[:12])
                        + ("…" if len(missing) > 12 else "")
                    )
                recognition_details = [
                    assessments[code].detail for code in witnesses
                    if assessments[code].witness_source == "recognition"
                ]
                if recognition_details:
                    detail += " " + " ".join(recognition_details)
                if witnesses:
                    detail += " Confirmed completion: " + ", ".join(witnesses) + "."
                if rule_type == "all_courses" and len(codes) == 1:
                    detail = f"{codes[0]} is represented as required. " + assessments[codes[0]].detail
                elif len(completed) < required:
                    detail += " " + " ".join(
                        assessment.detail for assessment in assessments.values()
                        if assessment.outcome in {"unresolved", "conflict"}
                    )
            return RuleEvaluation(
                rule_id,
                label,
                len(completed) >= required,
                float(len(completed)),
                float(required),
                detail,
                status,
                1.0 if status == "verified" else 0.7,
                blocking,
                completed,
                source=source,
                outcome_override=(
                    "not_satisfied"
                    if status != "conflict"
                    and len(completed) + sum(a.outcome in {"unresolved", "unsupported"} for a in assessments.values()) < required
                    else None
                ),
                assessment_complete_override=(
                    False
                    if len(completed) + sum(a.outcome in {"unresolved", "unsupported"} for a in assessments.values()) < required
                    and any(a.outcome in {"unresolved", "unsupported"} for a in assessments.values())
                    else None
                ),
            )

        if rule_type == "approved_credit_pool":
            required = float(rule.get("required", 0))
            maximum = float(rule.get("maximum", 0))
            allocation = self.open_allocation_by_id.get(rule_id)
            if allocation is None:
                detail = "No approved/open elective allocation could be constructed for this rule."
                optional_only = required <= 0 and maximum > 0
                return RuleEvaluation(
                    rule_id,
                    label,
                    optional_only,
                    0.0,
                    maximum if optional_only else required,
                    detail,
                    "unverified",
                    0.0,
                    blocking,
                    assumptions=[detail],
                    source=source,
                )
            current = float(
                allocation.recognised_credits + allocation.provisional_credits
            )
            provisional_codes = [result.code for result in allocation.results]
            known_codes = sorted(allocation.recognised_codes)
            if required > 0:
                detail = f"{int(current)} of {int(required)} credits identified for this approved/open elective pool."
            elif maximum > 0:
                detail = f"{int(current)} credits identified in this optional pool; up to {int(maximum)} may be recognised."
            else:
                detail = f"{int(current)} credits identified in this optional approved/open elective pool."
            assumptions: list[str] = []
            evaluation_status = status if status != "verified" else "unverified"
            confidence = 0.55
            if provisional_codes:
                detail += (
                    " Transcript-only course(s) provisionally allocated: "
                    + ", ".join(provisional_codes)
                    + "."
                )
                assumptions.append(allocation.note)
                confidence = 0.35
            else:
                detail += " Faculty approval and live registration eligibility still require confirmation."
                assumptions.append(allocation.note)
            complete = (
                current >= required
                if required > 0
                else (current <= maximum if maximum > 0 else True)
            )
            display_required = required if required > 0 else maximum
            return RuleEvaluation(
                rule_id,
                label,
                complete,
                current,
                display_required,
                detail,
                evaluation_status,
                confidence,
                blocking,
                used_course_codes=sorted(set(known_codes + provisional_codes)),
                assumptions=assumptions,
                source=source,
            )

        if rule_type == "credit_pool":
            filters = (
                rule.get("filters", {})
                if isinstance(rule.get("filters", {}), dict)
                else {}
            )
            explicit = set(_normalise_codes(rule.get("course_codes", [])))
            required = float(rule.get("required", 0))
            matched = sorted(
                code
                for code, fact in self.fact_by_code.items()
                if (not explicit or code in explicit)
                and _fact_matches_filters(
                    code, fact, filters, self.credit_framework, self.course_code_scheme
                )
            )
            current = float(sum(self.credit_value(self.fact_by_code[code]) for code in matched))
            detail = f"{int(current)} of {int(required)} credits completed in this approved course pool."
            if explicit and current < required:
                remaining = sorted(explicit - set(matched))
                if remaining:
                    detail += (
                        " Remaining recorded options include: "
                        + ", ".join(remaining[:12])
                        + ("…" if len(remaining) > 12 else "")
                    )
            evaluation_status = status
            if (self.academic_record_coverage_evidence is not None and not self._coverage_complete_for(
                explicit or self.catalogue.courses
            )) and current < required:
                evaluation_status = _combine_status([evaluation_status, "unverified"])
            return RuleEvaluation(
                rule_id,
                label,
                current >= required,
                current,
                required,
                detail,
                evaluation_status,
                1.0 if evaluation_status == "verified" else 0.7,
                blocking,
                matched,
                source=source,
                outcome_override=("unresolved" if current < required and evaluation_status == status else None),
                assessment_complete_override=(False if current < required and evaluation_status == status else None),
            )

        if rule_type == "maximum_credit_pool":
            filters = (
                rule.get("filters", {})
                if isinstance(rule.get("filters", {}), dict)
                else {}
            )
            explicit = set(_normalise_codes(rule.get("course_codes", [])))
            maximum = float(rule.get("maximum", rule.get("required", 0)))
            matched = sorted(
                code
                for code, fact in self.fact_by_code.items()
                if (not explicit or code in explicit)
                and _fact_matches_filters(
                    code, fact, filters, self.credit_framework, self.course_code_scheme
                )
            )
            current = float(sum(self.credit_value(self.fact_by_code[code]) for code in matched))
            evaluation_status = status
            if (self.academic_record_coverage_evidence is not None and not self._coverage_complete_for(
                explicit or self.catalogue.courses
            )) and current <= maximum:
                evaluation_status = _combine_status([evaluation_status, "unverified"])
            return RuleEvaluation(
                rule_id,
                label,
                current <= maximum,
                current,
                maximum,
                f"{int(current)} credits completed in this pool; no more than {int(maximum)} are permitted.",
                evaluation_status,
                1.0 if evaluation_status == "verified" else 0.7,
                blocking,
                matched,
                source=source,
                outcome_override=("unresolved" if current <= maximum and evaluation_status == status else None),
                assessment_complete_override=(False if current <= maximum and evaluation_status == status else None),
            )

        if rule_type == "same_department_credit_pool":
            filters = (
                rule.get("filters", {})
                if isinstance(rule.get("filters", {}), dict)
                else {}
            )
            transcript_filters = (
                rule.get("transcript_filters", {})
                if isinstance(rule.get("transcript_filters", {}), dict)
                else {}
            )
            explicit = set(_normalise_codes(rule.get("course_codes", [])))
            required = float(rule.get("required", 0))
            grouped: dict[str, list[str]] = {}
            grouped_credits: dict[str, int] = {}
            for code, fact in self.fact_by_code.items():
                if (explicit and code not in explicit) or not _fact_matches_filters(
                    code, fact, filters, self.credit_framework, self.course_code_scheme
                ):
                    continue
                group = self.department_for(code, fact)
                grouped.setdefault(group, []).append(code)
                grouped_credits[group] = (
                    grouped_credits.get(group, 0) + self.credit_value(fact)
                )
            provisional_groups: set[str] = set()
            if bool(rule.get("allow_unlisted_transcript_courses", False)):
                for result in self.student.credited_results(self.grading_scheme):
                    if (
                        result.code in self.catalogue.courses
                        or self.credit_value(result) <= 0
                    ):
                        continue
                    pseudo = CourseFact(
                        code=result.code,
                        name=result.name,
                        nqf_credits=result.nqf_credits,
                        nqf_level=result.nqf_level,
                        prerequisites=[],
                        offered=[],
                        department=self.department_for(result.code),
                    )
                    if not _fact_matches_filters(
                        result.code,
                        pseudo,
                        transcript_filters,
                        self.credit_framework,
                        self.course_code_scheme,
                    ):
                        continue
                    group = self.department_for(result.code, pseudo)
                    grouped.setdefault(group, []).append(result.code)
                    grouped_credits[group] = (
                        grouped_credits.get(group, 0) + self.credit_value(result)
                    )
                    provisional_groups.add(group)
            best_group = max(grouped_credits, key=grouped_credits.get, default="")
            current = float(grouped_credits.get(best_group, 0))
            used = sorted(grouped.get(best_group, []))
            evaluation_status = status
            assumptions: list[str] = []
            confidence = 1.0 if status == "verified" else 0.7
            if best_group in provisional_groups:
                evaluation_status = _combine_status([status, "unverified"])
                confidence = 0.35
                assumptions.append(
                    "This discipline pool includes transcript-only courses whose programme recognition must be confirmed."
                )
            detail = (
                f"{int(current)} of {int(required)} credits completed in one discipline"
            )
            if best_group:
                detail += f" ({best_group})"
            detail += "."
            return RuleEvaluation(
                rule_id,
                label,
                current >= required,
                current,
                required,
                detail,
                evaluation_status,
                confidence,
                blocking,
                used,
                assumptions=assumptions,
                source=source,
            )

        if rule_type == "no_failures":
            filters = (
                rule.get("filters", {})
                if isinstance(rule.get("filters", {}), dict)
                else {}
            )
            explicit = set(_normalise_codes(rule.get("course_codes", [])))
            failures: list[str] = []
            for result in self.student.results:
                if not result.is_failed(self.grading_scheme):
                    continue
                fact = self.catalogue.courses.get(result.code)
                if explicit and result.code not in explicit:
                    continue
                if (
                    fact is not None
                    and filters
                    and not _fact_matches_filters(
                        result.code, fact, filters, self.credit_framework, self.course_code_scheme
                    )
                ):
                    continue
                failures.append(result.code)
            complete = not failures
            note = (
                "No failed course attempts are recorded."
                if complete
                else "Failed attempt(s) recorded for: "
                + ", ".join(sorted(set(failures)))
                + "."
            )
            eval_status = status
            assumptions: list[str] = []
            if failures and bool(rule.get("condonable", False)):
                eval_status = "discretionary"
                note += " The handbook permits Senate to condone a failure for award purposes."
                assumptions.append(
                    "Any condonation must be confirmed from an official Senate or faculty decision."
                )
            return RuleEvaluation(
                rule_id,
                label,
                complete,
                0.0 if complete else float(len(set(failures))),
                0.0,
                note,
                eval_status,
                1.0 if eval_status == "verified" else 0.0,
                blocking,
                sorted(set(failures)),
                assumptions=assumptions,
                source=source,
            )

        if rule_type == "passed_mark_equivalents":
            filters = (
                rule.get("filters", {})
                if isinstance(rule.get("filters", {}), dict)
                else {}
            )
            explicit = set(_normalise_codes(rule.get("course_codes", [])))
            threshold = float(rule.get("minimum_mark", 75))
            required = float(rule.get("required", 1))
            equivalents = 0.0
            used: list[str] = []
            unknown: list[str] = []
            for code, result in self.result_by_code.items():
                fact = self.fact_by_code[code]
                if (explicit and code not in explicit) or not _fact_matches_filters(
                    code, fact, filters, self.credit_framework, self.course_code_scheme
                ):
                    continue
                if result.mark is None:
                    unknown.append(code)
                elif result.mark >= threshold:
                    unit = float(rule.get("equivalent_credit_unit", 0) or 0)
                    equivalents += (
                        (self.credit_value(fact) / unit)
                        if unit
                        else self.load_equivalent(result)
                    )
                    used.append(code)
            eval_status = (
                status if not unknown else _combine_status([status, "unverified"])
            )
            assumptions = (
                ["Numeric marks are missing for: " + ", ".join(sorted(unknown))]
                if unknown
                else []
            )
            return RuleEvaluation(
                rule_id,
                label,
                equivalents >= required,
                equivalents,
                required,
                f"{equivalents:g} of {required:g} full-course equivalents have marks of at least {threshold:g}%.",
                eval_status,
                1.0 if not unknown else 0.0,
                blocking,
                sorted(used),
                assumptions=assumptions,
                source=source,
            )

        if rule_type == "passed_mark_credits":
            filters = (
                rule.get("filters", {})
                if isinstance(rule.get("filters", {}), dict)
                else {}
            )
            explicit = set(_normalise_codes(rule.get("course_codes", [])))
            threshold = float(rule.get("minimum_mark", 75))
            required = float(rule.get("minimum_credits", rule.get("required", 0)))
            first_attempt_only = bool(rule.get("first_attempt_only", False))
            excluded_grade_tokens = {
                str(value).strip().upper()
                for value in rule.get("exclude_grade_tokens", [])
                if str(value).strip()
            }
            credits = 0.0
            used: list[str] = []
            unknown: list[str] = []
            excluded: list[str] = []
            for code, result in self.result_by_code.items():
                fact = self.fact_by_code[code]
                if (explicit and code not in explicit) or not _fact_matches_filters(
                    code, fact, filters, self.credit_framework, self.course_code_scheme
                ):
                    continue
                attempts = [
                    attempt
                    for attempt in self.student.results
                    if attempt.code == code and not attempt.is_pending(self.grading_scheme)
                ]
                grade = " ".join(str(result.grade or "").strip().upper().split())
                if (
                    first_attempt_only
                    and len(attempts) != 1
                    or grade in excluded_grade_tokens
                ):
                    excluded.append(code)
                    continue
                if result.mark is None:
                    unknown.append(code)
                elif result.mark >= threshold:
                    credits += float(self.credit_value(fact))
                    used.append(code)
            eval_status = (
                status if not unknown else _combine_status([status, "unverified"])
            )
            assumptions: list[str] = []
            if unknown:
                assumptions.append(
                    "Numeric marks are missing for: " + ", ".join(sorted(unknown))
                )
            if excluded:
                assumptions.append(
                    "Rule-configured attempt/status exclusions removed: "
                    + ", ".join(sorted(excluded))
                    + "."
                )
            detail = (
                f"{credits:g} of {required:g} academic credits have marks of at least "
                f"{threshold:g}%."
            )
            if excluded:
                detail += (
                    " Excluded by configured attempt/status treatment: "
                    + ", ".join(sorted(excluded))
                    + "."
                )
            evaluation_status = status
            if self.academic_record_coverage_evidence is not None and not self._coverage_complete_for(self.catalogue.courses):
                evaluation_status = _combine_status([evaluation_status, "unverified"])
            return RuleEvaluation(
                rule_id,
                label,
                credits >= required,
                credits,
                required,
                detail,
                eval_status,
                1.0 if eval_status == "verified" else 0.0,
                blocking,
                sorted(used),
                assumptions=assumptions,
                source=source,
            )

        if rule_type == "first_class_group":
            codes = _normalise_codes(rule.get("course_codes", []))
            required = int(rule.get("required", len(codes) or 1))
            threshold = float(rule.get("minimum_mark", 75))
            lower = float(rule.get("minimum_individual_mark", 70))
            allow_average = bool(rule.get("allow_group_average", True))
            candidates: list[tuple[str, CourseResult, CourseFact]] = []
            unknown: list[str] = []
            repeated_or_supp: list[str] = []
            for code in codes:
                result = self.result_by_code.get(code)
                fact = self.fact_by_code.get(code)
                if result is None or fact is None:
                    continue
                attempts = [
                    r
                    for r in self.student.results
                    if r.code == code and not r.is_pending(self.grading_scheme)
                ]
                grade = " ".join(str(result.grade or "").strip().upper().split())
                if len(attempts) != 1 or grade == "SP":
                    repeated_or_supp.append(code)
                    continue
                if result.mark is None:
                    unknown.append(code)
                    continue
                candidates.append((code, result, fact))
            candidates.sort(
                key=lambda row: (row[1].mark or -1, self.credit_value(row[2])),
                reverse=True,
            )
            selected = candidates[:required]
            marks = [float(row[1].mark) for row in selected if row[1].mark is not None]
            complete = len(selected) >= required and all(
                mark >= threshold for mark in marks
            )
            average_used = False
            if not complete and allow_average and len(selected) >= required:
                credits = {self.credit_value(row[2]) for row in selected}
                if len(credits) == 1:
                    credit = next(iter(credits))
                    averaging_allowed = (required == 2 and credit in {24, 36}) or (
                        required == 4 and credit == 12
                    )
                    if (
                        averaging_allowed
                        and min(marks, default=0) >= lower
                        and sum(marks) / len(marks) >= threshold
                    ):
                        complete = True
                        average_used = True
            status_out = status
            assumptions: list[str] = []
            if unknown:
                status_out = _combine_status([status_out, "unverified"])
                assumptions.append(
                    "Numeric marks are missing for: " + ", ".join(sorted(unknown))
                )
            if repeated_or_supp:
                assumptions.append(
                    "Repeated or supplementary passes do not count for Science distinction: "
                    + ", ".join(sorted(repeated_or_supp))
                )
            detail = (
                f"{len(selected)} of {required} first-attempt course results assessed; "
            )
            if marks:
                detail += f"selected average {sum(marks)/len(marks):.2f}% and minimum {min(marks):.0f}%."
            else:
                detail += "no eligible numeric marks are available."
            if repeated_or_supp:
                detail += (
                    " Repeated or supplementary passes were excluded: "
                    + ", ".join(sorted(repeated_or_supp))
                    + "."
                )
            if average_used:
                detail += " The FB8.1(b) group-averaging concession was applied."
            return RuleEvaluation(
                rule_id,
                label,
                complete,
                float(len(selected)),
                float(required),
                detail,
                status_out,
                1.0 if status_out == "verified" else 0.0,
                blocking,
                [row[0] for row in selected],
                assumptions=assumptions,
                source=source,
            )

        if rule_type == "best_n_average":
            codes = _normalise_codes(rule.get("course_codes", []))
            mandatory = set(_normalise_codes(rule.get("mandatory_course_codes", [])))
            required = int(rule.get("required", 1))
            threshold = float(
                rule.get("minimum_average", rule.get("required_average", 0))
            )
            minimum_mark = float(rule.get("minimum_mark", 0))
            minimum_mark_count = int(rule.get("minimum_mark_count", 0))
            basis = _weighting_basis(rule)
            filters = (
                rule.get("filters", {})
                if isinstance(rule.get("filters", {}), dict)
                else {}
            )
            first_attempt_only = bool(rule.get("first_attempt_only", False))
            excluded_grade_tokens = {
                " ".join(str(value).strip().upper().split())
                for value in rule.get("exclude_grade_tokens", [])
                if str(value).strip()
            }
            candidates: list[tuple[str, float, float]] = []
            missing_marks: list[str] = []
            excluded: list[str] = []
            candidate_codes = codes or sorted(self.result_by_code)
            for code in candidate_codes:
                result = self.result_by_code.get(code)
                fact = self.fact_by_code.get(code)
                if result is None or fact is None:
                    continue
                if not _fact_matches_filters(
                    code,
                    fact,
                    filters,
                    self.credit_framework,
                    self.course_code_scheme,
                ):
                    continue
                attempts = [
                    attempt
                    for attempt in self.student.results
                    if attempt.code == code
                    and not attempt.is_pending(self.grading_scheme)
                ]
                grade = " ".join(str(result.grade or "").strip().upper().split())
                if (
                    first_attempt_only
                    and len(attempts) != 1
                    or grade in excluded_grade_tokens
                ):
                    excluded.append(code)
                    continue
                if result.mark is None:
                    missing_marks.append(code)
                    continue
                candidates.append(
                    (code, float(result.mark), self.average_weight(fact, basis))
                )
            selected: list[tuple[str, float, float]] = []
            for code in mandatory:
                match = next((row for row in candidates if row[0] == code), None)
                if match is not None:
                    selected.append(match)
            remaining = [
                row
                for row in candidates
                if row[0] not in {item[0] for item in selected}
            ]
            remaining.sort(key=lambda row: row[1], reverse=True)
            selected.extend(remaining[: max(0, required - len(selected))])
            denominator = sum(weight for _, _, weight in selected)
            average = (
                sum(mark * weight for _, mark, weight in selected) / denominator
                if denominator
                else 0.0
            )
            mandatory_met = mandatory <= {code for code, _, _ in selected}
            mark_count = (
                sum(mark >= minimum_mark for _, mark, _ in selected)
                if minimum_mark
                else len(selected)
            )
            complete = (
                len(selected) >= required
                and mandatory_met
                and average >= threshold
                and mark_count >= minimum_mark_count
            )
            eval_status = status
            assumptions: list[str] = []
            if missing_marks:
                eval_status = _combine_status([eval_status, "unverified"])
                assumptions.append(
                    "Numeric marks are missing for: " + ", ".join(sorted(missing_marks))
                )
            if excluded:
                assumptions.append(
                    "Rule-configured attempt/status exclusions removed: "
                    + ", ".join(sorted(excluded))
                    + "."
                )
            detail = f"Best {len(selected)} of {required} eligible results average {average:.2f}%; at least {threshold:g}% is required."
            if mandatory and not mandatory_met:
                detail += (
                    " Mandatory course result(s) missing: "
                    + ", ".join(sorted(mandatory - {code for code, _, _ in selected}))
                    + "."
                )
            if minimum_mark_count:
                detail += f" {mark_count} of {minimum_mark_count} required results meet {minimum_mark:g}%."
            if excluded:
                detail += (
                    " Excluded by configured attempt/status treatment: "
                    + ", ".join(sorted(excluded))
                    + "."
                )
            return RuleEvaluation(
                rule_id,
                label,
                complete,
                average,
                threshold,
                detail,
                eval_status,
                1.0 if eval_status == "verified" else 0.0,
                blocking,
                [code for code, _, _ in selected],
                assumptions=assumptions,
                source=source,
            )

        if rule_type == "first_attempt_weighted_average":
            explicit = set(_normalise_codes(rule.get("course_codes", [])))
            filters = (
                rule.get("filters", {})
                if isinstance(rule.get("filters", {}), dict)
                else {}
            )
            threshold = float(rule.get("minimum_average", rule.get("required", 0)))
            level_weights_raw = (
                rule.get("level_weights", {})
                if isinstance(rule.get("level_weights", {}), dict)
                else {}
            )
            level_weights = {
                int(level): float(weight) for level, weight in level_weights_raw.items()
            }
            include_failed_as_zero = bool(rule.get("include_failed_as_zero", True))
            basis = _weighting_basis(rule)
            status_treatment = _status_treatment(rule)
            first_by_code: dict[str, CourseResult] = {}
            for result in self.student.results:
                normalised_grade = _normalise_status_token(result.grade)
                if (
                    result.is_pending(self.grading_scheme)
                    and normalised_grade not in status_treatment
                    or result.code in first_by_code
                ):
                    continue
                fact = self.catalogue.courses.get(result.code)
                if fact is None:
                    continue
                if explicit and result.code not in explicit:
                    continue
                if filters and not _fact_matches_filters(
                    result.code,
                    fact,
                    filters,
                    self.credit_framework,
                    self.course_code_scheme,
                ):
                    continue
                first_by_code[result.code] = result
            weighted_total = 0.0
            denominator = 0.0
            used: list[str] = []
            unknown: list[str] = []
            excluded: list[str] = []
            requires_verification: list[str] = []
            treated_as_zero: list[str] = []
            for code, result in first_by_code.items():
                fact = self.catalogue.courses[code]
                multiplier = level_weights.get(self.academic_level(fact), 1.0)
                weight = self.average_weight(fact, basis) * multiplier
                normalised_grade = _normalise_status_token(result.grade)
                treatment = status_treatment.get(normalised_grade)
                if treatment == "exclude":
                    excluded.append(code)
                    continue
                if treatment == "requires_verification":
                    requires_verification.append(code)
                    continue
                if treatment == "zero":
                    mark = 0.0
                    treated_as_zero.append(code)
                elif result.mark is not None:
                    mark = float(result.mark)
                elif (
                    result.is_failed(self.grading_scheme)
                    and include_failed_as_zero
                ):
                    mark = 0.0
                else:
                    unknown.append(code)
                    continue
                weighted_total += mark * weight
                denominator += weight
                used.append(code)
            if denominator == 0:
                note = "No first-attempt numeric results are available for this programme average."
                return RuleEvaluation(
                    rule_id,
                    label,
                    False,
                    0.0,
                    threshold,
                    note,
                    "unverified",
                    0.0,
                    blocking,
                    assumptions=[note],
                    source=source,
                )
            average = weighted_total / denominator
            eval_status = status
            assumptions: list[str] = []
            if unknown:
                eval_status = _combine_status([eval_status, "unverified"])
                assumptions.append(
                    "First-attempt numeric marks are missing for: "
                    + ", ".join(sorted(unknown))
                )
            if requires_verification:
                eval_status = _combine_status([eval_status, "unverified"])
                assumptions.append(
                    "Configured first-attempt status treatment requires verification for: "
                    + ", ".join(sorted(requires_verification))
                )
            if treated_as_zero:
                assumptions.append(
                    "Configured first-attempt status treatment counted as zero: "
                    + ", ".join(sorted(treated_as_zero))
                    + "."
                )
            if excluded:
                assumptions.append(
                    "Configured first-attempt status treatment excluded: "
                    + ", ".join(sorted(excluded))
                    + "."
                )
            detail = (
                f"First-attempt programme average is {average:.2f}%; "
                f"at least {threshold:g}% is required."
            )
            if treated_as_zero:
                detail += (
                    " Configured status treatment counted "
                    + ", ".join(sorted(treated_as_zero))
                    + " as zero."
                )
            if excluded:
                detail += (
                    " Configured status treatment excluded "
                    + ", ".join(sorted(excluded))
                    + "."
                )
            if requires_verification:
                detail += (
                    " Configured status treatment requires verification for "
                    + ", ".join(sorted(requires_verification))
                    + "."
                )
            return RuleEvaluation(
                rule_id,
                label,
                average >= threshold,
                average,
                threshold,
                detail,
                eval_status,
                1.0 if eval_status == "verified" else 0.0,
                blocking,
                sorted(used),
                assumptions=assumptions,
                source=source,
            )

        if rule_type == "weighted_average":
            filters = (
                rule.get("filters", {})
                if isinstance(rule.get("filters", {}), dict)
                else {}
            )
            explicit = set(_normalise_codes(rule.get("course_codes", [])))
            threshold = float(rule.get("minimum_average", rule.get("required", 0)))
            basis = _weighting_basis(rule)
            matched_codes = sorted(
                code
                for code, fact in self.fact_by_code.items()
                if (not explicit or code in explicit)
                and _fact_matches_filters(
                    code, fact, filters, self.credit_framework, self.course_code_scheme
                )
            )
            marked = [
                (
                    self.result_by_code[code],
                    self.average_weight(self.fact_by_code[code], basis),
                )
                for code in matched_codes
                if self.result_by_code[code].mark is not None
            ]
            missing_marks = [
                code for code in matched_codes if self.result_by_code[code].mark is None
            ]
            provisional_codes: list[str] = []
            # A cumulative degree average includes approved open/free electives.
            # Transcript-only electives are included provisionally only for an
            # unfiltered average; a filtered award rule must name its own pool.
            if not explicit and not filters:
                for result in self.provisional_results:
                    provisional_codes.append(result.code)
                    if result.mark is None:
                        missing_marks.append(result.code)
                    else:
                        marked.append((result, self.average_weight(result, basis)))
            if not marked:
                note = "No numeric marks are available for the courses in this average."
                return RuleEvaluation(
                    rule_id,
                    label,
                    False,
                    0.0,
                    threshold,
                    note,
                    "unverified",
                    0.0,
                    blocking,
                    used_course_codes=matched_codes + provisional_codes,
                    assumptions=[note],
                    source=source,
                )
            denominator = sum(weight for _, weight in marked)
            average = (
                sum(result.mark * weight for result, weight in marked) / denominator
            )
            evaluation_status = status
            assumptions: list[str] = []
            confidence = 1.0 if status == "verified" else 0.7
            if provisional_codes:
                evaluation_status = _combine_status([status, "unverified"])
                confidence = min(confidence, 0.35)
                assumptions.append(
                    "The average includes transcript-only elective credits whose programme approval is not verified: "
                    + ", ".join(sorted(provisional_codes))
                )
            if missing_marks:
                evaluation_status = _combine_status([evaluation_status, "unverified"])
                confidence = 0.0
                assumptions.append(
                    "Some passed courses have no numeric mark and were excluded: "
                    + ", ".join(sorted(set(missing_marks)))
                )
            return RuleEvaluation(
                rule_id,
                label,
                average >= threshold,
                average,
                threshold,
                f"Credit-weighted average is {average:.2f}%; at least {threshold:g}% is required.",
                evaluation_status,
                confidence,
                blocking,
                sorted(set(matched_codes + provisional_codes)),
                assumptions=assumptions,
                source=source,
            )

        if rule_type == "passed_mark_count":
            filters = (
                rule.get("filters", {})
                if isinstance(rule.get("filters", {}), dict)
                else {}
            )
            explicit = set(_normalise_codes(rule.get("course_codes", [])))
            excluded = set(_normalise_codes(rule.get("exclude_course_codes", [])))
            threshold = float(rule.get("minimum_mark", 75))
            required = int(rule.get("required", 1))
            matched: list[str] = []
            unknown: list[str] = []
            for code, result in self.result_by_code.items():
                fact = self.fact_by_code[code]
                if (
                    code in excluded
                    or (explicit and code not in explicit)
                    or not _fact_matches_filters(
                        code, fact, filters, self.credit_framework, self.course_code_scheme
                    )
                ):
                    continue
                if result.mark is None:
                    unknown.append(code)
                elif result.mark >= threshold:
                    matched.append(code)
            eval_status = (
                status if not unknown else _combine_status([status, "unverified"])
            )
            assumptions = (
                ["Numeric marks are missing for: " + ", ".join(sorted(unknown))]
                if unknown
                else []
            )
            return RuleEvaluation(
                rule_id,
                label,
                len(matched) >= required,
                float(len(matched)),
                float(required),
                f"{len(matched)} of {required} passed courses have marks of at least {threshold:g}%.",
                eval_status,
                1.0 if not unknown else 0.0,
                blocking,
                sorted(matched),
                assumptions=assumptions,
                source=source,
            )

        if rule_type == "course_count":
            filters = (
                rule.get("filters", {})
                if isinstance(rule.get("filters", {}), dict)
                else {}
            )
            required = int(rule.get("required", 0))
            matched = sorted(
                code
                for code, fact in self.fact_by_code.items()
                if _fact_matches_filters(
                    code, fact, filters, self.credit_framework, self.course_code_scheme
                )
            )
            return RuleEvaluation(
                rule_id,
                label,
                len(matched) >= required,
                float(len(matched)),
                float(required),
                f"{len(matched)} of {required} matching courses completed.",
                status,
                1.0 if status == "verified" else 0.7,
                blocking,
                matched,
                source=source,
            )

        if rule_type in {"all_of", "any_of"}:
            children = [
                self.evaluate(child)
                for child in rule.get("children", [])
                if isinstance(child, dict)
            ]
            if rule_type == "all_of":
                complete = all(child.complete for child in children)
                current = sum(1 for child in children if child.complete)
                required = len(children)
                unresolved = any(not child.complete and not child.assessment_complete for child in children)
            else:
                complete = any(child.complete for child in children)
                current = 1 if complete else 0
                required = 1
                unresolved = all(not child.complete and not child.assessment_complete for child in children)
            used = sorted(
                {
                    code
                    for child in children
                    if child.complete
                    for code in child.used_course_codes
                }
            )
            statuses = [child.status for child in children if child.complete] + [status]
            if unresolved and not complete:
                statuses.extend(child.status for child in children if not child.complete)
                statuses.append("unverified")
            bound_outcome = None
            bound_complete = None
            if rule_type == "all_of" and any(not child.complete and child.assessment_complete for child in children):
                bound_outcome = "not_satisfied"
                bound_complete = not unresolved
            elif rule_type == "any_of" and complete and unresolved:
                bound_outcome = "satisfied"
                bound_complete = False
            elif rule_type == "any_of" and complete and any(not child.complete and not child.assessment_complete for child in children):
                bound_outcome = "satisfied"
                bound_complete = False
            detail = f"{current} of {required} component requirements completed."
            if not complete:
                incomplete = [child.label for child in children if not child.complete]
                if incomplete:
                    detail += (
                        " Outstanding: "
                        + "; ".join(incomplete[:8])
                        + ("…" if len(incomplete) > 8 else "")
                    )
            return RuleEvaluation(
                rule_id,
                label,
                complete,
                float(current),
                float(required),
                detail,
                _combine_status(statuses),
                min([c.confidence for c in children] or [1.0]),
                blocking,
                used,
                source=source,
                outcome_override=bound_outcome,
                assessment_complete_override=bound_complete,
            )

        note = f"Unsupported curriculum rule type {rule_type!r}; manual verification is required."
        return RuleEvaluation(
            rule_id,
            label,
            True,
            0.0,
            1.0,
            note,
            "unverified",
            0.0,
            blocking,
            assumptions=[note],
            source=source,
        )
