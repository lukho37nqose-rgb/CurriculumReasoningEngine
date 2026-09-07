from curriculum_reasoning_engine.institutions.achievement import NumericAchievementScheme
from curriculum_reasoning_engine.institutions.grading import ResultState
from engine.models import Catalogue, CourseAttemptCoverageEvidence, CourseFact, CourseResult, StudentRecord
from engine.prerequisites import PrerequisiteEvaluator


class Grading:
    def classify(self, result):
        if result.mark is None:
            return ResultState.PENDING
        return ResultState.PASSED if result.mark >= 12 else ResultState.FAILED

    def is_passed(self, result): return self.classify(result) == ResultState.PASSED
    def is_failed(self, result): return self.classify(result) == ResultState.FAILED
    def is_pending(self, result): return self.classify(result) == ResultState.PENDING


def _catalogue():
    return Catalogue(
        courses={"PRE-A": CourseFact("PRE-A", "Preparation", 6, 1, [], [], "core")},
        majors={}, programmes={}, forbidden_combinations=[],
    )


def _student(*marks):
    return StudentRecord(
        "S", "Student", "route", [],
        [CourseResult("PRE-A", "Preparation", 1, 6, mark, None, attempt_id=f"a{i}") for i, mark in enumerate(marks)],
    )


def _evaluate(student, *, coverage=None, expression=None):
    return PrerequisiteEvaluator(
        student, _catalogue(), Grading(),
        achievement_scheme=NumericAchievementScheme(0, 20, "northstar-0-20", "northstar"),
        course_attempt_coverage_evidence=coverage,
    ).evaluate(expression or {
        "type": "course_achievement", "course_code": "PRE-A", "comparator": "gt",
        "threshold": 15, "attempt_selection": "any_qualifying_attempt",
    })


def test_non_percentage_scheme_separates_pass_from_achievement():
    assert _evaluate(_student(13)).outcome == "unresolved"
    assert _evaluate(_student(13), coverage=[CourseAttemptCoverageEvidence(("PRE-A",), "complete")]).outcome == "not_satisfied"
    assert _evaluate(_student(16)).outcome == "satisfied"


def test_any_qualifying_attempt_is_explicit_and_monotonic():
    assert _evaluate(_student(14, 16)).outcome == "satisfied"
    assert _evaluate(_student(16, 14)).outcome == "satisfied"


def test_markless_pass_does_not_satisfy_achievement():
    result = _evaluate(_student(None), coverage=[CourseAttemptCoverageEvidence(("PRE-A",), "complete")])
    assert result.outcome == "unresolved"


def test_recognition_is_not_used_as_achievement_evidence():
    result = _evaluate(_student(), coverage=[CourseAttemptCoverageEvidence(("PRE-A",), "complete")])
    assert result.outcome == "not_satisfied"


def test_comparators_are_policy_owned():
    assert _evaluate(_student(15), expression={
        "type": "course_achievement", "course_code": "PRE-A", "comparator": "gte",
        "threshold": 15, "attempt_selection": "any_qualifying_attempt",
    }).outcome == "satisfied"
