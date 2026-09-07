import inspect
from dataclasses import dataclass
from typing import Any

from curriculum_reasoning_engine.institutions import (
    CourseLoadFramework,
    UCTCourseLoadFramework,
    get_institution_release,
)
from curriculum_reasoning_engine.institutions import course_load as generic_load
from engine import curriculum, planner
from engine.models import Catalogue, CourseFact, CourseResult, ProgrammeRules, StudentRecord
from engine.rule_engine import (
    _compute_course_equivalents,
    _compute_distinction,
    _compute_exclusion_risk,
    compute_report,
)
from engine.utils import _course_weight


@dataclass(frozen=True, slots=True)
class SyntheticCreditFramework:
    framework_id: str = "synthetic-credit"
    institution_id: str = "test"

    def credit_value(self, item: Any) -> int:
        return {"ALPHA": 10, "BETA": 10, "GAMMA": 30}[item.code]

    def academic_level(self, item: Any) -> int:
        return {"ALPHA": 10, "BETA": 20, "GAMMA": 20}[item.code]

    def is_senior_level(self, item: Any) -> bool:
        return self.academic_level(item) == 20

    def is_level(self, item: Any, level: int) -> bool:
        return level == 7 and item.code == "GAMMA"


@dataclass(frozen=True, slots=True)
class SyntheticLoadFramework:
    framework_id: str = "synthetic-load"
    institution_id: str = "test"

    def load_equivalent(self, item: Any) -> float:
        return {"ALPHA": 0.5, "BETA": 2.0, "GAMMA": 1.0}[item.code]


@dataclass(frozen=True, slots=True)
class AlternateLoadFramework:
    framework_id: str = "alternate-load"
    institution_id: str = "test"

    def load_equivalent(self, item: Any) -> float:
        return {"ALPHA": 0.5, "BETA": 2.0, "GAMMA": 2.0}[item.code]


CREDIT = SyntheticCreditFramework()
LOAD = SyntheticLoadFramework()
ALT_LOAD = AlternateLoadFramework()


def _course(code: str, level: int, credits: int) -> CourseFact:
    return CourseFact(
        code=code,
        name=code,
        nqf_credits=credits,
        nqf_level=level,
        prerequisites=[],
        offered=["Semester 1"],
        department="Opaque",
    )


def _catalogue() -> Catalogue:
    programme = ProgrammeRules(
        key="load",
        name="Load Programme",
        total_nqf_credits=20,
        level_7_nqf_credits=0,
        semester_course_equivalents=2,
        senior_course_equivalents=2,
        humanities_course_equivalents=0,
        required_majors=0,
        required_humanities_majors=0,
        curriculum_rules=[
            {
                "type": "course_count",
                "id": "two_courses",
                "label": "Two explicit courses",
                "course_codes": ["ALPHA", "GAMMA"],
                "required": 2,
            },
            {
                "type": "passed_mark_equivalents",
                "id": "mark_equivalents",
                "label": "Marked load equivalents",
                "course_codes": ["ALPHA", "GAMMA"],
                "minimum_mark": 60,
                "required": 2.0,
            },
        ],
        progression_rules=[
            {
                "type": "annual_credits",
                "label": "Annual credit threshold",
                "minimum": 20,
            },
            {
                "type": "annual_course_equivalents",
                "label": "Annual load threshold",
                "minimum": 2.0,
            },
        ],
    )
    return Catalogue(
        courses={
            "ALPHA": _course("ALPHA", 5, 10),
            "BETA": _course("BETA", 6, 10),
            "GAMMA": _course("GAMMA", 7, 30),
        },
        majors={},
        programmes={programme.key: programme},
        forbidden_combinations=[],
        faculty_key="opaque",
        programme_key=programme.key,
        scope_status="verified",
    )


def _student(codes: list[str], mark: int = 70) -> StudentRecord:
    return StudentRecord(
        "1",
        "Synthetic Load Student",
        "Load Programme",
        [],
        [
            CourseResult(code, code, 0, 0, mark, "P", 2024)
            for code in codes
        ],
        faculty_key="opaque",
        programme_key="load",
        years_registered=1,
    )


def test_uct_release_exposes_course_load_framework():
    release = get_institution_release("uct", "2026")

    assert isinstance(release.course_load_framework, CourseLoadFramework)
    assert isinstance(release.course_load_framework, UCTCourseLoadFramework)


def test_legacy_course_weight_delegates_to_uct_load_framework():
    framework = UCTCourseLoadFramework()

    assert _course_weight("PHI1024F") == framework.load_equivalent("PHI1024F") == 1.0
    assert _course_weight("PVL1003W") == framework.load_equivalent("PVL1003W") == 2.0
    assert _course_weight("OPAQUE") == framework.load_equivalent("OPAQUE") == 1.0


def test_credit_totals_and_load_totals_are_independent_for_opaque_codes():
    catalogue = _catalogue()
    student = _student(["ALPHA", "GAMMA"])

    report = compute_report(
        student,
        catalogue,
        credit_framework=CREDIT,
        course_load_framework=LOAD,
    )
    requirements = {item.id: item for item in report.requirements}

    assert report.credits_completed == 40
    assert report.semester_course_equivalents == 1.5
    assert requirements["credits"].complete
    assert not requirements["courses"].complete


def test_load_framework_changes_load_requirements_without_changing_credit_or_count():
    catalogue = _catalogue()
    student = _student(["ALPHA", "GAMMA"])

    low_load = compute_report(
        student,
        catalogue,
        credit_framework=CREDIT,
        course_load_framework=LOAD,
    )
    high_load = compute_report(
        student,
        catalogue,
        credit_framework=CREDIT,
        course_load_framework=ALT_LOAD,
    )
    low_requirements = {item.id: item for item in low_load.requirements}
    high_requirements = {item.id: item for item in high_load.requirements}

    assert low_load.credits_completed == high_load.credits_completed == 40
    assert low_load.semester_course_equivalents == 1.5
    assert high_load.semester_course_equivalents == 2.5
    assert low_requirements["curriculum:two_courses"].complete
    assert high_requirements["curriculum:two_courses"].complete
    assert not low_requirements["curriculum:mark_equivalents"].complete
    assert high_requirements["curriculum:mark_equivalents"].complete


def test_progression_load_rules_use_load_framework_but_credit_rules_do_not():
    catalogue = _catalogue()
    student = _student(["ALPHA", "GAMMA"])

    low_risk = compute_report(
        student,
        catalogue,
        credit_framework=CREDIT,
        course_load_framework=LOAD,
    ).exclusion_risk
    high_risk = compute_report(
        student,
        catalogue,
        credit_framework=CREDIT,
        course_load_framework=ALT_LOAD,
    ).exclusion_risk

    assert any("Annual load threshold" in reason for reason in low_risk.reasons)
    assert not any("Annual credit threshold" in reason for reason in low_risk.reasons)
    assert not high_risk.at_risk


def test_generic_course_load_contract_contains_no_uct_suffix_policy():
    source = inspect.getsource(generic_load)

    assert "UCT" not in source
    assert '"W"' not in source
    assert '"F"' not in source
    assert "suffix" not in source.lower()


def test_generic_migrated_paths_do_not_call_legacy_course_weight_directly():
    assert "_course_weight" not in inspect.getsource(_compute_course_equivalents)
    assert "_course_weight" not in inspect.getsource(_compute_exclusion_risk)
    assert "_course_weight" not in inspect.getsource(planner.plan_next_semester)
    assert "_course_weight" not in inspect.getsource(curriculum.CurriculumEvaluator)
    assert "_course_weight" in inspect.getsource(_compute_distinction)
