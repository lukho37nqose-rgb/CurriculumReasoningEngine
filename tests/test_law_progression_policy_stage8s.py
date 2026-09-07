import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from engine.catalogue import load_catalogue
from engine.models import CourseResult, StudentRecord
from engine.rule_engine import (
    _evaluate_failed_progression_metric,
    _evaluate_progression_policy,
    _failed_progression_metric_spec,
    compute_report,
)
from tools import build_law_2026

LAW_FAILED_LOAD_POLICIES = {
    "llb_three_year_graduate": (4, 41),
    "llb_two_year_combined": (4, 50),
    "llb_four_year_undergraduate": (4, 43),
    "llb_five_year_continuing": (3, 52),
}


@dataclass(frozen=True, slots=True)
class SyntheticLawLoadFramework:
    values: dict[str, float]

    def load_equivalent(self, item: Any) -> float:
        code = item if isinstance(item, str) else item.code
        return self.values.get(code, 1.0)


def _catalogue():
    return load_catalogue("uct_law")


def _policy(catalogue, programme_key: str) -> dict[str, Any]:
    policies = [
        rule
        for rule in catalogue.programmes[programme_key].progression_rules
        if rule.get("type") == "progression_policy"
    ]
    assert len(policies) == 1
    return policies[0]


def _maximum_years_rule(catalogue, programme_key: str) -> dict[str, Any]:
    rules = [
        rule
        for rule in catalogue.programmes[programme_key].progression_rules
        if rule.get("type") == "maximum_years"
    ]
    assert len(rules) == 1
    return rules[0]


def _student(catalogue, programme_key: str, codes: list[str], *, mark=40, year=2026):
    results = []
    for code in codes:
        fact = catalogue.courses[code]
        results.append(
            CourseResult(
                code,
                fact.name,
                fact.nqf_level,
                fact.nqf_credits,
                mark,
                None,
                year,
            )
        )
    return StudentRecord(
        "LAW-8S",
        "Law Progression",
        "LLB",
        [],
        results,
        "uct_law",
        programme_key,
        "",
        3,
    )


def _risk(catalogue, programme_key: str, codes: list[str], *, mark=40, year=2026):
    return compute_report(
        _student(catalogue, programme_key, codes, mark=mark, year=year),
        catalogue,
    ).exclusion_risk


def _policy_result(catalogue, programme_key: str, codes: list[str]):
    policy = _policy(catalogue, programme_key)
    return _evaluate_progression_policy(
        policy,
        student=_student(catalogue, programme_key, codes),
        catalogue=catalogue,
        latest_year=2026,
        grading_scheme=None,
        course_load_framework=None,
        stage_repeat_evidence=None,
        result_context_evidence=None,
        programme_key=programme_key,
        pathway_key="",
    )


def _failed_result(catalogue, code: str, *, year=2026, mark=40) -> CourseResult:
    fact = catalogue.courses[code]
    return CourseResult(
        code,
        fact.name,
        fact.nqf_level,
        fact.nqf_credits,
        mark,
        None,
        year,
    )


def test_law_failed_load_policy_data_shape_and_thresholds():
    catalogue = _catalogue()
    policy_ids = set()

    for programme_key, (threshold, page) in LAW_FAILED_LOAD_POLICIES.items():
        policy = _policy(catalogue, programme_key)
        policy_ids.add(policy["policy_id"])
        condition = policy["condition"]
        consequence = policy["consequence"]

        assert policy["type"] == "progression_policy"
        assert policy["policy_id"] == (
            "UCT-LAW-2026-ANNUAL-FAILED-LOAD-"
            + programme_key.upper().replace("_", "-")
        )
        assert policy["verification_status"] == "unverified"
        assert policy["source_reference"] == (
            f"2026 Faculty of Law Handbook, page {page}, "
            "Admission and Curriculum Rules"
        )
        assert condition["type"] == "failed_metric"
        assert condition["metric_basis"] == "course_load_equivalent"
        assert condition["identity"] == "distinct_course"
        assert condition["temporal_scope"] == "latest_academic_year"
        assert condition["threshold"] == threshold
        assert consequence["type"] == "advisory_risk"
        assert consequence["type"] not in {"review_required", "progression_ineligible"}

    assert len(policy_ids) == len(LAW_FAILED_LOAD_POLICIES)


def test_law_failed_load_policy_has_no_duplicate_legacy_rule_and_keeps_maximum_years():
    catalogue = _catalogue()

    for programme_key in LAW_FAILED_LOAD_POLICIES:
        rules = catalogue.programmes[programme_key].progression_rules
        assert [rule["type"] for rule in rules] == [
            "progression_policy",
            "maximum_years",
        ]
        assert all(rule.get("type") != "failed_course_equivalents" for rule in rules)
        assert _maximum_years_rule(catalogue, programme_key)["label"] == (
            "Prescribed time plus one year"
        )


def test_law_builder_reproduces_policy_shape_and_stable_ids():
    catalogue = _catalogue()

    for programme_key, (threshold, page) in LAW_FAILED_LOAD_POLICIES.items():
        source = build_law_2026.law_source_reference(page)
        first = build_law_2026.law_failed_load_progression_policy(
            programme_key, threshold, source
        )
        second = build_law_2026.law_failed_load_progression_policy(
            programme_key, threshold, source
        )
        changed_threshold = build_law_2026.law_failed_load_progression_policy(
            programme_key, threshold + 1, source
        )

        assert first == second
        assert first == _policy(catalogue, programme_key)
        assert changed_threshold["policy_id"] == first["policy_id"]
        assert changed_threshold["condition"]["threshold"] == threshold + 1


def test_law_failed_load_policy_preserves_legacy_condition_trigger_parity():
    catalogue = _catalogue()
    codes = ["CML4004S", "PBL4801F", "PBL4802F", "PVL4008H"]

    for programme_key in LAW_FAILED_LOAD_POLICIES:
        policy = _policy(catalogue, programme_key)
        threshold = policy["condition"]["threshold"]
        legacy = {
            "type": "failed_course_equivalents",
            "label": "Annual failed-course-equivalent threshold",
            "threshold": threshold,
        }
        legacy_spec = _failed_progression_metric_spec(legacy, legacy["label"])
        assert legacy_spec is not None
        legacy_result = _evaluate_failed_progression_metric(
            legacy_spec,
            _student(catalogue, programme_key, codes),
            2026,
            None,
            None,
        )
        new_result = _policy_result(catalogue, programme_key, codes)

        assert (legacy_result.value >= legacy_result.threshold) == (
            new_result.condition.outcome == "satisfied"
        )
        assert legacy_result.threshold == threshold


def test_law_failed_load_below_at_and_above_threshold_public_compatibility():
    catalogue = _catalogue()

    below = _risk(
        catalogue,
        "llb_three_year_graduate",
        ["CML4004S", "PBL4801F", "PBL4802F"],
    )
    at_threshold = _risk(
        catalogue,
        "llb_three_year_graduate",
        ["CML4004S", "PBL4801F", "PBL4802F", "PVL4008H"],
    )
    above_five_year_threshold = _risk(
        catalogue,
        "llb_five_year_continuing",
        ["CML4004S", "PBL4801F", "PBL4802F", "PVL4008H"],
    )

    assert not below.at_risk
    assert below.status == "unverified"
    assert "configured condition did not trigger" in below.basis
    assert at_threshold.at_risk
    assert at_threshold.status == "unverified"
    assert "advisory_risk" in at_threshold.reasons[0]
    assert "configured threshold is 4" in at_threshold.reasons[0]
    assert above_five_year_threshold.at_risk
    assert "configured threshold is 3" in above_five_year_threshold.reasons[0]


def test_law_failed_load_policy_keeps_distinct_course_identity():
    catalogue = _catalogue()
    programme_key = "llb_three_year_graduate"
    student = StudentRecord(
        "LAW-8S-REPEAT",
        "Repeated Attempts",
        "LLB",
        [],
        [
            _failed_result(catalogue, "CML4004S", year=2026),
            _failed_result(catalogue, "CML4004S", year=2026),
            _failed_result(catalogue, "PBL4801F", year=2026),
            _failed_result(catalogue, "PBL4802F", year=2026),
        ],
        "uct_law",
        programme_key,
        "",
        3,
    )

    risk = compute_report(student, catalogue).exclusion_risk

    assert not risk.at_risk
    assert "failed course load equivalent is 3" in risk.basis
    assert "below the 4 threshold" in risk.basis


def test_law_failed_load_policy_uses_course_load_framework_not_credit_count():
    catalogue = _catalogue()
    programme_key = "llb_three_year_graduate"
    student = _student(catalogue, programme_key, ["CML4004S", "PBL4801F"])
    load_framework = SyntheticLawLoadFramework({"CML4004S": 3.0, "PBL4801F": 1.0})

    risk = compute_report(
        student,
        catalogue,
        course_load_framework=load_framework,
    ).exclusion_risk

    assert risk.at_risk
    assert "failed course load equivalent is 4" in risk.reasons[0]
    assert "credit" not in risk.reasons[0].lower()


def test_law_failed_load_policy_ignores_pending_results():
    catalogue = _catalogue()
    programme_key = "llb_three_year_graduate"
    fact = catalogue.courses["PVL4008H"]
    student = _student(
        catalogue,
        programme_key,
        ["CML4004S", "PBL4801F", "PBL4802F"],
    )
    student.results.append(
        CourseResult(
            fact.code,
            fact.name,
            fact.nqf_level,
            fact.nqf_credits,
            None,
            None,
            2026,
        )
    )

    risk = compute_report(student, catalogue).exclusion_risk

    assert not risk.at_risk
    assert "failed course load equivalent is 3" in risk.basis


def test_law_failed_load_policy_authority_and_decision_boundary():
    catalogue = _catalogue()
    risk = _risk(
        catalogue,
        "llb_three_year_graduate",
        ["CML4004S", "PBL4801F", "PBL4802F", "PVL4008H"],
    )

    assert risk.at_risk
    assert not risk.assessed
    assert risk.status == "unverified"
    assert "bounded by unverified authority/status" in risk.basis
    text = " ".join(risk.reasons + [risk.basis]).lower()
    assert "faculty examinations committee decision" not in text
    assert "senate decision" not in text
    assert "readmission denied" not in text
    assert "student is excluded" not in text


def test_law_policy_source_reference_is_not_strengthened():
    catalogue = _catalogue()

    for programme_key, (_, page) in LAW_FAILED_LOAD_POLICIES.items():
        policy = _policy(catalogue, programme_key)
        source = catalogue.programmes[programme_key].source
        assert policy["source_reference"] == (
            f"{source['document']}, page {page}, {source['section']}"
        )
        assert policy["verification_status"] == "unverified"


def test_law_stage8s_architecture_guards():
    from engine import rule_engine

    catalogue = _catalogue()
    runtime_source = inspect.getsource(rule_engine._compute_exclusion_risk)
    policy_source = inspect.getsource(rule_engine._evaluate_progression_policy)
    builder_source = inspect.getsource(build_law_2026.law_failed_load_progression_policy)

    assert "uct_law" not in runtime_source.lower()
    assert "llb_" not in runtime_source.lower()
    assert "law" not in policy_source.lower()
    assert "review_required" not in builder_source
    assert "progression_ineligible" not in builder_source
    assert "excluded" not in builder_source
    assert "any_of" not in builder_source
    assert "manual" not in builder_source

    for programme_key in LAW_FAILED_LOAD_POLICIES:
        rules = catalogue.programmes[programme_key].progression_rules
        assert rules[0]["type"] == "progression_policy"
        assert rules[1]["type"] == "maximum_years"

    health_text = Path("data/uct_health/degree_requirements.json").read_text()
    assert "repeat_year_failure" in health_text


def test_law_stage8s_does_not_migrate_other_faculties():
    for faculty in [
        "uct_commerce",
        "uct_ebe",
        "uct_health",
        "uct_humanities",
        "uct_science",
    ]:
        catalogue = load_catalogue(faculty)
        for programme in catalogue.programmes.values():
            for rule in programme.progression_rules:
                assert not (
                    rule.get("type") == "progression_policy"
                    and str(rule.get("policy_id", "")).startswith(
                        "UCT-LAW-2026-ANNUAL-FAILED-LOAD-"
                    )
                )


def test_law_stage8s_progression_helper_matches_committed_law_data():
    catalogue = _catalogue()

    for programme_key, (threshold, page) in LAW_FAILED_LOAD_POLICIES.items():
        expected_rules = build_law_2026.progression(
            programme_key,
            _maximum_years_rule(catalogue, programme_key)["maximum"],
            threshold,
            page,
        )

        assert expected_rules == catalogue.programmes[programme_key].progression_rules
