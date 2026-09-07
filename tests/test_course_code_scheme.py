import inspect
import json
from dataclasses import dataclass
from pathlib import Path

from curriculum_reasoning_engine.institutions import (
    CourseCodeScheme,
    UCTCourseCodeScheme,
    get_institution_release,
)
from curriculum_reasoning_engine.institutions import coding as generic_coding
from engine.catalogue import _nqf_level_from_code, load_catalogue
from engine.models import Catalogue, CourseFact, CourseResult, ProgrammeRules, StudentRecord
from engine.planner import plan_next_semester
from engine.recognition import _course_year_level, recognised_credited_pairs
from engine.rule_engine import compute_report


@dataclass(frozen=True, slots=True)
class HostileOpaqueCodeScheme:
    scheme_id: str = "hostile-opaque"
    institution_id: str = "test"

    def infer_academic_level(self, code: str) -> int:
        raise AssertionError(f"Generic reasoning tried to infer level from {code}.")

    def infer_year_level(self, code: str) -> int:
        raise AssertionError(f"Generic reasoning tried to infer year from {code}.")

    def infer_department(self, code: str) -> str:
        raise AssertionError(f"Generic reasoning tried to infer department from {code}.")


@dataclass(frozen=True, slots=True)
class MusicLimitCodeScheme:
    scheme_id: str = "music-limit-opaque"
    institution_id: str = "test"

    def infer_academic_level(self, code: str) -> int:
        return 0

    def infer_year_level(self, code: str) -> int:
        return 1 if code.startswith("MUZOPAQUE") else 0

    def infer_department(self, code: str) -> str:
        return ""


@dataclass(frozen=True, slots=True)
class LoaderFallbackCodeScheme:
    scheme_id: str = "loader-fallback"
    institution_id: str = "test"

    def infer_academic_level(self, code: str) -> int:
        return 8 if code in {"VOID", "FALL"} else 0

    def infer_year_level(self, code: str) -> int:
        return 0

    def infer_department(self, code: str) -> str:
        return ""


def _course(code: str, level: int, credits: int = 10, prereqs=None) -> CourseFact:
    return CourseFact(
        code=code,
        name=code,
        nqf_credits=credits,
        nqf_level=level,
        prerequisites=list(prereqs or []),
        offered=["Semester 1"],
        department="Opaque",
    )


def _opaque_catalogue() -> Catalogue:
    alpha = _course("ALPHA", 5, 7)
    beta = _course("BETA", 6, 11, prereqs=["ALPHA"])
    gamma = _course("GAMMA", 7, 5)
    programme = ProgrammeRules(
        key="opaque",
        name="Opaque Programme",
        total_nqf_credits=23,
        level_7_nqf_credits=5,
        semester_course_equivalents=0,
        senior_course_equivalents=0,
        humanities_course_equivalents=0,
        required_majors=0,
        required_humanities_majors=0,
        required_courses=["ALPHA", "BETA", "GAMMA"],
        curriculum_rules=[
            {
                "type": "level_credits",
                "id": "opaque_advanced",
                "label": "Opaque advanced level",
                "nqf_level": 7,
                "required": 5,
            }
        ],
    )
    return Catalogue(
        courses={course.code: course for course in (alpha, beta, gamma)},
        majors={},
        programmes={programme.key: programme},
        forbidden_combinations=[],
        faculty_key="opaque",
        programme_key=programme.key,
        scope_status="verified",
    )


def _student(codes: list[str]) -> StudentRecord:
    return StudentRecord(
        "1",
        "Opaque Code Student",
        "Opaque Programme",
        [],
        [CourseResult(code, code, 0, 0, 70, "P", 2024) for code in codes],
        faculty_key="opaque",
        programme_key="opaque",
    )


def test_uct_release_exposes_course_code_scheme():
    release = get_institution_release("uct", "2026")

    assert isinstance(release.course_code_scheme, CourseCodeScheme)
    assert isinstance(release.course_code_scheme, UCTCourseCodeScheme)


def test_legacy_code_helpers_delegate_to_uct_scheme():
    scheme = UCTCourseCodeScheme()

    assert _nqf_level_from_code("PHI2043F") == scheme.infer_academic_level("PHI2043F")
    assert _course_year_level("MUZ3001S") == scheme.infer_year_level("MUZ3001S")


def test_loader_uses_explicit_level_before_institutional_code_fallback(tmp_path: Path):
    courses_path = tmp_path / "courses.json"
    requirements_path = tmp_path / "degree_requirements.json"
    courses_path.write_text(
        json.dumps(
            [
                {"code": "VOID", "name": "Void", "credits": 12, "nqf_level": 6},
                {"code": "FALL", "name": "Fallback", "credits": 12},
                {"code": "BLANK", "name": "Blank", "credits": 12},
            ]
        ),
        encoding="utf-8",
    )
    requirements_path.write_text(
        json.dumps(
            {
                "programmes": {
                    "opaque": {
                        "name": "Opaque",
                        "minimum_nqf_credits": 24,
                        "minimum_nqf_level_7_credits": 0,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    catalogue = load_catalogue(
        "opaque",
        courses_path=courses_path,
        requirements_path=requirements_path,
        course_code_scheme=LoaderFallbackCodeScheme(),
    )

    assert catalogue.courses["VOID"].nqf_level == 6
    assert catalogue.courses["FALL"].nqf_level == 8
    assert catalogue.courses["BLANK"].nqf_level == 0
    assert "BLANK has an invalid or unknown NQF level" in " ".join(
        catalogue.data_issues
    )


def test_opaque_codes_work_from_explicit_catalogue_facts_without_code_inference():
    catalogue = _opaque_catalogue()
    student = _student(["ALPHA", "BETA", "GAMMA"])
    scheme = HostileOpaqueCodeScheme()

    report = compute_report(student, catalogue, course_code_scheme=scheme)
    recommendations = plan_next_semester(
        _student(["ALPHA"]), catalogue, course_code_scheme=scheme
    )

    assert report.credits_completed == 23
    assert report.level_7_credits == 5
    requirements = {item.id: item for item in report.requirements}
    assert requirements["credits"].complete
    assert requirements["level7"].complete
    assert [item.code for item in recommendations] == ["BETA", "GAMMA"]


def test_music_year_limit_uses_institutional_code_scheme_for_opaque_codes():
    courses = {
        f"MUZOPAQUE{index}": _course(f"MUZOPAQUE{index}", 5)
        for index in range(6)
    }
    programme = ProgrammeRules(
        key="music",
        name="Music",
        total_nqf_credits=40,
        level_7_nqf_credits=0,
        semester_course_equivalents=0,
        senior_course_equivalents=0,
        humanities_course_equivalents=0,
        required_majors=0,
        required_humanities_majors=0,
    )
    catalogue = Catalogue(
        courses=courses,
        majors={},
        programmes={programme.key: programme},
        forbidden_combinations=[],
        faculty_key="uct_humanities",
        programme_key=programme.key,
    )
    student = StudentRecord(
        "1",
        "Music Student",
        "Music",
        [],
        [
            CourseResult(code, code, 5, 10, 70, "P", 2024)
            for code in sorted(courses)
        ],
    )

    recognised, exclusions = recognised_credited_pairs(
        student, catalogue, course_code_scheme=MusicLimitCodeScheme()
    )

    assert len(recognised) == 4
    assert [item.code for item in exclusions] == ["MUZOPAQUE4", "MUZOPAQUE5"]


def test_generic_course_code_contract_contains_no_uct_code_semantics():
    source = inspect.getsource(generic_coding)

    assert "UCT" not in source
    assert "nqf" not in source.lower()
    assert "re." not in source
    assert "isdigit" not in source
