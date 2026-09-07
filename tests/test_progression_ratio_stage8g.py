import inspect
from dataclasses import dataclass
from typing import Any

from curriculum_reasoning_engine.institutions import ResultState
from engine.models import Catalogue, CourseFact, CourseResult, ProgrammeRules, StudentRecord
from engine.rule_engine import (
    _compute_exclusion_risk,
    _progression_ratio_spec,
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


@dataclass(frozen=True, slots=True)
class OpaqueCreditFramework:
    framework_id: str = "opaque-credit"
    institution_id: str = "university-two"

    def credit_value(self, item: Any) -> int:
        return {
            "A": 36,
            "B": 6,
            "C": 6,
            "D": 6,
            "PENDING": 12,
            "DIRECT_ONLY": 40,
            "CATALOGUE_ONLY": 10,
        }[item.code]

    def academic_level(self, item: Any) -> str:
        return "opaque"

    def is_senior_level(self, item: Any) -> bool:
        return False

    def is_level(self, item: Any, level: int) -> bool:
        return False


GRADING = SixtyPassGradingScheme()
CREDIT = OpaqueCreditFramework()


def _course(code: str) -> CourseFact:
    return CourseFact(
        code=code,
        name=code,
        nqf_credits=1,
        nqf_level=0,
        prerequisites=[],
        offered=["Any"],
        department="Opaque",
    )


def _catalogue(
    rules: list[dict[str, Any]], *, include_direct_only: bool = True
) -> Catalogue:
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
    codes = ["A", "B", "C", "D", "PENDING", "CATALOGUE_ONLY"]
    if include_direct_only:
        codes.append("DIRECT_ONLY")
    return Catalogue(
        courses={code: _course(code) for code in codes},
        majors={},
        programmes={programme.key: programme},
        forbidden_combinations=[],
        faculty_key="university_two",
        programme_key=programme.key,
        scope_status="verified",
    )


def _risk(
    rules: list[dict[str, Any]],
    results: list[CourseResult],
    *,
    include_direct_only: bool = True,
):
    return _compute_exclusion_risk(
        StudentRecord(
            "UTWO-RATIO",
            "Opaque Student",
            "Opaque Progression",
            [],
            results,
            faculty_key="university_two",
            programme_key="opaque_progression",
            years_registered=1,
        ),
        _catalogue(rules, include_direct_only=include_direct_only),
        "opaque_progression",
        grading_scheme=GRADING,
        credit_framework=CREDIT,
    )


def _result(code: str, mark: int | None, year: int | None = 2026) -> CourseResult:
    return CourseResult(code, code, 0, 1, mark, "R", year)


def test_worked_regression_credit_ratio_and_course_fraction_diverge():
    results = [
        _result("A", 40),
        _result("B", 70),
        _result("C", 70),
        _result("D", 70),
    ]
    pass_rate = _risk(
        [{"type": "pass_rate", "label": "Annual pass rate", "minimum": 0.8}],
        results,
    )
    failed_fraction = _risk(
        [
            {
                "type": "failed_course_fraction",
                "label": "Annual failed fraction",
                "threshold": 0.5,
            }
        ],
        results,
    )

    assert pass_rate.at_risk
    assert "33.3% of annual attempted credits passed" in pass_rate.reasons[0]
    assert not failed_fraction.at_risk
    assert "annual failed-course proportion is 25.0%" in failed_fraction.basis


def test_same_code_attempt_order_is_preserved_for_legacy_ratio_rules():
    fail_then_pass = [_result("A", 40), _result("A", 70), _result("B", 70)]
    pass_then_fail = [_result("A", 70), _result("A", 40), _result("B", 70)]

    pass_rate = _risk(
        [{"type": "pass_rate", "label": "Pass rate", "minimum": 0.8}],
        fail_then_pass,
    )
    fraction_pass_last = _risk(
        [
            {
                "type": "failed_course_fraction",
                "label": "Failed fraction",
                "threshold": 0.5,
            }
        ],
        fail_then_pass,
    )
    fraction_fail_last = _risk(
        [
            {
                "type": "failed_course_fraction",
                "label": "Failed fraction",
                "threshold": 0.5,
            }
        ],
        pass_then_fail,
    )

    assert pass_rate.at_risk
    assert "53.8% of annual attempted credits passed" in pass_rate.reasons[0]
    assert not fraction_pass_last.at_risk
    assert "annual failed-course proportion is 0.0%" in fraction_pass_last.basis
    assert fraction_fail_last.at_risk
    assert "1 of 2 course(s) failed" in fraction_fail_last.reasons[0]


def test_pending_results_are_excluded_and_pending_only_denominator_is_unresolved():
    mixed = [_result("PENDING", None), _result("B", 70), _result("C", 40)]
    pass_rate = _risk(
        [{"type": "pass_rate", "label": "Pass rate", "minimum": 0.4}],
        mixed,
    )
    failed_fraction = _risk(
        [
            {
                "type": "failed_course_fraction",
                "label": "Failed fraction",
                "threshold": 0.5,
            }
        ],
        mixed,
    )
    pending_only = _risk(
        [{"type": "pass_rate", "label": "Pass rate", "minimum": 0.7}],
        [_result("PENDING", None)],
    )

    assert not pass_rate.at_risk
    assert "annual pass rate meets 40%" in pass_rate.basis
    assert failed_fraction.at_risk
    assert "1 of 2 course(s) failed" in failed_fraction.reasons[0]
    assert not pending_only.assessed
    assert "annual attempted credits are unavailable" in pending_only.basis


def test_canonical_progression_ratio_supports_university_two_failed_credit_ratio():
    risk = _risk(
        [
            {
                "type": "progression_ratio",
                "label": "Failed credit ratio",
                "temporal_scope": "latest_academic_year",
                "temporal_anchor": "recognised_or_provisional",
                "numerator": {
                    "metric_basis": "credit_value",
                    "identity": "attempt",
                    "result_population": "failed",
                    "evidence_population": "direct_results",
                },
                "denominator": {
                    "metric_basis": "credit_value",
                    "identity": "attempt",
                    "result_population": "attempted_non_pending",
                    "evidence_population": "direct_results",
                },
                "comparison": "gte",
                "threshold": 0.3,
            }
        ],
        [_result("A", 40), _result("B", 70), _result("PENDING", None)],
    )

    assert risk.at_risk
    assert "ratio is 85.7%" in risk.reasons[0]


def test_canonical_progression_ratio_supports_passed_distinct_course_ratio():
    risk = _risk(
        [
            {
                "type": "progression_ratio",
                "label": "Passed course ratio",
                "temporal_scope": "latest_academic_year",
                "temporal_anchor": "recognised_or_provisional",
                "numerator": {
                    "metric_basis": "course_count",
                    "identity": "distinct_course",
                    "distinct_course_resolution": "last_observed",
                    "result_population": "passed",
                    "evidence_population": "direct_results",
                },
                "denominator": {
                    "metric_basis": "course_count",
                    "identity": "distinct_course",
                    "distinct_course_resolution": "last_observed",
                    "result_population": "completed_non_pending",
                    "evidence_population": "direct_results",
                },
                "comparison": "lt",
                "threshold": 0.7,
            }
        ],
        [_result("A", 40), _result("A", 70), _result("B", 70), _result("C", 40)],
    )

    assert risk.at_risk
    assert "ratio is 66.7%" in risk.reasons[0]


def test_evidence_population_is_rule_owned_for_ratio_selectors():
    rules = [
        {
            "type": "progression_ratio",
            "label": "Direct evidence ratio",
            "temporal_scope": "latest_academic_year",
            "temporal_anchor": "recognised_or_provisional",
            "numerator": {
                "metric_basis": "credit_value",
                "identity": "attempt",
                "result_population": "failed",
                "evidence_population": "direct_results",
            },
            "denominator": {
                "metric_basis": "credit_value",
                "identity": "attempt",
                "result_population": "attempted_non_pending",
                "evidence_population": "direct_results",
            },
            "comparison": "gte",
            "threshold": 0.5,
        },
        {
            "type": "progression_ratio",
            "label": "Recognised evidence ratio",
            "temporal_scope": "latest_academic_year",
            "temporal_anchor": "recognised_or_provisional",
            "numerator": {
                "metric_basis": "credit_value",
                "identity": "attempt",
                "result_population": "failed",
                "evidence_population": "recognised_or_provisional",
            },
            "denominator": {
                "metric_basis": "credit_value",
                "identity": "attempt",
                "result_population": "attempted_non_pending",
                "evidence_population": "recognised_or_provisional",
            },
            "comparison": "gte",
            "threshold": 0.5,
        },
    ]

    risk = _risk(
        rules,
        [_result("DIRECT_ONLY", 40), _result("CATALOGUE_ONLY", 70)],
        include_direct_only=False,
    )

    assert any("Direct evidence ratio: ratio is 80.0%" in item for item in risk.reasons)
    assert "Recognised evidence ratio: ratio is 0.0%." in risk.basis


def test_legacy_ratio_aliases_translate_to_explicit_progression_ratio_specs():
    pass_rate = _progression_ratio_spec(
        {"type": "pass_rate", "minimum": 0.8}, "Pass rate"
    )
    failed_fraction = _progression_ratio_spec(
        {"type": "failed_course_fraction", "threshold": 0.5}, "Failed fraction"
    )

    assert pass_rate is not None
    assert failed_fraction is not None
    assert pass_rate.numerator.metric_basis == "credit_value"
    assert pass_rate.denominator.result_population == "attempted_non_pending"
    assert pass_rate.comparison == "lt"
    assert failed_fraction.numerator.identity == "distinct_course"
    assert failed_fraction.numerator.distinct_course_resolution == "last_observed"
    assert failed_fraction.denominator.evidence_population == "direct_results"
    assert failed_fraction.comparison == "gte"


def test_progression_ratio_architecture_keeps_scope_narrow_and_explicit():
    import engine.rule_engine as rule_engine

    source = inspect.getsource(rule_engine._compute_exclusion_risk)
    ratio_source = inspect.getsource(rule_engine._evaluate_progression_ratio)
    selector_source = inspect.getsource(rule_engine._progression_ratio_selector_value)
    repeated_spec_source = inspect.getsource(rule_engine._repeated_item_failure_spec)

    assert "pass_rate" not in source
    assert "failed_course_fraction" not in source
    assert "CourseLoadFramework" not in ratio_source
    assert "uct_" not in ratio_source.lower()
    assert "ebe" not in ratio_source.lower()
    assert "health" not in ratio_source.lower()
    assert "nqf" not in selector_source.lower()
    assert "repeat_failure" in repeated_spec_source
    assert "repeat_year_failure" in source
