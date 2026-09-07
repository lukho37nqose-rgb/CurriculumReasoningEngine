from engine.completion import (
    CourseCompletionRecognitionInput,
    RecognitionEvidenceCoverage,
)
from engine.curriculum import CurriculumEvaluator
from engine.models import (
    AcademicRecordCoverageEvidence,
    Catalogue,
    CourseFact,
    CourseResult,
    ProgrammeRules,
    StudentRecord,
)


def _catalogue(codes=("A", "B", "C")):
    return Catalogue(
        courses={code: CourseFact(code, code, 15, 1, [], [], "TEST") for code in codes},
        majors={},
        programmes={"P": ProgrammeRules("P", "P", 0, 0, 0, 0, 0, 0, 0)},
        forbidden_combinations=[],
        faculty_key="test",
        catalogue_version="test",
        programme_key="P",
    )


def _evaluator(results=(), coverage=None):
    catalogue = _catalogue()
    student = StudentRecord("S", "Student", "P", [], list(results), "uct", "P")
    return CurriculumEvaluator(
        student,
        catalogue,
        completion_recognition=CourseCompletionRecognitionInput(
            (), (RecognitionEvidenceCoverage("S", "uct", "test", ("A", "B", "C"), "registry", "snapshot", "verified"),)
            if coverage is not None else (),
        ),
        academic_record_coverage_evidence=coverage,
    )


def _result(code, mark=70):
    return CourseResult(code, code, 1, 15, mark, None, 2026)


def _complete_coverage():
    return [AcademicRecordCoverageEvidence(("A", "B", "C"), "complete")]


def test_exact_course_omission_is_unresolved_without_coverage_and_negative_with_coverage():
    rule = {"type": "course", "course_codes": ["A"]}
    assert _evaluator().evaluate(rule).outcome == "unresolved"
    assert _evaluator(coverage=_complete_coverage()).evaluate(rule).outcome == "not_satisfied"


def test_positive_course_does_not_need_coverage():
    result = _evaluator([_result("A")]).evaluate({"type": "course", "course_codes": ["A"]})
    assert result.outcome == "satisfied"


def test_choose_n_uses_lower_and_upper_bounds():
    rule = {"type": "choose_n", "required": 2, "children": [
        {"type": "course", "course_codes": ["A"]},
        {"type": "course", "course_codes": ["B"]},
        {"type": "course", "course_codes": ["C"]},
    ]}
    satisfied = _evaluator([_result("A"), _result("B")]).evaluate(rule)
    assert satisfied.outcome == "satisfied"
    assert not satisfied.assessment_complete
    unresolved = _evaluator([_result("A")]).evaluate(rule)
    assert unresolved.outcome == "unresolved"
    impossible = _evaluator(coverage=_complete_coverage()).evaluate(rule)
    assert impossible.outcome == "not_satisfied"


def test_all_of_and_any_of_preserve_decisive_truth_with_unknown_siblings():
    all_of = {"type": "all_of", "children": [
        {"type": "course", "course_codes": ["A"]},
        {"type": "course", "course_codes": ["B"]},
    ]}
    any_of = {"type": "any_of", "children": [
        {"type": "course", "course_codes": ["A"]},
        {"type": "course", "course_codes": ["B"]},
    ]}
    assert _evaluator([_result("A")], coverage=_complete_coverage()).evaluate(all_of).outcome == "not_satisfied"
    any_result = _evaluator([_result("A")]).evaluate(any_of)
    assert any_result.outcome == "satisfied"
    assert not any_result.assessment_complete


def test_credit_bounds_are_monotonic_and_coverage_aware():
    minimum = {"type": "credit_pool", "course_codes": ["A", "B", "C"], "required": 30}
    maximum = {"type": "maximum_credit_pool", "course_codes": ["A", "B", "C"], "maximum": 30}
    low = _evaluator([_result("A")]).evaluate(minimum)
    assert low.outcome == "unresolved"
    high = _evaluator([_result("A"), _result("B"), _result("C")]).evaluate(minimum)
    assert high.outcome == "satisfied"
    max_unknown = _evaluator([_result("A")]).evaluate(maximum)
    assert max_unknown.outcome == "unresolved"
    max_violation = _evaluator([_result("A"), _result("B"), _result("C")]).evaluate(maximum)
    assert max_violation.outcome == "not_satisfied"
