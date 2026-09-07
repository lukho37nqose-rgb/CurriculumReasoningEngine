"""Pure data models for CurriculumAdvisor.

The catalogue stores handbook facts and provenance. It never stores a
student-specific conclusion such as "may graduate"; those views are computed
by the rule engine from a selected programme scope.
"""

from dataclasses import dataclass, field
from typing import Any


def _legacy_default_grading_scheme() -> Any:
    from curriculum_reasoning_engine.institutions.grading import (
        legacy_default_grading_scheme,
    )

    return legacy_default_grading_scheme()


@dataclass
class CourseResult:
    """A single course attempt appearing on a transcript."""

    code: str
    name: str
    nqf_level: int
    nqf_credits: int
    mark: int | None
    grade: str | None
    academic_year: int | None = None
    attempt_id: str = ""
    academic_period_key: str | None = None
    achievement_value: int | float | str | None = None

    def is_passed(self, grading_scheme: Any = None) -> bool:
        """Compatibility helper; prefer an explicit institutional grading scheme."""
        return (grading_scheme or _legacy_default_grading_scheme()).is_passed(self)

    def is_failed(self, grading_scheme: Any = None) -> bool:
        """Compatibility helper; prefer an explicit institutional grading scheme."""
        return (grading_scheme or _legacy_default_grading_scheme()).is_failed(self)

    def is_pending(self, grading_scheme: Any = None) -> bool:
        """Compatibility helper; prefer an explicit institutional grading scheme."""
        return (grading_scheme or _legacy_default_grading_scheme()).is_pending(self)


@dataclass
class StudentRecord:
    """Raw facts extracted from a transcript plus explicit routing context."""

    student_id: str
    name: str
    programme: str
    declared_majors: list[str]
    results: list[CourseResult] = field(default_factory=list)
    faculty_key: str = ""
    programme_key: str = ""
    pathway_key: str = ""
    years_registered: int | None = None

    def passed_codes(self, grading_scheme: Any = None) -> set[str]:
        scheme = grading_scheme or _legacy_default_grading_scheme()
        return {r.code for r in self.results if scheme.is_passed(r)}

    def failed_codes(self, grading_scheme: Any = None) -> set[str]:
        scheme = grading_scheme or _legacy_default_grading_scheme()
        return {r.code for r in self.results if scheme.is_failed(r)}

    def attempted_codes(self, grading_scheme: Any = None) -> set[str]:
        scheme = grading_scheme or _legacy_default_grading_scheme()
        return {r.code for r in self.results if not scheme.is_pending(r)}

    def result_for(self, code: str) -> CourseResult | None:
        for result in reversed(self.results):
            if result.code == code:
                return result
        return None

    def passed_result_for(self, code: str, grading_scheme: Any = None) -> CourseResult | None:
        scheme = grading_scheme or _legacy_default_grading_scheme()
        for result in reversed(self.results):
            if result.code == code and scheme.is_passed(result):
                return result
        return None

    def credited_results(self, grading_scheme: Any = None) -> list[CourseResult]:
        """Return one passing attempt per course code.

        A later pass replaces an earlier fail or duplicate pass. This preserves
        attempt history while preventing credit inflation.
        """
        scheme = grading_scheme or _legacy_default_grading_scheme()
        credited: dict[str, CourseResult] = {}
        for result in self.results:
            if scheme.is_passed(result):
                credited[result.code] = result
        return list(credited.values())


@dataclass(frozen=True)
class AuthorisedAwardCourseSelection:
    """Replayable external decision naming courses to assess for an award."""

    policy_id: str
    major_key: str
    selected_course_codes: tuple[str, ...]
    authority: str
    source_reference: str
    verification_status: str = "verified"
    catalogue_version: str = ""


@dataclass(frozen=True)
class StageRepeatEvidence:
    """Institutional evidence about formal repeat state for one stage period."""

    programme_key: str
    stage_key: str
    registration_period_key: str
    repeat_state: str
    source_reference: str = ""
    authority: str = ""
    verification_status: str = "verified"
    pathway_key: str = ""


@dataclass(frozen=True)
class ResultContextEvidence:
    """Institutional context for one explicit result/attempt occurrence."""

    attempt_id: str
    programme_key: str
    stage_key: str
    registration_period_key: str
    source_reference: str = ""
    authority: str = ""
    verification_status: str = "verified"
    pathway_key: str = ""


@dataclass(frozen=True)
class AcademicRecordCoverageEvidence:
    """Evidence about academic-result coverage for a course-code scope."""

    course_codes: tuple[str, ...]
    coverage_state: str
    source_reference: str = ""
    authority: str = ""
    verification_status: str = "verified"


@dataclass(frozen=True)
class CourseAttemptCoverageEvidence:
    """Evidence that all relevant attempts for exact course codes are covered."""

    course_codes: tuple[str, ...]
    coverage_state: str
    source_reference: str = ""
    authority: str = ""
    verification_status: str = "verified"


@dataclass(frozen=True)
class RequirementRecognitionEvidence:
    """A scoped institutional decision satisfying one governed requirement."""

    recognition_id: str
    student_id: str
    institution_id: str
    release_id: str
    programme_key: str
    target_requirement_id: str
    source_learning_identity: str
    authority: str
    source_reference: str
    verification_status: str = "unverified"
    pathway_key: str = ""


@dataclass(frozen=True)
class RequirementRecognitionCoverage:
    """Completeness of requirement-recognition decisions for a scoped target set."""

    student_id: str
    institution_id: str
    release_id: str
    programme_key: str
    requirement_ids: tuple[str, ...]
    coverage_state: str
    source_reference: str = ""
    authority: str = ""
    verification_status: str = "verified"
    pathway_key: str = ""


@dataclass(frozen=True)
class ExternalSubjectAchievementEvidence:
    evidence_id: str
    student_id: str
    qualification_system_id: str
    subject_id: str
    achievement_value: int | float | str
    authority: str
    source_reference: str
    verification_status: str = "unverified"
    credential_id: str = ""


@dataclass(frozen=True)
class ExternalSubjectAchievementCoverage:
    student_id: str
    qualification_system_id: str
    subject_ids: tuple[str, ...]
    coverage_state: str
    authority: str
    source_reference: str
    verification_status: str = "verified"


@dataclass(frozen=True)
class PriorQualificationEvidence:
    evidence_id: str
    student_id: str
    qualification_system_id: str
    qualification_id: str
    authority: str
    source_reference: str
    verification_status: str = "unverified"
    credential_id: str = ""


@dataclass(frozen=True)
class PriorQualificationCoverage:
    student_id: str
    qualification_system_id: str
    qualification_ids: tuple[str, ...]
    coverage_state: str
    authority: str
    source_reference: str
    verification_status: str = "verified"


@dataclass
class ChoiceGroup:
    label: str
    required: int
    courses: list[str]


@dataclass
class MajorDefinition:
    key: str
    name: str
    qualification: str
    required_courses: list[str]
    choice_groups: list[ChoiceGroup] = field(default_factory=list)
    faculty_owned: bool = True
    handbook_code: str = ""
    verification_status: str = "provisional"
    verification_notes: list[str] = field(default_factory=list)
    curriculum_rules: list[dict[str, Any]] = field(default_factory=list)
    stage_rules: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    required_co_majors: list[str] = field(default_factory=list)
    admission_limited: bool = False
    admission_note: str = ""
    award_rules: list[dict[str, Any]] = field(default_factory=list)
    source: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReadmissionThreshold:
    year: int
    minimum_passed_courses: int
    minimum_senior_courses: int = 0


@dataclass
class PathwayDefinition:
    """A stream, concentration, intake pattern, or professional specialisation.

    Structured Humanities qualifications frequently share a qualification code
    but prescribe different curricula.  A pathway keeps those alternatives
    inside one programme route without pretending that every stream has the
    same compulsory courses.
    """

    key: str
    name: str
    curriculum_rules: list[dict[str, Any]] = field(default_factory=list)
    required_courses: list[str] = field(default_factory=list)
    support_course_codes: list[str] = field(default_factory=list)
    verification_status: str = "verified"
    availability: str = "open"
    availability_note: str = ""
    progression_rules: list[dict[str, Any]] = field(default_factory=list)
    award_rules: list[dict[str, Any]] = field(default_factory=list)
    source: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProgrammeRules:
    key: str
    name: str
    total_nqf_credits: int
    level_7_nqf_credits: int
    semester_course_equivalents: int
    senior_course_equivalents: int
    humanities_course_equivalents: int
    required_majors: int
    required_humanities_majors: int
    max_courses_per_semester: float | None = None
    required_courses: list[str] = field(default_factory=list)
    minimum_duration_years: int = 3
    maximum_registration_years: int | None = None
    qualification_codes: list[str] = field(default_factory=list)
    major_keys: list[str] = field(default_factory=list)
    elective_course_codes: list[str] = field(default_factory=list)
    elective_departments: list[str] = field(default_factory=list)
    scope_verified: bool = False
    route_type: str = "regular"
    degree_category: str = ""
    readmission_thresholds: list[ReadmissionThreshold] = field(default_factory=list)
    introductory_course_options: list[str] = field(default_factory=list)
    introductory_courses_required: int = 0
    augmenting_courses_required: int = 0
    support_course_codes: list[str] = field(default_factory=list)
    programme_type: str = "general_degree"
    curriculum_rules: list[dict[str, Any]] = field(default_factory=list)
    pathways: dict[str, PathwayDefinition] = field(default_factory=dict)
    pathway_required: bool = False
    default_pathway_key: str = ""
    level_credit_requirements: dict[int, int] = field(default_factory=dict)
    availability: str = "open"
    availability_note: str = ""
    admission_notes: list[str] = field(default_factory=list)
    progression_notes: list[str] = field(default_factory=list)
    award_notes: list[str] = field(default_factory=list)
    progression_rules: list[dict[str, Any]] = field(default_factory=list)
    award_rules: list[dict[str, Any]] = field(default_factory=list)
    prerequisite_overrides: dict[str, list[str]] = field(default_factory=dict)
    co_requisite_overrides: dict[str, list[str]] = field(default_factory=dict)
    prerequisite_expression_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    source: dict[str, Any] = field(default_factory=dict)
    qualification_completion: dict[str, Any] = field(default_factory=dict)
    graduation_eligibility: dict[str, Any] = field(default_factory=dict)
    programme_entry_eligibility: dict[str, Any] = field(default_factory=dict)
    pathway_entry_eligibility: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass
class CourseFact:
    code: str
    name: str
    nqf_credits: int
    nqf_level: int
    prerequisites: list[str]
    offered: list[str]
    department: str
    description: str = ""
    prerequisites_verified: bool = True
    offering_verified: bool = True
    co_requisites: list[str] = field(default_factory=list)
    augmenting_course: str = ""
    augmenting: bool = False
    credit_bearing: bool = True
    counts_towards_general_degree: bool = True
    counts_as_humanities: bool = True
    counts_as_science: bool = False
    verification_status: str = "provisional"
    source: dict[str, Any] = field(default_factory=dict)
    general_elective: bool = True
    counts_towards_course_equivalents: bool = True
    recognition_note: str = ""
    prerequisite_expression: dict[str, Any] | None = None


@dataclass
class Catalogue:
    """Catalogue build metadata is distinct from its selected institutional release."""
    courses: dict[str, CourseFact]
    majors: dict[str, MajorDefinition]
    programmes: dict[str, ProgrammeRules]
    forbidden_combinations: list[tuple[str, str]]
    data_issues: list[str] = field(default_factory=list)
    faculty_key: str = ""
    programme_key: str = ""
    pathway_key: str = ""
    scope_status: str = "unscoped"
    elective_course_codes: set[str] = field(default_factory=set)
    cross_credit_exclusions: list[dict[str, Any]] = field(default_factory=list)
    source: str = ""
    catalogue_version: str = ""
    award_rules: list[dict[str, Any]] = field(default_factory=list)
    institution_release_id: str = ""

    @property
    def recognition_release_id(self) -> str:
        """Explicit release binding; unbound legacy catalogues retain their contract."""
        return self.institution_release_id or self.catalogue_version
