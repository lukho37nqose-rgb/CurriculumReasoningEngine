"""Catalogue loader: JSON handbook facts -> typed models."""

from __future__ import annotations
import json
from pathlib import Path
from .models import (
    Catalogue,
    ChoiceGroup,
    CourseFact,
    MajorDefinition,
    ProgrammeRules,
    PathwayDefinition,
    ReadmissionThreshold,
)

_BASE = Path(__file__).parent.parent


def _nqf_level_from_code(code: str) -> int:
    for ch in code:
        if ch.isdigit():
            return {1: 5, 2: 6, 3: 7, 4: 8}.get(int(ch), 0)
    return 0


def load_catalogue(
    faculty_key: str = "uct_humanities",
    courses_path: Path | None = None,
    requirements_path: Path | None = None,
) -> Catalogue:
    data_dir = _BASE / "data" / faculty_key
    courses_path = courses_path or data_dir / "courses.json"
    requirements_path = requirements_path or data_dir / "degree_requirements.json"
    with open(courses_path, encoding="utf-8") as handle:
        raw_courses = json.load(handle)
    with open(requirements_path, encoding="utf-8") as handle:
        raw_reqs = json.load(handle)

    issues: list[str] = []
    courses: dict[str, CourseFact] = {}
    for raw in raw_courses:
        code = str(raw.get("code", "")).strip().upper()
        if not code:
            issues.append("A course entry without a course code was ignored.")
            continue
        if code in courses:
            issues.append(
                f"Duplicate course definition for {code}; the later entry was used."
            )
        try:
            credits = int(raw.get("credits", 0))
        except (TypeError, ValueError):
            credits = 0
        try:
            level = int(raw.get("nqf_level", 0) or _nqf_level_from_code(code))
        except (TypeError, ValueError):
            level = 0
        credit_bearing = bool(raw.get("credit_bearing", credits > 0))
        if credit_bearing and credits <= 0:
            issues.append(
                f"{code} has invalid or missing credit value: {raw.get('credits')!r}."
            )
        if not 1 <= level <= 10:
            issues.append(
                f"{code} has an invalid or unknown NQF level: {raw.get('nqf_level')!r}."
            )

        raw_prereqs = raw.get("prerequisites", [])
        prereq_valid = isinstance(raw_prereqs, list) and all(
            isinstance(p, str) for p in raw_prereqs
        )
        prereqs = (
            [p.strip().upper() for p in raw_prereqs if isinstance(p, str) and p.strip()]
            if prereq_valid
            else []
        )
        prereq_verified = bool(
            raw.get(
                "prerequisites_verified", prereq_valid and (bool(prereqs) or level == 5)
            )
        )
        raw_offered = raw.get("offered", [])
        offering_valid = isinstance(raw_offered, list) and all(
            isinstance(o, str) for o in raw_offered
        )
        offered = (
            [o.strip() for o in raw_offered if o.strip()] if offering_valid else []
        )
        co_reqs = [
            str(c).strip().upper()
            for c in raw.get("co_requisites", [])
            if str(c).strip()
        ]

        courses[code] = CourseFact(
            code=code,
            name=str(raw.get("name", "")).strip(),
            nqf_credits=credits,
            nqf_level=level,
            prerequisites=prereqs,
            offered=offered,
            department=str(raw.get("department", "")).strip(),
            description=str(raw.get("description", "")).strip(),
            prerequisites_verified=prereq_verified,
            offering_verified=offering_valid,
            co_requisites=co_reqs,
            augmenting_course=str(raw.get("augmenting_course", "")).strip().upper(),
            augmenting=bool(raw.get("augmenting", False)),
            credit_bearing=credit_bearing,
            counts_towards_general_degree=bool(
                raw.get("counts_towards_general_degree", True)
            ),
            counts_as_humanities=bool(raw.get("counts_as_humanities", True)),
            counts_as_science=bool(raw.get("counts_as_science", False)),
            verification_status=str(raw.get("verification_status", "provisional")),
            source=(
                raw.get("source", {}) if isinstance(raw.get("source", {}), dict) else {}
            ),
            general_elective=bool(
                raw.get(
                    "general_elective", raw.get("counts_towards_general_degree", True)
                )
            ),
            counts_towards_course_equivalents=bool(
                raw.get("counts_towards_course_equivalents", True)
            ),
            recognition_note=str(raw.get("recognition_note", "")).strip(),
        )

    majors: dict[str, MajorDefinition] = {}
    for key, raw in raw_reqs.get("majors", {}).items():
        groups: list[ChoiceGroup] = []
        for group in raw.get("choice_groups", []):
            courses_in_group = [
                str(c).strip().upper()
                for c in group.get("courses", [])
                if str(c).strip()
            ]
            required = int(group.get("required", group.get("choose", 1)))
            groups.append(
                ChoiceGroup(
                    label=str(group.get("label", group.get("name", "Choose courses"))),
                    required=required,
                    courses=courses_in_group,
                )
            )
            if required <= 0 or required > len(courses_in_group):
                issues.append(
                    f"Major '{raw.get('name', key)}' has an invalid choice group requirement."
                )
        major = MajorDefinition(
            key=key,
            name=str(raw.get("name", key)),
            qualification=str(raw.get("qualification", "HUMANITIES")),
            required_courses=[
                str(c).strip().upper()
                for c in raw.get("required_courses", [])
                if str(c).strip()
            ],
            choice_groups=groups,
            faculty_owned=bool(raw.get("faculty_owned", True)),
            handbook_code=str(raw.get("handbook_code", "")),
            verification_status=str(raw.get("verification_status", "provisional")),
            verification_notes=[str(n) for n in raw.get("verification_notes", [])],
            curriculum_rules=[
                r for r in raw.get("curriculum_rules", []) if isinstance(r, dict)
            ],
            stage_rules={
                str(stage): [r for r in rules if isinstance(r, dict)]
                for stage, rules in raw.get("stage_rules", {}).items()
                if isinstance(rules, list)
            },
            required_co_majors=[str(m) for m in raw.get("required_co_majors", [])],
            admission_limited=bool(raw.get("admission_limited", False)),
            admission_note=str(raw.get("admission_note", "")),
            award_rules=[r for r in raw.get("award_rules", []) if isinstance(r, dict)],
            source=(
                raw.get("source", {}) if isinstance(raw.get("source", {}), dict) else {}
            ),
        )
        majors[key] = major
        if (
            not major.required_courses
            and not major.choice_groups
            and not major.curriculum_rules
        ):
            issues.append(f"Major '{major.name}' has no representable requirements.")
        referenced_codes = major.required_courses + [
            c for g in major.choice_groups for c in g.courses
        ]
        from .curriculum import collect_curriculum_course_codes

        referenced_codes += sorted(
            collect_curriculum_course_codes(major.curriculum_rules)
        )
        for stage_rules in major.stage_rules.values():
            referenced_codes += sorted(collect_curriculum_course_codes(stage_rules))
        for code in referenced_codes:
            if code not in courses:
                issues.append(
                    f"{code} is referenced by major '{major.name}' but has no course definition."
                )

    programmes: dict[str, ProgrammeRules] = {}
    for key, raw in raw_reqs.get("programmes", {}).items():
        thresholds = [
            ReadmissionThreshold(
                year=int(t.get("year", 0)),
                minimum_passed_courses=int(t.get("minimum_passed_courses", 0)),
                minimum_senior_courses=int(t.get("minimum_senior_courses", 0)),
            )
            for t in raw.get("readmission_thresholds", [])
            if isinstance(t, dict)
        ]
        pathways: dict[str, PathwayDefinition] = {}
        for pathway_key, pathway_raw in raw.get("pathways", {}).items():
            if not isinstance(pathway_raw, dict):
                issues.append(
                    f"Programme '{key}' has an invalid pathway definition for {pathway_key!r}."
                )
                continue
            pathways[pathway_key] = PathwayDefinition(
                key=pathway_key,
                name=str(pathway_raw.get("name", pathway_key)),
                curriculum_rules=[
                    r
                    for r in pathway_raw.get("curriculum_rules", [])
                    if isinstance(r, dict)
                ],
                required_courses=[
                    str(c).strip().upper()
                    for c in pathway_raw.get("required_courses", [])
                    if str(c).strip()
                ],
                support_course_codes=[
                    str(c).strip().upper()
                    for c in pathway_raw.get("support_course_codes", [])
                    if str(c).strip()
                ],
                verification_status=str(
                    pathway_raw.get("verification_status", "verified")
                ),
                availability=str(pathway_raw.get("availability", "open")),
                availability_note=str(pathway_raw.get("availability_note", "")),
                progression_rules=[
                    r
                    for r in pathway_raw.get("progression_rules", [])
                    if isinstance(r, dict)
                ],
                award_rules=[
                    r for r in pathway_raw.get("award_rules", []) if isinstance(r, dict)
                ],
                source=(
                    pathway_raw.get("source", {})
                    if isinstance(pathway_raw.get("source", {}), dict)
                    else {}
                ),
            )

        level_requirements: dict[int, int] = {}
        for level, credits in raw.get("level_credit_requirements", {}).items():
            try:
                level_requirements[int(level)] = int(credits)
            except (TypeError, ValueError):
                issues.append(
                    f"Programme '{key}' has an invalid NQF-level credit requirement: {level!r} -> {credits!r}."
                )

        programmes[key] = ProgrammeRules(
            key=key,
            name=str(raw.get("name", key)),
            total_nqf_credits=int(
                raw.get("minimum_nqf_credits", raw.get("total_nqf_credits", 360))
            ),
            level_7_nqf_credits=int(
                raw.get(
                    "minimum_nqf_level_7_credits", raw.get("level_7_nqf_credits", 120)
                )
            ),
            semester_course_equivalents=int(
                raw.get(
                    "minimum_semester_courses",
                    raw.get("semester_course_equivalents", 20),
                )
            ),
            senior_course_equivalents=int(
                raw.get(
                    "minimum_senior_semester_courses",
                    raw.get("senior_course_equivalents", 10),
                )
            ),
            humanities_course_equivalents=int(
                raw.get(
                    "minimum_humanities_semester_courses",
                    raw.get("humanities_course_equivalents", 0),
                )
            ),
            required_majors=int(
                raw.get("minimum_majors", raw.get("required_majors", 0))
            ),
            required_humanities_majors=int(
                raw.get(
                    "minimum_humanities_majors",
                    raw.get("required_humanities_majors", 0),
                )
            ),
            max_courses_per_semester=(
                float(raw["max_courses_per_semester"])
                if raw.get("max_courses_per_semester") is not None
                else None
            ),
            required_courses=[
                str(c).strip().upper()
                for c in raw.get("required_courses", [])
                if str(c).strip()
            ],
            minimum_duration_years=int(raw.get("minimum_duration_years", 3)),
            maximum_registration_years=(
                int(raw["maximum_registration_years"])
                if raw.get("maximum_registration_years")
                else None
            ),
            qualification_codes=[str(c) for c in raw.get("qualification_codes", [])],
            major_keys=[str(m) for m in raw.get("major_keys", [])],
            elective_course_codes=[
                str(c).strip().upper()
                for c in raw.get("elective_course_codes", [])
                if str(c).strip()
            ],
            elective_departments=[str(d) for d in raw.get("elective_departments", [])],
            scope_verified=bool(raw.get("scope_verified", False)),
            route_type=str(raw.get("route_type", "regular")),
            degree_category=str(raw.get("degree_category", "")),
            readmission_thresholds=thresholds,
            introductory_course_options=[
                str(c).strip().upper()
                for c in raw.get("introductory_course_options", [])
            ],
            introductory_courses_required=int(
                raw.get("introductory_courses_required", 0)
            ),
            augmenting_courses_required=int(raw.get("augmenting_courses_required", 0)),
            support_course_codes=[
                str(c).strip().upper()
                for c in raw.get("support_course_codes", [])
                if str(c).strip()
            ],
            programme_type=str(raw.get("programme_type", "general_degree")),
            curriculum_rules=[
                r for r in raw.get("curriculum_rules", []) if isinstance(r, dict)
            ],
            pathways=pathways,
            pathway_required=bool(raw.get("pathway_required", False)),
            default_pathway_key=str(raw.get("default_pathway_key", "")),
            level_credit_requirements=level_requirements,
            availability=str(raw.get("availability", "open")),
            availability_note=str(raw.get("availability_note", "")),
            admission_notes=[str(n) for n in raw.get("admission_notes", [])],
            progression_notes=[str(n) for n in raw.get("progression_notes", [])],
            award_notes=[str(n) for n in raw.get("award_notes", [])],
            progression_rules=[
                r for r in raw.get("progression_rules", []) if isinstance(r, dict)
            ],
            award_rules=[r for r in raw.get("award_rules", []) if isinstance(r, dict)],
            prerequisite_overrides={
                str(code)
                .strip()
                .upper(): [
                    str(item).strip().upper() for item in values if str(item).strip()
                ]
                for code, values in raw.get("prerequisite_overrides", {}).items()
                if isinstance(values, list)
            },
            co_requisite_overrides={
                str(code)
                .strip()
                .upper(): [
                    str(item).strip().upper() for item in values if str(item).strip()
                ]
                for code, values in raw.get("co_requisite_overrides", {}).items()
                if isinstance(values, list)
            },
            source=(
                raw.get("source", {}) if isinstance(raw.get("source", {}), dict) else {}
            ),
        )

    forbidden = [
        tuple(pair)
        for pair in raw_reqs.get("forbidden_major_combinations", [])
        if isinstance(pair, list) and len(pair) == 2
    ]
    return Catalogue(
        courses=courses,
        majors=majors,
        programmes=programmes,
        forbidden_combinations=forbidden,
        data_issues=issues,
        faculty_key=faculty_key,
        cross_credit_exclusions=raw_reqs.get("cross_credit_exclusions", []),
        source=str(raw_reqs.get("source", "")),
        catalogue_version=str(raw_reqs.get("catalogue_version", "")),
    )
