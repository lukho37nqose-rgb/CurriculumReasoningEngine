import inspect
from pathlib import Path
from typing import Any

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
from engine.rule_engine import (
    _evaluate_failed_progression_metric,
    _evaluate_progression_policy,
    _failed_progression_metric_spec,
    compute_report,
)
from tools import build_health_2026

NMFC_POLICY_ID = "UCT-HEALTH-2026-NMFC-FIRST-SEMESTER-PROGRESSION"
NMFC_SOURCE_REFERENCE = (
    "2026 Faculty of Health Sciences Undergraduate Handbook, page 65, "
    "Rules and curricula for undergraduate programmes"
)
NMFC_FIRST_SEMESTER = [
    "AAE4003W",
    "MDN4017W",
    "PED4017W",
    "OBS4006W",
    "PRY4001W",
]


class SyntheticSeventyPassGradingScheme:
    institution_id = "synthetic"
    def is_passed(self, result: Any) -> bool:
        return result.mark is not None and result.mark >= 70

    def is_failed(self, result: Any) -> bool:
        return result.mark is not None and result.mark < 70

    def is_pending(self, result: Any) -> bool:
        return result.mark is None


def _catalogue() -> Catalogue:
    return load_catalogue("uct_health")


def _nmfc_policy(catalogue: Catalogue) -> dict[str, Any]:
    policies = [
        rule
        for rule in catalogue.programmes["nmfc_medical_training"].progression_rules
        if rule.get("type") == "progression_policy"
    ]
    assert len(policies) == 1
    return policies[0]


def _result(catalogue: Catalogue, code: str, mark: int | None, year: int = 2026):
    fact = catalogue.courses[code]
    return CourseResult(code, fact.name, fact.nqf_level, fact.nqf_credits, mark, None, year)


def _student(results: list[CourseResult]) -> StudentRecord:
    return StudentRecord(
        "NMFC-8Y",
        "NMFC Progression",
        "Nelson Mandela Fidel Castro Medical Training Programme",
        [],
        results,
        "uct_health",
        "nmfc_medical_training",
        "",
        1,
    )


def _policy_result(
    catalogue: Catalogue,
    results: list[CourseResult],
    *,
    grading_scheme: Any = None,
    academic_record_coverage_evidence: list[AcademicRecordCoverageEvidence]
    | None = None,
):
    return _evaluate_progression_policy(
        _nmfc_policy(catalogue),
        student=_student(results),
        catalogue=catalogue,
        latest_year=2026,
        grading_scheme=grading_scheme,
        credit_framework=None,
        course_code_scheme=None,
        course_load_framework=None,
        stage_repeat_evidence=None,
        result_context_evidence=None,
        academic_record_coverage_evidence=academic_record_coverage_evidence,
        completion_recognition=empty_recognition_snapshot(_student(results), catalogue, grading_scheme),
        programme_key="nmfc_medical_training",
        pathway_key="",
    )


def _all_passed(catalogue: Catalogue) -> list[CourseResult]:
    return [_result(catalogue, code, 70) for code in NMFC_FIRST_SEMESTER]


def test_nmfc_policy_is_canonical_completion_prerequisite():
    catalogue = _catalogue()
    policy = _nmfc_policy(catalogue)
    condition = policy["condition"]

    assert policy["type"] == "progression_policy"
    assert policy["policy_id"] == NMFC_POLICY_ID
    assert policy["verification_status"] == "unverified"
    assert policy["source_reference"] == NMFC_SOURCE_REFERENCE
    assert condition["type"] == "required_course_pool_incomplete"
    assert condition["id"] == "nmfc_first_semester_completion"
    assert condition["course_codes"] == NMFC_FIRST_SEMESTER
    assert policy["consequence"]["type"] == "progression_ineligible"
    assert policy["consequence"]["type"] not in {"advisory_risk", "review_required"}


def test_nmfc_has_no_duplicate_legacy_failed_any_for_this_policy():
    catalogue = _catalogue()
    rules = catalogue.programmes["nmfc_medical_training"].progression_rules

    assert [rule["type"] for rule in rules] == ["progression_policy", "repeat_failure"]
    assert all(
        not (
            rule.get("type") == "failed_any"
            and rule.get("course_codes") == NMFC_FIRST_SEMESTER
        )
        for rule in rules
    )


def test_nmfc_builder_reproduces_policy_and_stable_id():
    catalogue = _catalogue()
    first = build_health_2026.nmfc_first_semester_progression_policy(
        build_health_2026.health_source_reference(65)
    )
    second = build_health_2026.nmfc_first_semester_progression_policy(
        build_health_2026.health_source_reference(65)
    )

    assert first == second
    assert first == _nmfc_policy(catalogue)
    assert first["policy_id"] == NMFC_POLICY_ID


def test_nmfc_all_passed_first_attempt_does_not_trigger_progression_ineligible():
    catalogue = _catalogue()
    policy = _policy_result(catalogue, _all_passed(catalogue))

    assert policy.condition.outcome == "not_satisfied"
    assert not policy.consequence_established
    assert "course requirement completed" in policy.condition.detail


def test_nmfc_one_failed_with_no_later_pass_is_unresolved_without_coverage():
    catalogue = _catalogue()
    results = _all_passed(catalogue)
    results[0] = _result(catalogue, "AAE4003W", 40)
    policy = _policy_result(catalogue, results)
    report = compute_report(_student(results), catalogue)

    assert policy.condition.outcome == "unresolved"
    assert not policy.consequence_established
    assert policy.consequence is not None
    assert policy.consequence.consequence_type == "progression_ineligible"
    assert report.progression_policy_assessments[0].consequence_type == (
        "progression_ineligible"
    )
    assert not report.progression_policy_assessments[0].consequence_established


def test_nmfc_failed_then_later_passed_no_longer_triggers_policy():
    catalogue = _catalogue()
    results = _all_passed(catalogue)
    results.insert(0, _result(catalogue, "AAE4003W", 40, 2025))
    policy = _policy_result(catalogue, results)
    report = compute_report(_student(results), catalogue)

    assert policy.condition.outcome == "not_satisfied"
    assert not policy.consequence_established
    assert report.progression_policy_assessments[0].condition_outcome == (
        "not_satisfied"
    )
    assert not report.progression_policy_assessments[0].consequence_established
    assert not any(
        "All first-semester courses must be passed before progression" in reason
        for reason in report.exclusion_risk.reasons
    )


def test_nmfc_multiple_failures_then_pass_counts_as_completed():
    catalogue = _catalogue()
    results = _all_passed(catalogue)
    results.insert(0, _result(catalogue, "AAE4003W", 35, 2024))
    results.insert(1, _result(catalogue, "AAE4003W", 45, 2025))
    policy = _policy_result(catalogue, results)

    assert policy.condition.outcome == "not_satisfied"
    assert not policy.consequence_established


def test_nmfc_pass_then_later_fail_preserves_existing_completion_semantics():
    catalogue = _catalogue()
    results = _all_passed(catalogue)
    results.append(_result(catalogue, "AAE4003W", 40, 2027))
    policy = _policy_result(catalogue, results)

    assert policy.condition.outcome == "not_satisfied"
    assert not policy.consequence_established


def test_nmfc_pending_required_course_is_unresolved_not_failed():
    catalogue = _catalogue()
    results = _all_passed(catalogue)
    results[0] = _result(catalogue, "AAE4003W", None)
    policy = _policy_result(catalogue, results)

    assert policy.condition.outcome == "unresolved"
    assert not policy.condition.assessment_complete
    assert not policy.consequence_established
    assert "AAE4003W" in policy.condition.detail
    assert "failed course" not in policy.condition.detail.lower()


def test_nmfc_missing_required_course_evidence_is_unresolved_without_coverage():
    catalogue = _catalogue()
    results = [
        _result(catalogue, code, 70)
        for code in NMFC_FIRST_SEMESTER
        if code != "AAE4003W"
    ]
    policy = _policy_result(catalogue, results)

    assert policy.condition.outcome == "unresolved"
    assert not policy.condition.assessment_complete
    assert not policy.consequence_established
    assert "complete academic-record coverage" in policy.condition.detail.lower()
    assert "AAE4003W" in policy.condition.detail


def test_nmfc_grading_scheme_owns_pass_classification():
    catalogue = _catalogue()
    results = _all_passed(catalogue)
    results[0] = _result(catalogue, "AAE4003W", 65)

    default_policy = _policy_result(catalogue, results)
    seventy_policy = _policy_result(
        catalogue,
        results,
        grading_scheme=SyntheticSeventyPassGradingScheme(),
        academic_record_coverage_evidence=[
            AcademicRecordCoverageEvidence(
                tuple(NMFC_FIRST_SEMESTER),
                "complete",
                authority="registry",
                verification_status="verified",
            )
        ],
    )

    assert default_policy.condition.outcome == "not_satisfied"
    assert seventy_policy.condition.outcome == "satisfied"


def test_nmfc_policy_status_source_and_formal_act_boundary():
    catalogue = _catalogue()
    results = _all_passed(catalogue)
    results[0] = _result(catalogue, "AAE4003W", 40)
    report = compute_report(_student(results), catalogue)
    assessment = report.progression_policy_assessments[0]

    assert assessment.policy_id == NMFC_POLICY_ID
    assert assessment.policy_status == "unverified"
    assert assessment.effective_status == "unverified"
    assert assessment.source_reference == NMFC_SOURCE_REFERENCE
    text = str(report).lower()
    assert "student is excluded" not in text
    assert "readmission refused" not in text
    assert "senate decision" not in text
    assert "faculty decision" not in text


def test_university_two_completion_prerequisite_is_institution_neutral():
    courses = {
        code: CourseFact(code, code, 0, 0, [], [], "SYN")
        for code in ("REQ-A", "REQ-B", "REQ-C")
    }
    catalogue = Catalogue(
        courses=courses,
        majors={},
        programmes={
            "P-OMEGA": ProgrammeRules(
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
                        "policy_id": "U2-FOUNDATION-COMPLETE",
                        "verification_status": "verified",
                        "condition": {
                            "type": "required_course_pool_incomplete",
                            "label": "Foundation requirements incomplete",
                            "course_codes": ["REQ-A", "REQ-B", "REQ-C"],
                        },
                        "consequence": {
                            "type": "progression_ineligible",
                            "label": "Foundation progression requirement not met",
                        },
                    }
                ],
            )
        },
        forbidden_combinations=[],
        faculty_key="university_two",
        programme_key="P-OMEGA",
        scope_status="verified",
    )
    student = StudentRecord(
        "U2",
        "University Two",
        "P-OMEGA",
        [],
        [
            CourseResult("REQ-A", "REQ-A", 0, 0, 40, None, 2025),
            CourseResult("REQ-A", "REQ-A", 0, 0, 70, None, 2026),
            CourseResult("REQ-B", "REQ-B", 0, 0, 70, None, 2026),
            CourseResult("REQ-C", "REQ-C", 0, 0, 70, None, 2026),
        ],
        "university_two",
        "P-OMEGA",
    )

    report = compute_report(student, catalogue)

    assert report.progression_policy_assessments[0].condition_outcome == (
        "not_satisfied"
    )
    assert not report.progression_policy_assessments[0].consequence_established


def test_stage8e_failed_any_legacy_behavior_remains_global():
    raw = {
        "type": "failed_any",
        "label": "Legacy failed any",
        "course_codes": ["ALPHA"],
    }
    spec = _failed_progression_metric_spec(raw, raw["label"])
    assert spec is not None
    student = StudentRecord(
        "LEGACY",
        "Legacy",
        "Legacy",
        [],
        [
            CourseResult("ALPHA", "Alpha", 0, 0, 40, None, 2025),
            CourseResult("ALPHA", "Alpha", 0, 0, 70, None, 2026),
        ],
    )

    result = _evaluate_failed_progression_metric(spec, student, 2026, None, None)

    assert result.value == 1
    assert result.failed_codes == ("ALPHA",)


def test_stage8y_architecture_guards():
    from engine import rule_engine

    condition_source = inspect.getsource(rule_engine._required_course_pool_condition_result)
    runtime_source = inspect.getsource(rule_engine._evaluate_progression_condition)
    spec_source = inspect.getsource(rule_engine._required_course_pool_completion_spec)
    builder_source = inspect.getsource(build_health_2026.nmfc_first_semester_progression_policy)
    health_text = Path("data/uct_health/degree_requirements.json").read_text(
        encoding="utf-8"
    )

    assert "_completion_progression_result" in condition_source
    shared = inspect.getsource(rule_engine._completion_progression_result)
    assert "CourseCompletionResolver" in shared
    assert ".resolve(" in shared
    assert "is_passed" not in condition_source
    assert "is_failed" not in condition_source
    assert "mark >=" not in condition_source
    assert "failed_any" not in builder_source
    assert "required_course_pool_incomplete" in spec_source
    assert "rule_type == \"not\"" not in runtime_source
    assert "uct_health" not in condition_source.lower()
    assert "nmfc" not in condition_source.lower()
    assert "repeat_year_failure" in health_text
    assert "Fundamentals course must be passed" in health_text
