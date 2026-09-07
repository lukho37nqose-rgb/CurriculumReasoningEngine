import inspect
from typing import Any

from engine.models import (
    Catalogue,
    CourseResult,
    ProgrammeRules,
    ResultContextEvidence,
    StageRepeatEvidence,
    StudentRecord,
)
from engine.rule_engine import (
    ProgressionConditionResult,
    _compute_exclusion_risk,
    _evaluate_progression_all_of,
    _evaluate_progression_condition,
)


def _failed_child(**context_overrides: Any) -> dict[str, Any]:
    context = {
        "stage_key": "PROFESSIONAL",
        "registration_period_key": "R-C",
    }
    context.update(context_overrides)
    return {
        "type": "failed_metric",
        "label": "Failure in repeated context",
        "metric_basis": "course_count",
        "identity": "attempt",
        "temporal_scope": "institutional_context",
        "threshold": 1,
        "context": context,
    }


def _repeat_child(**overrides: Any) -> dict[str, Any]:
    rule = {
        "type": "formal_stage_repeat",
        "label": "Formal repeated stage",
        "stage_key": "PROFESSIONAL",
        "registration_period_key": "R-C",
    }
    rule.update(overrides)
    return rule


def _all_of(*children: dict[str, Any], label: str = "Repeat-stage failure"):
    return {
        "type": "all_of",
        "label": label,
        "children": list(children) or [_repeat_child(), _failed_child()],
    }


def _catalogue(rules: list[dict[str, Any]]) -> Catalogue:
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
        progression_rules=rules,
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


def _student(results: list[CourseResult] | None = None) -> StudentRecord:
    return StudentRecord(
        "UTWO-ALLOF",
        "Opaque Student",
        "P-OMEGA",
        [],
        results or [_result()],
        faculty_key="university_two",
        programme_key="P-OMEGA",
        years_registered=3,
    )


def _result(*, code: str = "X", attempt_id: str = "X-2", mark: int = 40):
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


def _stage_repeat(
    repeat_state: str = "repeated",
    *,
    verification_status: str = "verified",
) -> StageRepeatEvidence:
    return StageRepeatEvidence(
        programme_key="P-OMEGA",
        stage_key="PROFESSIONAL",
        registration_period_key="R-C",
        repeat_state=repeat_state,
        source_reference="stage-repeat",
        authority="registrar",
        verification_status=verification_status,
    )


def _context(
    *,
    attempt_id: str = "X-2",
    programme_key: str = "P-OMEGA",
    stage_key: str = "PROFESSIONAL",
    registration_period_key: str = "R-C",
    verification_status: str = "verified",
) -> ResultContextEvidence:
    return ResultContextEvidence(
        attempt_id=attempt_id,
        programme_key=programme_key,
        stage_key=stage_key,
        registration_period_key=registration_period_key,
        source_reference="result-context",
        authority="registrar",
        verification_status=verification_status,
    )


def _risk(
    *,
    rules: list[dict[str, Any]] | None = None,
    results: list[CourseResult] | None = None,
    repeat_evidence: list[StageRepeatEvidence] | None = None,
    context_evidence: list[ResultContextEvidence] | None = None,
):
    return _compute_exclusion_risk(
        _student(results),
        _catalogue(rules or [_all_of()]),
        "P-OMEGA",
        stage_repeat_evidence=repeat_evidence if repeat_evidence is not None else [_stage_repeat()],
        result_context_evidence=context_evidence if context_evidence is not None else [_context()],
    )


def test_positive_university_two_all_of_establishes_condition_without_exclusion_claim():
    risk = _risk()

    assert risk.at_risk
    assert risk.assessed
    assert risk.status == "verified"
    assert "Repeat-stage failure: 2 of 2 component progression condition(s) satisfied." in risk.reasons[0]
    assert "excluded" not in risk.reasons[0].lower()
    assert "readmission denied" not in risk.reasons[0].lower()


def test_negative_period_control_does_not_satisfy_all_of():
    risk = _risk(context_evidence=[_context(registration_period_key="R-B")])

    assert not risk.at_risk
    assert risk.assessed
    assert risk.status == "verified"
    assert "1 of 2 component progression condition(s) satisfied" in risk.basis


def test_negative_stage_control_does_not_satisfy_all_of():
    risk = _risk(context_evidence=[_context(stage_key="CORE")])

    assert not risk.at_risk
    assert risk.assessed
    assert "1 of 2 component progression condition(s) satisfied" in risk.basis


def test_wrong_programme_context_does_not_satisfy_all_of():
    risk = _risk(context_evidence=[_context(programme_key="P-ALPHA")])

    assert not risk.at_risk
    assert risk.assessed
    assert "1 of 2 component progression condition(s) satisfied" in risk.basis


def test_continuation_not_repeat_control_does_not_satisfy_all_of():
    risk = _risk(repeat_evidence=[_stage_repeat("not_repeated")])

    assert not risk.at_risk
    assert risk.assessed
    assert "1 of 2 component progression condition(s) satisfied" in risk.basis


def test_missing_repeat_evidence_makes_parent_unresolved_not_false():
    risk = _risk(repeat_evidence=[])

    assert not risk.at_risk
    assert not risk.assessed
    assert risk.status == "unverified"
    assert "no matching formal stage-repeat evidence" in risk.basis


def test_missing_result_context_makes_parent_unresolved():
    risk = _risk(context_evidence=[])

    assert not risk.at_risk
    assert not risk.assessed
    assert risk.status == "unverified"
    assert "institutional context evidence is unavailable" in risk.basis


def test_repeat_evidence_conflict_blocks_verified_satisfaction():
    risk = _risk(repeat_evidence=[_stage_repeat("repeated"), _stage_repeat("not_repeated")])

    assert not risk.at_risk
    assert not risk.assessed
    assert risk.status == "conflict"
    assert "conflicting formal stage-repeat evidence" in risk.basis


def test_result_context_conflict_blocks_verified_satisfaction():
    risk = _risk(context_evidence=[_context(), _context(stage_key="CORE")])

    assert not risk.at_risk
    assert not risk.assessed
    assert risk.status == "conflict"
    assert "conflicting institutional context evidence" in risk.basis


def test_provisional_repeat_evidence_bounds_parent_authority():
    risk = _risk(repeat_evidence=[_stage_repeat("repeated", verification_status="provisional")])

    assert risk.at_risk
    assert not risk.assessed
    assert risk.status == "unverified"
    assert "bounded by provisional evidence" in risk.basis


def test_provisional_result_context_bounds_parent_authority():
    risk = _risk(context_evidence=[_context(verification_status="provisional")])

    assert risk.at_risk
    assert not risk.assessed
    assert risk.status == "unverified"
    assert "bounded by provisional evidence" in risk.basis


def test_false_plus_unknown_is_logically_false_but_assessment_incomplete():
    condition = _evaluate_progression_condition(
        _all_of(_repeat_child(), _failed_child()),
        student=_student(),
        catalogue=_catalogue([]),
        latest_year=2026,
        grading_scheme=None,
        course_load_framework=None,
        stage_repeat_evidence=[_stage_repeat("not_repeated")],
        result_context_evidence=[],
        programme_key="P-OMEGA",
        pathway_key="",
    )

    assert condition.outcome == "not_satisfied"
    assert not condition.assessment_complete
    assert any(child.outcome == "unresolved" for child in condition.children)


def test_unsupported_child_is_not_silently_ignored_or_manual():
    risk = _risk(rules=[_all_of(_repeat_child(), {"type": "some_future_rule", "label": "Future"})])

    assert not risk.at_risk
    assert not risk.assessed
    assert risk.status == "unverified"
    assert "unsupported progression condition type" in risk.basis
    assert "manual" not in risk.basis.lower()


def test_nested_all_of_is_explicitly_unsupported_for_stage8o():
    risk = _risk(rules=[_all_of(_repeat_child(), _all_of(label="Nested"))])

    assert not risk.at_risk
    assert not risk.assessed
    assert "unsupported progression condition type 'all_of'" in risk.basis


def test_flat_progression_rules_remain_independent_not_implicit_conjunction():
    risk = _risk(
        rules=[_repeat_child(), _failed_child()],
        repeat_evidence=[_stage_repeat("not_repeated")],
        context_evidence=[_context()],
    )

    assert risk.at_risk
    assert risk.assessed
    assert risk.reasons == [
        "Failure in repeated context: failed course count is 1; the configured threshold is 1."
    ]


def test_neutral_condition_result_shape_allows_future_any_of_witnesses():
    result = ProgressionConditionResult(
        "Verified witness",
        "satisfied",
        True,
        "verified",
        "Verified witness established.",
    )

    assert result.outcome == "satisfied"
    assert result.status == "verified"
    assert result.children == ()


def test_all_of_is_pure_logic_and_health_compatibility_remains_separate():
    source = inspect.getsource(_compute_exclusion_risk)
    all_of_source = inspect.getsource(_evaluate_progression_condition)

    assert 'rule_type == "repeat_year_failure"' in source
    assert 'rule_type == "all_of"' in all_of_source
    assert 'rule_type == "any_of"' not in all_of_source
    assert "uct_health" not in all_of_source
    assert "result.is_failed" not in inspect.getsource(_evaluate_progression_all_of)
