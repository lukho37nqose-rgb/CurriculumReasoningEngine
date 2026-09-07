import inspect
from typing import Any

from engine.models import (
    Catalogue,
    CourseResult,
    PathwayDefinition,
    ProgrammeRules,
    ResultContextEvidence,
    StageRepeatEvidence,
    StudentRecord,
)
from engine.rule_engine import (
    _compute_exclusion_risk,
    _evaluate_failed_progression_metric,
    _failed_progression_metric_spec,
)


def _rule(**overrides: Any) -> dict[str, Any]:
    rule = {
        "type": "failed_metric",
        "label": "Professional-period failed attempt",
        "metric_basis": "course_count",
        "identity": "attempt",
        "temporal_scope": "institutional_context",
        "threshold": 1,
        "context": {
            "stage_key": "PROFESSIONAL",
            "registration_period_key": "R-C",
        },
    }
    rule.update(overrides)
    return rule


def _catalogue(
    rules: list[dict[str, Any]],
    *,
    programme_key: str = "P-OMEGA",
    pathways: dict[str, PathwayDefinition] | None = None,
) -> Catalogue:
    programme = ProgrammeRules(
        key=programme_key,
        name=programme_key,
        total_nqf_credits=0,
        level_7_nqf_credits=0,
        semester_course_equivalents=0,
        senior_course_equivalents=0,
        humanities_course_equivalents=0,
        required_majors=0,
        required_humanities_majors=0,
        progression_rules=rules,
        pathways=pathways or {},
    )
    return Catalogue(
        courses={},
        majors={},
        programmes={programme.key: programme},
        forbidden_combinations=[],
        faculty_key="university_two",
        programme_key=programme.key,
        scope_status="verified",
    )


def _student(
    results: list[CourseResult],
    *,
    programme_key: str = "P-OMEGA",
    pathway_key: str = "",
) -> StudentRecord:
    return StudentRecord(
        "UTWO-CONTEXT",
        "Opaque Student",
        programme_key,
        [],
        results,
        faculty_key="university_two",
        programme_key=programme_key,
        pathway_key=pathway_key,
        years_registered=3,
    )


def _result(code: str = "X", *, attempt_id: str = "X-A1", mark: int = 40):
    return CourseResult(
        code,
        code,
        0,
        0,
        mark,
        "RAW",
        academic_year=2026,
        attempt_id=attempt_id,
    )


def _context(
    attempt_id: str = "X-A1",
    *,
    programme_key: str = "P-OMEGA",
    pathway_key: str = "",
    stage_key: str = "PROFESSIONAL",
    registration_period_key: str = "R-C",
    verification_status: str = "verified",
    authority: str = "registrar",
) -> ResultContextEvidence:
    return ResultContextEvidence(
        attempt_id=attempt_id,
        programme_key=programme_key,
        pathway_key=pathway_key,
        stage_key=stage_key,
        registration_period_key=registration_period_key,
        source_reference="staff-entry:attempt-context",
        authority=authority,
        verification_status=verification_status,
    )


def _stage_repeat() -> StageRepeatEvidence:
    return StageRepeatEvidence(
        programme_key="P-OMEGA",
        stage_key="PROFESSIONAL",
        registration_period_key="R-C",
        repeat_state="repeated",
        source_reference="staff-entry:stage-repeat",
        authority="registrar",
        verification_status="verified",
    )


def _risk(
    results: list[CourseResult],
    contexts: list[ResultContextEvidence] | None,
    *,
    rules: list[dict[str, Any]] | None = None,
    programme_key: str = "P-OMEGA",
    pathway_key: str = "",
    pathways: dict[str, PathwayDefinition] | None = None,
):
    return _compute_exclusion_risk(
        _student(results, programme_key=programme_key, pathway_key=pathway_key),
        _catalogue(rules or [_rule()], programme_key=programme_key, pathways=pathways),
        programme_key,
        stage_repeat_evidence=[_stage_repeat()],
        result_context_evidence=contexts,
    )


def test_student_a_correct_context_identifies_failed_attempt_without_composition():
    risk = _risk([_result()], [_context()])

    assert risk.at_risk
    assert risk.assessed
    assert risk.status == "verified"
    assert (
        "Professional-period failed attempt: failed course count is 1; "
        "the configured threshold is 1."
    ) in risk.reasons


def test_student_b_wrong_period_is_verified_non_match_not_missing_context():
    risk = _risk(
        [_result()],
        [_context(registration_period_key="R-B")],
    )

    assert not risk.at_risk
    assert risk.assessed
    assert risk.status == "verified"
    assert "below the 1 threshold" in risk.basis
    assert "unavailable" not in risk.basis


def test_student_c_wrong_stage_is_verified_non_match_not_missing_context():
    risk = _risk([_result()], [_context(stage_key="CORE")])

    assert not risk.at_risk
    assert risk.assessed
    assert "below the 1 threshold" in risk.basis
    assert "unavailable" not in risk.basis


def test_student_d_programme_change_context_does_not_cross_apply():
    wrong_programme = _risk([_result()], [_context(programme_key="P-ALPHA")])
    assert not wrong_programme.at_risk
    assert wrong_programme.assessed

    matched_programme = _risk(
        [_result(attempt_id="X-A1"), _result("Y", attempt_id="Y-A1")],
        [
            _context("X-A1", programme_key="P-ALPHA"),
            _context("Y-A1", programme_key="P-OMEGA"),
        ],
    )
    assert matched_programme.at_risk
    assert matched_programme.status == "verified"


def test_student_e_same_course_two_attempts_are_distinguished_by_attempt_id():
    attempts = [
        _result("X", attempt_id="X-A1"),
        _result("X", attempt_id="X-A2"),
    ]
    spec = _failed_progression_metric_spec(_rule(), "Professional-period failed attempt")
    assert spec is not None

    result = _evaluate_failed_progression_metric(
        spec,
        _student(attempts),
        latest_year=2026,
        grading_scheme=None,
        course_load_framework=None,
        result_context_evidence=[
            _context("X-A1", registration_period_key="R-B"),
            _context("X-A2", registration_period_key="R-C"),
        ],
        programme_key="P-OMEGA",
        pathway_key="",
    )

    assert result.value == 1
    assert result.matched_context_attempt_ids == ("X-A2",)
    assert result.failed_codes == ("X",)


def test_student_f_missing_context_is_unresolved_not_verified_non_match():
    risk = _risk([_result()], [])

    assert not risk.at_risk
    assert not risk.assessed
    assert risk.status == "unverified"
    assert "institutional context evidence is unavailable" in risk.basis
    assert "X-A1" in risk.basis


def test_student_g_explicit_non_match_is_distinct_from_missing_context():
    risk = _risk([_result()], [_context(stage_key="CORE")])

    assert not risk.at_risk
    assert risk.assessed
    assert risk.status == "verified"
    assert "institutional context evidence is unavailable" not in risk.basis


def test_manual_pilot_context_entry_is_evidence_not_discretionary_policy():
    risk = _risk(
        [_result()],
        [
            _context(
                authority="authorised-advisor",
                verification_status="verified",
            )
        ],
    )

    assert risk.at_risk
    assert risk.status == "verified"
    assert "manual" not in risk.basis.lower()
    assert "discretion" not in risk.basis.lower()


def test_unverified_context_evidence_does_not_upgrade_to_verified_fact():
    risk = _risk([_result()], [_context(verification_status="provisional")])

    assert risk.at_risk
    assert not risk.assessed
    assert risk.status == "unverified"
    assert "provisional" in risk.basis
    assert "cannot be verified" in risk.basis


def test_conflicting_context_for_same_attempt_is_not_resolved_by_list_order():
    risk = _risk([_result()], [_context(stage_key="PROFESSIONAL"), _context(stage_key="CORE")])

    assert not risk.at_risk
    assert not risk.assessed
    assert risk.status == "conflict"
    assert "conflicting institutional context evidence" in risk.basis


def test_pathway_bound_context_does_not_apply_to_another_pathway():
    pathways = {
        "TRACK-A": PathwayDefinition(
            key="TRACK-A",
            name="Track A",
            progression_rules=[
                _rule(
                    context={
                        "stage_key": "PROFESSIONAL",
                        "registration_period_key": "R-C",
                        "pathway_key": "TRACK-A",
                    }
                )
            ],
        ),
        "TRACK-B": PathwayDefinition(
            key="TRACK-B",
            name="Track B",
            progression_rules=[
                _rule(
                    context={
                        "stage_key": "PROFESSIONAL",
                        "registration_period_key": "R-C",
                        "pathway_key": "TRACK-B",
                    }
                )
            ],
        ),
    }

    wrong_pathway = _risk(
        [_result()],
        [_context(pathway_key="TRACK-A")],
        rules=[],
        pathway_key="TRACK-B",
        pathways=pathways,
    )
    assert not wrong_pathway.at_risk
    assert wrong_pathway.assessed

    matched_pathway = _risk(
        [_result()],
        [_context(pathway_key="TRACK-B")],
        rules=[],
        pathway_key="TRACK-B",
        pathways=pathways,
    )
    assert matched_pathway.at_risk
    assert matched_pathway.status == "verified"


def test_contextual_failed_metric_does_not_derive_period_or_stage_from_academic_year():
    risk = _risk([_result(attempt_id="X-A1")], None)

    assert not risk.at_risk
    assert not risk.assessed
    assert "institutional context evidence is unavailable" in risk.basis


def test_health_repeat_year_failure_and_progression_all_of_remain_unintroduced():
    source = inspect.getsource(_compute_exclusion_risk)

    assert 'rule_type == "repeat_year_failure"' in source
    assert "ResultContextEvidence" in source
