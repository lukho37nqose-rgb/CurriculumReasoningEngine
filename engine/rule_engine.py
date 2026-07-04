"""
Rule Engine — the core of CurriculumAdvisor.

"Store facts, compute views."

This module takes raw facts (StudentRecord + Catalogue) and computes
everything: graduation eligibility, major progress, eligible courses,
exclusion risk, distinction eligibility, and warnings.

No conclusions are stored in the JSON. Everything is derived here.
"""

from dataclasses import dataclass, field
import re
from typing import Optional
from .models import StudentRecord, Catalogue, MajorDefinition, CourseFact, CourseResult
from .reasoning import (
    Evidence,
    build_major_completion_graph,
    build_total_nqf_credits_graph,
    ReasoningGraph,
    build_credit_reasoning_graph,
)
from .utils import (
    _course_weight,
    _is_senior,
    _is_humanities,
    _normalise_major_keys,
    _infer_programme_key,
)
from .recognition import recognised_credited_pairs, provisional_open_credit_results
from .curriculum import CurriculumEvaluator, collect_curriculum_course_codes

# ---------------------------------------------------------------------------
# Output types — these are the "views" computed from facts
# ---------------------------------------------------------------------------


@dataclass
class Requirement:
    id: str
    label: str
    complete: bool
    current: float
    required: float
    detail: str = ""
    evidence: list[Evidence] = field(default_factory=list)
    applied_rules: list[str] = field(default_factory=list)
    explanation: str = ""
    status: str = "verified"
    confidence: float = 1.0
    assumptions: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    blocking: bool = True


@dataclass
class MajorProgress:
    key: str
    name: str
    complete: bool
    completed_requirements: list[str]
    outstanding_requirements: list[str]
    status: str = "verified"
    confidence: float = 1.0
    used_course_codes: list[str] = field(default_factory=list)


@dataclass
class EligibleCourse:
    code: str
    name: str
    credits: int
    department: str
    offered: list[str]
    is_major_requirement: bool = False
    major_key: Optional[str] = None
    major_name: Optional[str] = None
    reason: str = ""
    status: str = "provisional"
    confidence: float = 0.75
    limitations: list[str] = field(default_factory=list)


@dataclass
class ExclusionRisk:
    at_risk: bool
    reasons: list[str]
    assessed: bool = True
    status: str = "provisional"
    confidence: float = 0.6
    basis: str = ""


@dataclass
class SubjectDistinction:
    major: str
    average: float
    senior_courses_assessed: int
    eligible: bool = False
    status: str = "provisional"
    reason: str = ""


@dataclass
class Distinction:
    qualification_eligible: bool
    provisional: bool
    subjects: list[SubjectDistinction]
    status: str = "provisional"
    confidence: float = 0.5
    reason: str = ""


@dataclass
class Report:
    """The complete computed view for a student. Matches the app_2.py DEMO contract."""

    graduation_eligible: bool
    credits_completed: int
    level_7_credits: int
    semester_course_equivalents: float
    requirements: list[Requirement]
    majors: list[MajorProgress]
    eligible_courses: list[EligibleCourse]
    exclusion_risk: ExclusionRisk
    distinction: Distinction
    warnings: list[str]
    failed_attempts: dict[str, int]  # code -> number of failures
    student_name: str = ""  # for display in the UI
    graduation_status: str = "not_eligible"
    verification_messages: list[str] = field(default_factory=list)
    faculty_key: str = ""
    programme_key: str = ""
    programme_name: str = ""
    pathway_key: str = ""
    pathway_name: str = ""
    scope_status: str = "unscoped"


# ---------------------------------------------------------------------------
# Major progress computation
# ---------------------------------------------------------------------------


def _compute_major_progress(
    major_def: MajorDefinition,
    student: StudentRecord,
    base_graph: Optional[ReasoningGraph] = None,
    catalogue: Catalogue | None = None,
) -> MajorProgress:
    completed_reqs: list[str] = []
    outstanding_reqs: list[str] = []
    used_codes: list[str] = []

    if major_def.curriculum_rules and catalogue is not None:
        evaluator = CurriculumEvaluator(student, catalogue)
        evaluations = evaluator.evaluate_many(major_def.curriculum_rules)
        for row in evaluations:
            target = completed_reqs if row.complete else outstanding_reqs
            target.append(f"{row.label}: {row.detail}")
            used_codes.extend(row.used_course_codes)
        blocking = [row for row in evaluations if row.blocking]
        complete = bool(blocking) and all(row.complete for row in blocking)
        statuses = [row.status for row in blocking]
        if major_def.verification_status != "verified":
            status = "unverified"
        elif any(value == "conflict" for value in statuses):
            status = "conflict"
        elif any(
            value in {"unverified", "discretionary", "provisional"}
            for value in statuses
        ):
            status = "unverified"
        else:
            status = "verified"
        if major_def.admission_limited:
            status = "unverified"
            outstanding_reqs.append(
                major_def.admission_note
                or "Formal admission to this major must be confirmed."
            )
        return MajorProgress(
            key=major_def.key,
            name=major_def.name,
            complete=complete,
            completed_requirements=completed_reqs,
            outstanding_requirements=outstanding_reqs,
            status=status,
            confidence=1.0 if status == "verified" else 0.45,
            used_course_codes=sorted(set(used_codes)),
        )

    if not major_def.required_courses and not major_def.choice_groups:
        return MajorProgress(
            key=major_def.key,
            name=major_def.name,
            complete=False,
            completed_requirements=[],
            outstanding_requirements=[
                "Requirements are not representable in the current catalogue; manual verification is required."
            ],
            status="unverified",
            confidence=0.0,
            used_course_codes=[],
        )

    graph = build_major_completion_graph(student, major_def, base_graph)
    passed = student.passed_codes()
    for code in major_def.required_courses:
        requirement = graph.conclusions[f"major_required_course:{major_def.key}:{code}"]
        if requirement.result:
            completed_reqs.append(f"Pass {code}")
            used_codes.append(code)
        else:
            outstanding_reqs.append(f"Pass {code}")

    for index, group in enumerate(major_def.choice_groups):
        requirement = graph.conclusions[f"major_choice_group:{major_def.key}:{index}"]
        selected = [code for code in group.courses if code in passed][: group.required]
        used_codes.extend(selected)
        satisfied = int(requirement.current)
        if requirement.result:
            completed_reqs.append(f"{group.label}: {satisfied}/{group.required}")
        else:
            outstanding_reqs.append(
                f"{group.label}: {satisfied}/{group.required} - need {group.required - satisfied} more from {group.courses}"
            )

    complete = bool(graph.conclusions[f"major_complete:{major_def.key}"].result)
    status = "verified" if major_def.verification_status == "verified" else "unverified"
    if status != "verified":
        outstanding_reqs.extend(
            major_def.verification_notes
            or [
                "This major has conditional pathways that require handbook or advisor verification."
            ]
        )
    return MajorProgress(
        key=major_def.key,
        name=major_def.name,
        complete=complete,
        completed_requirements=completed_reqs,
        outstanding_requirements=outstanding_reqs,
        status=status,
        confidence=1.0 if status == "verified" else 0.45,
        used_course_codes=used_codes,
    )


# ---------------------------------------------------------------------------
# Eligible courses computation (prerequisites met, not yet passed)
# ---------------------------------------------------------------------------


def _prerequisite_satisfied(prerequisite: str, passed: set[str]) -> bool:
    """Match exact codes and handbook prerequisite stems such as ECO1010.

    Handbook text often omits the semester suffix, while transcript codes use
    forms such as ECO1010F or ECO1010S.  A suffixed prerequisite remains an
    exact requirement; an unsuffixed four-digit stem may match any variant.
    """
    prerequisite = prerequisite.strip().upper()
    if prerequisite in passed:
        return True
    match = re.fullmatch(r"([A-Z]{2,4}\d{4})([A-Z]{0,2})", prerequisite)
    if not match or match.group(2):
        return False
    stem = match.group(1)
    return any(code.startswith(stem) for code in passed)


def _prereqs_met(course: CourseFact, passed: set[str]) -> bool:
    if not course.prerequisites_verified:
        return False
    return all(_prerequisite_satisfied(p, passed) for p in course.prerequisites)


def _curriculum_option_labels(rules: list[dict]) -> dict[str, str]:
    labels: dict[str, str] = {}

    def walk(rule: dict, optional_context: bool = False) -> None:
        rule_type = str(rule.get("type", "")).strip().lower()
        optional_here = optional_context or rule_type in {
            "choose_n",
            "credit_pool",
            "approved_credit_pool",
            "same_department_credit_pool",
            "maximum_credit_pool",
            "any_of",
        }
        if optional_here:
            label = str(rule.get("label", "Programme option"))
            for code in collect_curriculum_course_codes([rule]):
                labels.setdefault(code, label)
        for child in rule.get("children", []):
            if isinstance(child, dict):
                walk(child, optional_here)

    for rule in rules:
        if isinstance(rule, dict):
            walk(rule)
    return labels


def _compute_eligible_courses(
    student: StudentRecord,
    catalogue: Catalogue,
) -> list[EligibleCourse]:
    passed = student.passed_codes()
    major_keys = _normalise_major_keys(student.declared_majors, catalogue)

    major_defs = []
    for m_key in major_keys:
        m_def = catalogue.majors.get(m_key)
        if m_def:
            major_defs.append((m_key, m_def))

    major_course_codes = {
        code
        for _, major_def in major_defs
        for code in (
            list(major_def.required_courses)
            + [course for group in major_def.choice_groups for course in group.courses]
            + list(
                collect_curriculum_course_codes(major_def.curriculum_rules, catalogue)
            )
            + [
                course
                for stage_rules in major_def.stage_rules.values()
                for course in collect_curriculum_course_codes(stage_rules, catalogue)
            ]
        )
    }
    major_option_labels: dict[tuple[str, str], str] = {}
    for m_key, m_def in major_defs:
        labels = _curriculum_option_labels(m_def.curriculum_rules)
        for stage_rules in m_def.stage_rules.values():
            labels.update(_curriculum_option_labels(stage_rules))
        for code, label in labels.items():
            major_option_labels[(m_key, code)] = label
    programme = catalogue.programmes.get(
        student.programme_key or _infer_programme_key(student.programme)
    )
    programme_required_codes = set(programme.required_courses) if programme else set()
    programme_support_codes = (
        set(programme.support_course_codes) if programme else set()
    )
    option_labels: dict[str, str] = {}
    if programme:
        programme_rule_codes = collect_curriculum_course_codes(
            programme.curriculum_rules, catalogue
        )
        programme_required_codes.update(programme_rule_codes)
        option_labels.update(_curriculum_option_labels(programme.curriculum_rules))
        pathway = programme.pathways.get(student.pathway_key or catalogue.pathway_key)
        if pathway:
            programme_required_codes.update(pathway.required_courses)
            programme_required_codes.update(
                collect_curriculum_course_codes(pathway.curriculum_rules, catalogue)
            )
            option_labels.update(_curriculum_option_labels(pathway.curriculum_rules))
            programme_support_codes.update(pathway.support_course_codes)
    explicitly_allowed_codes = (
        major_course_codes
        | programme_required_codes
        | programme_support_codes
        | set(catalogue.elective_course_codes)
    )
    highest_observed_level = max(
        (r.nqf_level for r in student.results if r.nqf_level > 0),
        default=7,
    )
    max_elective_level = max(7, highest_observed_level)

    # Augmenting course facts are stored separately from their regular
    # co-requisite.  This reverse map lets the engine recommend them only when
    # the linked subject course belongs to the student's selected route.
    augmenting_parents: dict[str, list[str]] = {}
    for parent_code, parent in catalogue.courses.items():
        if parent.augmenting_course:
            augmenting_parents.setdefault(parent.augmenting_course, []).append(
                parent_code
            )

    eligible = []
    for code, course in catalogue.courses.items():
        if catalogue.programme_key and code not in explicitly_allowed_codes:
            continue  # outside the selected programme/major/elective boundary
        if code in passed:
            continue  # already passed
        if (course.credit_bearing and course.nqf_credits <= 0) or course.nqf_level <= 0:
            continue  # malformed catalogue fact cannot support advice

        is_major_code = code in major_course_codes
        is_programme_required = code in programme_required_codes
        is_support_course = code in programme_support_codes
        is_general_elective = course.general_elective and (
            code in catalogue.elective_course_codes or not catalogue.programme_key
        )
        if not (
            is_major_code
            or is_programme_required
            or is_support_course
            or is_general_elective
        ):
            continue
        if not course.counts_towards_general_degree and not is_programme_required:
            continue
        if not course.offering_verified or not course.offered:
            continue
        if not _prereqs_met(course, passed):
            continue  # recorded prerequisites not met or not verified
        # FB5.1 ordinarily prevents first-year non-Humanities courses unless
        # they are required by a recognised non-Humanities major.  A transcript
        # does not prove the student's registration year, so the safe default is
        # to recommend them only inside a selected major pathway.
        if (
            catalogue.faculty_key == "uct_humanities"
            and not course.counts_as_humanities
            and course.nqf_level == 5
            and not is_major_code
            and not is_programme_required
        ):
            continue

        if course.augmenting:
            parents = augmenting_parents.get(code, [])
            if not parents or not any(
                parent in major_course_codes
                or parent in catalogue.elective_course_codes
                for parent in parents
            ):
                continue

        # Do not present unrelated postgraduate courses as general electives.
        if course.nqf_level > max_elective_level and not is_major_code:
            continue
        if (
            not is_major_code
            and not is_support_course
            and course.nqf_level > 5
            and not course.prerequisites
        ):
            # An advanced course with no recorded prerequisites may genuinely
            # be open, but it may equally reflect incomplete extraction.
            continue

        is_major = False
        major_key = None
        major_name = None
        reason = "Recorded prerequisites are met"
        status = "provisional"
        confidence = 0.75

        for m_key, m_def in major_defs:
            curriculum_codes = collect_curriculum_course_codes(
                m_def.curriculum_rules, catalogue
            )
            if code in curriculum_codes:
                is_major = True
                major_key = m_key
                major_name = m_def.name
                option_label = major_option_labels.get((m_key, code))
                reason = (
                    f"Option for {option_label} ({m_def.name} major)"
                    if option_label
                    else f"Required for {m_def.name} major"
                )
                status = (
                    "verified"
                    if (
                        m_def.verification_status == "verified"
                        and course.verification_status == "verified"
                    )
                    else "provisional"
                )
                if m_def.admission_limited and course.nqf_level >= 6:
                    status = "discretionary"
                    reason += (
                        "; formal admission to the limited major must be confirmed"
                    )
                confidence = 0.9 if status == "verified" else 0.5
                break
            if code in m_def.required_courses:
                is_major = True
                major_key = m_key
                major_name = m_def.name
                reason = f"Required for {m_def.name} major"
                status = (
                    "verified"
                    if (
                        m_def.verification_status == "verified"
                        and course.verification_status == "verified"
                    )
                    else "provisional"
                )
                confidence = 0.95 if status == "verified" else 0.7
                break
            for group in m_def.choice_groups:
                if code in group.courses:
                    is_major = True
                    major_key = m_key
                    major_name = m_def.name
                    reason = (
                        f"{group.label} ({m_def.name} major), pick {group.required}"
                    )
                    status = (
                        "verified"
                        if (
                            m_def.verification_status == "verified"
                            and course.verification_status == "verified"
                        )
                        else "provisional"
                    )
                    confidence = 0.9 if status == "verified" else 0.7
                    break
            if is_major:
                break

        if not is_major and is_programme_required:
            if code in option_labels:
                reason = f"Option for {option_labels[code]}"
                status = (
                    "verified"
                    if course.verification_status == "verified"
                    else "provisional"
                )
                confidence = 0.9 if status == "verified" else 0.65
            else:
                reason = (
                    f"Compulsory for {programme.name}"
                    if programme
                    else "Compulsory programme course"
                )
                status, confidence = "verified", 0.95
        elif not is_major and is_support_course:
            if course.augmenting:
                parents = augmenting_parents.get(code, [])
                reason = (
                    "Extended-programme augmenting course; take concurrently with "
                    + ", ".join(parents)
                )
            else:
                reason = "One of the additional introductory courses for the extended programme"
            status, confidence = "verified", 0.9
        elif not is_major and is_general_elective:
            reason = (
                "Recognised general-degree elective; recorded prerequisites are met"
            )
            status = (
                "verified"
                if course.verification_status == "verified"
                else "provisional"
            )
            confidence = 0.9 if status == "verified" else 0.6

        eligible.append(
            EligibleCourse(
                code=code,
                name=course.name,
                credits=course.nqf_credits,
                department=course.department,
                offered=course.offered,
                is_major_requirement=is_major,
                major_key=major_key,
                major_name=major_name,
                reason=reason,
                status=status,
                confidence=confidence,
                limitations=[
                    "This checks only prerequisites recorded in the catalogue.",
                    *(
                        [
                            "Co-requisite course(s) must be taken with this course: "
                            + ", ".join(course.co_requisites)
                        ]
                        if course.co_requisites
                        else []
                    ),
                    *([course.recognition_note] if course.recognition_note else []),
                    "Timetable clashes, class limits, concessions, and faculty approval are not verified.",
                ],
            )
        )

    eligible.sort(
        key=lambda c: (
            not c.is_major_requirement,
            c.status != "verified",
            not _is_senior(c.code),
            c.code,
        )
    )
    return eligible


# ---------------------------------------------------------------------------
# Exclusion risk
# ---------------------------------------------------------------------------


def _compute_exclusion_risk(
    student: StudentRecord,
    catalogue: Catalogue,
    programme_key: str,
) -> ExclusionRisk:
    """Evaluate faculty-specific progression/readmission indicators.

    The result is an indicator rather than a prediction of a Faculty
    Examinations Committee or Senate decision.  Annual-credit rules require
    either academic-year labels parsed from the transcript or an explicitly
    supplied registration-year context; missing temporal evidence is surfaced
    as unverified rather than silently inferred.
    """
    prog = catalogue.programmes.get(programme_key)
    if not prog:
        return ExclusionRisk(
            at_risk=False,
            reasons=[
                "No verified readmission threshold table is available because no programme rules were identified."
            ],
            assessed=False,
            status="unverified",
            confidence=0.0,
            basis="Programme-specific progression rules are missing.",
        )

    recognised, _ = recognised_credited_pairs(student, catalogue)
    provisional_progression = provisional_open_credit_results(student, catalogue)
    provisional_by_code = {result.code: result for result in provisional_progression}
    cumulative_credits = sum(fact.nqf_credits for _, fact in recognised) + sum(
        result.nqf_credits for result in provisional_progression
    )
    passed_by_year: dict[int, int] = {}
    attempted_by_year: dict[int, int] = {}
    for result in student.results:
        if result.academic_year is None:
            continue
        fact = catalogue.courses.get(result.code)
        if fact is not None:
            credits = fact.nqf_credits
        elif result.code in provisional_by_code:
            credits = result.nqf_credits
        else:
            continue
        if not result.is_pending():
            attempted_by_year[result.academic_year] = (
                attempted_by_year.get(result.academic_year, 0) + credits
            )
        if result.is_passed():
            passed_by_year[result.academic_year] = (
                passed_by_year.get(result.academic_year, 0) + credits
            )

    active_progression_rules = list(prog.progression_rules)
    active_pathway = prog.pathways.get(student.pathway_key or catalogue.pathway_key)
    if active_pathway:
        active_progression_rules.extend(active_pathway.progression_rules)

    if active_progression_rules:
        reasons: list[str] = []
        unknown: list[str] = []
        notes: list[str] = []
        years = student.years_registered
        latest_year = max(attempted_by_year or passed_by_year, default=None)
        annual_passed = (
            passed_by_year.get(latest_year, 0) if latest_year is not None else None
        )
        annual_attempted = (
            attempted_by_year.get(latest_year, 0) if latest_year is not None else None
        )
        science_credits = sum(
            fact.nqf_credits for _, fact in recognised if fact.counts_as_science
        )
        senior_credits = sum(
            fact.nqf_credits for _, fact in recognised if fact.nqf_level >= 6
        )
        course_equivalents = sum(
            _course_weight(result.code)
            for result, fact in recognised
            if fact.counts_towards_general_degree
        )
        senior_course_equivalents = sum(
            _course_weight(result.code)
            for result, fact in recognised
            if fact.counts_towards_general_degree and fact.nqf_level >= 6
        )

        for raw in active_progression_rules:
            rule_type = str(raw.get("type", "")).strip().lower()
            label = str(raw.get("label", rule_type or "progression rule"))
            rule_year = raw.get("year")
            if rule_year is not None and years is not None and int(rule_year) != years:
                continue
            if rule_year is not None and years is None:
                unknown.append(f"{label}: years registered are required.")
                continue

            if rule_type == "annual_credits":
                minimum = int(raw.get("minimum", 0))
                if annual_passed is None:
                    unknown.append(
                        f"{label}: the transcript does not expose academic-year labels needed to isolate annual credits."
                    )
                elif annual_passed < minimum:
                    concession = raw.get("concession_minimum")
                    message = f"{label}: {annual_passed} annual recognised credits passed; at least {minimum} are ordinarily required."
                    if concession is not None and annual_passed >= int(concession):
                        message += f" This lies within the published concession-to-continue range (from {int(concession)} credits), but a concession is discretionary."
                    reasons.append(message)
                else:
                    notes.append(
                        f"{label}: annual recognised credits meet the {minimum}-credit threshold."
                    )

            elif rule_type == "annual_course_equivalents":
                minimum = float(raw.get("minimum", 0))
                if latest_year is None:
                    unknown.append(
                        f"{label}: academic-year labels are required to isolate annual course equivalents."
                    )
                else:
                    latest_passed: set[str] = set()
                    equivalents = 0.0
                    for result in student.results:
                        if (
                            result.academic_year != latest_year
                            or not result.is_passed()
                            or result.code in latest_passed
                        ):
                            continue
                        fact = catalogue.courses.get(result.code)
                        if fact is None or not fact.counts_towards_general_degree:
                            continue
                        latest_passed.add(result.code)
                        equivalents += _course_weight(result.code)
                    if equivalents < minimum:
                        reasons.append(
                            f"{label}: {equivalents:g} semester-course equivalent(s) passed in {latest_year}; at least {minimum:g} are ordinarily required."
                        )
                    else:
                        notes.append(
                            f"{label}: {equivalents:g} annual course equivalent(s) meet {minimum:g}."
                        )

            elif rule_type == "cumulative_failed_course_equivalents":
                threshold = float(raw.get("threshold", raw.get("minimum", 7)))
                failed_equivalents = sum(
                    _course_weight(result.code)
                    for result in student.results
                    if result.is_failed()
                )
                if failed_equivalents >= threshold:
                    reasons.append(
                        f"{label}: {failed_equivalents:g} failed semester-course equivalent attempt(s) are recorded; the published threshold is {threshold:g}."
                    )
                else:
                    notes.append(
                        f"{label}: {failed_equivalents:g} failed equivalent attempt(s) is below {threshold:g}."
                    )

            elif rule_type == "cumulative_credits":
                minimum = int(raw.get("minimum", 0))
                if cumulative_credits < minimum:
                    reasons.append(
                        f"{label}: {cumulative_credits} cumulative recognised credits; at least {minimum} are required."
                    )
                else:
                    notes.append(
                        f"{label}: cumulative recognised credits meet the {minimum}-credit threshold."
                    )

            elif rule_type == "science_cumulative_credits":
                minimum = int(raw.get("minimum", 0))
                if science_credits < minimum:
                    reasons.append(
                        f"{label}: {science_credits} recognised Science credits; at least {minimum} are required."
                    )
                else:
                    notes.append(
                        f"{label}: Science credits meet the {minimum}-credit threshold."
                    )

            elif rule_type == "senior_cumulative_credits":
                minimum = int(raw.get("minimum", 0))
                if senior_credits < minimum:
                    reasons.append(
                        f"{label}: {senior_credits} senior credits; at least {minimum} are required."
                    )
                else:
                    notes.append(
                        f"{label}: senior credits meet the {minimum}-credit threshold."
                    )

            elif rule_type == "course_equivalents_cumulative":
                minimum = float(raw.get("minimum", 0))
                if course_equivalents < minimum:
                    reasons.append(
                        f"{label}: {course_equivalents:g} full-course equivalents; at least {minimum:g} are required."
                    )
                else:
                    notes.append(f"{label}: full-course equivalents meet {minimum:g}.")

            elif rule_type == "senior_course_equivalents_cumulative":
                minimum = float(raw.get("minimum", 0))
                if senior_course_equivalents < minimum:
                    reasons.append(
                        f"{label}: {senior_course_equivalents:g} senior full-course equivalents; at least {minimum:g} are required."
                    )
                else:
                    notes.append(
                        f"{label}: senior full-course equivalents meet {minimum:g}."
                    )

            elif rule_type == "selected_major_stage_complete":
                stage = str(raw.get("stage", "year1"))
                required_count = int(
                    raw.get(
                        "required",
                        len(_normalise_major_keys(student.declared_majors, catalogue))
                        or 1,
                    )
                )
                selected = _normalise_major_keys(student.declared_majors, catalogue)
                if not selected:
                    unknown.append(f"{label}: no intended Science major was supplied.")
                else:
                    evaluator = CurriculumEvaluator(student, catalogue)
                    completed_count = 0
                    for key in selected:
                        major = catalogue.majors.get(key)
                        if major is None or stage not in major.stage_rules:
                            continue
                        rows = evaluator.evaluate_many(major.stage_rules[stage])
                        if rows and all(row.complete for row in rows if row.blocking):
                            completed_count += 1
                    if completed_count < required_count:
                        reasons.append(
                            f"{label}: {completed_count} of {required_count} selected-major stage requirement(s) completed."
                        )
                    else:
                        notes.append(
                            f"{label}: selected-major stage requirements are complete."
                        )

            elif rule_type == "qualification_expected":
                if years is None:
                    unknown.append(f"{label}: years registered are required.")
                else:
                    evaluator = CurriculumEvaluator(student, catalogue)
                    selected = _normalise_major_keys(student.declared_majors, catalogue)
                    majors_done = [
                        _compute_major_progress(
                            catalogue.majors[key], student, catalogue=catalogue
                        ).complete
                        for key in selected
                        if key in catalogue.majors
                    ]
                    if cumulative_credits < prog.total_nqf_credits or not any(
                        majors_done
                    ):
                        reasons.append(
                            f"{label}: the degree requirements are not yet complete."
                        )
                    else:
                        notes.append(
                            f"{label}: the recorded requirements appear complete."
                        )

            elif rule_type == "pass_rate":
                minimum = float(raw.get("minimum", 0))
                if annual_attempted in (None, 0):
                    unknown.append(
                        f"{label}: annual attempted credits are unavailable."
                    )
                else:
                    rate = (annual_passed or 0) / annual_attempted
                    if rate < minimum:
                        reasons.append(
                            f"{label}: {rate * 100:.1f}% of annual attempted credits passed; at least {minimum * 100:.0f}% is required."
                        )
                    else:
                        notes.append(
                            f"{label}: annual pass rate meets {minimum * 100:.0f}%."
                        )

            elif rule_type == "failed_any":
                codes = {
                    str(code).strip().upper() for code in raw.get("course_codes", [])
                }
                failed = sorted(
                    code
                    for code in codes
                    if any(r.code == code and r.is_failed() for r in student.results)
                )
                if failed:
                    reasons.append(f"{label}: failed course(s): {', '.join(failed)}.")

            elif rule_type == "repeat_failure":
                maximum = int(raw.get("maximum_failures", 1))
                counts: dict[str, int] = {}
                for result in student.results:
                    if result.is_failed():
                        counts[result.code] = counts.get(result.code, 0) + 1
                exceeded = sorted(
                    code for code, count in counts.items() if count > maximum
                )
                if exceeded:
                    reasons.append(
                        f"{label}: more than {maximum} failed attempt(s) recorded for {', '.join(exceeded)}."
                    )

            elif rule_type == "failed_course_equivalents":
                threshold = float(raw.get("threshold", raw.get("minimum", 4)))
                if latest_year is None:
                    unknown.append(
                        f"{label}: academic-year labels are required to isolate failures in the latest year."
                    )
                else:
                    failed_codes: set[str] = set()
                    failed_equivalents = 0.0
                    for result in student.results:
                        if (
                            result.academic_year != latest_year
                            or not result.is_failed()
                        ):
                            continue
                        if result.code in failed_codes:
                            continue
                        failed_codes.add(result.code)
                        failed_equivalents += _course_weight(result.code)
                    if failed_equivalents >= threshold:
                        reasons.append(
                            f"{label}: {failed_equivalents:g} half-course equivalent(s) failed in {latest_year}; "
                            f"the published risk threshold is {threshold:g}."
                        )
                    else:
                        notes.append(
                            f"{label}: {failed_equivalents:g} failed equivalent(s) is below {threshold:g}."
                        )

            elif rule_type == "failed_course_count":
                threshold = int(raw.get("threshold", raw.get("minimum", 2)))
                course_codes = {
                    str(code).strip().upper()
                    for code in raw.get("course_codes", [])
                    if str(code).strip()
                }
                if latest_year is None:
                    unknown.append(
                        f"{label}: academic-year labels are required to isolate failures in the latest year."
                    )
                else:
                    failed = {
                        result.code
                        for result in student.results
                        if result.academic_year == latest_year
                        and result.is_failed()
                        and (not course_codes or result.code in course_codes)
                    }
                    if len(failed) >= threshold:
                        reasons.append(
                            f"{label}: {len(failed)} distinct course(s) failed in {latest_year}; "
                            f"the published risk threshold is {threshold}."
                        )
                    else:
                        notes.append(
                            f"{label}: {len(failed)} failed course(s) is below {threshold}."
                        )

            elif rule_type == "failed_course_fraction":
                threshold = float(raw.get("threshold", raw.get("minimum", 0.5)))
                course_codes = {
                    str(code).strip().upper()
                    for code in raw.get("course_codes", [])
                    if str(code).strip()
                }
                if latest_year is None:
                    unknown.append(
                        f"{label}: academic-year labels are required to isolate the latest academic year."
                    )
                else:
                    latest_results: dict[str, CourseResult] = {}
                    for result in student.results:
                        if (
                            result.academic_year == latest_year
                            and not result.is_pending()
                        ):
                            if not course_codes or result.code in course_codes:
                                latest_results[result.code] = result
                    if not latest_results:
                        unknown.append(
                            f"{label}: no completed course results are labelled for {latest_year}."
                        )
                    else:
                        failed = sum(
                            1
                            for result in latest_results.values()
                            if result.is_failed()
                        )
                        fraction = failed / len(latest_results)
                        if fraction >= threshold:
                            reasons.append(
                                f"{label}: {failed} of {len(latest_results)} course(s) failed in {latest_year} "
                                f"({fraction * 100:.1f}%); the published threshold is {threshold * 100:.0f}%."
                            )
                        else:
                            notes.append(
                                f"{label}: annual failed-course proportion is {fraction * 100:.1f}%."
                            )

            elif rule_type == "failed_courses_by_group":
                groups = [
                    group for group in raw.get("groups", []) if isinstance(group, dict)
                ]
                if latest_year is None:
                    unknown.append(
                        f"{label}: academic-year labels are required to isolate the latest academic year."
                    )
                else:
                    triggered: list[str] = []
                    for group in groups:
                        group_codes = {
                            str(code).strip().upper()
                            for code in group.get("course_codes", [])
                            if str(code).strip()
                        }
                        threshold = int(group.get("threshold", 2))
                        failed = sorted(
                            {
                                result.code
                                for result in student.results
                                if result.academic_year == latest_year
                                and result.is_failed()
                                and result.code in group_codes
                            }
                        )
                        if len(failed) >= threshold:
                            triggered.append(
                                f"{group.get('label', 'course group')} ({len(failed)} failed: {', '.join(failed)})"
                            )
                    if triggered:
                        reasons.append(f"{label}: " + "; ".join(triggered) + ".")
                    else:
                        notes.append(
                            f"{label}: no published course-group failure threshold was reached."
                        )

            elif rule_type == "curriculum_stage_complete":
                rules = [
                    item for item in raw.get("rules", []) if isinstance(item, dict)
                ]
                if not rules:
                    unknown.append(f"{label}: no stage rules were supplied.")
                else:
                    evaluations = CurriculumEvaluator(student, catalogue).evaluate_many(
                        rules
                    )
                    blocking_rows = [row for row in evaluations if row.blocking]
                    incomplete = [
                        row.label for row in blocking_rows if not row.complete
                    ]
                    unresolved = [
                        row.label for row in blocking_rows if row.status != "verified"
                    ]
                    if incomplete:
                        reasons.append(
                            f"{label}: outstanding: "
                            + "; ".join(incomplete[:8])
                            + ("…" if len(incomplete) > 8 else "")
                            + "."
                        )
                    elif unresolved:
                        unknown.append(
                            f"{label}: completion depends on unresolved rule(s): "
                            + ", ".join(unresolved[:8])
                            + "."
                        )
                    else:
                        notes.append(
                            f"{label}: the supplied stage requirements are complete."
                        )

            elif rule_type == "repeat_year_failure":
                if latest_year is None:
                    unknown.append(
                        f"{label}: academic-year labels are required to identify a repeat year."
                    )
                else:
                    earlier_codes = {
                        result.code
                        for result in student.results
                        if result.academic_year is not None
                        and result.academic_year < latest_year
                        and not result.is_pending()
                    }
                    repeated_in_latest = {
                        result.code
                        for result in student.results
                        if result.academic_year == latest_year
                        and result.code in earlier_codes
                        and not result.is_pending()
                    }
                    failed_latest = sorted(
                        {
                            result.code
                            for result in student.results
                            if result.academic_year == latest_year
                            and result.is_failed()
                        }
                    )
                    if repeated_in_latest and failed_latest:
                        reasons.append(
                            f"{label}: the latest year includes repeated course(s) ({', '.join(sorted(repeated_in_latest))}) "
                            f"and failed course(s) ({', '.join(failed_latest)})."
                        )
                    else:
                        notes.append(
                            f"{label}: no repeat-year failure pattern is evident from the labelled results."
                        )

            elif rule_type == "maximum_years":
                maximum = int(raw.get("maximum", prog.maximum_registration_years or 0))
                if years is None:
                    unknown.append(f"{label}: years registered are required.")
                elif maximum and years > maximum:
                    reasons.append(
                        f"{label}: {years} years registered exceeds the ordinary {maximum}-year limit."
                    )
                else:
                    notes.append(
                        f"{label}: supplied registration period is within {maximum} years."
                    )

            elif rule_type == "manual":
                unknown.append(
                    str(raw.get("note", label + " requires Faculty confirmation."))
                )

        if provisional_progression:
            unknown.append(
                "Annual/cumulative totals include transcript-only approved/open elective credits whose programme approval is not verified: "
                + ", ".join(result.code for result in provisional_progression)
                + "."
            )
        assessed = not unknown
        status = "verified" if assessed else "unverified"
        basis_parts = []
        if years is not None:
            basis_parts.append(f"{years} explicitly supplied year(s) of registration")
        if latest_year is not None:
            basis_parts.append(f"academic-year-labelled results through {latest_year}")
        if notes:
            basis_parts.extend(notes[:3])
        if unknown:
            basis_parts.append("Unresolved: " + " ".join(unknown[:4]))
        return ExclusionRisk(
            at_risk=bool(reasons),
            reasons=reasons,
            assessed=assessed,
            status=status,
            confidence=0.95 if assessed else 0.35,
            basis="; ".join(basis_parts)
            or "Insufficient temporal evidence for the published progression rules.",
        )

    # Compatibility path for the general Humanities course-equivalent tables.
    if not prog.readmission_thresholds:
        return ExclusionRisk(
            at_risk=False,
            reasons=[
                "No verified readmission threshold table is available for this programme."
            ],
            assessed=False,
            status="unverified",
            confidence=0.0,
            basis="Programme-specific readmission rules are missing.",
        )

    credited = [
        (result, fact)
        for result, fact in recognised
        if fact.counts_towards_course_equivalents
    ]
    passed_count = sum(_course_weight(result.code) for result, _ in credited)
    senior_passed = sum(
        _course_weight(result.code) for result, fact in credited if fact.nqf_level >= 6
    )

    if student.years_registered is not None and student.years_registered > 0:
        year = student.years_registered
        status, confidence = "verified", 0.95
        basis = f"Assessed using {year} explicitly supplied year(s) of registration."
    else:
        attempted = len(student.attempted_codes())
        year = max(1, min(5, (attempted + 7) // 8))
        status, confidence = "provisional", 0.55
        basis = (
            f"Estimated year {year} from {attempted} distinct attempted courses; "
            "the transcript does not prove years of registration."
        )

    applicable = [t for t in prog.readmission_thresholds if t.year <= year]
    threshold = max(applicable, key=lambda t: t.year) if applicable else None
    if threshold is None:
        return ExclusionRisk(
            False, [], False, "unverified", 0.0, "No threshold applies."
        )

    reasons: list[str] = []
    if passed_count < threshold.minimum_passed_courses:
        reasons.append(
            f"By the end of year {threshold.year}, the handbook requires at least "
            f"{threshold.minimum_passed_courses} semester-course equivalents passed; "
            f"the record shows {passed_count:.1f}."
        )
    if senior_passed < threshold.minimum_senior_courses:
        reasons.append(
            f"By the end of year {threshold.year}, the handbook requires at least "
            f"{threshold.minimum_senior_courses} senior semester-course equivalents; "
            f"the record shows {senior_passed:.1f}."
        )
    return ExclusionRisk(
        at_risk=bool(reasons),
        reasons=reasons,
        assessed=True,
        status=status,
        confidence=confidence,
        basis=basis,
    )


# ---------------------------------------------------------------------------
# Distinction computation
# ---------------------------------------------------------------------------


def _compute_distinction(
    student: StudentRecord,
    catalogue: Catalogue,
    major_keys: list[str],
) -> Distinction:
    """Evaluate the general BA/BSocSc distinction rules in FB1.1-FB1.4.

    Standard Humanities subjects use the four-senior-course rule in FB1.1.
    Economics, Law, Industrial and Organisational Psychology, Psychology and
    Informatics use the subject-specific tests in FB1.2. Science-major
    distinctions remain unverified until the Science handbook is loaded.
    """

    programme = catalogue.programmes.get(
        student.programme_key or catalogue.programme_key
    )

    if catalogue.faculty_key == "uct_science" or (
        programme is not None and programme.programme_type == "science_degree"
    ):
        evaluator = CurriculumEvaluator(student, catalogue)
        subjects: list[SubjectDistinction] = []
        verified_subject = False
        possible_subject = False
        for key in major_keys:
            major = catalogue.majors.get(key)
            if major is None:
                continue
            if not major.award_rules:
                subjects.append(
                    SubjectDistinction(
                        major=major.name,
                        average=0.0,
                        senior_courses_assessed=0,
                        eligible=False,
                        status="unverified",
                        reason="No machine-checkable FB8.1 distinction rule set is available for this major.",
                    )
                )
                continue
            checks = evaluator.evaluate_many(major.award_rules)
            complete = all(check.complete for check in checks if check.blocking)
            statuses = [check.status for check in checks if check.blocking]
            status = "verified"
            if any(value == "conflict" for value in statuses):
                status = "conflict"
            elif any(
                value in {"unverified", "discretionary", "provisional"}
                for value in statuses
            ):
                status = "unverified"
            used = sorted(
                {code for check in checks for code in check.used_course_codes}
            )
            marked = [student.passed_result_for(code) for code in used]
            numeric = [
                result.mark
                for result in marked
                if result is not None and result.mark is not None
            ]
            average = sum(numeric) / len(numeric) if numeric else 0.0
            reason = "; ".join(check.detail for check in checks)
            if not complete:
                reason += " A first-class pass in a cognate substitute may be approved only by the Faculty Board and is not inferred here."
            subjects.append(
                SubjectDistinction(
                    major=major.name,
                    average=round(average, 1),
                    senior_courses_assessed=len(used),
                    eligible=complete and status == "verified",
                    status=status,
                    reason=reason,
                )
            )
            possible_subject = possible_subject or complete
            verified_subject = verified_subject or (complete and status == "verified")

        recognised, _ = recognised_credited_pairs(student, catalogue)
        eligible_rows: list[tuple[CourseResult, CourseFact]] = []
        for result, fact in recognised:
            attempts = [
                r
                for r in student.results
                if r.code == result.code and not r.is_pending()
            ]
            grade = " ".join(str(result.grade or "").strip().upper().split())
            if len(attempts) == 1 and grade != "SP" and result.mark is not None:
                eligible_rows.append((result, fact))
        first_rows = [
            (result, fact) for result, fact in eligible_rows if result.mark >= 75
        ]
        first_credits = sum(fact.nqf_credits for result, fact in first_rows)
        senior_first_credits = sum(
            fact.nqf_credits for result, fact in first_rows if fact.nqf_level >= 6
        )
        direct_path = first_credits >= 264 and senior_first_credits >= 192

        alternate_groups: list[bool] = []
        for credit_value, count in ((18, 6), (24, 6), (36, 4)):
            group = sorted(
                [
                    result.mark
                    for result, fact in eligible_rows
                    if fact.nqf_credits == credit_value and result.mark is not None
                ],
                reverse=True,
            )[:count]
            alternate_groups.append(len(group) == count and sum(group) / count >= 75)
        duration_known = student.years_registered is not None
        duration_met = (
            duration_known
            and programme is not None
            and student.years_registered <= programme.minimum_duration_years
        )
        alternate_path = all(alternate_groups) and duration_met
        qualification_eligible = verified_subject and (direct_path or alternate_path)
        status = "verified"
        provisional = False
        if not subjects or any(subject.status != "verified" for subject in subjects):
            status = "unverified"
            provisional = True
        if all(alternate_groups) and not duration_known and not direct_path:
            status = "unverified"
            provisional = True
        reason = (
            f"FB8.2: {first_credits} first-class credits, including {senior_first_credits} senior credits; "
            f"direct 264/192 path {'met' if direct_path else 'not met'}. "
            f"Alternate 18/24/36-credit aggregate path {'met' if alternate_path else 'not verified or not met'}. "
            "At least one verified major distinction is also required."
        )
        return Distinction(
            qualification_eligible=qualification_eligible,
            provisional=provisional or (possible_subject and not verified_subject),
            subjects=subjects,
            status=status,
            confidence=(
                0.95 if qualification_eligible else (0.45 if provisional else 0.85)
            ),
            reason=reason,
        )

    if programme is not None and programme.programme_type != "general_degree":
        active_pathway = programme.pathways.get(
            student.pathway_key or catalogue.pathway_key
        )
        structured_award_rules = list(programme.award_rules)
        if active_pathway is not None:
            structured_award_rules.extend(active_pathway.award_rules)
        if not structured_award_rules:
            return Distinction(
                qualification_eligible=False,
                provisional=True,
                subjects=[],
                status="unverified",
                confidence=0.0,
                reason=(
                    "This structured qualification has programme-specific award rules, "
                    "but no machine-checkable award rule set has been verified."
                ),
            )

        evaluator = CurriculumEvaluator(student, catalogue)
        award_rows: list[SubjectDistinction] = []
        verified_award = False
        possible_award = False
        overall_status = "verified"
        explanations: list[str] = []
        for award in structured_award_rules:
            name = str(award.get("name", "Programme award"))
            checks = evaluator.evaluate_many(award.get("curriculum_rules", []))
            complete = all(check.complete for check in checks)
            statuses = [check.status for check in checks]
            status = "verified"
            if any(value == "conflict" for value in statuses):
                status = "conflict"
            elif any(value in {"unverified", "discretionary"} for value in statuses):
                status = "unverified"
            elif any(value == "provisional" for value in statuses):
                status = "provisional"

            min_time = award.get("complete_within_years")
            duration_detail = ""
            if min_time is not None:
                if student.years_registered is None:
                    status = "unverified"
                    duration_detail = f" Completion within {int(min_time)} years cannot be verified without years registered."
                elif student.years_registered > int(min_time):
                    complete = False
                    duration_detail = f" The record states {student.years_registered} years registered; the award requires completion within {int(min_time)}."
                else:
                    duration_detail = f" Completion time ({student.years_registered} years) meets the {int(min_time)}-year limit."

            numeric = [
                check.current for check in checks if check.required and check.current
            ]
            display_average = round(max(numeric), 1) if numeric else 0.0
            reason = "; ".join(check.detail for check in checks) + duration_detail
            award_rows.append(
                SubjectDistinction(
                    major=name,
                    average=display_average,
                    senior_courses_assessed=len(
                        {code for check in checks for code in check.used_course_codes}
                    ),
                    eligible=complete and status == "verified",
                    status=status,
                    reason=reason,
                )
            )
            possible_award = possible_award or complete
            verified_award = verified_award or (complete and status == "verified")
            explanations.append(
                f"{name}: " + ("thresholds met" if complete else "thresholds not met")
            )
            if status != "verified" and overall_status == "verified":
                overall_status = status

        return Distinction(
            qualification_eligible=verified_award,
            provisional=not verified_award
            and possible_award
            or overall_status != "verified",
            subjects=award_rows,
            status="verified" if verified_award else overall_status,
            confidence=0.95 if verified_award else (0.5 if possible_award else 0.8),
            reason="Programme-specific award assessment. " + "; ".join(explanations),
        )

    def marked_result(code: str) -> CourseResult | None:
        result = student.passed_result_for(code)
        return result if result is not None and result.mark is not None else None

    def first_attempt_pass(code: str) -> bool:
        attempts = [
            result
            for result in student.results
            if result.code == code and not result.is_pending()
        ]
        return len(attempts) == 1 and attempts[0].is_passed()

    def weighted_average(codes: list[str]) -> float:
        weighted_total = 0.0
        weight_total = 0.0
        for code in codes:
            result = marked_result(code)
            if result is None:
                continue
            weight = _course_weight(code)
            weighted_total += result.mark * weight
            weight_total += weight
        return weighted_total / weight_total if weight_total else 0.0

    def subject_record(
        major_name: str, codes: list[str], eligible: bool, status: str, reason: str
    ) -> SubjectDistinction:
        return SubjectDistinction(
            major=major_name,
            average=round(weighted_average(codes), 1),
            senior_courses_assessed=len(codes),
            eligible=eligible,
            status=status,
            reason=reason,
        )

    subjects: list[SubjectDistinction] = []
    for key in major_keys:
        major_def = catalogue.majors.get(key)
        if not major_def:
            continue
        progress = _compute_major_progress(major_def, student, catalogue=catalogue)
        used = progress.used_course_codes
        senior_codes = [
            code
            for code in used
            if (fact := catalogue.courses.get(code)) is not None and fact.nqf_level >= 6
        ]
        level7_codes = [
            code for code in senior_codes if catalogue.courses[code].nqf_level == 7
        ]

        if major_def.verification_status != "verified":
            subjects.append(
                subject_record(
                    major_def.name,
                    senior_codes,
                    False,
                    "unverified",
                    "The major pathway is provisional, so its distinction cannot be verified.",
                )
            )
            continue

        # FB1.2 subject-specific rules.
        if key == "economics":
            chosen = [code for code in level7_codes if code.startswith("ECO")]
            required = "ECO3020F" in chosen and len(chosen) >= 3
            considered = ["ECO3020F"] + [code for code in chosen if code != "ECO3020F"][
                :2
            ]
            marks = [
                marked_result(code).mark for code in considered if marked_result(code)
            ]
            eligible = (
                progress.complete
                and required
                and len(marks) == 3
                and sum(marks) / 3 >= 80
                and sum(mark >= 75 for mark in marks) >= 2
            )
            subjects.append(
                subject_record(
                    major_def.name,
                    considered,
                    eligible,
                    "verified",
                    "FB1.2 requires an 80% average across ECO3020F and two other 3000-level ECO courses, with at least two first-class passes.",
                )
            )
            continue

        if key == "informatics":
            fixed = ["INF3011F", "INF3014F", "INF2011S"]
            alternatives = [
                code for code in ("INF2010S", "INF3012S") if marked_result(code)
            ]
            considered = fixed + alternatives[:1]
            marks = [
                marked_result(code).mark for code in considered if marked_result(code)
            ]
            level7_marks = [
                marked_result(code).mark
                for code in ("INF3011F", "INF3014F")
                if marked_result(code)
            ]
            eligible = (
                len(marks) == 4
                and min(marks) >= 70
                and sum(marks) / 4 >= 75
                and len(level7_marks) == 2
                and sum(level7_marks) / 2 >= 75
            )
            subjects.append(
                subject_record(
                    major_def.name,
                    considered,
                    eligible,
                    "unverified",
                    "FB1.2 is represented, but the current Informatics major pathway itself remains provisional.",
                )
            )
            continue

        if key == "law":
            considered = [
                code for code in used if code.startswith(("PBL", "PVL", "CML"))
            ]
            marked = [code for code in considered if marked_result(code)]
            credit_total = sum(
                catalogue.courses[code].nqf_credits
                for code in marked
                if code in catalogue.courses
            )
            average = (
                sum(
                    marked_result(code).mark * catalogue.courses[code].nqf_credits
                    for code in marked
                )
                / credit_total
                if credit_total
                else 0.0
            )
            eligible = (
                progress.complete
                and len(marked) == len(considered) == 6
                and average >= 75
            )
            subjects.append(
                SubjectDistinction(
                    major=major_def.name,
                    average=round(average, 1),
                    senior_courses_assessed=len(considered),
                    eligible=eligible,
                    status="verified",
                    reason="FB1.2 requires a credit-weighted average of at least 75% across all six Law-major courses.",
                )
            )
            continue

        if key == "industrial_and_organisational_psychology":
            considered = [
                code
                for code in used
                if (fact := catalogue.courses.get(code)) is not None
                and fact.nqf_level in {6, 7}
            ]
            level6 = [
                code for code in considered if catalogue.courses[code].nqf_level == 6
            ]
            level7 = [
                code for code in considered if catalogue.courses[code].nqf_level == 7
            ]
            marks = [
                marked_result(code).mark for code in considered if marked_result(code)
            ]
            eligible = (
                progress.complete
                and len(level6) >= 2
                and len(level7) >= 2
                and len(marks) == len(considered)
                and all(mark >= 75 for mark in marks)
            )
            subjects.append(
                subject_record(
                    major_def.name,
                    considered,
                    eligible,
                    "verified",
                    "FB1.2 requires first-class passes in two 2000-level and two 3000-level courses required for the major.",
                )
            )
            continue

        if key == "psychology":
            second_options = [
                code
                for code in senior_codes
                if catalogue.courses[code].nqf_level == 6 and code != "PSY2015F"
            ]
            third_options = [code for code in level7_codes if code != "PSY3007S"]
            considered = (
                ["PSY2015F"] + second_options[:1] + ["PSY3007S"] + third_options[:1]
            )
            marks = [
                marked_result(code).mark for code in considered if marked_result(code)
            ]
            eligible = (
                progress.complete
                and len(marks) == 4
                and all(mark >= 75 for mark in marks)
            )
            subjects.append(
                subject_record(
                    major_def.name,
                    considered,
                    eligible,
                    "verified",
                    "FB1.2 requires first-class passes in PSY2015F, one other second-year Psychology course, PSY3007S and one other third-year Psychology course.",
                )
            )
            continue

        if not major_def.faculty_owned:
            subjects.append(
                subject_record(
                    major_def.name,
                    senior_codes,
                    False,
                    "unverified",
                    "The distinction rule is controlled by the major's home faculty and is not yet loaded.",
                )
            )
            continue

        # Standard FB1.1 rule.
        weights = sum(_course_weight(code) for code in senior_codes)
        level7_weights = sum(_course_weight(code) for code in level7_codes)
        marks = [
            marked_result(code).mark for code in senior_codes if marked_result(code)
        ]
        first_attempt = all(first_attempt_pass(code) for code in senior_codes)
        eligible = (
            progress.complete
            and weights >= 4
            and level7_weights >= 2
            and len(marks) == len(senior_codes)
            and bool(marks)
            and min(marks) >= 70
            and weighted_average(senior_codes) >= 75
            and weighted_average(level7_codes) >= 75
            and first_attempt
        )
        status = "verified"
        reason = (
            "FB1.1 requires a first-attempt average of at least 75% across four senior semester-course equivalents, "
            "including two at 3000 level, with no mark below 70% and a 3000-level average of at least 75%."
        )
        if weights > 4:
            status = "provisional"
            eligible = False
            reason += " More than four senior courses are available, so the Head of Department must determine which four are considered."
        subjects.append(
            subject_record(major_def.name, senior_codes, eligible, status, reason)
        )

    recognised, _ = recognised_credited_pairs(student, catalogue)
    first_class_sce = sum(
        _course_weight(result.code)
        for result, fact in recognised
        if fact.counts_towards_course_equivalents
        and result.mark is not None
        and result.mark >= 75
    )
    first_class_senior_sce = sum(
        _course_weight(result.code)
        for result, fact in recognised
        if fact.counts_towards_course_equivalents
        and fact.nqf_level >= 6
        and result.mark is not None
        and result.mark >= 75
    )
    subject_distinction = any(subject.eligible for subject in subjects)
    qualification_eligible = (
        first_class_sce >= 10 and first_class_senior_sce >= 8 and subject_distinction
    )
    unresolved = any(subject.status != "verified" for subject in subjects)
    status = "provisional" if unresolved else "verified"
    return Distinction(
        qualification_eligible=qualification_eligible,
        provisional=status != "verified",
        subjects=subjects,
        status=status,
        confidence=0.65 if unresolved else 0.95,
        reason=(
            f"FB1.4 requires at least 10 first-class semester-course equivalents, including 8 senior, "
            f"and a distinction in at least one subject. The record currently shows {first_class_sce:.1f} first-class "
            f"equivalents and {first_class_senior_sce:.1f} senior first-class equivalents."
        ),
    )


# ---------------------------------------------------------------------------
# Warnings
# ---------------------------------------------------------------------------


def _compute_warnings(
    student: StudentRecord,
    catalogue: Catalogue,
    major_keys: list[str],
) -> list[str]:
    warnings = []
    passed = student.passed_codes()

    # Warn about failed courses
    for result in student.results:
        if result.is_failed():
            recorded = (
                f"{result.mark}%"
                if result.mark is not None
                else (result.grade or "fail")
            )
            warnings.append(
                f"{result.code} ({result.name}): fail result {recorded} — "
                "this attempt counts under the faculty repetition rules."
            )

    # Warn about forbidden major combinations
    for a, b in catalogue.forbidden_combinations:
        if a in major_keys and b in major_keys:
            warnings.append(
                f"Forbidden major combination: {a} and {b} cannot be taken together."
            )

    # Warn if declared majors could not be matched.  Previously unmatched
    # names were silently dropped during normalisation, so this loop never ran.
    catalogue_keys_lower = {key.lower() for key in catalogue.majors}
    for declared_name in student.declared_majors:
        direct_key = re.sub(r"_+", "_", declared_name.lower().strip().replace(" ", "_"))
        if (
            direct_key not in catalogue_keys_lower
            and declared_name.lower().strip() not in catalogue_keys_lower
            and not _normalise_major_keys([declared_name], catalogue)
        ):
            warnings.append(
                f"Major '{declared_name}' is not in the course catalogue and could not be matched. "
                "Check spelling or contact your faculty advisor."
            )

    provisional_codes = {
        result.code for result in provisional_open_credit_results(student, catalogue)
    }
    unknown_passes = sorted(
        result.code
        for result in student.credited_results()
        if result.code not in catalogue.courses and result.code not in provisional_codes
    )
    if unknown_passes:
        warnings.append(
            "The following passed course(s) are outside the selected programme catalogue and "
            "were not counted automatically: " + ", ".join(unknown_passes) + "."
        )

    failed_attempts = _compute_failed_attempts(student)
    for code, attempts in sorted(failed_attempts.items()):
        if attempts >= 2:
            if catalogue.faculty_key == "uct_humanities":
                message = (
                    f"{code} has {attempts} recorded fail attempts. Humanities rule F5 ordinarily "
                    "prevents a third registration without Senate permission; if it is required, a "
                    "programme change or concession may be necessary."
                )
            elif catalogue.faculty_key == "uct_law":
                message = (
                    f"{code} has {attempts} recorded fail attempts. Law progression and readmission "
                    "rules FP7-FP11 require the full pattern of failed course equivalents and any "
                    "permission to carry courses to be assessed by the Faculty."
                )
            else:
                message = (
                    f"{code} has {attempts} recorded fail attempts. The selected faculty's programme-specific "
                    "progression and readmission rules may restrict further registration."
                )
            warnings.append(message)

    if catalogue.faculty_key == "uct_science":
        warnings.append(
            "Science-major acceptance is confirmed only at second-year registration; completing first-year prerequisites does not itself guarantee a place in a limited major."
        )
        for key in major_keys:
            major = catalogue.majors.get(key)
            if major is not None and major.admission_limited:
                warnings.append(
                    major.admission_note
                    or f"Admission to {major.name} must be confirmed by the relevant department."
                )

    recognised, recognition_exclusions = recognised_credited_pairs(student, catalogue)
    if recognition_exclusions:
        warnings.append(
            "Music-course recognition limit applied: "
            + "; ".join(
                f"{item.code}: {item.reason}" for item in recognition_exclusions
            )
            + " Final course allocation should be confirmed with Humanities Undergraduate Administration."
        )
    additional_codes = [
        result.code
        for result, fact in recognised
        if not fact.counts_towards_course_equivalents
    ]
    if additional_codes and catalogue.faculty_key == "uct_humanities":
        warnings.append(
            "Additional introductory/augmenting course(s) counted toward NQF credits but not toward "
            "the 20 semester subject-course requirement: "
            + ", ".join(sorted(additional_codes))
            + "."
        )

    if catalogue.data_issues:
        warnings.append(
            f"Catalogue validation found {len(catalogue.data_issues)} unresolved data issue(s). "
            "Malformed entries are excluded from positive advice; consult the handbook or faculty office for affected courses."
        )
        attempted = student.attempted_codes()
        for issue in catalogue.data_issues:
            if any(issue.startswith(code) for code in attempted):
                warnings.append(issue)

    return warnings


# ---------------------------------------------------------------------------
# Failed attempts tracking
# ---------------------------------------------------------------------------


def _compute_failed_attempts(student: StudentRecord) -> dict[str, int]:
    """Count how many times each course was failed."""
    counts: dict[str, int] = {}
    for result in student.results:
        if result.is_failed():
            counts[result.code] = counts.get(result.code, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Programme key inference
# ---------------------------------------------------------------------------

# Imported from utils


# ---------------------------------------------------------------------------
# Major key normalisation
# ---------------------------------------------------------------------------

# Imported from utils


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def _compute_credits(
    student: StudentRecord,
    catalogue: Catalogue,
) -> tuple[int, int, list[CourseResult]]:
    """Count verified catalogue credits plus explicitly permitted provisional electives.

    Catalogue values outrank transcript-extracted fields for known courses.
    Transcript-only credits are considered only where the active programme has
    an ``approved_credit_pool`` rule (for example, an open elective or a live
    complementary-studies list). Those credits remain provisional and therefore
    cannot support a fully verified graduation conclusion.
    """
    recognised, _ = recognised_credited_pairs(student, catalogue)
    provisional = provisional_open_credit_results(student, catalogue)
    credits_completed = sum(fact.nqf_credits for _, fact in recognised) + sum(
        result.nqf_credits for result in provisional
    )
    level_7_credits = sum(
        fact.nqf_credits for _, fact in recognised if fact.nqf_level == 7
    ) + sum(result.nqf_credits for result in provisional if result.nqf_level == 7)
    return credits_completed, level_7_credits, provisional


def _compute_course_equivalents(
    student: StudentRecord, catalogue: Catalogue
) -> tuple[float, float, float]:
    recognised, _ = recognised_credited_pairs(student, catalogue)
    credited = [
        (result, fact)
        for result, fact in recognised
        if fact.counts_towards_course_equivalents
    ]
    sce_total = sum(_course_weight(result.code) for result, _ in credited)
    senior_sce = sum(
        _course_weight(result.code) for result, fact in credited if fact.nqf_level >= 6
    )
    humanities_sce = sum(
        _course_weight(result.code)
        for result, fact in credited
        if fact.counts_as_humanities
    )
    return sce_total, senior_sce, humanities_sce


def _compute_all_major_progresses(
    student: StudentRecord, catalogue: Catalogue, major_keys: list[str]
) -> tuple[list[MajorProgress], int, int]:
    major_progresses = []
    base_graph = None
    for key in major_keys:
        major_def = catalogue.majors.get(key)
        if major_def:
            if base_graph is None:
                base_graph = build_credit_reasoning_graph(student)
            major_progresses.append(
                _compute_major_progress(major_def, student, base_graph, catalogue)
            )

    majors_complete = sum(1 for m in major_progresses if m.complete)
    humanities_majors_complete = sum(
        1
        for m in major_progresses
        if m.complete
        and catalogue.majors.get(m.key)
        and catalogue.majors[m.key].faculty_owned
    )
    return major_progresses, majors_complete, humanities_majors_complete


def _check_forbidden_combinations(catalogue: Catalogue, major_keys: list[str]) -> bool:
    for a, b in catalogue.forbidden_combinations:
        if a in major_keys and b in major_keys:
            return False
    return True


def _build_requirements(
    student: StudentRecord,
    catalogue: Catalogue,
    programme_key: str,
    prog,
    sce_total: float,
    senior_sce: float,
    humanities_sce: float,
    credits_completed: int,
    level_7_credits: int,
    provisional_credit_results: list[CourseResult],
    major_progresses: list[MajorProgress],
    majors_complete: int,
    humanities_majors_complete: int,
    forbidden_ok: bool,
) -> list[Requirement]:
    """Build handbook-grounded graduation requirements."""
    min_years = prog.minimum_duration_years if prog else 3
    total_nqf_credits = prog.total_nqf_credits if prog else 360
    level_7_nqf_credits = prog.level_7_nqf_credits if prog else 120
    semester_course_equivalents = prog.semester_course_equivalents if prog else 20
    senior_course_equivalents = prog.senior_course_equivalents if prog else 10
    humanities_course_equivalents = prog.humanities_course_equivalents if prog else 0
    required_majors = prog.required_majors if prog else 0
    required_humanities_majors = prog.required_humanities_majors if prog else 0

    if not prog:
        programme_status, programme_confidence = "unverified", 0.0
        programme_assumptions = ["No matching programme rule set was found."]
    elif catalogue.scope_status != "verified":
        programme_status, programme_confidence = "unverified", 0.5
        programme_assumptions = [
            "The selected programme scope contains unresolved catalogue references."
        ]
    else:
        programme_status, programme_confidence = "verified", 1.0
        programme_assumptions = []

    if student.years_registered is None:
        duration_complete = True
        duration_current = 0.0
        duration_status = "unverified"
        duration_detail = "The transcript does not state years of registration; duration requires confirmation."
    else:
        duration_complete = student.years_registered >= min_years
        duration_current = float(student.years_registered)
        duration_status = "verified"
        duration_detail = f"{student.years_registered} year(s) registered; minimum duration is {min_years}."

    requirements: list[Requirement] = [
        Requirement(
            id="duration",
            label=f"Minimum {min_years} years of study",
            complete=duration_complete,
            current=duration_current,
            required=float(min_years),
            detail=duration_detail,
            status=duration_status,
            confidence=1.0 if duration_status == "verified" else 0.0,
        ),
    ]
    if prog and prog.maximum_registration_years:
        if student.years_registered is None:
            max_complete = True
            max_current = 0.0
            max_status = "unverified"
            max_detail = (
                f"The transcript does not establish years of registration. The ordinary maximum is "
                f"{prog.maximum_registration_years} years; continuation beyond it requires Senate permission."
            )
        else:
            max_complete = student.years_registered <= prog.maximum_registration_years
            max_current = float(student.years_registered)
            max_status = "verified" if max_complete else "discretionary"
            max_detail = (
                f"{student.years_registered} year(s) registered; the ordinary maximum is "
                f"{prog.maximum_registration_years}."
                + (
                    " Senate permission may be required to continue."
                    if not max_complete
                    else ""
                )
            )
        requirements.append(
            Requirement(
                id="maximum_registration",
                label="Maximum registration period",
                complete=max_complete,
                current=max_current,
                required=float(prog.maximum_registration_years),
                detail=max_detail,
                status=max_status,
                confidence=1.0 if student.years_registered is not None else 0.0,
                blocking=False,
            )
        )
    if semester_course_equivalents:
        requirements.append(
            Requirement(
                id="courses",
                label="Semester course equivalents",
                complete=sce_total >= semester_course_equivalents,
                current=sce_total,
                required=float(semester_course_equivalents),
                detail=f"{sce_total:.1f} of {semester_course_equivalents} required semester-course equivalents passed",
                status=programme_status,
                confidence=programme_confidence,
            )
        )
    if senior_course_equivalents:
        requirements.append(
            Requirement(
                id="senior",
                label="Senior semester courses",
                complete=senior_sce >= senior_course_equivalents,
                current=senior_sce,
                required=float(senior_course_equivalents),
                detail=f"{senior_sce:.1f} of {senior_course_equivalents} required senior courses passed",
                status=programme_status,
                confidence=programme_confidence,
            )
        )

    if humanities_course_equivalents:
        requirements.append(
            Requirement(
                id="humanities",
                label="Humanities semester courses",
                complete=humanities_sce >= humanities_course_equivalents,
                current=humanities_sce,
                required=float(humanities_course_equivalents),
                detail=f"{humanities_sce:.1f} of {humanities_course_equivalents} required Humanities courses passed",
                status=programme_status,
                confidence=programme_confidence,
            )
        )

    credit_assumptions = list(programme_assumptions)
    if provisional_credit_results:
        credit_assumptions.append(
            "Includes transcript-only credits provisionally allocated to a published approved/open elective pool; faculty approval is not verified."
        )
    total_credits_graph = build_total_nqf_credits_graph(
        student=student,
        required_credits=total_nqf_credits,
        programme_key=programme_key,
        programme_name=prog.name if prog else programme_key,
        assumptions=credit_assumptions,
        catalogue=catalogue,
        provisional_results=provisional_credit_results,
    )
    credit_conclusion = total_credits_graph.conclusions[
        f"{programme_key.upper()}_TOTAL_NQF_CREDITS"
    ]
    requirements.extend(
        [
            Requirement(
                id="credits",
                label="NQF credits",
                complete=credits_completed >= total_nqf_credits,
                current=float(credits_completed),
                required=float(total_nqf_credits),
                detail=(
                    f"{credits_completed} of {total_nqf_credits} NQF credits completed"
                    + (
                        "; includes provisional approved/open elective credit(s): "
                        + ", ".join(
                            result.code for result in provisional_credit_results
                        )
                        if provisional_credit_results
                        else ""
                    )
                ),
                evidence=credit_conclusion.evidence,
                applied_rules=credit_conclusion.applied_rules,
                explanation=credit_conclusion.explanation,
                status="unverified" if provisional_credit_results else programme_status,
                confidence=0.35 if provisional_credit_results else programme_confidence,
                assumptions=credit_assumptions,
                depends_on=credit_conclusion.depends_on,
            ),
        ]
    )
    if level_7_nqf_credits:
        requirements.append(
            Requirement(
                id="level7",
                label="NQF Level 7 credits",
                complete=level_7_credits >= level_7_nqf_credits,
                current=float(level_7_credits),
                required=float(level_7_nqf_credits),
                detail=f"{level_7_credits} of {level_7_nqf_credits} NQF Level 7 credits completed",
                status=programme_status,
                confidence=programme_confidence,
            )
        )
    if required_majors:
        requirements.append(
            Requirement(
                id="majors",
                label="Completed majors",
                complete=majors_complete >= required_majors,
                current=float(majors_complete),
                required=float(required_majors),
                detail=f"{majors_complete} of {required_majors} majors completed",
                status=(
                    "unverified"
                    if any(m.status != "verified" for m in major_progresses)
                    else programme_status
                ),
                confidence=(
                    0.4
                    if any(m.status != "verified" for m in major_progresses)
                    else programme_confidence
                ),
            )
        )

    # Some Science majors are valid only when paired with Computer Science.
    if catalogue.faculty_key == "uct_science":
        selected_major_keys = set(
            _normalise_major_keys(student.declared_majors, catalogue)
        )
        for key in sorted(selected_major_keys):
            major = catalogue.majors.get(key)
            if major is None or not major.required_co_majors:
                continue
            missing = [
                required
                for required in major.required_co_majors
                if required not in selected_major_keys
            ]
            requirements.append(
                Requirement(
                    id=f"major_co_requirement:{key}",
                    label=f"Required co-major for {major.name}",
                    complete=not missing,
                    current=float(len(major.required_co_majors) - len(missing)),
                    required=float(len(major.required_co_majors)),
                    detail=(
                        f"{major.name} must be taken with "
                        + ", ".join(
                            catalogue.majors[m].name if m in catalogue.majors else m
                            for m in major.required_co_majors
                        )
                        + "."
                        + ((" Missing: " + ", ".join(missing) + ".") if missing else "")
                    ),
                    status="verified",
                    confidence=1.0,
                )
            )

    if required_humanities_majors:
        requirements.append(
            Requirement(
                id="humanities_major",
                label="At least one Humanities major",
                complete=humanities_majors_complete >= required_humanities_majors,
                current=float(humanities_majors_complete),
                required=float(required_humanities_majors),
                detail="At least one major must be offered by a department established in Humanities, including Economics.",
                status=programme_status,
                confidence=programme_confidence,
            )
        )

    # BA/BSocSc identity follows the category of the Humanities major(s).
    declared_keys = _normalise_major_keys(student.declared_majors, catalogue)
    faculty_categories = {
        catalogue.majors[key].qualification
        for key in declared_keys
        if key in catalogue.majors and catalogue.majors[key].faculty_owned
    }
    degree_match = bool(faculty_categories)
    if prog and prog.degree_category == "BA" and faculty_categories == {"BSocSc"}:
        degree_match = False
    if prog and prog.degree_category == "BSocSc" and faculty_categories == {"BA"}:
        degree_match = False
    if prog and prog.required_majors > 0 and prog.degree_category in {"BA", "BSocSc"}:
        requirements.append(
            Requirement(
                id="degree_major_identity",
                label="Majors match the selected degree title",
                complete=degree_match,
                current=1.0 if degree_match else 0.0,
                required=1.0,
                detail=(
                    "Mixed BA and BSocSc Humanities majors may lead to either degree title."
                    if degree_match
                    else "The selected degree title does not match the category of the declared Humanities major(s), or no Humanities major was identified."
                ),
                status=programme_status,
                confidence=programme_confidence,
            )
        )

    passed = student.passed_codes()
    if prog:
        for code in prog.required_courses:
            requirements.append(
                Requirement(
                    id=f"programme_course:{code}",
                    label=f"Required programme course: {code}",
                    complete=code in passed,
                    current=1.0 if code in passed else 0.0,
                    required=1.0,
                    detail=f"{code} is compulsory for {prog.name}.",
                    status=programme_status,
                    confidence=programme_confidence,
                )
            )
        if prog.introductory_courses_required:
            intro_done = sum(
                1 for code in prog.introductory_course_options if code in passed
            )
            requirements.append(
                Requirement(
                    id="extended_introductory",
                    label="Extended-programme introductory courses",
                    complete=intro_done >= prog.introductory_courses_required,
                    current=float(intro_done),
                    required=float(prog.introductory_courses_required),
                    detail=f"Complete {prog.introductory_courses_required} from {prog.introductory_course_options}.",
                    status=programme_status,
                    confidence=programme_confidence,
                )
            )
        if prog.augmenting_courses_required:
            augmenting_done = sum(
                1
                for code in passed
                if (fact := catalogue.courses.get(code)) is not None and fact.augmenting
            )
            requirements.append(
                Requirement(
                    id="extended_augmenting",
                    label="Extended-programme augmenting courses",
                    complete=augmenting_done >= prog.augmenting_courses_required,
                    current=float(augmenting_done),
                    required=float(prog.augmenting_courses_required),
                    detail=f"At least {prog.augmenting_courses_required} augmenting courses are required.",
                    status=programme_status,
                    confidence=programme_confidence,
                )
            )

        evaluator = CurriculumEvaluator(student, catalogue)
        structured_rules = list(prog.curriculum_rules)
        pathway = prog.pathways.get(student.pathway_key or catalogue.pathway_key)
        if pathway:
            structured_rules.extend(pathway.curriculum_rules)
        for evaluated in evaluator.evaluate_many(structured_rules):
            requirements.append(
                Requirement(
                    id=f"curriculum:{evaluated.id}",
                    label=evaluated.label,
                    complete=evaluated.complete,
                    current=evaluated.current,
                    required=evaluated.required,
                    detail=evaluated.detail,
                    status=evaluated.status,
                    confidence=evaluated.confidence,
                    assumptions=evaluated.assumptions,
                    blocking=evaluated.blocking,
                )
            )

        # Four-year and professional qualifications may prescribe credits at
        # NQF levels other than level 7. These requirements are independent of
        # the legacy level-7 field retained for general degrees.
        for level, required_credits in sorted(prog.level_credit_requirements.items()):
            current = evaluator.credits_by_level.get(level, 0)
            if level == 7 and level_7_nqf_credits == required_credits:
                continue
            requirements.append(
                Requirement(
                    id=f"level{level}",
                    label=f"NQF Level {level} credits",
                    complete=current >= required_credits,
                    current=float(current),
                    required=float(required_credits),
                    detail=f"{current} of {required_credits} NQF Level {level} credits completed",
                    status=programme_status,
                    confidence=programme_confidence,
                )
            )

        if prog.availability != "open":
            requirements.append(
                Requirement(
                    id="programme_availability",
                    label="Programme intake status",
                    complete=True,
                    current=1.0,
                    required=1.0,
                    detail=prog.availability_note
                    or f"Programme status: {prog.availability}.",
                    status=(
                        "unverified"
                        if prog.availability == "continuing_only"
                        else "discretionary"
                    ),
                    confidence=1.0,
                    blocking=False,
                )
            )

    # The same senior course may not be recognised as part of two majors.
    usage: dict[str, list[str]] = {}
    for major in major_progresses:
        for code in major.used_course_codes:
            if _is_senior(code):
                usage.setdefault(code, []).append(major.name)
    overlaps = {code: names for code, names in usage.items() if len(names) > 1}
    if catalogue.faculty_key == "uct_science":
        overlap_credits = sum(
            catalogue.courses[code].nqf_credits
            for code in overlaps
            if code in catalogue.courses and catalogue.courses[code].nqf_level == 7
        )
        selected_count = len(_normalise_major_keys(student.declared_majors, catalogue))
        if not overlaps:
            overlap_complete, overlap_status = True, "verified"
            overlap_detail = "No level-7 course overlap was detected between selected Science majors."
        elif overlap_credits <= 36:
            overlap_complete, overlap_status = True, "discretionary"
            overlap_detail = (
                f"{overlap_credits} level-7 credits overlap between majors. FB7.7 permits up to 36 shared credits only with Deputy Dean approval: "
                + "; ".join(
                    f"{code} ({', '.join(names)})" for code, names in overlaps.items()
                )
            )
        elif selected_count >= 3 and level_7_credits >= 180:
            overlap_complete, overlap_status = True, "discretionary"
            overlap_detail = f"{overlap_credits} level-7 credits overlap. A three-major allocation may be approved where at least 180 level-7 credits are completed; Deputy Dean approval is required."
        else:
            overlap_complete, overlap_status = False, "verified"
            overlap_detail = f"{overlap_credits} overlapping level-7 credits exceed the ordinary 36-credit shared-major allowance."
        requirements.append(
            Requirement(
                id="major_course_allocation",
                label="Distinct level-7 credits across Science majors",
                complete=overlap_complete,
                current=float(overlap_credits),
                required=36.0,
                detail=overlap_detail,
                status=overlap_status,
                confidence=1.0 if overlap_status == "verified" else 0.0,
            )
        )
        requirements.append(
            Requirement(
                id="major_combination",
                label="Valid Science major combination",
                complete=forbidden_ok,
                current=1.0 if forbidden_ok else 0.0,
                required=1.0,
                detail=(
                    ""
                    if forbidden_ok
                    else "Applied Statistics, Mathematical Statistics, and Statistics & Data Science may not be combined with one another."
                ),
                status="verified",
                confidence=1.0,
            )
        )
    elif prog is None or prog.programme_type == "general_degree":
        requirements.append(
            Requirement(
                id="major_course_allocation",
                label="No senior course double-counted across majors",
                complete=True,
                current=0.0 if overlaps else 1.0,
                required=1.0,
                detail=(
                    "Manual allocation is required for: "
                    + "; ".join(
                        f"{code} ({', '.join(names)})"
                        for code, names in overlaps.items()
                    )
                    if overlaps
                    else "No senior-course overlap was detected in the courses allocated by the engine."
                ),
                status="unverified" if overlaps else "verified",
                confidence=0.4 if overlaps else 1.0,
            )
        )
        requirements.append(
            Requirement(
                id="major_combination",
                label="Valid major combination",
                complete=forbidden_ok,
                current=1.0 if forbidden_ok else 0.0,
                required=1.0,
                detail=(
                    ""
                    if forbidden_ok
                    else "The selected majors are a forbidden combination under FB3(e)."
                ),
                status="verified",
                confidence=1.0,
            )
        )
    requirements.append(
        Requirement(
            id="qualification_match",
            label="Programme rules identified",
            complete=prog is not None,
            current=1.0 if prog else 0.0,
            required=1.0,
            detail=(
                f"Using {prog.name}."
                if prog
                else f"No rule set matched {student.programme!r}."
            ),
            status=programme_status,
            confidence=programme_confidence,
        )
    )
    return requirements


def compute_report(student: StudentRecord, catalogue: Catalogue) -> Report:
    """
    Compute the full graduation report from raw facts.
    This is the only place where conclusions are drawn.
    """
    programme_key = student.programme_key or _infer_programme_key(student.programme)
    prog = catalogue.programmes.get(programme_key)

    major_keys = _normalise_major_keys(student.declared_majors, catalogue)

    credits_completed, level_7_credits, provisional_credit_results = _compute_credits(
        student, catalogue
    )
    sce_total, senior_sce, humanities_sce = _compute_course_equivalents(
        student, catalogue
    )
    major_progresses, majors_complete, humanities_majors_complete = (
        _compute_all_major_progresses(student, catalogue, major_keys)
    )
    forbidden_ok = _check_forbidden_combinations(catalogue, major_keys)

    requirements = _build_requirements(
        student,
        catalogue,
        programme_key,
        prog,
        sce_total,
        senior_sce,
        humanities_sce,
        credits_completed,
        level_7_credits,
        provisional_credit_results,
        major_progresses,
        majors_complete,
        humanities_majors_complete,
        forbidden_ok,
    )

    blocking_requirements = [r for r in requirements if r.blocking]
    if any(not r.complete for r in blocking_requirements):
        graduation_status = "not_eligible"
    elif any(r.status != "verified" for r in blocking_requirements):
        graduation_status = "requires_verification"
    else:
        graduation_status = "eligible"
    graduation_eligible = graduation_status == "eligible"

    eligible_courses = _compute_eligible_courses(student, catalogue)
    exclusion_risk = _compute_exclusion_risk(student, catalogue, programme_key)
    distinction = _compute_distinction(student, catalogue, major_keys)
    warnings = _compute_warnings(student, catalogue, major_keys)
    if prog is None:
        warnings.append(
            f"No programme rule set matched {student.programme!r}; graduation cannot be verified."
        )
    warnings.append(
        "Course suggestions are provisional: they do not verify timetable clashes, co-requisites, class limits, concessions, or faculty approval."
    )
    if prog:
        warnings.extend(note for note in prog.admission_notes if note not in warnings)
        warnings.extend(note for note in prog.progression_notes if note not in warnings)
        warnings.extend(note for note in prog.award_notes if note not in warnings)
    if provisional_credit_results:
        warnings.append(
            "The credit total provisionally includes transcript-only approved/open elective course(s): "
            + ", ".join(result.code for result in provisional_credit_results)
            + ". Faculty approval must be confirmed before these credits are treated as definitive."
        )

    failed_attempts = _compute_failed_attempts(student)

    verification_messages = [
        r.detail or r.label
        for r in blocking_requirements
        if r.complete and r.status != "verified"
    ]

    return Report(
        graduation_eligible=graduation_eligible,
        credits_completed=credits_completed,
        level_7_credits=level_7_credits,
        semester_course_equivalents=sce_total,
        requirements=requirements,
        majors=major_progresses,
        eligible_courses=eligible_courses,
        exclusion_risk=exclusion_risk,
        distinction=distinction,
        warnings=warnings,
        failed_attempts=failed_attempts,
        student_name=student.name,
        graduation_status=graduation_status,
        verification_messages=verification_messages,
        faculty_key=student.faculty_key or catalogue.faculty_key,
        programme_key=programme_key,
        programme_name=prog.name if prog else student.programme,
        pathway_key=student.pathway_key or catalogue.pathway_key,
        pathway_name=(
            prog.pathways[student.pathway_key or catalogue.pathway_key].name
            if prog and (student.pathway_key or catalogue.pathway_key) in prog.pathways
            else ""
        ),
        scope_status=catalogue.scope_status,
    )
