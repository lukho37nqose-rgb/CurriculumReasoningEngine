"""Programme-scoped catalogue construction.

The full faculty catalogue is an ingestion store.  It must not be used as the
student's reasoning universe.  A selected faculty + programme determines the
majors and courses that the engine is allowed to consider.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from .models import Catalogue, ProgrammeRules
from .curriculum import collect_curriculum_course_codes


@dataclass(frozen=True)
class ProgrammeScope:
    faculty_key: str
    programme_key: str
    programme_name: str
    pathway_key: str
    pathway_name: str
    major_keys: tuple[str, ...]
    course_codes: tuple[str, ...]
    elective_course_codes: tuple[str, ...]
    status: str
    warnings: tuple[str, ...]


def build_programme_scope(
    faculty_key: str,
    catalogue: Catalogue,
    programme_key: str,
    pathway_key: str = "",
) -> tuple[Catalogue, ProgrammeScope]:
    """Return a catalogue containing only facts relevant to one programme.

    Explicit ``major_keys`` and ``elective_course_codes`` are preferred.  Old
    catalogues that do not yet contain those mappings remain usable, but the
    scope is marked unverified and no faculty-wide course is treated as a
    general elective merely because it exists in the ingestion store.
    """
    programme = catalogue.programmes.get(programme_key)
    if programme is None:
        raise ValueError(
            f"Unknown programme {programme_key!r} for {faculty_key!r}. "
            f"Expected one of: {', '.join(sorted(catalogue.programmes)) or 'none'}."
        )

    warnings: list[str] = []
    selected_pathway = None
    if programme.pathways:
        effective_pathway_key = pathway_key or programme.default_pathway_key
        if programme.pathway_required and not effective_pathway_key:
            raise ValueError(
                f"{programme.name} requires a pathway or stream selection. "
                f"Expected one of: {', '.join(sorted(programme.pathways))}."
            )
        if effective_pathway_key:
            selected_pathway = programme.pathways.get(effective_pathway_key)
            if selected_pathway is None:
                raise ValueError(
                    f"Unknown pathway {effective_pathway_key!r} for {programme.name}. "
                    f"Expected one of: {', '.join(sorted(programme.pathways))}."
                )
            pathway_key = effective_pathway_key
    elif pathway_key:
        raise ValueError(f"{programme.name} does not define a pathway selection.")
    missing_major_keys: list[str] = []
    explicit_major_mapping = bool(programme.major_keys) or programme.programme_type != "general_degree"
    if explicit_major_mapping:
        major_keys = [key for key in programme.major_keys if key in catalogue.majors]
        missing_major_keys = [key for key in programme.major_keys if key not in catalogue.majors]
        if missing_major_keys:
            warnings.append(
                "Programme mapping references undefined majors: "
                + ", ".join(sorted(missing_major_keys))
                + "."
            )
    elif programme.programme_type == "general_degree":
        # Compatibility bridge for the current extracted catalogues.  This is
        # deliberately visible as unverified rather than silently authoritative.
        major_keys = sorted(catalogue.majors)
        warnings.append(
            "This programme does not yet have an explicit major mapping. "
            "All faculty major definitions are visible, but the mapping requires handbook verification."
        )
    else:
        major_keys = []

    scoped_majors = {
        key: catalogue.majors[key]
        for key in major_keys
        if key in catalogue.majors
    }

    required_course_codes: set[str] = set(programme.required_courses)
    required_course_codes.update(collect_curriculum_course_codes(programme.curriculum_rules, catalogue))
    if selected_pathway:
        required_course_codes.update(selected_pathway.required_courses)
        required_course_codes.update(collect_curriculum_course_codes(selected_pathway.curriculum_rules, catalogue))
    for major in scoped_majors.values():
        required_course_codes.update(major.required_courses)
        for group in major.choice_groups:
            required_course_codes.update(group.courses)
        required_course_codes.update(collect_curriculum_course_codes(major.curriculum_rules, catalogue))
        for stage_rules in major.stage_rules.values():
            required_course_codes.update(collect_curriculum_course_codes(stage_rules, catalogue))

    explicit_electives = {
        code for code in programme.elective_course_codes
        if code in catalogue.courses and catalogue.courses[code].general_elective
    }
    non_elective_mappings = [
        code for code in programme.elective_course_codes
        if code in catalogue.courses and not catalogue.courses[code].general_elective
    ]
    if non_elective_mappings:
        warnings.append(
            "Programme elective mapping included course(s) that are not marked as general electives: "
            + ", ".join(sorted(non_elective_mappings))
            + "."
        )
    missing_electives = [
        code for code in programme.elective_course_codes
        if code not in catalogue.courses
    ]
    if missing_electives:
        warnings.append(
            "Programme mapping references undefined elective courses: "
            + ", ".join(sorted(missing_electives))
            + "."
        )

    if programme.elective_departments:
        allowed_departments = {
            department.strip().lower()
            for department in programme.elective_departments
            if department.strip()
        }
        explicit_electives.update(
            code for code, course in catalogue.courses.items()
            if course.department.strip().lower() in allowed_departments and course.general_elective
        )

    if (
        programme.programme_type == "general_degree"
        and not programme.elective_course_codes
        and not programme.elective_departments
    ):
        warnings.append(
            "No programme-specific elective pool has been verified. "
            "The engine will recommend major and compulsory courses only."
        )

    support_course_codes = {
        code for code in programme.support_course_codes
        if code in catalogue.courses
    }
    if selected_pathway:
        support_course_codes.update(
            code for code in selected_pathway.support_course_codes
            if code in catalogue.courses
        )
    missing_support = [
        code for code in programme.support_course_codes
        if code not in catalogue.courses
    ]
    if selected_pathway:
        missing_support.extend(
            code for code in selected_pathway.support_course_codes
            if code not in catalogue.courses
        )
    if missing_support:
        warnings.append(
            "Programme mapping references undefined support courses: "
            + ", ".join(sorted(missing_support))
            + "."
        )

    allowed_course_codes = required_course_codes | explicit_electives | support_course_codes
    scoped_courses = {}
    for code in sorted(allowed_course_codes):
        if code not in catalogue.courses:
            continue
        fact = catalogue.courses[code]
        if code in programme.prerequisite_overrides or code in programme.co_requisite_overrides:
            fact = replace(
                fact,
                prerequisites=list(programme.prerequisite_overrides.get(code, fact.prerequisites)),
                prerequisites_verified=True if code in programme.prerequisite_overrides else fact.prerequisites_verified,
                co_requisites=list(programme.co_requisite_overrides.get(code, fact.co_requisites)),
            )
        scoped_courses[code] = fact

    missing_required = sorted(code for code in required_course_codes if code not in catalogue.courses)
    if missing_required:
        warnings.append(
            "Programme or major requirements reference missing course definitions: "
            + ", ".join(missing_required)
            + "."
        )

    allowed_major_set = set(scoped_majors)
    scoped_forbidden = [
        pair for pair in catalogue.forbidden_combinations
        if pair[0] in allowed_major_set and pair[1] in allowed_major_set
    ]

    scope_verified = (
        programme.scope_verified
        and explicit_major_mapping
        and not missing_required
        and not missing_major_keys
        and not missing_electives
        and not non_elective_mappings
        and not missing_support
        and (selected_pathway is None or selected_pathway.verification_status == "verified")
    )
    status = "verified" if scope_verified else "unverified"

    scope_issues = list(catalogue.data_issues)
    scope_issues.extend(f"Programme scope: {warning}" for warning in warnings)

    scoped = Catalogue(
        courses=scoped_courses,
        majors=scoped_majors,
        programmes={programme_key: programme},
        forbidden_combinations=scoped_forbidden,
        data_issues=scope_issues,
        faculty_key=faculty_key,
        programme_key=programme_key,
        pathway_key=pathway_key,
        scope_status=status,
        elective_course_codes=explicit_electives,
        cross_credit_exclusions=list(catalogue.cross_credit_exclusions),
        source=catalogue.source,
        catalogue_version=catalogue.catalogue_version,
    )
    scope = ProgrammeScope(
        faculty_key=faculty_key,
        programme_key=programme_key,
        programme_name=programme.name,
        pathway_key=pathway_key,
        pathway_name=selected_pathway.name if selected_pathway else "",
        major_keys=tuple(scoped_majors),
        course_codes=tuple(scoped_courses),
        elective_course_codes=tuple(sorted(explicit_electives)),
        status=status,
        warnings=tuple(warnings),
    )
    return scoped, scope
