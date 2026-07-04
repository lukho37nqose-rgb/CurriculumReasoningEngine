"""
Planner — computes the optimal next courses to register for.

Given a student's current state, recommends which courses to take
next to make progress toward graduation and major completion.
Uses backward chaining: start from graduation goal, work backwards
to find what's needed now.
"""

from dataclasses import dataclass
from .models import StudentRecord, Catalogue
from .rule_engine import _prereqs_met
from .utils import _course_weight, _infer_programme_key, _normalise_major_keys
from .recognition import recognised_credited_pairs


@dataclass
class CourseRecommendation:
    code: str
    name: str
    department: str
    offered: list[str]
    credits: int
    reason: str  # Why this course is recommended
    priority: int  # 1=critical (required for major), 2=important, 3=optional
    status: str = "provisional"
    limitations: tuple[str, ...] = (
        "Recorded prerequisites and semester offering only.",
        "Timetable, co-requisites, class limits, and faculty approval are not verified.",
    )


def plan_next_semester(
    student: StudentRecord,
    catalogue: Catalogue,
    semester: str = "Semester 1",  # "Semester 1", "Semester 2", or "Full Year"
    max_courses: int = 4,
) -> list[CourseRecommendation]:
    """
    Recommend courses for the next semester using backward chaining.

    Priority order:
    1. Required courses for declared majors (prerequisites met)
    2. Choice group courses for declared majors (prerequisites met)
    3. Any senior course to meet senior-course requirement
    4. Any available course to meet total-course requirement
    """
    passed = student.passed_codes()
    major_keys = _normalise_major_keys(student.declared_majors, catalogue)
    programme = catalogue.programmes.get(
        (student.programme_key or _infer_programme_key(student.programme))
    )
    selected_major_codes: set[str] = set()
    for key in major_keys:
        major = catalogue.majors.get(key)
        if not major:
            continue
        selected_major_codes.update(major.required_courses)
        for group in major.choice_groups:
            selected_major_codes.update(group.courses)
    route_codes = selected_major_codes | set(catalogue.elective_course_codes)
    if programme:
        route_codes.update(programme.required_courses)
        route_codes.update(programme.support_course_codes)

    recommendations: list[CourseRecommendation] = []
    seen_codes: set[str] = set()

    def add(code: str, reason: str, priority: int) -> None:
        if code in seen_codes or code in passed:
            return
        course = catalogue.courses.get(code)
        if not course:
            return
        if code not in route_codes:
            return
        if course.nqf_credits <= 0 or course.nqf_level <= 0:
            return
        if not course.offering_verified:
            return
        if not _prereqs_met(course, passed):
            return
        # Filter by semester offering
        if semester != "Any" and not any(
            semester.lower() in o.lower()
            or "full year" in o.lower()
            or "year" in o.lower()
            for o in course.offered
        ):
            return
        seen_codes.add(code)
        recommendations.append(
            CourseRecommendation(
                code=code,
                name=course.name,
                department=course.department,
                offered=course.offered,
                credits=course.nqf_credits,
                reason=reason,
                priority=priority,
            )
        )

    # --- Priority 1: Compulsory programme courses ---
    if programme:
        for code in programme.required_courses:
            add(code, f"Compulsory for {programme.name}", 1)

    # --- Priority 1: Required courses for majors ---
    for key in major_keys:
        major_def = catalogue.majors.get(key)
        if not major_def:
            continue
        for code in major_def.required_courses:
            if code not in passed:
                add(code, f"Required for {major_def.name} major", 1)

    # --- Priority 2: Choice group courses for majors ---
    for key in major_keys:
        major_def = catalogue.majors.get(key)
        if not major_def:
            continue
        for group in major_def.choice_groups:
            satisfied = [c for c in group.courses if c in passed]
            if len(satisfied) < group.required:
                for code in group.courses:
                    add(code, f"{group.label} ({major_def.name} major)", 2)

    # --- Priority 3: Senior courses to meet senior-course requirement ---
    recognised, _ = recognised_credited_pairs(student, catalogue)
    senior_passed = sum(
        _course_weight(result.code)
        for result, fact in recognised
        if fact.nqf_level >= 6 and fact.counts_towards_course_equivalents
    )
    senior_required = programme.senior_course_equivalents if programme else 0
    if senior_required and senior_passed < senior_required:
        for code, course in catalogue.courses.items():
            if (
                code in route_codes
                and course.nqf_level >= 6
                and course.prerequisites
                and code not in passed
            ):
                add(
                    code,
                    f"May count toward the senior-course requirement ({senior_required:g} needed)",
                    3,
                )

    # --- Priority 4: Explicit programme electives only ---
    for code in sorted(catalogue.elective_course_codes):
        add(code, "Verified elective for the selected programme", 4)

    # Sort by priority, then by course code
    recommendations.sort(key=lambda r: (r.priority, r.code))
    return recommendations[:max_courses]


def explain_requirement(
    requirement_id: str,
    student: StudentRecord,
    catalogue: Catalogue,
) -> str:
    """
    Backward-chaining explanation: given a requirement that is NOT met,
    explain what the student needs to do to satisfy it.
    """
    from .rule_engine import compute_report

    passed = student.passed_codes()
    major_keys = _normalise_major_keys(student.declared_majors, catalogue)

    report = compute_report(student, catalogue)
    requirement = next((r for r in report.requirements if r.id == requirement_id), None)

    if requirement_id == "credits" and requirement:
        needed = max(requirement.required - requirement.current, 0)
        return (
            f"You need {needed} more NQF credits. "
            "Credit values differ by course, so use the catalogue value for each planned course."
        )

    if requirement_id == "senior" and requirement:
        needed = max(requirement.required - requirement.current, 0)
        return (
            f"You need {needed:.1f} more senior semester-course equivalents. "
            "Confirm that each planned course is recognised as senior in your programme."
        )

    if requirement_id == "majors":
        lines = []
        for key in major_keys:
            major_def = catalogue.majors.get(key)
            if not major_def:
                continue
            outstanding = []
            for code in major_def.required_courses:
                if code not in passed:
                    outstanding.append(code)
            for group in major_def.choice_groups:
                satisfied = [c for c in group.courses if c in passed]
                if len(satisfied) < group.required:
                    outstanding.append(
                        f"{group.required - len(satisfied)} from {group.label}"
                    )
            if outstanding:
                lines.append(f"{major_def.name}: still need {', '.join(outstanding)}")
        return "\n".join(lines) if lines else "Both majors are complete."

    if requirement_id == "level7" and requirement:
        needed = max(requirement.required - requirement.current, 0)
        return (
            f"You need {needed} more NQF Level 7 credits. "
            "Use the explicit NQF level and credit value in the catalogue; course-code year is not sufficient proof."
        )

    if requirement:
        return requirement.detail or f"{requirement.label} is not yet met."

    return f"Requirement '{requirement_id}' is not yet met. See your faculty advisor for details."
