from pathlib import Path
from typing import Any

from recognition_fixtures import empty_recognition_snapshot

from app import _to_dict
from curriculum_reasoning_engine.adapters.transcripts.uct import UCTTranscriptAdapter
from engine.catalogue import load_catalogue
from engine.curriculum import CurriculumEvaluator
from engine.models import (
    AcademicRecordCoverageEvidence,
    Catalogue,
    CourseFact,
    CourseResult,
    ProgrammeRules,
    StudentRecord,
)
from engine.rule_engine import (
    _evaluate_progression_policy,
    compute_report,
)

NMFC_POLICY_ID = "UCT-HEALTH-2026-NMFC-FIRST-SEMESTER-PROGRESSION"
NMFC_SOURCE_REFERENCE = (
    "2026 Faculty of Health Sciences Undergraduate Handbook, page 65, "
    "Rules and curricula for undergraduate programmes"
)
NMFC_FIRST_SEMESTER = (
    "AAE4003W",
    "MDN4017W",
    "PED4017W",
    "OBS4006W",
    "PRY4001W",
)


def _health_catalogue() -> Catalogue:
    return load_catalogue("uct_health")


def _nmfc_policy(catalogue: Catalogue) -> dict[str, Any]:
    policies = [
        rule
        for rule in catalogue.programmes["nmfc_medical_training"].progression_rules
        if rule.get("type") == "progression_policy"
    ]
    assert len(policies) == 1
    return policies[0]


def _health_result(
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


def _nmfc_student(results: list[CourseResult]) -> StudentRecord:
    return StudentRecord(
        "NMFC-8Y2",
        "NMFC Coverage",
        "Nelson Mandela Fidel Castro Medical Training Programme",
        [],
        results,
        "uct_health",
        "nmfc_medical_training",
        "",
        1,
    )


def _nmfc_all_passed(catalogue: Catalogue) -> list[CourseResult]:
    return [_health_result(catalogue, code, 70) for code in NMFC_FIRST_SEMESTER]


def _coverage(
    codes: tuple[str, ...] = NMFC_FIRST_SEMESTER,
    *,
    coverage_state: str = "complete",
    verification_status: str = "verified",
    source_reference: str = "SIS result snapshot",
) -> AcademicRecordCoverageEvidence:
    return AcademicRecordCoverageEvidence(
        course_codes=codes,
        coverage_state=coverage_state,
        source_reference=source_reference,
        authority="registry",
        verification_status=verification_status,
    )


def _nmfc_policy_result(
    results: list[CourseResult],
    *,
    coverage: list[AcademicRecordCoverageEvidence] | None = None,
):
    catalogue = _health_catalogue()
    return _evaluate_progression_policy(
        _nmfc_policy(catalogue),
        student=_nmfc_student(results),
        catalogue=catalogue,
        latest_year=2026,
        grading_scheme=None,
        credit_framework=None,
        course_code_scheme=None,
        course_load_framework=None,
        stage_repeat_evidence=None,
        result_context_evidence=None,
        academic_record_coverage_evidence=coverage,
        completion_recognition=empty_recognition_snapshot(_nmfc_student(results), catalogue),
        programme_key="nmfc_medical_training",
        pathway_key="",
    )


def _u2_catalogue() -> Catalogue:
    courses = {
        code: CourseFact(code, code, 0, 0, [], [], "SYN")
        for code in ("REQ-A", "REQ-B", "REQ-C")
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
                "policy_id": "U2-FOUNDATION-COVERAGE",
                "verification_status": "verified",
                "source_reference": "University Two Regulation 1",
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


def _u2_student(results: list[CourseResult]) -> StudentRecord:
    return StudentRecord(
        "U2-8Y2",
        "University Two",
        "P-OMEGA",
        [],
        results,
        "university_two",
        "P-OMEGA",
        "",
        1,
    )


def _u2_result(code: str, mark: int | None, year: int = 2026) -> CourseResult:
    return CourseResult(code, code, 0, 0, mark, None, year)


def _u2_report(
    results: list[CourseResult],
    *,
    coverage: list[AcademicRecordCoverageEvidence] | None = None,
):
    return compute_report(
        _u2_student(results),
        _u2_catalogue(),
        academic_record_coverage_evidence=coverage,
        completion_recognition=empty_recognition_snapshot(_u2_student(results), _u2_catalogue()),
    )


def test_no_coverage_all_passed_still_establishes_completion():
    catalogue = _health_catalogue()
    policy = _nmfc_policy_result(_nmfc_all_passed(catalogue))

    assert policy.condition.outcome == "not_satisfied"
    assert policy.condition.assessment_complete
    assert not policy.consequence_established


def test_no_coverage_one_missing_is_unresolved_not_ineligible():
    catalogue = _health_catalogue()
    results = [
        _health_result(catalogue, code, 70)
        for code in NMFC_FIRST_SEMESTER
        if code != "AAE4003W"
    ]
    policy = _nmfc_policy_result(results)

    assert policy.condition.outcome == "unresolved"
    assert not policy.condition.assessment_complete
    assert policy.condition.status == "unverified"
    assert not policy.consequence_established
    assert "AAE4003W" in policy.condition.detail


def test_no_coverage_fail_only_is_unresolved_because_record_may_be_partial():
    catalogue = _health_catalogue()
    results = _nmfc_all_passed(catalogue)
    results[0] = _health_result(catalogue, "AAE4003W", 40)
    policy = _nmfc_policy_result(results)

    assert policy.condition.outcome == "unresolved"
    assert not policy.consequence_established
    assert "AAE4003W" in policy.condition.detail


def test_no_coverage_pending_is_unresolved_not_failure():
    catalogue = _health_catalogue()
    results = _nmfc_all_passed(catalogue)
    results[0] = _health_result(catalogue, "AAE4003W", None)
    policy = _nmfc_policy_result(results)

    assert policy.condition.outcome == "unresolved"
    assert "AAE4003W has a pending result" in policy.condition.detail
    assert "failed course" not in policy.condition.detail.lower()
    assert not policy.consequence_established


def test_verified_complete_coverage_missing_course_establishes_incomplete_pool():
    catalogue = _health_catalogue()
    results = [
        _health_result(catalogue, code, 70)
        for code in NMFC_FIRST_SEMESTER
        if code != "AAE4003W"
    ]
    policy = _nmfc_policy_result(results, coverage=[_coverage()])

    assert policy.condition.outcome == "satisfied"
    assert policy.condition.assessment_complete
    assert policy.consequence_established
    assert "No completion witness for AAE4003W" in policy.condition.detail


def test_verified_complete_coverage_fail_only_establishes_incomplete_pool():
    catalogue = _health_catalogue()
    results = _nmfc_all_passed(catalogue)
    results[0] = _health_result(catalogue, "AAE4003W", 40)
    policy = _nmfc_policy_result(results, coverage=[_coverage()])

    assert policy.condition.outcome == "satisfied"
    assert policy.condition.assessment_complete
    assert policy.consequence_established


def test_complete_coverage_does_not_turn_pending_into_failure():
    catalogue = _health_catalogue()
    results = _nmfc_all_passed(catalogue)
    results[0] = _health_result(catalogue, "AAE4003W", None)
    policy = _nmfc_policy_result(results, coverage=[_coverage()])

    assert policy.condition.outcome == "unresolved"
    assert not policy.condition.assessment_complete
    assert not policy.consequence_established


def test_partial_coverage_missing_course_remains_unresolved():
    catalogue = _health_catalogue()
    results = [
        _health_result(catalogue, code, 70)
        for code in NMFC_FIRST_SEMESTER
        if code != "AAE4003W"
    ]
    policy = _nmfc_policy_result(
        results,
        coverage=[_coverage(coverage_state="partial")],
    )

    assert policy.condition.outcome == "unresolved"
    assert not policy.consequence_established


def test_unverified_complete_coverage_bounds_condition_authority():
    catalogue = _health_catalogue()
    results = [
        _health_result(catalogue, code, 70)
        for code in NMFC_FIRST_SEMESTER
        if code != "AAE4003W"
    ]
    policy = _nmfc_policy_result(
        results,
        coverage=[_coverage(verification_status="unverified")],
    )

    assert policy.condition.outcome == "satisfied"
    assert policy.condition.status == "unverified"
    assert not policy.condition.assessment_complete
    assert policy.consequence_established
    assert policy.effective_status == "unverified"


def test_conflicting_coverage_preserves_conflict():
    catalogue = _health_catalogue()
    results = [
        _health_result(catalogue, code, 70)
        for code in NMFC_FIRST_SEMESTER
        if code != "AAE4003W"
    ]
    policy = _nmfc_policy_result(
        results,
        coverage=[
            AcademicRecordCoverageEvidence(
                ("AAE4003W",),
                "conflict",
                authority="registry",
                verification_status="verified",
            )
        ],
    )

    assert policy.condition.outcome == "conflict"
    assert not policy.condition.assessment_complete
    assert policy.effective_status == "conflict"


def test_fail_then_pass_without_coverage_preserves_source_faithful_completion():
    catalogue = _health_catalogue()
    results = _nmfc_all_passed(catalogue)
    results.insert(0, _health_result(catalogue, "AAE4003W", 40, 2025))
    policy = _nmfc_policy_result(results)

    assert policy.condition.outcome == "not_satisfied"
    assert not policy.consequence_established


def test_multiple_failures_then_pass_without_coverage_is_complete():
    catalogue = _health_catalogue()
    results = _nmfc_all_passed(catalogue)
    results.insert(0, _health_result(catalogue, "AAE4003W", 35, 2024))
    results.insert(1, _health_result(catalogue, "AAE4003W", 45, 2025))
    policy = _nmfc_policy_result(results)

    assert policy.condition.outcome == "not_satisfied"
    assert not policy.consequence_established


def test_mixed_known_incomplete_and_unknown_keeps_assessment_incomplete():
    report = _u2_report(
        [_u2_result("REQ-C", 70)],
        coverage=[
            AcademicRecordCoverageEvidence(
                ("REQ-A",),
                "complete",
                authority="registry",
                verification_status="verified",
            )
        ],
    )
    assessment = report.progression_policy_assessments[0]

    assert assessment.condition_outcome == "satisfied"
    assert assessment.consequence_established
    assert not assessment.assessment_complete
    assert "REQ-A" in assessment.detail
    assert "REQ-B" in assessment.detail


def test_mixed_known_incomplete_and_pending_keeps_assessment_incomplete():
    report = _u2_report(
        [_u2_result("REQ-B", None), _u2_result("REQ-C", 70)],
        coverage=[
            AcademicRecordCoverageEvidence(
                ("REQ-A",),
                "complete",
                authority="registry",
                verification_status="verified",
            )
        ],
    )
    assessment = report.progression_policy_assessments[0]

    assert assessment.condition_outcome == "satisfied"
    assert assessment.consequence_established
    assert not assessment.assessment_complete
    assert "REQ-B has a pending result" in assessment.detail


def test_coverage_source_is_separate_from_policy_source():
    catalogue = _health_catalogue()
    results = [
        _health_result(catalogue, code, 70)
        for code in NMFC_FIRST_SEMESTER
        if code != "AAE4003W"
    ]
    report = compute_report(
        _nmfc_student(results),
        catalogue,
        academic_record_coverage_evidence=[
            _coverage(source_reference="Verified SIS snapshot")
        ],
    )
    assessment = report.progression_policy_assessments[0]

    assert assessment.source_reference == NMFC_SOURCE_REFERENCE
    assert "Verified SIS snapshot" not in assessment.source_reference


def test_nmfc_policy_authority_still_bounds_verified_coverage():
    catalogue = _health_catalogue()
    results = [
        _health_result(catalogue, code, 70)
        for code in NMFC_FIRST_SEMESTER
        if code != "AAE4003W"
    ]
    report = compute_report(
        _nmfc_student(results),
        catalogue,
        academic_record_coverage_evidence=[_coverage()],
        completion_recognition=empty_recognition_snapshot(_nmfc_student(results), catalogue),
    )
    assessment = report.progression_policy_assessments[0]

    assert assessment.policy_status == "unverified"
    assert assessment.effective_status == "unverified"
    assert assessment.consequence_type == "progression_ineligible"
    assert assessment.consequence_established


def test_manual_nmfc_partial_record_without_coverage_is_unresolved():
    catalogue = _health_catalogue()
    results = [
        _health_result(catalogue, code, 70)
        for code in NMFC_FIRST_SEMESTER
        if code != "AAE4003W"
    ]
    report = compute_report(_nmfc_student(results), catalogue)
    assessment = report.progression_policy_assessments[0]

    assert assessment.condition_outcome == "unresolved"
    assert not assessment.consequence_established
    assert not report.exclusion_risk.at_risk


def test_authoritative_complete_record_can_support_absence_without_failed_result():
    catalogue = _health_catalogue()
    results = [
        _health_result(catalogue, code, 70)
        for code in NMFC_FIRST_SEMESTER
        if code != "AAE4003W"
    ]
    report = compute_report(
        _nmfc_student(results),
        catalogue,
        academic_record_coverage_evidence=[_coverage()],
        completion_recognition=empty_recognition_snapshot(_nmfc_student(results), catalogue),
    )
    assessment = report.progression_policy_assessments[0]

    assert assessment.condition_outcome == "satisfied"
    assert assessment.consequence_established
    assert not any(result.code == "AAE4003W" for result in results)


def test_university_two_partial_manual_record_without_coverage_is_unresolved():
    report = _u2_report([_u2_result("REQ-B", 70), _u2_result("REQ-C", 70)])
    assessment = report.progression_policy_assessments[0]

    assert assessment.condition_outcome == "unresolved"
    assert not assessment.consequence_established


def test_university_two_complete_coverage_with_missing_requirement_triggers():
    report = _u2_report(
        [_u2_result("REQ-B", 70), _u2_result("REQ-C", 70)],
        coverage=[_coverage(("REQ-A", "REQ-B", "REQ-C"))],
    )
    assessment = report.progression_policy_assessments[0]

    assert assessment.condition_outcome == "satisfied"
    assert assessment.consequence_established


def test_university_two_fail_only_needs_coverage_to_trigger():
    no_coverage = _u2_report(
        [_u2_result("REQ-A", 40), _u2_result("REQ-B", 70), _u2_result("REQ-C", 70)]
    ).progression_policy_assessments[0]
    covered = _u2_report(
        [_u2_result("REQ-A", 40), _u2_result("REQ-B", 70), _u2_result("REQ-C", 70)],
        coverage=[_coverage(("REQ-A", "REQ-B", "REQ-C"))],
    ).progression_policy_assessments[0]

    assert no_coverage.condition_outcome == "unresolved"
    assert not no_coverage.consequence_established
    assert covered.condition_outcome == "satisfied"
    assert covered.consequence_established


def test_university_two_fail_then_pass_without_coverage_is_complete():
    report = _u2_report(
        [
            _u2_result("REQ-A", 40, 2025),
            _u2_result("REQ-A", 70, 2026),
            _u2_result("REQ-B", 70),
            _u2_result("REQ-C", 70),
        ]
    )
    assessment = report.progression_policy_assessments[0]

    assert assessment.condition_outcome == "not_satisfied"
    assert not assessment.consequence_established


def test_policy_assessment_serializes_unresolved_and_ineligible_states():
    unresolved = _to_dict(
        _u2_report([_u2_result("REQ-B", 70), _u2_result("REQ-C", 70)])
    )
    established = _to_dict(
        _u2_report(
            [_u2_result("REQ-B", 70), _u2_result("REQ-C", 70)],
            coverage=[_coverage(("REQ-A", "REQ-B", "REQ-C"))],
        )
    )

    unresolved_assessment = unresolved["progression_policy_assessments"][0]
    established_assessment = established["progression_policy_assessments"][0]
    assert unresolved_assessment["condition_outcome"] == "unresolved"
    assert not unresolved_assessment["consequence_established"]
    assert established_assessment["condition_outcome"] == "satisfied"
    assert established_assessment["consequence_type"] == "progression_ineligible"
    assert established_assessment["consequence_established"]


def test_parser_does_not_silently_assert_complete_coverage():
    student = UCTTranscriptAdapter().parse_text(
        """
        Name: Student, Test
        Campus ID: ABC123
        Programme: P-OMEGA
        Year: 2026
        REQ 1000A Requirement B 0 0 70 P
        """
    )

    assert not hasattr(student, "academic_record_coverage_evidence")


def test_all_courses_global_boolean_behavior_is_unchanged():
    catalogue = _u2_catalogue()
    evaluation = CurriculumEvaluator(
        _u2_student([_u2_result("REQ-B", 70), _u2_result("REQ-C", 70)]),
        catalogue,
    ).evaluate(
        {
            "type": "all_courses",
            "label": "Foundation",
            "course_codes": ["REQ-A", "REQ-B", "REQ-C"],
        }
    )

    assert not evaluation.complete
    assert evaluation.status == "unverified"  # Neither evidence domain is closed here.
    assert evaluation.used_course_codes == ["REQ-B", "REQ-C"]


def test_existing_failed_any_compatibility_remains_in_source():
    source = Path("engine/rule_engine.py").read_text(encoding="utf-8")

    assert '"failed_any"' in source
    assert "failed_metric" in source
