import inspect

import pytest

from curriculum_reasoning_engine.adapters.transcripts.uct import UCTTranscriptAdapter
from curriculum_reasoning_engine.institutions import (
    GradingScheme,
    ResultState,
    UCTGradingScheme,
    get_institution_release,
)
from engine.catalogue import load_catalogue
from engine.models import CourseResult, StudentRecord
from engine.rule_engine import compute_report
from engine.scope import build_programme_scope

PASSING_TOKENS = ("1", "2+", "2-", "3", "P", "PA", "UP", "SP")
FAILING_TOKENS = (
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
)
PENDING_TOKENS = ("DE", "ATT", "GIP", "LOA", "OS", "", None, "unexpected")


def _result(mark=None, grade=None, code="AAA1001F") -> CourseResult:
    return CourseResult(code, "Course", 5, 18, mark, grade, 2024)


def test_generic_grading_contract_contains_no_uct_policy():
    source = inspect.getsource(ResultState) + inspect.getsource(GradingScheme)
    for token in ("DPR", "UF SM", "A/SF", "SP", "UP"):
        assert token not in source
    assert "50" not in source
    assert "uct" not in source.lower()


def test_uct_release_exposes_grading_scheme():
    release = get_institution_release("uct", "2026")
    assert isinstance(release.grading_scheme, GradingScheme)
    assert isinstance(release.grading_scheme, UCTGradingScheme)
    assert release.grading_scheme.scheme_id == "uct-2026"


@pytest.mark.parametrize(
    ("mark", "state"),
    [(50, ResultState.PASSED), (49, ResultState.FAILED), (0, ResultState.FAILED), (100, ResultState.PASSED)],
)
def test_uct_numeric_threshold_behaviour_is_unchanged(mark, state):
    assert UCTGradingScheme().classify(_result(mark=mark, grade=None)) == state


@pytest.mark.parametrize("token", PASSING_TOKENS)
def test_uct_passing_tokens_are_unchanged(token):
    result = _result(mark=None, grade=f" {token.lower()} ")
    assert UCTGradingScheme().classify(result) == ResultState.PASSED
    assert result.is_passed()


@pytest.mark.parametrize("token", FAILING_TOKENS)
def test_uct_failing_tokens_are_unchanged(token):
    result = _result(mark=None, grade=f" {token.lower()} ")
    assert UCTGradingScheme().classify(result) == ResultState.FAILED
    assert result.is_failed()


@pytest.mark.parametrize("token", PENDING_TOKENS)
def test_uct_pending_or_unrecognised_tokens_are_unchanged(token):
    result = _result(mark=None, grade=token)
    assert UCTGradingScheme().classify(result) == ResultState.PENDING
    assert result.is_pending()


def test_numeric_mark_precedence_over_status_token_is_unchanged():
    scheme = UCTGradingScheme()
    assert scheme.classify(_result(mark=49, grade="1")) == ResultState.FAILED
    assert scheme.classify(_result(mark=50, grade="F")) == ResultState.PASSED


def test_student_record_helpers_accept_explicit_grading_scheme_and_remain_compatible():
    scheme = UCTGradingScheme()
    student = StudentRecord(
        "123",
        "Student",
        "BA",
        [],
        [
            _result(45, "F", "AAA1001F"),
            _result(None, "DE", "BBB1001F"),
            _result(65, "2-", "AAA1001F"),
            _result(None, "PA", "CCC1001F"),
        ],
    )

    assert student.passed_codes() == student.passed_codes(scheme) == {"AAA1001F", "CCC1001F"}
    assert student.failed_codes() == student.failed_codes(scheme) == {"AAA1001F"}
    assert student.attempted_codes() == student.attempted_codes(scheme) == {
        "AAA1001F",
        "CCC1001F",
    }
    assert student.passed_result_for("AAA1001F", scheme).mark == 65
    assert [result.code for result in student.credited_results(scheme)] == [
        "AAA1001F",
        "CCC1001F",
    ]


def test_repeated_attempt_credit_and_report_outcome_are_unchanged_with_explicit_scheme():
    scheme = get_institution_release("uct", "2026").grading_scheme
    catalogue, _ = build_programme_scope(
        "uct_humanities",
        load_catalogue("uct_humanities"),
        programme_key="ba_regular",
    )
    student = StudentRecord(
        "123",
        "Student",
        "Bachelor of Arts",
        [],
        [
            CourseResult("POL1004F", "Introduction to Politics", 5, 18, 45, "F", 2024),
            CourseResult("POL1004F", "Introduction to Politics", 5, 18, 65, "2-", 2025),
            CourseResult("PHI1024F", "Introduction to Philosophy", 5, 18, None, "PA", 2025),
        ],
        faculty_key="uct_humanities",
        programme_key="ba_regular",
    )

    legacy_report = compute_report(student, catalogue)
    explicit_report = compute_report(student, catalogue, scheme)

    assert explicit_report.credits_completed == legacy_report.credits_completed
    assert explicit_report.failed_attempts == legacy_report.failed_attempts
    assert explicit_report.graduation_status == legacy_report.graduation_status


def test_uct_raw_status_parsing_and_grading_interpretation_have_separate_owners():
    adapter_source = inspect.getsource(UCTTranscriptAdapter)
    scheme_source = inspect.getsource(UCTGradingScheme)
    assert "grade" in adapter_source
    assert "DPR" in scheme_source
    assert "is_passed" not in adapter_source


def test_engine_models_no_longer_owns_uct_grade_policy():
    import engine.models as models

    source = inspect.getsource(models)
    assert "_PASS_GRADES" not in source
    assert "_FAIL_GRADES" not in source
    assert "_PENDING_GRADES" not in source
    assert "mark >= 50" not in source
    assert "DPR" not in source
