import inspect
from pathlib import Path
from typing import Any

import pytest
from recognition_fixtures import empty_recognition_snapshot

from engine.catalogue import load_catalogue
from engine.models import (
    AcademicRecordCoverageEvidence,
    Catalogue,
    CourseFact,
    CourseResult,
    ProgrammeRules,
    StudentRecord,
)
from engine.rule_engine import _evaluate_progression_policy, compute_report
from tools import build_health_2026

POLICY_ID = "UCT-HEALTH-2026-MBCHB-FUNDAMENTALS-PROGRESSION"
SOURCE_REFERENCE = (
    "2026 Faculty of Health Sciences Undergraduate Handbook, page 62, "
    "Rules and curricula for undergraduate programmes"
)
FUNDAMENTALS_CODES = ("HSE1001F", "HSE1001S")
OTHER_FUNDAMENTALS_ROUTES = (
    "bsc_audiology_fundamentals",
    "bsc_speech_language_pathology_fundamentals",
    "bsc_occupational_therapy_fundamentals",
    "bsc_physiotherapy_fundamentals",
)


def _catalogue() -> Catalogue:
    return load_catalogue("uct_health")


def _policy(catalogue: Catalogue) -> dict[str, Any]:
    policies = [
        rule
        for rule in catalogue.programmes["mbchb_fundamentals"].progression_rules
        if rule.get("type") == "progression_policy"
    ]
    assert len(policies) == 1
    return policies[0]


def _result(
    catalogue: Catalogue, code: str, mark: int | None, year: int = 2026
) -> CourseResult:
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


def _student(results: list[CourseResult], programme_key: str = "mbchb_fundamentals"):
    return StudentRecord(
        "MBCHB-FUND-8Z2",
        "MBChB Fundamentals",
        "MBChB - Fundamentals of Health Sciences route",
        [],
        results,
        "uct_health",
        programme_key,
        "",
        1,
    )


def _coverage(
    codes: tuple[str, ...] = FUNDAMENTALS_CODES,
    *,
    coverage_state: str = "complete",
    verification_status: str = "verified",
) -> AcademicRecordCoverageEvidence:
    return AcademicRecordCoverageEvidence(
        course_codes=codes,
        coverage_state=coverage_state,
        source_reference="SIS result snapshot",
        authority="registry",
        verification_status=verification_status,
    )


def _policy_result(
    results: list[CourseResult],
    *,
    coverage: list[AcademicRecordCoverageEvidence] | None = None,
):
    catalogue = _catalogue()
    return _evaluate_progression_policy(
        _policy(catalogue),
        student=_student(results),
        catalogue=catalogue,
        latest_year=2026,
        grading_scheme=None,
        credit_framework=None,
        course_code_scheme=None,
        course_load_framework=None,
        stage_repeat_evidence=None,
        result_context_evidence=None,
        academic_record_coverage_evidence=coverage,
        completion_recognition=empty_recognition_snapshot(_student(results), catalogue),
        programme_key="mbchb_fundamentals",
        pathway_key="",
    )


def _u2_catalogue(required: int | float = 1) -> Catalogue:
    courses = {
        code: CourseFact(code, code, 0, 0, [], [], "SYN")
        for code in ("FOUND-F", "FOUND-S")
    }
    programme = ProgrammeRules(
        key="P-OMEGA",
        name="P-OMEGA",
        total_nqf_credits=0,
        level_7_nqf_credits=0,
        semester_course_equivalents=0,
        senior_course_equivalents=0,
        humanities_course_equivalents=0,
        required_majors=0,
        required_humanities_majors=0,
        progression_rules=[
            {
                "type": "progression_policy",
                "policy_id": "U2-FOUNDATION-ONE-OF",
                "verification_status": "verified",
                "condition": {
                    "type": "course_requirement_incomplete",
                    "label": "Foundation course requirement incomplete",
                    "course_codes": ["FOUND-F", "FOUND-S"],
                    "required": required,
                },
                "consequence": {
                    "type": "progression_ineligible",
                    "label": "Foundation progression requirement not met",
                },
            }
        ],
    )
    return Catalogue(
        courses=courses,
        majors={},
        programmes={programme.key: programme},
        forbidden_combinations=[],
        faculty_key="university_two",
        catalogue_version="test-release",
        programme_key=programme.key,
        scope_status="verified",
    )


def _u2_result(code: str, mark: int | None, year: int = 2026) -> CourseResult:
    return CourseResult(code, code, 0, 0, mark, None, year)


def _u2_report(
    results: list[CourseResult],
    *,
    coverage: list[AcademicRecordCoverageEvidence] | None = None,
    required: int | float = 1,
):
    catalogue = _u2_catalogue(required)
    student = StudentRecord(
        "U2-8Z2",
        "University Two",
        "P-OMEGA",
        [],
        results,
        "university_two",
        "P-OMEGA",
    )
    return compute_report(
        student,
        catalogue,
        academic_record_coverage_evidence=coverage,
        completion_recognition=empty_recognition_snapshot(student, catalogue),
    )


def test_mbchb_fundamentals_policy_has_canonical_one_course_requirement_shape():
    policy = _policy(_catalogue())
    condition = policy["condition"]

    assert policy["policy_id"] == POLICY_ID
    assert policy["verification_status"] == "unverified"
    assert policy["source_reference"] == SOURCE_REFERENCE
    assert condition == {
        "type": "course_requirement_incomplete",
        "label": "Fundamentals course requirement incomplete",
        "id": "mbchb_fundamentals_completion",
        "course_codes": list(FUNDAMENTALS_CODES),
        "required": 1,
    }
    assert policy["consequence"]["type"] == "progression_ineligible"


@pytest.mark.parametrize("required", [2, 1.5, True])
def test_required_other_than_exact_integer_one_is_explicitly_unsupported(required):
    assessment = _u2_report([], required=required).progression_policy_assessments[0]

    assert assessment.condition_outcome == "unsupported"
    assert not assessment.assessment_complete
    assert not assessment.consequence_established
    assert "required=1 only" in assessment.detail


@pytest.mark.parametrize("code", FUNDAMENTALS_CODES)
def test_either_fundamentals_code_alone_completes_requirement(code: str):
    catalogue = _catalogue()
    policy = _policy_result([_result(catalogue, code, 70)])

    assert policy.condition.outcome == "not_satisfied"
    assert policy.condition.assessment_complete
    assert code in policy.condition.detail
    assert not policy.consequence_established


def test_both_passed_complete_the_single_requirement():
    catalogue = _catalogue()
    policy = _policy_result(
        [_result(catalogue, code, 70) for code in FUNDAMENTALS_CODES]
    )

    assert policy.condition.outcome == "not_satisfied"
    assert not policy.consequence_established


@pytest.mark.parametrize(
    "results",
    [
        [("HSE1001F", 40, 2025), ("HSE1001F", 70, 2026)],
        [("HSE1001F", 40, 2025), ("HSE1001S", 70, 2026)],
        [("HSE1001F", 70, 2025), ("HSE1001S", 40, 2026)],
    ],
)
def test_historical_failure_does_not_override_valid_completion_witness(results):
    catalogue = _catalogue()
    policy = _policy_result(
        [_result(catalogue, code, mark, year) for code, mark, year in results]
    )

    assert policy.condition.outcome == "not_satisfied"
    assert not policy.consequence_established


@pytest.mark.parametrize("code", FUNDAMENTALS_CODES)
def test_single_failure_without_coverage_is_unresolved(code: str):
    catalogue = _catalogue()
    policy = _policy_result([_result(catalogue, code, 40)])

    assert policy.condition.outcome == "unresolved"
    assert not policy.condition.assessment_complete
    assert not policy.consequence_established


def test_no_evidence_without_coverage_is_unresolved():
    policy = _policy_result([])

    assert policy.condition.outcome == "unresolved"
    assert not policy.consequence_established


def test_complete_coverage_without_witness_establishes_incomplete_requirement():
    policy = _policy_result([], coverage=[_coverage()])

    assert policy.condition.outcome == "satisfied"
    assert policy.condition.assessment_complete
    assert policy.consequence_established
    assert policy.effective_status == "unverified"


def test_complete_coverage_with_one_failure_establishes_incomplete_requirement():
    catalogue = _catalogue()
    policy = _policy_result(
        [_result(catalogue, "HSE1001F", 40)], coverage=[_coverage()]
    )

    assert policy.condition.outcome == "satisfied"
    assert policy.consequence_established


def test_two_failures_need_complete_coverage_to_establish_incompletion():
    catalogue = _catalogue()
    failures = [_result(catalogue, code, 40) for code in FUNDAMENTALS_CODES]

    uncovered = _policy_result(failures)
    covered = _policy_result(failures, coverage=[_coverage()])

    assert uncovered.condition.outcome == "unresolved"
    assert not uncovered.consequence_established
    assert covered.condition.outcome == "satisfied"
    assert covered.consequence_established


def test_partial_alternative_coverage_is_insufficient_for_negative_inference():
    policy = _policy_result([], coverage=[_coverage(("HSE1001F",))])

    assert policy.condition.outcome == "unresolved"
    assert "HSE1001S" in policy.condition.detail
    assert not policy.consequence_established


def test_pending_possible_witness_remains_unresolved_even_with_complete_coverage():
    catalogue = _catalogue()
    policy = _policy_result(
        [_result(catalogue, "HSE1001F", None)], coverage=[_coverage()]
    )

    assert policy.condition.outcome == "unresolved"
    assert "HSE1001F" in policy.condition.detail
    assert not policy.consequence_established


def test_valid_witness_short_circuits_unused_pending_alternative():
    catalogue = _catalogue()
    policy = _policy_result(
        [
            _result(catalogue, "HSE1001F", 70),
            _result(catalogue, "HSE1001S", None),
        ]
    )

    assert policy.condition.outcome == "not_satisfied"
    assert policy.condition.status == "verified"
    assert policy.condition.assessment_complete


def test_unverified_complete_coverage_bounds_negative_authority():
    policy = _policy_result(
        [], coverage=[_coverage(verification_status="unverified")]
    )

    assert policy.condition.outcome == "satisfied"
    assert policy.condition.status == "unverified"
    assert not policy.condition.assessment_complete
    assert policy.consequence_established
    assert policy.effective_status == "unverified"


def test_conflicting_coverage_is_preserved():
    policy = _policy_result(
        [],
        coverage=[
            _coverage(
                coverage_state="conflict",
                verification_status="conflict",
            )
        ],
    )

    assert policy.condition.outcome == "conflict"
    assert policy.effective_status == "conflict"
    assert not policy.consequence_established


def test_real_policy_assessment_preserves_triggered_and_non_triggered_states():
    catalogue = _catalogue()
    triggered = compute_report(
        _student([]),
        catalogue,
        academic_record_coverage_evidence=[_coverage()],
        completion_recognition=empty_recognition_snapshot(_student([]), catalogue),
    ).progression_policy_assessments[0]
    completed = compute_report(
        _student([_result(catalogue, "HSE1001S", 70)]),
        catalogue,
    ).progression_policy_assessments[0]

    assert triggered.policy_id == POLICY_ID
    assert triggered.condition_outcome == "satisfied"
    assert triggered.consequence_type == "progression_ineligible"
    assert triggered.consequence_established
    assert triggered.policy_status == "unverified"
    assert triggered.effective_status == "unverified"
    assert triggered.source_reference == SOURCE_REFERENCE
    assert completed.condition_outcome == "not_satisfied"
    assert not completed.consequence_established


def test_progression_ineligible_remains_distinct_from_formal_act():
    catalogue = _catalogue()
    report = compute_report(
        _student([]),
        _catalogue(),
        academic_record_coverage_evidence=[_coverage()],
        completion_recognition=empty_recognition_snapshot(_student([]), catalogue),
    )
    assessment = report.progression_policy_assessments[0]
    rendered = assessment.detail.lower()

    assert assessment.consequence_type == "progression_ineligible"
    assert "student is excluded" not in rendered
    assert "continuation formally refused" not in rendered
    assert "senate decision" not in rendered
    assert "faculty decision" not in rendered


def test_policy_is_scoped_to_mbchb_fundamentals_programme():
    catalogue = _catalogue()
    standard_report = compute_report(_student([], "mbchb"), catalogue)

    assert all(
        assessment.policy_id != POLICY_ID
        for assessment in standard_report.progression_policy_assessments
    )


def test_builder_reproduces_governed_policy():
    first = build_health_2026.mbchb_fundamentals_progression_policy(
        build_health_2026.health_source_reference(62)
    )
    second = build_health_2026.mbchb_fundamentals_progression_policy(
        build_health_2026.health_source_reference(62)
    )

    assert first == second == _policy(_catalogue())


def test_no_duplicate_legacy_failed_any_and_other_health_routes_are_unchanged():
    catalogue = _catalogue()
    rules = catalogue.programmes["mbchb_fundamentals"].progression_rules

    assert sum(rule.get("type") == "progression_policy" for rule in rules) == 1
    assert not any(
        rule.get("type") == "failed_any"
        and set(rule.get("course_codes", [])) == set(FUNDAMENTALS_CODES)
        for rule in rules
    )
    for key in OTHER_FUNDAMENTALS_ROUTES:
        route_rules = catalogue.programmes[key].progression_rules
        assert any(
            rule.get("type") == "failed_any"
            and set(rule.get("course_codes", [])) == set(FUNDAMENTALS_CODES)
            for rule in route_rules
        )


def test_nmfc_all_required_policy_and_health_repeat_rules_are_preserved():
    catalogue = _catalogue()
    nmfc = catalogue.programmes["nmfc_medical_training"].progression_rules[0]
    health_text = Path("data/uct_health/degree_requirements.json").read_text(
        encoding="utf-8"
    )

    assert nmfc["condition"]["type"] == "required_course_pool_incomplete"
    assert "repeat_year_failure" in health_text
    assert "repeat_failure" in health_text


@pytest.mark.parametrize(
    ("results", "coverage", "expected"),
    [
        ([("FOUND-F", 70)], None, "not_satisfied"),
        ([("FOUND-S", 70)], None, "not_satisfied"),
        ([("FOUND-F", 40)], None, "unresolved"),
        ([("FOUND-F", 40)], [ _coverage(("FOUND-F", "FOUND-S")) ], "satisfied"),
        ([("FOUND-F", 40), ("FOUND-S", 70)], None, "not_satisfied"),
        ([("FOUND-F", None)], [ _coverage(("FOUND-F", "FOUND-S")) ], "unresolved"),
        ([("FOUND-F", 70), ("FOUND-S", None)], None, "not_satisfied"),
    ],
)
def test_university_two_one_of_requirement_is_institution_neutral(
    results, coverage, expected
):
    report = _u2_report(
        [_u2_result(code, mark) for code, mark in results], coverage=coverage
    )
    assessment = report.progression_policy_assessments[0]

    assert assessment.condition_outcome == expected
    assert assessment.consequence_established is (expected == "satisfied")


def test_architecture_guards():
    from engine import rule_engine

    evaluator_source = inspect.getsource(
        rule_engine._course_requirement_condition_result
    )
    dispatch_source = inspect.getsource(rule_engine._evaluate_progression_condition)
    builder_source = inspect.getsource(
        build_health_2026.mbchb_fundamentals_progression_policy
    )

    assert "_completion_progression_result" in evaluator_source
    shared = inspect.getsource(rule_engine._completion_progression_result)
    assert "CourseCompletionResolver" in shared
    assert ".resolve(" in shared
    assert "is_passed" not in evaluator_source
    assert "is_failed" not in evaluator_source
    assert "mark >=" not in evaluator_source
    assert "required=1 only" in evaluator_source
    assert 'rule_type == "any_of"' not in dispatch_source
    assert 'rule_type == "not"' not in dispatch_source
    assert "uct_health" not in evaluator_source.lower()
    assert "mbchb" not in evaluator_source.lower()
    assert "failed_any" not in builder_source
