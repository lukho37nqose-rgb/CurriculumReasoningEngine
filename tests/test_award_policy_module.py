"""Boundary and compatibility cases for the selected-set policy extraction."""

import ast
import inspect
import subprocess
import sys
from dataclasses import asdict, replace

import pytest

from engine import award_policy, curriculum, framework_adapters, rule_engine, utils
from engine.models import (
    AuthorisedAwardCourseSelection,
    Catalogue,
    CourseFact,
    CourseResult,
    MajorDefinition,
    StudentRecord,
)


class Load:
    def __init__(self, values=None):
        self.values = values or {}

    def load_equivalent(self, item):
        return self.values.get(item.code, 1.0)


class Credit:
    def credit_value(self, item):
        return {"A": 2, "B": 6}.get(item.code, 0)

    def is_senior_level(self, item):
        return item.code != "LOW"

    def is_level(self, item, level):
        return level == 42 and item.code in {"A", "B"}


def case():
    codes = ["A", "B", "C", "LOW", "OUT"]
    courses = {code: CourseFact(code, code, 10, 5 if code == "LOW" else 7, [], [], "Unit") for code in codes}
    major = MajorDefinition("major", "Major", "UNIT", ["A", "B", "C", "LOW"], verification_status="verified")
    catalogue = Catalogue(courses, {"major": major}, {}, [], catalogue_version="v1")
    student = StudentRecord(
        "S", "Student", "Programme", [], [CourseResult(code, code, 7, 10, 80, None) for code in codes]
    )
    rule = {
        "id": "policy",
        "required_load_equivalents": 2,
        "advanced_level": 7,
        "required_advanced_load_equivalents": 2,
        "minimum_average": 75,
        "advanced_minimum_average": 75,
        "minimum_individual_mark": 60,
        "first_attempt_only": True,
        "weighting": {"basis": "course_load_equivalent"},
        "selection_boundary": {"maximum": 2, "status": "discretionary"},
    }
    return rule, major, student, catalogue


def selection(codes=("A", "B"), version="v1"):
    return AuthorisedAwardCourseSelection(
        "policy", "major", tuple(codes), "Authority", "Source", catalogue_version=version
    )


def evaluate(data=None, *, selections=None, load=None, credit=None):
    rule, major, student, catalogue = data or case()
    return award_policy.standard_subject_award(
        rule,
        major,
        True,
        ["A", "B", "C"],
        student=student,
        catalogue=catalogue,
        grading_scheme=None,
        credit_framework=credit,
        course_load_framework=load or Load(),
        selections=selections or [],
    )


def test_import_and_dependency_boundary():
    subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            "import sys; import engine.award_policy; assert 'engine.rule_engine' not in sys.modules; assert 'engine.award' not in sys.modules",
        ],
        check=True,
    )
    for name in (
        "Report",
        "MajorProgress",
        "Distinction",
        "EvaluationContext",
        "CurriculumEvaluator",
        "QualificationAwardEvidence",
    ):
        assert not hasattr(award_policy, name)
    assert rule_engine.SubjectDistinction is award_policy.SubjectDistinction
    assert award_policy.SubjectDistinction.__module__ == "engine.award_policy"
    definitions = {
        n.name
        for n in ast.parse(inspect.getsource(award_policy)).body
        if isinstance(n, (ast.ClassDef, ast.FunctionDef))
    }
    assert definitions == {
        "SubjectDistinction",
        "marked_result",
        "first_attempt_pass",
        "weighted_average",
        "subject_record",
        "average_for_basis",
        "standard_subject_award",
    }
    assert award_policy._combine_status is curriculum._combine_status
    assert award_policy._credit_value is framework_adapters._credit_value
    assert award_policy._load_equivalent is framework_adapters._load_equivalent
    assert award_policy._course_weight is utils._course_weight


def test_independent_evaluation_and_unchanged_row_contract():
    row = evaluate(selections=[selection()])
    assert row.eligible and row.status == "verified"
    assert row.average == 80 and row.senior_courses_assessed == 2
    assert row.major_key == "major" and row.policy_id == "policy"
    assert set(asdict(row)) == {
        "major",
        "average",
        "senior_courses_assessed",
        "eligible",
        "status",
        "reason",
        "major_key",
        "policy_id",
    }
    assert row == rule_engine.SubjectDistinction(**asdict(row))


def test_identical_matching_selections_still_conflict():
    row = evaluate(selections=[selection(), selection()])
    assert not row.eligible and row.status == "conflict"
    assert "Multiple authorised course selections" in row.reason


@pytest.mark.parametrize(
    "codes,message",
    [
        ((" a ", "A"), "duplicate course codes"),
        (("A", "UNKNOWN"), "unknown course(s)"),
        (("A", "OUT"), "outside the governed major pool"),
        (("A", "LOW"), "non-senior course(s)"),
    ],
)
def test_invalid_selection_keeps_existing_outcome(codes, message):
    row = evaluate(selections=[selection(codes)])
    assert not row.eligible and row.status == "unverified"
    assert message in row.reason


def test_missing_selection_excess_load_and_version_wildcard():
    missing = evaluate()
    assert not missing.eligible and missing.status == "discretionary"
    assert "Authorised selection is required" in missing.reason
    assert evaluate(selections=[selection(version="wrong")]) == missing
    assert evaluate(selections=[selection(version="")]) == evaluate(selections=[selection()])


def test_repeated_unselected_senior_course_still_blocks_first_attempt_policy():
    data = case()
    before = evaluate(data, selections=[selection()])
    data[2].results.insert(0, CourseResult("C", "C", 7, 10, 40, None))
    after = evaluate(data, selections=[selection()])
    assert before.eligible
    assert not after.eligible and after.status == "verified"
    assert after.average == before.average
    assert after.senior_courses_assessed == 2


@pytest.mark.parametrize("basis", ["equal", "credit_value", "course_load_equivalent", "unsupported-basis"])
def test_custom_framework_eligibility_keeps_legacy_display_average(basis):
    data = case()
    data[2].results[0].mark = 70
    data[2].results[1].mark = 90
    data[0].update(
        advanced_level=42, minimum_average=84, advanced_minimum_average=84, weighting={"basis": basis}
    )
    row = evaluate(data, selections=[selection()], load=Load({"A": 1, "B": 3}), credit=Credit())
    assert row.eligible is (basis != "equal")
    assert row.average == 80  # Legacy display weights remain independent of eligibility weights.


def test_display_rounding_does_not_round_eligibility_threshold():
    data = case()
    data[2].results[0].mark = 74.96
    data[2].results[1].mark = 74.96
    row = evaluate(data, selections=[selection()])
    assert row.average == 75.0
    assert not row.eligible and row.status == "verified"


def test_last_passing_result_and_exactly_one_nonpending_attempt():
    _, _, student, _ = case()
    original = student.results[0]
    student.results.extend([replace(original, mark=90), replace(original, mark=40)])
    assert award_policy.marked_result("A", student=student, grading_scheme=None).mark == 90
    assert not award_policy.first_attempt_pass("A", student=student, grading_scheme=None)
    student.results.append(replace(original, mark=None, grade="P"))
    assert award_policy.marked_result("A", student=student, grading_scheme=None) is None
