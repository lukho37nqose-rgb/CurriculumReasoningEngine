import inspect
from dataclasses import dataclass
from typing import Any

from curriculum_reasoning_engine.institutions import ResultState
from engine.models import Catalogue, CourseFact, CourseResult, ProgrammeRules, StudentRecord
from engine.rule_engine import (
    _accumulated_progression_metric_spec,
    _compute_exclusion_risk,
)


@dataclass(frozen=True, slots=True)
class SixtyPassGradingScheme:
    scheme_id: str = "university-two-60"
    institution_id: str = "university-two"

    def classify(self, result: CourseResult) -> ResultState:
        if result.mark is not None and result.mark >= 60:
            return ResultState.PASSED
        if result.mark is not None:
            return ResultState.FAILED
        return ResultState.PENDING

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
        return {"ORBIT": 11, "LANTERN": 19, "QUARTZ": 7}[item.code]

    def academic_level(self, item: Any) -> str:
        return {"ORBIT": "foundation", "LANTERN": "advanced", "QUARTZ": "advanced"}[
            item.code
        ]

    def is_senior_level(self, item: Any) -> bool:
        return self.academic_level(item) == "advanced"

    def is_level(self, item: Any, level: int) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class OpaqueLoadFramework:
    framework_id: str = "opaque-load"
    institution_id: str = "university-two"

    def load_equivalent(self, item: Any) -> float:
        return {"ORBIT": 2.0, "LANTERN": 0.5, "QUARTZ": 1.25}[item.code]


GRADING = SixtyPassGradingScheme()
CREDIT = OpaqueCreditFramework()
LOAD = OpaqueLoadFramework()


def _course(code: str, *, science: bool = False, general: bool = True) -> CourseFact:
    return CourseFact(
        code=code,
        name=code,
        nqf_credits=1,
        nqf_level=0,
        prerequisites=[],
        offered=["Any"],
        department="Opaque",
        counts_as_science=science,
        counts_towards_general_degree=general,
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
            "ORBIT": _course("ORBIT"),
            "LANTERN": _course("LANTERN", science=True),
            "QUARTZ": _course("QUARTZ", science=True),
        },
        majors={},
        programmes={programme.key: programme},
        forbidden_combinations=[],
        faculty_key="university_two",
        programme_key=programme.key,
        scope_status="verified",
    )


def _student(mark: int = 65, *, include_years: bool = True) -> StudentRecord:
    year = 2026 if include_years else None
    return StudentRecord(
        "UTWO-1",
        "Opaque Student",
        "Opaque Progression",
        [],
        [
            CourseResult("ORBIT", "ORBIT", 0, 0, mark, "CLEAR", year),
            CourseResult("LANTERN", "LANTERN", 0, 0, mark, "CLEAR", year),
            CourseResult("QUARTZ", "QUARTZ", 0, 0, 55, "LOW", 2025 if include_years else None),
        ],
        faculty_key="university_two",
        programme_key="opaque_progression",
        years_registered=1,
    )


def _risk(rules: list[dict[str, Any]], student: StudentRecord | None = None):
    catalogue = _catalogue(rules)
    return _compute_exclusion_risk(
        student or _student(),
        catalogue,
        "opaque_progression",
        grading_scheme=GRADING,
        credit_framework=CREDIT,
        course_load_framework=LOAD,
    )


def test_canonical_accumulated_metric_supports_credit_and_load_without_uct_aliases():
    risk = _risk(
        [
            {
                "type": "accumulated_metric",
                "label": "Cumulative credit",
                "metric_basis": "credit_value",
                "temporal_scope": "cumulative",
                "minimum": 30,
            },
            {
                "type": "accumulated_metric",
                "label": "Cumulative load",
                "metric_basis": "course_load_equivalent",
                "temporal_scope": "cumulative",
                "minimum": 3.0,
            },
        ]
    )

    assert not any("Cumulative credit" in reason for reason in risk.reasons)
    assert any("Cumulative load" in reason for reason in risk.reasons)
    assert "accumulated course load equivalent" in risk.reasons[0]


def test_canonical_accumulated_metric_supports_latest_academic_year_scope():
    risk = _risk(
        [
            {
                "type": "accumulated_metric",
                "label": "Latest-year credit",
                "metric_basis": "credit_value",
                "temporal_scope": "latest_academic_year",
                "minimum": 31,
            },
            {
                "type": "accumulated_metric",
                "label": "Latest-year load",
                "metric_basis": "course_load_equivalent",
                "temporal_scope": "latest_academic_year",
                "minimum": 2.4,
            },
        ]
    )

    assert any("Latest-year credit" in reason for reason in risk.reasons)
    assert not any("Latest-year load" in reason for reason in risk.reasons)


def test_canonical_accumulated_metric_supports_senior_filter_from_credit_framework():
    risk = _risk(
        [
            {
                "type": "accumulated_metric",
                "label": "Senior credit",
                "metric_basis": "credit_value",
                "temporal_scope": "cumulative",
                "filters": {"senior": True},
                "minimum": 20,
            },
            {
                "type": "accumulated_metric",
                "label": "Senior load",
                "metric_basis": "course_load_equivalent",
                "temporal_scope": "cumulative",
                "filters": {"senior": True},
                "minimum": 2.0,
            },
        ]
    )

    assert any("Senior credit" in reason for reason in risk.reasons)
    assert any("Senior load" in reason for reason in risk.reasons)


def test_missing_year_evidence_for_canonical_annual_scope_remains_unverified():
    risk = _risk(
        [
            {
                "type": "accumulated_metric",
                "label": "Annual opaque credits",
                "metric_basis": "credit_value",
                "temporal_scope": "latest_academic_year",
                "minimum": 1,
            }
        ],
        _student(include_years=False),
    )

    assert not risk.assessed
    assert risk.status == "unverified"
    assert "academic-year labels" in risk.basis


def test_legacy_progression_aliases_translate_to_accumulated_metric_specs():
    expected = {
        "cumulative_credits": ("credit_value", "cumulative", {}),
        "science_cumulative_credits": ("credit_value", "cumulative", {"science": True}),
        "senior_cumulative_credits": ("credit_value", "cumulative", {"senior": True}),
        "course_equivalents_cumulative": (
            "course_load_equivalent",
            "cumulative",
            {"counts_towards_general_degree": True},
        ),
        "senior_course_equivalents_cumulative": (
            "course_load_equivalent",
            "cumulative",
            {"counts_towards_general_degree": True, "senior": True},
        ),
        "annual_credits": ("credit_value", "latest_academic_year", {}),
        "annual_course_equivalents": (
            "course_load_equivalent",
            "latest_academic_year",
            {"counts_towards_general_degree": True},
        ),
    }

    for rule_type, spec_tuple in expected.items():
        spec = _accumulated_progression_metric_spec(
            {"type": rule_type, "minimum": 1}, rule_type
        )
        assert spec is not None
        assert (spec.metric_basis, spec.temporal_scope, spec.filters) == spec_tuple


def test_science_compatibility_alias_uses_catalogue_science_flag_only():
    risk = _risk(
        [
            {
                "type": "science_cumulative_credits",
                "label": "Legacy Science alias",
                "minimum": 25,
            }
        ]
    )

    assert any("Legacy Science alias" in reason for reason in risk.reasons)
    assert "recognised Science credits" in risk.reasons[0]


def test_general_degree_filter_remains_legacy_alias_compatibility_only():
    legacy = _accumulated_progression_metric_spec(
        {"type": "course_equivalents_cumulative", "minimum": 1},
        "Legacy general-degree load",
    )
    canonical = _accumulated_progression_metric_spec(
        {
            "type": "accumulated_metric",
            "metric_basis": "course_load_equivalent",
            "temporal_scope": "cumulative",
            "minimum": 1,
        },
        "Canonical unrestricted load",
    )

    assert legacy is not None
    assert canonical is not None
    assert legacy.filters == {"counts_towards_general_degree": True}
    assert canonical.filters == {}


def test_accumulated_metric_architecture_keeps_failed_progression_rules_out_of_scope():
    source = inspect.getsource(_compute_exclusion_risk)
    helper_source = inspect.getsource(_accumulated_progression_metric_spec)

    assert "failed_course_equivalents" not in helper_source
    assert "cumulative_failed_course_equivalents" not in helper_source
    assert "uct_science" not in helper_source
    assert "Semester 1" not in helper_source
    assert "_course_weight" not in source
