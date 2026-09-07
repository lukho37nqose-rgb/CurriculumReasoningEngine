import inspect
from dataclasses import dataclass
from typing import Any

from curriculum_reasoning_engine.institutions import ResultState
from engine.curriculum import CurriculumEvaluator
from engine.knowledge_graph import KnowledgeGraph
from engine.models import (
    Catalogue,
    CourseFact,
    CourseResult,
    ProgrammeRules,
    ReadmissionThreshold,
    StudentRecord,
)
from engine.planner import plan_next_semester
from engine.reasoning import build_credit_reasoning_graph, passed_nqf_credits
from engine.rule_engine import compute_report
from engine.simulator import SimulationEngine


@dataclass(frozen=True, slots=True)
class SyntheticSixtyGradingScheme:
    scheme_id: str = "synthetic-60"
    institution_id: str = "test"

    def classify(self, result: Any) -> ResultState:
        mark = getattr(result, "mark", None)
        if mark is None:
            return ResultState.PENDING
        return ResultState.PASSED if mark >= 60 else ResultState.FAILED

    def is_passed(self, result: Any) -> bool:
        return self.classify(result) == ResultState.PASSED

    def is_failed(self, result: Any) -> bool:
        return self.classify(result) == ResultState.FAILED

    def is_pending(self, result: Any) -> bool:
        return self.classify(result) == ResultState.PENDING


SCHEME = SyntheticSixtyGradingScheme()


def _course(code: str, credits: int = 18, prereqs=None) -> CourseFact:
    return CourseFact(
        code=code,
        name=code,
        nqf_credits=credits,
        nqf_level=5,
        prerequisites=list(prereqs or []),
        offered=["Semester 1"],
        department=code[:3],
    )


def _catalogue() -> Catalogue:
    aaa = _course("AAA1001F")
    bbb = _course("BBB1001S", prereqs=["AAA1001F"])
    programme = ProgrammeRules(
        key="test_programme",
        name="Test Programme",
        total_nqf_credits=36,
        level_7_nqf_credits=0,
        semester_course_equivalents=0,
        senior_course_equivalents=0,
        humanities_course_equivalents=0,
        required_majors=0,
        required_humanities_majors=0,
        required_courses=["AAA1001F", "BBB1001S"],
        readmission_thresholds=[ReadmissionThreshold(year=1, minimum_passed_courses=1)],
        progression_rules=[
            {
                "type": "annual_credits",
                "label": "Annual credits",
                "minimum": 18,
            }
        ],
        curriculum_rules=[
            {
                "type": "course",
                "id": "aaa_passed",
                "label": "AAA passed",
                "course_codes": ["AAA1001F"],
                "blocking": True,
            }
        ],
    )
    return Catalogue(
        courses={aaa.code: aaa, bbb.code: bbb},
        majors={},
        programmes={programme.key: programme},
        forbidden_combinations=[],
        faculty_key="test",
        programme_key=programme.key,
        scope_status="verified",
    )


def _student(mark: int) -> StudentRecord:
    return StudentRecord(
        "1",
        "Synthetic Student",
        "Test Programme",
        [],
        [
            CourseResult(
                "AAA1001F",
                "AAA1001F",
                5,
                18,
                mark,
                "2-",
                2024,
            )
        ],
        faculty_key="test",
        programme_key="test_programme",
        years_registered=1,
    )


def test_synthetic_scheme_changes_recognition_credits_graduation_and_warnings():
    catalogue = _catalogue()
    fifty_five = _student(55)
    sixty_five = _student(65)

    failing_report = compute_report(fifty_five, catalogue, SCHEME)
    passing_report = compute_report(sixty_five, catalogue, SCHEME)

    assert failing_report.credits_completed == 0
    assert failing_report.failed_attempts == {"AAA1001F": 1}
    assert failing_report.graduation_status == "not_eligible"
    assert any("AAA1001F" in warning for warning in failing_report.warnings)
    assert failing_report.exclusion_risk.at_risk

    assert passing_report.credits_completed == 18
    assert passing_report.failed_attempts == {}
    assert not passing_report.exclusion_risk.at_risk


def test_synthetic_scheme_propagates_to_prerequisite_planning():
    catalogue = _catalogue()

    failed_recommendations = plan_next_semester(_student(55), catalogue, grading_scheme=SCHEME)
    passed_recommendations = plan_next_semester(_student(65), catalogue, grading_scheme=SCHEME)

    assert "BBB1001S" not in {item.code for item in failed_recommendations}
    assert "BBB1001S" in {item.code for item in passed_recommendations}


def test_synthetic_scheme_propagates_to_curriculum_evaluation():
    catalogue = _catalogue()
    rule = catalogue.programmes["test_programme"].curriculum_rules[0]

    failed = CurriculumEvaluator(_student(55), catalogue, SCHEME).evaluate(rule)
    passed = CurriculumEvaluator(_student(65), catalogue, SCHEME).evaluate(rule)

    assert not failed.complete
    assert passed.complete


def test_synthetic_scheme_propagates_to_reasoning_graphs():
    failed_graph = build_credit_reasoning_graph(_student(55), SCHEME)
    passed_graph = build_credit_reasoning_graph(_student(65), SCHEME)

    assert not failed_graph.conclusions["course_pass:AAA1001F"].result
    assert passed_graph.conclusions["course_pass:AAA1001F"].result
    assert passed_nqf_credits(_student(55), SCHEME).value == 0
    assert passed_nqf_credits(_student(65), SCHEME).value == 18


def test_synthetic_scheme_propagates_to_simulation():
    catalogue = _catalogue()
    engine = SimulationEngine(_student(55), catalogue, KnowledgeGraph(catalogue), SCHEME)

    report = engine.simulate_pass_course("BBB1001S", mark=55)
    assert report.failed_attempts == {"AAA1001F": 1, "BBB1001S": 1}
    assert report.credits_completed == 0

    report = engine.simulate_pass_course("BBB1001S", mark=65)
    assert report.failed_attempts == {"AAA1001F": 1}
    assert report.credits_completed == 18


def test_generic_modules_do_not_reintroduce_canonical_uct_grade_policy():
    import engine.models as models
    import engine.reasoning as reasoning

    generic_source = inspect.getsource(models) + inspect.getsource(reasoning)
    assert "TRANSCRIPT_PASS_MARK_50" not in generic_source
    assert "mark >= 50" not in generic_source
    assert "_PASS_GRADES" not in generic_source
    assert "DPR" not in generic_source
