from dataclasses import dataclass
from typing import Any

from curriculum_reasoning_engine.institutions import (
    AcademicCreditFramework,
    UCTCreditFramework,
    get_institution_release,
)
from curriculum_reasoning_engine.institutions import credit_framework as generic_credit
from engine.curriculum import CurriculumEvaluator
from engine.knowledge_graph import KnowledgeGraph
from engine.models import Catalogue, CourseFact, CourseResult, ProgrammeRules, StudentRecord
from engine.planner import plan_next_semester
from engine.reasoning import build_credit_reasoning_graph, passed_nqf_credits
from engine.rule_engine import compute_report
from engine.simulator import SimulationEngine


@dataclass(frozen=True, slots=True)
class SyntheticCreditFramework:
    framework_id: str = "synthetic-non-nqf"
    institution_id: str = "test"

    credit_by_code: dict[str, int] = None
    level_by_code: dict[str, int] = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "credit_by_code",
            {"ALPHA": 7, "BETA": 11, "GAMMA": 5},
        )
        object.__setattr__(self, "level_by_code", {"ALPHA": 10, "BETA": 20, "GAMMA": 30})

    def credit_value(self, item: Any) -> int:
        return self.credit_by_code[item.code]

    def academic_level(self, item: Any) -> int:
        return self.level_by_code[item.code]

    def is_senior_level(self, item: Any) -> bool:
        return self.academic_level(item) >= 20

    def is_level(self, item: Any, level: int) -> bool:
        return level == 7 and self.academic_level(item) == 30


SYNTHETIC_CREDIT = SyntheticCreditFramework()


def _course(code: str, prereqs=None) -> CourseFact:
    return CourseFact(
        code=code,
        name=code,
        nqf_credits=1,
        nqf_level=0,
        prerequisites=list(prereqs or []),
        offered=["Semester 1"],
        department="Synthetic",
    )


def _catalogue() -> Catalogue:
    alpha = _course("ALPHA")
    beta = _course("BETA", prereqs=["ALPHA"])
    gamma = _course("GAMMA")
    programme = ProgrammeRules(
        key="synthetic",
        name="Synthetic Programme",
        total_nqf_credits=18,
        level_7_nqf_credits=5,
        semester_course_equivalents=0,
        senior_course_equivalents=1,
        humanities_course_equivalents=0,
        required_majors=0,
        required_humanities_majors=0,
        required_courses=["ALPHA", "BETA", "GAMMA"],
        curriculum_rules=[
            {
                "type": "level_credits",
                "id": "synthetic_level_7",
                "label": "Synthetic advanced level",
                "nqf_level": 7,
                "required": 5,
            },
            {
                "type": "credit_pool",
                "id": "synthetic_pool",
                "label": "Synthetic pool",
                "course_codes": ["ALPHA", "BETA"],
                "required": 18,
            },
        ],
    )
    return Catalogue(
        courses={course.code: course for course in (alpha, beta, gamma)},
        majors={},
        programmes={programme.key: programme},
        forbidden_combinations=[],
        faculty_key="synthetic",
        programme_key=programme.key,
        scope_status="verified",
    )


def _student(codes: list[str]) -> StudentRecord:
    return StudentRecord(
        "1",
        "Synthetic Credit Student",
        "Synthetic Programme",
        [],
        [
            CourseResult(code, code, 0, 1, 70, "P", 2024)
            for code in codes
        ],
        faculty_key="synthetic",
        programme_key="synthetic",
    )


def test_uct_release_exposes_credit_framework():
    release = get_institution_release("uct", "2026")
    assert isinstance(release.credit_framework, AcademicCreditFramework)
    assert isinstance(release.credit_framework, UCTCreditFramework)


def test_synthetic_framework_changes_report_credit_level_and_senior_conclusions():
    catalogue = _catalogue()
    student = _student(["ALPHA", "BETA", "GAMMA"])

    legacy_report = compute_report(student, catalogue)
    synthetic_report = compute_report(
        student,
        catalogue,
        credit_framework=SYNTHETIC_CREDIT,
    )

    assert legacy_report.credits_completed == 3
    assert legacy_report.level_7_credits == 0
    assert synthetic_report.credits_completed == 23
    assert synthetic_report.level_7_credits == 5
    requirements = {item.id: item for item in synthetic_report.requirements}
    assert requirements["senior"].current == 2


def test_synthetic_framework_controls_planning_prerequisite_and_senior_filtering():
    catalogue = _catalogue()
    student = _student(["ALPHA"])

    legacy = plan_next_semester(student, catalogue)
    synthetic = plan_next_semester(
        student,
        catalogue,
        credit_framework=SYNTHETIC_CREDIT,
    )

    assert "BETA" not in {item.code for item in legacy}
    assert "BETA" in {item.code for item in synthetic}


def test_synthetic_framework_controls_curriculum_credit_and_level_rules():
    catalogue = _catalogue()
    student = _student(["ALPHA", "BETA", "GAMMA"])
    rules = catalogue.programmes["synthetic"].curriculum_rules

    legacy = CurriculumEvaluator(student, catalogue).evaluate_many(rules)
    synthetic = CurriculumEvaluator(
        student,
        catalogue,
        credit_framework=SYNTHETIC_CREDIT,
    ).evaluate_many(rules)

    assert [row.complete for row in legacy] == [False, False]
    assert [row.complete for row in synthetic] == [True, True]


def test_synthetic_framework_controls_reasoning_graphs_and_simulation():
    catalogue = _catalogue()
    student = _student(["ALPHA"])

    legacy_graph = build_credit_reasoning_graph(student)
    synthetic_graph = build_credit_reasoning_graph(
        student,
        credit_framework=SYNTHETIC_CREDIT,
    )
    assert legacy_graph.conclusions["credit_awarded:ALPHA"].current == 1
    assert synthetic_graph.conclusions["credit_awarded:ALPHA"].current == 7
    assert passed_nqf_credits(student, credit_framework=SYNTHETIC_CREDIT).value == 7

    simulator = SimulationEngine(
        student,
        catalogue,
        KnowledgeGraph(catalogue),
        credit_framework=SYNTHETIC_CREDIT,
    )
    report = simulator.simulate_pass_course("BETA", mark=70)
    assert report.credits_completed == 18


def test_generic_credit_contract_contains_no_nqf_or_uct_policy():
    import inspect

    source = inspect.getsource(generic_credit.AcademicCreditFramework)
    assert "nqf" not in source.lower()
    assert "uct" not in source.lower()
    assert ">= 6" not in source
