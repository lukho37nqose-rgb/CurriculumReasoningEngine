import copy
import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from engine.catalogue import load_catalogue
from engine.models import CourseResult, StudentRecord
from engine.recognition import provisional_open_credit_results
from engine.rule_engine import (
    _compute_exclusion_risk,
    _evaluate_progression_policy,
    _evaluate_progression_ratio,
    _progression_ratio_spec,
)
from tools import build_ebe_2026

BAS_POLICY_ID = "UCT-EBE-2026-BAS-ANNUAL-PASS-RATE"
BAS_SOURCE_REFERENCE = "2026 EBE Undergraduate Handbook, page 22, Programmes of Study"


@dataclass(frozen=True, slots=True)
class SyntheticCreditFramework:
    values: dict[str, int]

    def credit_value(self, item: Any) -> int:
        return self.values.get(item.code, item.nqf_credits)

    def academic_level(self, item: Any) -> int:
        return item.nqf_level

    def is_senior_level(self, item: Any) -> bool:
        return False

    def is_level(self, item: Any, level: int) -> bool:
        return item.nqf_level == level


def _catalogue():
    return load_catalogue("uct_ebe")


def _bas_policy(catalogue) -> dict[str, Any]:
    policies = [
        rule
        for rule in catalogue.programmes["bas"].progression_rules
        if rule.get("type") == "progression_policy"
    ]
    assert len(policies) == 1
    return policies[0]


def _student(results: list[CourseResult], *, years_registered: int | None = 3):
    return StudentRecord(
        "EBE-8U",
        "BAS Progression",
        "BAS",
        [],
        results,
        "uct_ebe",
        "bas",
        "",
        years_registered,
    )


def _result(
    catalogue,
    code: str,
    mark: int | None,
    *,
    year: int | None = 2026,
    credits: int | None = None,
    attempt_id: str = "",
) -> CourseResult:
    fact = catalogue.courses.get(code)
    if fact is None:
        return CourseResult(code, code, 0, credits or 0, mark, None, year, attempt_id)
    return CourseResult(
        code,
        fact.name,
        fact.nqf_level,
        credits if credits is not None else fact.nqf_credits,
        mark,
        None,
        year,
        attempt_id,
    )


def _policy_result(
    catalogue,
    results: list[CourseResult],
    *,
    credit_framework: SyntheticCreditFramework | None = None,
):
    return _evaluate_progression_policy(
        _bas_policy(catalogue),
        student=_student(results),
        catalogue=catalogue,
        latest_year=2026,
        grading_scheme=None,
        credit_framework=credit_framework,
        course_code_scheme=None,
        course_load_framework=None,
        stage_repeat_evidence=None,
        result_context_evidence=None,
        programme_key="bas",
        pathway_key="",
    )


def _legacy_pass_rate_result(
    catalogue,
    results: list[CourseResult],
    *,
    credit_framework: SyntheticCreditFramework | None = None,
):
    legacy = {
        "type": "pass_rate",
        "label": "Pass at least 80% of annual registered credits",
        "minimum": 0.8,
    }
    spec = _progression_ratio_spec(legacy, legacy["label"])
    assert spec is not None
    student = _student(results)
    provisional = provisional_open_credit_results(
        student, catalogue, None, credit_framework, None
    )
    return _evaluate_progression_ratio(
        spec, student, catalogue, provisional, 2026, None, credit_framework
    )


def _policy_only_catalogue(catalogue):
    scoped = copy.deepcopy(catalogue)
    scoped.programmes["bas"].progression_rules = [_bas_policy(catalogue)]
    return scoped


def _policy_only_risk(catalogue, results: list[CourseResult]):
    scoped = _policy_only_catalogue(catalogue)
    return _compute_exclusion_risk(_student(results), scoped, "bas")


def test_bas_pass_rate_policy_data_shape():
    catalogue = _catalogue()
    policy = _bas_policy(catalogue)
    condition = policy["condition"]

    assert policy["type"] == "progression_policy"
    assert policy["policy_id"] == BAS_POLICY_ID
    assert policy["verification_status"] == "unverified"
    assert policy["source_reference"] == BAS_SOURCE_REFERENCE
    assert condition["type"] == "progression_ratio"
    assert condition["temporal_scope"] == "latest_academic_year"
    assert condition["temporal_anchor"] == "recognised_or_provisional"
    assert condition["comparison"] == "lt"
    assert condition["threshold"] == 0.8
    assert condition["numerator"] == {
        "metric_basis": "credit_value",
        "identity": "attempt",
        "result_population": "passed",
        "evidence_population": "recognised_or_provisional",
    }
    assert condition["denominator"] == {
        "metric_basis": "credit_value",
        "identity": "attempt",
        "result_population": "attempted_non_pending",
        "evidence_population": "recognised_or_provisional",
    }
    assert policy["consequence"]["type"] == "advisory_risk"
    assert policy["consequence"]["type"] not in {
        "review_required",
        "progression_ineligible",
    }


def test_bas_progression_rules_have_no_duplicate_legacy_pass_rate():
    catalogue = _catalogue()
    rules = catalogue.programmes["bas"].progression_rules

    assert [rule["type"] for rule in rules] == [
        "failed_any",
        "repeat_failure",
        "progression_policy",
        "maximum_years",
    ]
    assert all(rule.get("type") != "pass_rate" for rule in rules)
    assert any(
        rule.get("type") == "annual_credits"
        for key, programme in catalogue.programmes.items()
        if key != "bas"
        for rule in programme.progression_rules
    )


def test_ebe_builder_reproduces_bas_policy_and_stable_id():
    catalogue = _catalogue()
    first = build_ebe_2026.bas_annual_pass_rate_policy(
        build_ebe_2026.ebe_source_reference(22)
    )
    second = build_ebe_2026.bas_annual_pass_rate_policy(
        build_ebe_2026.ebe_source_reference(22)
    )

    assert first == second
    assert first == _bas_policy(catalogue)
    assert first["policy_id"] == BAS_POLICY_ID
    changed = copy.deepcopy(first)
    changed["condition"]["threshold"] = 0.7
    assert changed["policy_id"] == first["policy_id"]


def test_bas_policy_matches_legacy_pass_rate_above_equal_and_below_threshold():
    catalogue = _catalogue()
    cases = [
        (
            [_result(catalogue, "APG1003W", 75), _result(catalogue, "APG1020W", 75)],
            "not_satisfied",
        ),
        (
            [
                _result(catalogue, "APG1020W", 75),
                _result(catalogue, "APG1003W", 75),
                _result(catalogue, "APG2021W", 40),
            ],
            "not_satisfied",
        ),
        (
            [
                _result(catalogue, "APG1003W", 75),
                _result(catalogue, "APG2021W", 40),
                _result(catalogue, "APG1020W", 40),
            ],
            "satisfied",
        ),
    ]

    for results, expected_outcome in cases:
        policy = _policy_result(catalogue, results)
        legacy = _legacy_pass_rate_result(catalogue, results)

        assert policy.condition.outcome == expected_outcome
        assert (legacy.ratio is not None and legacy.ratio < 0.8) == (
            policy.condition.outcome == "satisfied"
        )


def test_bas_pass_rate_is_credit_weighted_not_course_count():
    catalogue = _catalogue()
    credit = SyntheticCreditFramework(
        {
            "APG1003W": 36,
            "APG1020W": 6,
            "APG2021W": 6,
            "APG2039W": 6,
        }
    )
    results = [
        _result(catalogue, "APG1003W", 40),
        _result(catalogue, "APG1020W", 75),
        _result(catalogue, "APG2021W", 75),
        _result(catalogue, "APG2039W", 75),
    ]

    policy = _policy_result(catalogue, results, credit_framework=credit)
    legacy = _legacy_pass_rate_result(catalogue, results, credit_framework=credit)

    assert legacy.numerator_value == 18
    assert legacy.denominator_value == 54
    assert legacy.ratio == 1 / 3
    assert policy.condition.outcome == "satisfied"
    assert "33.3%" in policy.condition.detail


def test_bas_pending_results_are_excluded_from_denominator():
    catalogue = _catalogue()
    results = [
        _result(catalogue, "APG1020W", 75),
        _result(catalogue, "APG1003W", 75),
        _result(catalogue, "APG2021W", 40),
        _result(catalogue, "APG2039W", None),
    ]

    policy = _policy_result(catalogue, results)
    legacy = _legacy_pass_rate_result(catalogue, results)

    assert legacy.ratio == 0.8
    assert policy.condition.outcome == "not_satisfied"
    assert "80.0%" in policy.condition.detail


def test_bas_zero_denominator_is_unresolved_not_zero_or_safe():
    catalogue = _catalogue()
    policy = _policy_result(
        catalogue,
        [
            _result(catalogue, "APG1003W", None),
            _result(catalogue, "APG1020W", None),
        ],
    )
    risk = _policy_only_risk(catalogue, [_result(catalogue, "APG1003W", None)])

    assert policy.condition.outcome == "unresolved"
    assert not policy.consequence_established
    assert "ratio denominator evidence is unavailable" in policy.detail
    assert not risk.at_risk
    assert not risk.assessed
    assert "ratio denominator evidence is unavailable" in risk.basis


def test_bas_recognised_or_provisional_boundary_excludes_unrecognised_direct_results():
    catalogue = _catalogue()
    results = [
        _result(catalogue, "APG1003W", 75),
        _result(catalogue, "UNRECOGNISED-BAS-FAIL", 40, credits=100),
    ]

    policy = _policy_result(catalogue, results)
    legacy = _legacy_pass_rate_result(catalogue, results)

    assert legacy.numerator_value == 20
    assert legacy.denominator_value == 20
    assert legacy.ratio == 1
    assert policy.condition.outcome == "not_satisfied"


def test_bas_attempt_identity_counts_repeated_same_code_attempts():
    catalogue = _catalogue()
    results = [
        _result(catalogue, "APG1003W", 40, attempt_id="APG1003W-1"),
        _result(catalogue, "APG1003W", 75, attempt_id="APG1003W-2"),
        _result(catalogue, "APG2021W", 75, attempt_id="APG2021W-1"),
    ]

    policy = _policy_result(catalogue, results)
    legacy = _legacy_pass_rate_result(catalogue, results)

    assert legacy.numerator_value == 40
    assert legacy.denominator_value == 60
    assert policy.condition.outcome == "satisfied"
    assert "66.7%" in policy.condition.detail


def test_bas_policy_authority_and_advisory_decision_boundary():
    catalogue = _catalogue()
    results = [
        _result(catalogue, "APG1003W", 75),
        _result(catalogue, "APG2021W", 40),
        _result(catalogue, "APG1020W", 40),
    ]
    policy = _policy_result(catalogue, results)
    risk = _policy_only_risk(catalogue, results)

    assert policy.condition.outcome == "satisfied"
    assert policy.policy_status == "unverified"
    assert policy.effective_status == "unverified"
    assert policy.consequence is not None
    assert policy.consequence.consequence_type == "advisory_risk"
    assert risk.at_risk
    assert not risk.assessed
    assert risk.status == "unverified"
    text = " ".join(risk.reasons + [risk.basis]).lower()
    assert "progression_ineligible" not in text
    assert "review_required" not in text
    assert "excluded" not in text
    assert "senate decision" not in text
    assert "faculty decision" not in text


def test_stage8u_architecture_guards():
    from engine import rule_engine

    ratio_adapter = inspect.getsource(rule_engine._progression_ratio_condition_result)
    condition_source = inspect.getsource(rule_engine._evaluate_progression_condition)
    policy_source = inspect.getsource(rule_engine._evaluate_progression_policy)
    runtime_source = inspect.getsource(rule_engine._compute_exclusion_risk)
    builder_source = inspect.getsource(build_ebe_2026.bas_annual_pass_rate_policy)

    assert "_evaluate_progression_ratio" in condition_source
    assert "_progression_ratio_triggers_risk" in ratio_adapter
    assert "numerator_value / denominator_value" not in ratio_adapter
    assert "_credit_value" not in ratio_adapter
    assert "pass_rate" not in condition_source
    assert "ebe" not in condition_source.lower()
    assert "bas" not in condition_source.lower()
    assert "ebe" not in policy_source.lower()
    assert "bas" not in policy_source.lower()
    assert "if faculty" not in runtime_source.lower()
    assert "progression_ineligible" not in builder_source
    assert "review_required" not in builder_source
    assert "manual" not in builder_source
    assert "any_of" not in builder_source

    law_text = Path("data/uct_law/degree_requirements.json").read_text(encoding="utf-8")
    health_text = Path("data/uct_health/degree_requirements.json").read_text(
        encoding="utf-8"
    )
    assert "UCT-LAW-2026-ANNUAL-FAILED-LOAD" in law_text
    assert "repeat_year_failure" in health_text
