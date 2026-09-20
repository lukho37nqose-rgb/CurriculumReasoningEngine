"""Selected-set subject-distinction policy and existing assessment projection.

Formal qualification conferment belongs to engine.award. Major progress and
report aggregation remain caller responsibilities.
"""

from dataclasses import dataclass
from typing import Any

from curriculum_reasoning_engine.institutions import (
    AcademicCreditFramework,
    CourseLoadFramework,
    GradingScheme,
)

from .curriculum import _combine_status
from .framework_adapters import _credit_value, _load_equivalent
from .models import AuthorisedAwardCourseSelection, Catalogue, CourseResult, MajorDefinition, StudentRecord
from .utils import _course_weight


@dataclass
class SubjectDistinction:
    major: str
    average: float
    senior_courses_assessed: int
    eligible: bool = False
    status: str = "provisional"
    reason: str = ""
    major_key: str = ""
    policy_id: str = ""


def marked_result(
    code: str, *, student: StudentRecord, grading_scheme: GradingScheme | None
) -> CourseResult | None:
    result = student.passed_result_for(code, grading_scheme)
    return result if result is not None and result.mark is not None else None


def first_attempt_pass(code: str, *, student: StudentRecord, grading_scheme: GradingScheme | None) -> bool:
    attempts = [
        result for result in student.results if result.code == code and not result.is_pending(grading_scheme)
    ]
    return len(attempts) == 1 and attempts[0].is_passed(grading_scheme)


def weighted_average(
    codes: list[str], *, student: StudentRecord, grading_scheme: GradingScheme | None
) -> float:
    weighted_total = 0.0
    weight_total = 0.0
    for code in codes:
        result = marked_result(code, student=student, grading_scheme=grading_scheme)
        if result is None:
            continue
        weight = _course_weight(code)
        weighted_total += result.mark * weight
        weight_total += weight
    return weighted_total / weight_total if weight_total else 0.0


def subject_record(
    major_name: str,
    codes: list[str],
    eligible: bool,
    status: str,
    reason: str,
    *,
    student: StudentRecord,
    grading_scheme: GradingScheme | None,
    major_key: str = "",
    policy_id: str = "",
) -> SubjectDistinction:
    return SubjectDistinction(
        major=major_name,
        average=round(weighted_average(codes, student=student, grading_scheme=grading_scheme), 1),
        senior_courses_assessed=len(codes),
        eligible=eligible,
        status=status,
        reason=reason,
        major_key=major_key,
        policy_id=policy_id,
    )


def average_for_basis(
    codes: list[str],
    basis: str,
    *,
    student: StudentRecord,
    grading_scheme: GradingScheme | None,
    catalogue: Catalogue,
    credit_framework: AcademicCreditFramework | None,
    course_load_framework: CourseLoadFramework | None,
) -> float:
    weighted_total = 0.0
    weight_total = 0.0
    for code in codes:
        result = marked_result(code, student=student, grading_scheme=grading_scheme)
        fact = catalogue.courses.get(code)
        if result is None or fact is None:
            continue
        if basis == "equal":
            weight = 1.0
        elif basis == "credit_value":
            weight = float(_credit_value(fact, credit_framework))
        else:
            weight = _load_equivalent(result, course_load_framework)
        weighted_total += result.mark * weight
        weight_total += weight
    return weighted_total / weight_total if weight_total else 0.0


def standard_subject_award(
    rule: dict[str, Any],
    major_def: MajorDefinition,
    major_complete: bool,
    senior_codes: list[str],
    *,
    student: StudentRecord,
    grading_scheme: GradingScheme | None,
    catalogue: Catalogue,
    credit_framework: AcademicCreditFramework | None,
    course_load_framework: CourseLoadFramework | None,
    selections: list[AuthorisedAwardCourseSelection],
) -> SubjectDistinction:
    rule_status = str(rule.get("verification_status", rule.get("status", "verified")))
    status = _combine_status([major_def.verification_status, rule_status])
    basis = str(
        rule.get("weighting", {}).get("basis", "course_load_equivalent")
        if isinstance(rule.get("weighting", {}), dict)
        else "course_load_equivalent"
    )
    required_load = float(rule.get("required_load_equivalents", 0))
    advanced_level = int(rule.get("advanced_level", 7))
    required_advanced = float(rule.get("required_advanced_load_equivalents", 0))
    minimum_average = float(rule.get("minimum_average", 0))
    advanced_average = float(rule.get("advanced_minimum_average", 0))
    minimum_mark = float(rule.get("minimum_individual_mark", 0))
    first_attempt_only = bool(rule.get("first_attempt_only", False))
    policy_id = str(rule.get("id", ""))
    boundary = (
        rule.get("selection_boundary", {}) if isinstance(rule.get("selection_boundary", {}), dict) else {}
    )
    selection_max = float(boundary.get("maximum", required_load))
    matching_selections = [
        selection
        for selection in selections
        if selection.policy_id == policy_id
        and selection.major_key == major_def.key
        and (not selection.catalogue_version or selection.catalogue_version == catalogue.catalogue_version)
    ]
    selection_status = "verified"
    selected_codes = list(senior_codes)
    governed_major_pool = set(major_def.required_courses)
    for group in major_def.choice_groups:
        governed_major_pool.update(group.courses)
    if len(matching_selections) > 1:
        return subject_record(
            major_def.name,
            senior_codes,
            False,
            "conflict",
            "Multiple authorised course selections match this award context; manual reconciliation is required.",
            major_key=major_def.key,
            policy_id=policy_id,
            student=student,
            grading_scheme=grading_scheme,
        )
    if matching_selections:
        selection = matching_selections[0]
        selected_codes = [code.strip().upper() for code in selection.selected_course_codes]
        selection_status = selection.verification_status
        if len(set(selected_codes)) != len(selected_codes):
            return subject_record(
                major_def.name,
                sorted(set(selected_codes)),
                False,
                _combine_status([status, selection_status, "unverified"]),
                "Authorised selection contains duplicate course codes and cannot be used to inflate course-load totals.",
                major_key=major_def.key,
                policy_id=policy_id,
                student=student,
                grading_scheme=grading_scheme,
            )
        unknown = [code for code in selected_codes if code not in catalogue.courses]
        if unknown:
            return subject_record(
                major_def.name,
                selected_codes,
                False,
                _combine_status([status, selection_status, "unverified"]),
                "Authorised selection includes unknown course(s): " + ", ".join(sorted(unknown)) + ".",
                major_key=major_def.key,
                policy_id=policy_id,
                student=student,
                grading_scheme=grading_scheme,
            )
        selected_outside_pool = [code for code in selected_codes if code not in governed_major_pool]
        if selected_outside_pool:
            return subject_record(
                major_def.name,
                selected_codes,
                False,
                _combine_status([status, selection_status, "unverified"]),
                "Authorised selection includes course(s) outside the governed major pool: "
                + ", ".join(sorted(selected_outside_pool))
                + ".",
                major_key=major_def.key,
                policy_id=policy_id,
                student=student,
                grading_scheme=grading_scheme,
            )
        non_senior = [
            code
            for code in selected_codes
            if not (
                credit_framework.is_senior_level(catalogue.courses[code])
                if credit_framework is not None
                else catalogue.courses[code].nqf_level >= 6
            )
        ]
        if non_senior:
            return subject_record(
                major_def.name,
                selected_codes,
                False,
                _combine_status([status, selection_status, "unverified"]),
                "Authorised selection includes non-senior course(s): " + ", ".join(sorted(non_senior)) + ".",
                major_key=major_def.key,
                policy_id=policy_id,
                student=student,
                grading_scheme=grading_scheme,
            )
        status = _combine_status([status, selection_status])
    senior_load = sum(
        _load_equivalent(catalogue.courses[code], course_load_framework)
        for code in selected_codes
        if code in catalogue.courses
    )
    advanced_codes = [
        code
        for code in selected_codes
        if (
            credit_framework.is_level(catalogue.courses[code], advanced_level)
            if credit_framework is not None
            else catalogue.courses[code].nqf_level == advanced_level
        )
    ]
    advanced_load = sum(
        _load_equivalent(catalogue.courses[code], course_load_framework)
        for code in advanced_codes
        if code in catalogue.courses
    )
    marked = [marked_result(code, student=student, grading_scheme=grading_scheme) for code in selected_codes]
    marks = [result.mark for result in marked if result is not None and result.mark is not None]
    first_attempt = (not first_attempt_only) or all(
        first_attempt_pass(code, student=student, grading_scheme=grading_scheme) for code in senior_codes
    )
    if senior_load > selection_max and not matching_selections:
        boundary_status = str(boundary.get("status", "discretionary"))
        return subject_record(
            major_def.name,
            selected_codes,
            False,
            _combine_status([status, boundary_status]),
            str(
                boundary.get(
                    "message",
                    "Authorised selection is required before this award can be verified.",
                )
            ),
            major_key=major_def.key,
            policy_id=policy_id,
            student=student,
            grading_scheme=grading_scheme,
        )

    complete = (
        major_complete
        and senior_load >= required_load
        and advanced_load >= required_advanced
        and len(marks) == len(selected_codes)
        and bool(marks)
        and min(marks) >= minimum_mark
        and average_for_basis(
            selected_codes,
            basis,
            student=student,
            grading_scheme=grading_scheme,
            catalogue=catalogue,
            credit_framework=credit_framework,
            course_load_framework=course_load_framework,
        )
        >= minimum_average
        and average_for_basis(
            advanced_codes,
            basis,
            student=student,
            grading_scheme=grading_scheme,
            catalogue=catalogue,
            credit_framework=credit_framework,
            course_load_framework=course_load_framework,
        )
        >= advanced_average
        and first_attempt
    )
    reason = (
        f"{rule.get('source', {}).get('rule', rule.get('id', 'Subject award'))} "
        f"requires {required_load:g} senior load equivalents including "
        f"{required_advanced:g} at the advanced level, an overall average of "
        f"at least {minimum_average:g}%, an advanced-level average of at least "
        f"{advanced_average:g}%, no mark below {minimum_mark:g}%, and "
        "first-attempt passes."
    )
    return subject_record(
        major_def.name,
        selected_codes,
        complete and status == "verified",
        status,
        reason,
        major_key=major_def.key,
        policy_id=policy_id,
        student=student,
        grading_scheme=grading_scheme,
    )
