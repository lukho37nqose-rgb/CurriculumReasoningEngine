"""Pure data models for CurriculumAdvisor.

The catalogue stores handbook facts and provenance. It never stores a
student-specific conclusion such as "may graduate"; those views are computed
by the rule engine from a selected programme scope.
"""

from dataclasses import dataclass, field
from typing import Optional, Any

_PASS_GRADES = {"1", "2+", "2-", "3", "P", "PA", "UP", "SP"}
_FAIL_GRADES = {
    "F",
    "FS",
    "SF",
    "A/SF",
    "AB",
    "DPR",
    "INC",
    "EXA",
    "UF",
    "UF SM",
    "OSS",
}
_PENDING_GRADES = {"DE", "ATT", "GIP", "LOA", "OS", ""}


def _normalise_grade(value: Optional[str]) -> str:
    return " ".join(str(value or "").strip().upper().split())


@dataclass
class CourseResult:
    """A single course attempt appearing on a transcript."""

    code: str
    name: str
    nqf_level: int
    nqf_credits: int
    mark: Optional[int]
    grade: Optional[str]
    academic_year: Optional[int] = None

    def is_passed(self) -> bool:
        if self.mark is not None:
            return self.mark >= 50
        return _normalise_grade(self.grade) in _PASS_GRADES

    def is_failed(self) -> bool:
        if self.mark is not None:
            return self.mark < 50
        return _normalise_grade(self.grade) in _FAIL_GRADES

    def is_pending(self) -> bool:
        return not self.is_passed() and not self.is_failed()


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
    years_registered: Optional[int] = None

    def passed_codes(self) -> set[str]:
        return {r.code for r in self.results if r.is_passed()}

    def failed_codes(self) -> set[str]:
        return {r.code for r in self.results if r.is_failed()}

    def attempted_codes(self) -> set[str]:
        return {r.code for r in self.results if not r.is_pending()}

    def result_for(self, code: str) -> Optional[CourseResult]:
        for result in reversed(self.results):
            if result.code == code:
                return result
        return None

    def passed_result_for(self, code: str) -> Optional[CourseResult]:
        for result in reversed(self.results):
            if result.code == code and result.is_passed():
                return result
        return None

    def credited_results(self) -> list[CourseResult]:
        """Return one passing attempt per course code.

        A later pass replaces an earlier fail or duplicate pass. This preserves
        attempt history while preventing credit inflation.
        """
        credited: dict[str, CourseResult] = {}
        for result in self.results:
            if result.is_passed():
                credited[result.code] = result
        return list(credited.values())


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
    max_courses_per_semester: Optional[float] = None
    required_courses: list[str] = field(default_factory=list)
    minimum_duration_years: int = 3
    maximum_registration_years: Optional[int] = None
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
    source: dict[str, Any] = field(default_factory=dict)


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


@dataclass
class Catalogue:
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
