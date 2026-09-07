import inspect
from dataclasses import dataclass
from typing import Any

from curriculum_reasoning_engine.institutions import ResultState
from engine import rule_engine
from engine.models import Catalogue, CourseFact, CourseResult, ProgrammeRules, StudentRecord
from engine.rule_engine import (
    _compute_exclusion_risk,
    _evaluate_failed_progression_metric,
    _failed_progression_metric_spec,
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
class OpaqueLoadFramework:
    framework_id: str = "opaque-load"
    institution_id: str = "university-two"

    def load_equivalent(self, item: Any) -> float:
        return {
            "ALPHA": 0.5,
            "BETA": 3.0,
            "GAMMA": 1.25,
            "OLD-A": 2.0,
            "NEW-X": 2.0,
        }[item.code]


GRADING = SixtyPassGradingScheme()
LOAD = OpaqueLoadFramework()


def _course(code: str, credits: int = 99) -> CourseFact:
    return CourseFact(
        code=code,
        name=code,
        nqf_credits=credits,
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
        courses={code: _course(code) for code in ["ALPHA", "BETA", "GAMMA", "OLD-A", "NEW-X"]},
        majors={},
        programmes={programme.key: programme},
        forbidden_combinations=[],
        faculty_key="university_two",
        programme_key=programme.key,
        scope_status="verified",
    )


def _student(*, include_years: bool = True, include_equivalent_pair: bool = False) -> StudentRecord:
    def year(value: int) -> int | None:
        return value if include_years else None

    results = [
        CourseResult("ALPHA", "ALPHA", 0, 99, 40, "LOW", year(2024)),
        CourseResult("ALPHA", "ALPHA", 0, 99, 40, "LOW", year(2025)),
        CourseResult("BETA", "BETA", 0, 99, 40, "LOW", year(2025)),
        CourseResult("ALPHA", "ALPHA", 0, 99, 65, "CLEAR", year(2026)),
        CourseResult("GAMMA", "GAMMA", 0, 99, 40, "LOW", year(2026)),
    ]
    if include_equivalent_pair:
        results.extend(
            [
                CourseResult("OLD-A", "OLD-A", 0, 99, 40, "LOW", year(2025)),
                CourseResult("NEW-X", "NEW-X", 0, 99, 40, "LOW", year(2025)),
            ]
        )
    return StudentRecord(
        "UTWO-FAIL",
        "Opaque Student",
        "Opaque Progression",
        [],
        results,
        faculty_key="university_two",
        programme_key="opaque_progression",
        years_registered=3,
    )


def _risk(rules: list[dict[str, Any]], student: StudentRecord | None = None):
    return _compute_exclusion_risk(
        student or _student(),
        _catalogue(rules),
        "opaque_progression",
        grading_scheme=GRADING,
        course_load_framework=LOAD,
    )


def test_failed_metric_direct_cumulative_attempt_load_counts_historical_failures():
    risk = _risk(
        [
            {
                "type": "failed_metric",
                "label": "Cumulative failed attempt load",
                "metric_basis": "course_load_equivalent",
                "identity": "attempt",
                "temporal_scope": "cumulative",
                "threshold": 5,
            }
        ]
    )

    assert risk.at_risk
    assert "failed course load equivalent is 5.25" in risk.reasons[0]


def test_failed_metric_direct_attempt_count_and_distinct_count_are_different():
    attempt = _risk(
        [
            {
                "type": "failed_metric",
                "label": "Failed attempts",
                "metric_basis": "course_count",
                "identity": "attempt",
                "temporal_scope": "cumulative",
                "threshold": 4,
            }
        ]
    )
    distinct = _risk(
        [
            {
                "type": "failed_metric",
                "label": "Distinct failed courses",
                "metric_basis": "course_count",
                "identity": "distinct_course",
                "temporal_scope": "cumulative",
                "threshold": 4,
            }
        ]
    )

    assert attempt.at_risk
    assert not distinct.at_risk
    assert "failed course count is 4" in attempt.reasons[0]
    assert "failed course count is 3" in distinct.basis


def test_failed_metric_direct_latest_year_uses_distinct_failures_only():
    risk = _risk(
        [
            {
                "type": "failed_metric",
                "label": "Latest failed courses",
                "metric_basis": "course_count",
                "identity": "distinct_course",
                "temporal_scope": "latest_academic_year",
                "threshold": 1,
            }
        ]
    )

    assert risk.at_risk
    assert "failed course count is 1" in risk.reasons[0]
    assert "ALPHA" not in risk.reasons[0]


def test_failed_metric_direct_load_uses_course_load_not_credit_values():
    risk = _risk(
        [
            {
                "type": "failed_metric",
                "label": "Latest failed load",
                "metric_basis": "course_load_equivalent",
                "identity": "distinct_course",
                "temporal_scope": "latest_academic_year",
                "threshold": 2,
            }
        ]
    )

    assert not risk.at_risk
    assert "failed course load equivalent is 1.25" in risk.basis
    assert "99" not in risk.basis


def test_failed_metric_direct_supports_governed_course_pool_filter():
    risk = _risk(
        [
            {
                "type": "failed_metric",
                "label": "BETA-only failures",
                "metric_basis": "course_count",
                "identity": "distinct_course",
                "temporal_scope": "cumulative",
                "threshold": 1,
                "filters": {"course_codes": ["BETA"]},
            }
        ]
    )

    assert risk.at_risk
    assert "GAMMA" not in risk.reasons[0]


def test_failed_metric_direct_does_not_invent_requirement_equivalence_identity():
    risk = _risk(
        [
            {
                "type": "failed_metric",
                "label": "Narrative equivalent codes",
                "metric_basis": "course_count",
                "identity": "distinct_course",
                "temporal_scope": "cumulative",
                "threshold": 5,
            }
        ],
        _student(include_equivalent_pair=True),
    )

    assert risk.at_risk
    assert "failed course count is 5" in risk.reasons[0]


def test_legacy_failed_aliases_translate_to_failed_metric_specs():
    expected = {
        "cumulative_failed_course_equivalents": (
            "course_load_equivalent",
            "attempt",
            "cumulative",
            {},
        ),
        "failed_course_equivalents": (
            "course_load_equivalent",
            "distinct_course",
            "latest_academic_year",
            {},
        ),
        "failed_course_count": (
            "course_count",
            "distinct_course",
            "latest_academic_year",
            {"course_codes": ["GAMMA"]},
        ),
        "failed_any": (
            "course_count",
            "distinct_course",
            "cumulative",
            {"course_codes": ["ALPHA"]},
        ),
    }

    for rule_type, spec_tuple in expected.items():
        raw = {"type": rule_type, "threshold": 1}
        if rule_type in {"failed_course_count", "failed_any"}:
            raw["course_codes"] = spec_tuple[3]["course_codes"]
        spec = _failed_progression_metric_spec(raw, rule_type)
        assert spec is not None
        assert (
            spec.metric_basis,
            spec.identity,
            spec.temporal_scope,
            spec.filters,
        ) == spec_tuple


def test_legacy_cumulative_failed_equivalents_keeps_attempt_identity_and_wording():
    risk = _risk(
        [
            {
                "type": "cumulative_failed_course_equivalents",
                "label": "Legacy cumulative failed load",
                "threshold": 5,
            }
        ]
    )

    assert risk.at_risk
    assert (
        "Legacy cumulative failed load: 5.25 failed semester-course equivalent attempt(s) are recorded"
        in risk.reasons[0]
    )


def test_legacy_failed_course_equivalents_keeps_latest_year_distinct_course_behavior():
    risk = _risk(
        [
            {
                "type": "failed_course_equivalents",
                "label": "Legacy latest failed load",
                "threshold": 2,
            }
        ]
    )

    assert not risk.at_risk
    assert "Legacy latest failed load: 1.25 failed equivalent(s) is below 2." in risk.basis


def test_legacy_failed_course_count_keeps_latest_year_pool_behavior():
    risk = _risk(
        [
            {
                "type": "failed_course_count",
                "label": "Legacy pool failed count",
                "threshold": 1,
                "course_codes": ["GAMMA"],
            }
        ]
    )

    assert risk.at_risk
    assert (
        "Legacy pool failed count: 1 distinct course(s) failed in 2026; the published risk threshold is 1."
        in risk.reasons[0]
    )


def test_legacy_failed_any_preserves_cumulative_governed_pool_existence_behavior():
    risk = _risk(
        [
            {
                "type": "failed_any",
                "label": "Legacy failed any",
                "course_codes": ["ALPHA", "BETA"],
            }
        ]
    )

    assert risk.at_risk
    assert "Legacy failed any: failed course(s): ALPHA, BETA." in risk.reasons


def test_missing_year_evidence_for_latest_failed_metrics_remains_unverified():
    risk = _risk(
        [
            {
                "type": "failed_course_count",
                "label": "Latest failures",
                "threshold": 1,
            }
        ],
        _student(include_years=False),
    )

    assert not risk.assessed
    assert risk.status == "unverified"
    assert "academic-year labels are required to isolate failures" in risk.basis


def test_grouped_failures_reuse_failed_metric_without_changing_group_semantics():
    risk = _risk(
        [
            {
                "type": "failed_courses_by_group",
                "label": "Grouped failures",
                "groups": [
                    {"label": "Core", "threshold": 1, "course_codes": ["GAMMA"]},
                    {"label": "Other", "threshold": 2, "course_codes": ["ALPHA", "BETA"]},
                ],
            }
        ]
    )

    assert risk.at_risk
    assert "Grouped failures: Core (1 failed: GAMMA)." in risk.reasons


def test_failed_metric_helper_uses_grading_scheme_for_failed_state():
    spec = _failed_progression_metric_spec(
        {
            "type": "failed_metric",
            "metric_basis": "course_count",
            "identity": "attempt",
            "temporal_scope": "cumulative",
            "threshold": 1,
        },
        "Failure state",
    )

    assert spec is not None
    result = _evaluate_failed_progression_metric(
        spec,
        StudentRecord(
            "UTWO-PASS",
            "Opaque Student",
            "Opaque Progression",
            [],
            [CourseResult("ALPHA", "ALPHA", 0, 99, 55, "LOW", 2026)],
        ),
        2026,
        GRADING,
        LOAD,
    )

    assert result.value == 1


def test_failed_metric_architecture_keeps_ratio_and_repeat_rules_out_of_scope():
    source = inspect.getsource(_compute_exclusion_risk)
    spec_source = inspect.getsource(_failed_progression_metric_spec)
    evaluator_source = inspect.getsource(_evaluate_failed_progression_metric)
    repeated_spec_source = inspect.getsource(rule_engine._repeated_item_failure_spec)

    assert "repeat_failure" in repeated_spec_source
    assert "repeat_year_failure" in source
    assert "failed_course_fraction" not in spec_source
    assert "pass_rate" not in spec_source
    assert "repeat_failure" not in spec_source
    assert "repeat_year_failure" not in spec_source
    assert "uct_" not in evaluator_source.lower()
    assert "nqf" not in evaluator_source.lower()
    assert "semester" not in evaluator_source.lower()
