import inspect
from dataclasses import dataclass
from typing import Any

import pytest

from curriculum_reasoning_engine.institutions import ResultState
from engine.models import Catalogue, CourseFact, CourseResult, ProgrammeRules, StudentRecord
from engine.rule_engine import (
    _compute_exclusion_risk,
    _evaluate_repeated_item_failure,
    _repeated_item_failure_spec,
)


@dataclass(frozen=True, slots=True)
class SixtyPassGradingScheme:
    scheme_id: str = "university-two-60"
    institution_id: str = "university-two"

    def classify(self, result: CourseResult) -> ResultState:
        if result.mark is None:
            return ResultState.PENDING
        if result.mark >= 60:
            return ResultState.PASSED
        return ResultState.FAILED

    def is_passed(self, result: CourseResult) -> bool:
        return self.classify(result) is ResultState.PASSED

    def is_failed(self, result: CourseResult) -> bool:
        return self.classify(result) is ResultState.FAILED

    def is_pending(self, result: CourseResult) -> bool:
        return self.classify(result) is ResultState.PENDING


GRADING = SixtyPassGradingScheme()


def _course(code: str) -> CourseFact:
    return CourseFact(
        code=code,
        name=code,
        nqf_credits=99,
        nqf_level=0,
        prerequisites=[],
        offered=["Any"],
        department="Opaque",
    )


def _catalogue(rules: list[dict[str, Any]]) -> Catalogue:
    programme = ProgrammeRules(
        key="opaque_progression",
        name="Opaque Progression",
        total_nqf_credits=0,
        level_7_nqf_credits=0,
        semester_course_equivalents=0,
        senior_course_equivalents=0,
        humanities_course_equivalents=0,
        required_majors=0,
        required_humanities_majors=0,
        progression_rules=rules,
    )
    return Catalogue(
        courses={
            code: _course(code)
            for code in ["AAA100", "OLD-A", "NEW-X", "ALPHA", "D"]
        },
        majors={},
        programmes={programme.key: programme},
        forbidden_combinations=[],
        faculty_key="university_two",
        programme_key=programme.key,
        scope_status="verified",
    )


def _risk(
    results: list[CourseResult], rules: list[dict[str, Any]]
):
    return _compute_exclusion_risk(
        StudentRecord(
            "UTWO-REPEAT",
            "Opaque Student",
            "Opaque Progression",
            [],
            results,
            faculty_key="university_two",
            programme_key="opaque_progression",
            years_registered=3,
        ),
        _catalogue(rules),
        "opaque_progression",
        grading_scheme=GRADING,
    )


def _result(code: str, mark: int, year: int | None = None) -> CourseResult:
    return CourseResult(code, code, 0, 99, mark, "RAW", year)


def test_legacy_worked_case_a_two_failures_trigger_with_default_maximum():
    risk = _risk(
        [_result("AAA100", 40, 2024), _result("AAA100", 40, 2025)],
        [{"type": "repeat_failure", "label": "No repeated failures"}],
    )

    assert risk.at_risk
    assert risk.assessed
    assert risk.status == "verified"
    assert (
        "No repeated failures: more than 1 failed attempt(s) recorded for AAA100."
        in risk.reasons
    )


def test_legacy_worked_case_b_later_pass_does_not_reset_history():
    risk = _risk(
        [
            _result("AAA100", 40, 2024),
            _result("AAA100", 65, 2025),
            _result("AAA100", 40, 2026),
        ],
        [{"type": "repeat_failure", "label": "No repeated failures"}],
    )

    assert risk.at_risk
    assert "AAA100" in risk.reasons[0]


def test_legacy_worked_case_c_failures_need_not_be_consecutive():
    risk = _risk(
        [
            _result("AAA100", 65, 2024),
            _result("AAA100", 40, 2025),
            _result("AAA100", 40, 2026),
        ],
        [{"type": "repeat_failure", "label": "No repeated failures"}],
    )

    assert risk.at_risk
    assert "AAA100" in risk.reasons[0]


def test_legacy_worked_case_d_different_codes_do_not_merge():
    risk = _risk(
        [_result("OLD-A", 40, 2024), _result("NEW-X", 40, 2025)],
        [{"type": "repeat_failure", "label": "No repeated failures"}],
    )

    assert not risk.at_risk
    assert "OLD-A" not in risk.basis
    assert "NEW-X" not in risk.basis


def test_canonical_repeated_item_failure_supports_university_two_directly():
    risk = _risk(
        [
            _result("ALPHA", 40, None),
            _result("ALPHA", 65, None),
            _result("ALPHA", 40, None),
        ],
        [
            {
                "type": "repeated_item_failure",
                "label": "Exact institutional course failure limit",
                "identity_basis": "exact_course_code",
                "temporal_scope": "cumulative",
                "maximum_failures": 1,
            }
        ],
    )

    assert risk.at_risk
    assert risk.assessed
    assert (
        "Exact institutional course failure limit: repeated item(s) with more than 1 failed attempt(s): ALPHA."
        in risk.reasons
    )


def test_canonical_repeated_item_failure_requires_explicit_maximum():
    with pytest.raises(ValueError, match="requires maximum_failures"):
        _repeated_item_failure_spec(
            {
                "type": "repeated_item_failure",
                "identity_basis": "exact_course_code",
                "temporal_scope": "cumulative",
            },
            "Malformed policy",
        )


def test_unknown_identity_is_not_silently_treated_as_exact_code_or_manual():
    spec = _repeated_item_failure_spec(
        {
            "type": "repeated_item_failure",
            "identity_basis": "requirement",
            "temporal_scope": "cumulative",
            "maximum_failures": 1,
        },
        "Requirement-equivalence repeat policy",
    )

    assert spec is not None
    with pytest.raises(ValueError, match="Unsupported repeated-item failure identity"):
        _evaluate_repeated_item_failure(
            spec,
            StudentRecord(
                "UTWO-EQUIV",
                "Opaque Student",
                "Opaque Progression",
                [],
                [_result("OLD-A", 40, 2024), _result("NEW-X", 40, 2025)],
            ),
            GRADING,
        )


def test_ordering_does_not_change_repeated_item_failure_outcome():
    rule = {
        "type": "repeated_item_failure",
        "label": "Repeated item limit",
        "identity_basis": "exact_course_code",
        "temporal_scope": "cumulative",
        "maximum_failures": 1,
    }
    chronological = [
        _result("AAA100", 40, 2024),
        _result("D", 65, 2025),
        _result("AAA100", 40, 2026),
    ]
    shuffled = list(reversed(chronological))

    assert _risk(chronological, [rule]).reasons == _risk(shuffled, [rule]).reasons


def test_repeat_year_failure_preserves_current_distinct_transcript_pattern():
    risk = _risk(
        [
            _result("AAA100", 65, 2025),
            _result("AAA100", 65, 2026),
            _result("D", 40, 2026),
        ],
        [{"type": "repeat_year_failure", "label": "No failed course during a repeat year"}],
    )

    assert risk.at_risk
    assert (
        "No failed course during a repeat year: the latest year includes repeated course(s) (AAA100) "
        "and failed course(s) (D)."
    ) in risk.reasons


def test_repeated_item_failure_architecture_is_narrow_and_separate():
    compute_source = inspect.getsource(_compute_exclusion_risk)
    spec_source = inspect.getsource(_repeated_item_failure_spec)
    evaluator_source = inspect.getsource(_evaluate_repeated_item_failure)

    assert "repeat_failure" in spec_source
    assert "repeat_year_failure" in compute_source
    assert "repeat_year_failure" not in evaluator_source
    assert "failed_metric" not in spec_source
    assert "progression_ratio" not in spec_source
    assert "academic_year" not in evaluator_source
    assert "recognised" not in evaluator_source
    assert "uct_" not in evaluator_source.lower()
    assert "nqf" not in evaluator_source.lower()
