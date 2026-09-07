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
    _compute_exclusion_risk,
    _evaluate_progression_all_of,
    _evaluate_progression_policy,
)


def _failed_child() -> dict[str, Any]:
    return {
        "type": "failed_metric",
        "label": "Failure in repeated context",
        "metric_basis": "course_count",
        "identity": "attempt",
        "temporal_scope": "institutional_context",
        "threshold": 1,
        "context": {
            "stage_key": "PROFESSIONAL",
            "registration_period_key": "R-C",
        },
    }


def _repeat_child() -> dict[str, Any]:
    return {
        "type": "formal_stage_repeat",
        "label": "Formal repeated stage",
        "stage_key": "PROFESSIONAL",
        "registration_period_key": "R-C",
    }


def _condition() -> dict[str, Any]:
    return {
        "type": "all_of",
        "label": "Repeat-stage failure condition",
        "children": [_repeat_child(), _failed_child()],
    }


def _policy(
    *,
    policy_id: str = "U2-PROF-REPEAT-REVIEW",
    verification_status: str = "verified",
    consequence_type: str = "review_required",
    consequence_label: str = "Academic Review Panel review required",
    condition: dict[str, Any] | None = None,
    source_reference: str | None = "University Two Regulation 4.3",
) -> dict[str, Any]:
    rule: dict[str, Any] = {
        "type": "progression_policy",
        "label": "Professional repeat failure policy",
        "policy_id": policy_id,
        "verification_status": verification_status,
        "condition": condition or _condition(),
        "consequence": {
            "type": consequence_type,
            "label": consequence_label,
        },
    }
    if source_reference is not None:
        rule["source_reference"] = source_reference
    return rule


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
        faculty_key="synthetic_university",
        programme_key=programme.key,
        scope_status="verified",
    )


def _student(results: list[CourseResult] | None = None) -> StudentRecord:
    return StudentRecord(
        "STAGE8Q",
        "Policy Student",
        "P-OMEGA",
        [],
        results or [_result()],
        faculty_key="synthetic_university",
        programme_key="P-OMEGA",
        years_registered=3,
    )


def _result(
    *,
    code: str = "X",
    attempt_id: str = "X-2",
    mark: int = 40,
) -> CourseResult:
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


def _context(*, verification_status: str = "verified") -> ResultContextEvidence:
    return ResultContextEvidence(
        attempt_id="X-2",
        programme_key="P-OMEGA",
        stage_key="PROFESSIONAL",
        registration_period_key="R-C",
        source_reference="result-context",
        authority="registrar",
        verification_status=verification_status,
    )


def _risk(
    rule: dict[str, Any],
    *,
    repeat_evidence: list[StageRepeatEvidence] | None = None,
    context_evidence: list[ResultContextEvidence] | None = None,
):
    return _compute_exclusion_risk(
        _student(),
        _catalogue([rule]),
        "P-OMEGA",
        stage_repeat_evidence=(
            [_stage_repeat()] if repeat_evidence is None else repeat_evidence
        ),
        result_context_evidence=(
            [_context()] if context_evidence is None else context_evidence
        ),
    )


def _policy_result(
    rule: dict[str, Any],
    *,
    repeat_evidence: list[StageRepeatEvidence] | None = None,
    context_evidence: list[ResultContextEvidence] | None = None,
):
    return _evaluate_progression_policy(
        rule,
        student=_student(),
        catalogue=_catalogue([]),
        latest_year=2026,
        grading_scheme=None,
        course_load_framework=None,
        stage_repeat_evidence=(
            [_stage_repeat()] if repeat_evidence is None else repeat_evidence
        ),
        result_context_evidence=(
            [_context()] if context_evidence is None else context_evidence
        ),
        programme_key="P-OMEGA",
        pathway_key="",
    )


def test_university_two_review_required_policy_is_not_formal_exclusion():
    rule = _policy()
    result = _policy_result(rule)
    risk = _risk(rule)

    assert result.policy_id == "U2-PROF-REPEAT-REVIEW"
    assert result.condition.outcome == "satisfied"
    assert result.consequence_established
    assert result.consequence is not None
    assert result.consequence.consequence_type == "review_required"
    assert result.effective_status == "verified"
    assert "University Two Regulation 4.3" in result.detail
    assert risk.at_risk
    assert risk.assessed
    assert risk.status == "verified"
    assert "Academic Review Panel review required" in risk.reasons[0]
    assert "excluded" not in risk.reasons[0].lower()
    assert "continuation approved" not in risk.reasons[0].lower()


def test_university_three_same_condition_can_be_progression_ineligible():
    rule = _policy(
        policy_id="U3-PROF-REPEAT-INELIGIBLE",
        consequence_type="progression_ineligible",
        consequence_label="Not eligible to progress to the next stage",
        source_reference="University Three Regulation 9",
    )
    result = _policy_result(rule)
    risk = _risk(rule)

    assert result.condition.outcome == "satisfied"
    assert result.consequence is not None
    assert result.consequence.consequence_type == "progression_ineligible"
    assert result.effective_status == "verified"
    assert risk.at_risk
    assert "Not eligible to progress to the next stage" in risk.reasons[0]
    assert "University Three Regulation 9" in risk.reasons[0]


def test_university_four_same_condition_can_be_advisory_only():
    rule = _policy(
        policy_id="U4-PROF-REPEAT-ADVISORY",
        consequence_type="advisory_risk",
        consequence_label="Academic risk advisory",
        source_reference=None,
    )
    result = _policy_result(rule)

    assert result.condition.outcome == "satisfied"
    assert result.consequence is not None
    assert result.consequence.consequence_type == "advisory_risk"
    assert result.source_reference == ""


def test_unverified_policy_does_not_become_verified_from_verified_evidence():
    rule = _policy(verification_status="unverified")
    result = _policy_result(rule)
    risk = _risk(rule)

    assert result.condition.outcome == "satisfied"
    assert result.consequence_established
    assert result.policy_status == "unverified"
    assert result.effective_status == "unverified"
    assert risk.at_risk
    assert not risk.assessed
    assert risk.status == "unverified"
    assert "bounded by unverified authority/status" in risk.basis


def test_unverified_evidence_bounds_verified_policy():
    rule = _policy()
    result = _policy_result(
        rule,
        context_evidence=[_context(verification_status="provisional")],
    )
    risk = _risk(rule, context_evidence=[_context(verification_status="provisional")])

    assert result.condition.outcome == "satisfied"
    assert result.condition.status == "provisional"
    assert result.effective_status == "provisional"
    assert risk.at_risk
    assert not risk.assessed
    assert risk.status == "unverified"
    assert "bounded by provisional authority/status" in risk.basis


def test_policy_conflict_preserves_condition_truth_without_verified_consequence():
    rule = _policy(verification_status="conflict")
    result = _policy_result(rule)
    risk = _risk(rule)

    assert result.condition.outcome == "satisfied"
    assert not result.consequence_established
    assert result.effective_status == "conflict"
    assert not risk.at_risk
    assert not risk.assessed
    assert risk.status == "conflict"
    assert "policy consequence is bounded by conflict authority/status" in risk.basis


def test_condition_not_satisfied_does_not_trigger_policy_consequence():
    rule = _policy()
    result = _policy_result(rule, repeat_evidence=[_stage_repeat("not_repeated")])
    risk = _risk(rule, repeat_evidence=[_stage_repeat("not_repeated")])

    assert result.condition.outcome == "not_satisfied"
    assert not result.consequence_established
    assert not risk.at_risk
    assert risk.assessed
    assert "configured condition did not trigger" in risk.basis


def test_condition_unresolved_does_not_default_to_safe_or_discretionary():
    rule = _policy()
    result = _policy_result(rule, repeat_evidence=[])
    risk = _risk(rule, repeat_evidence=[])

    assert result.condition.outcome == "unresolved"
    assert not result.consequence_established
    assert not risk.at_risk
    assert not risk.assessed
    assert risk.status == "unverified"
    assert "no matching formal stage-repeat evidence" in risk.basis
    assert "manual" not in risk.basis.lower()


def test_condition_conflict_does_not_establish_verified_consequence():
    rule = _policy()
    conflict_evidence = [_stage_repeat("repeated"), _stage_repeat("not_repeated")]
    result = _policy_result(rule, repeat_evidence=conflict_evidence)
    risk = _risk(rule, repeat_evidence=conflict_evidence)

    assert result.condition.outcome == "conflict"
    assert not result.consequence_established
    assert result.effective_status == "conflict"
    assert not risk.at_risk
    assert not risk.assessed
    assert risk.status == "conflict"


def test_condition_unsupported_does_not_trigger_or_become_manual():
    rule = _policy(condition={"type": "some_future_rule", "label": "Future"})
    result = _policy_result(rule)
    risk = _risk(rule)

    assert result.condition.outcome == "unsupported"
    assert not result.consequence_established
    assert not risk.at_risk
    assert not risk.assessed
    assert "unsupported progression condition type" in risk.basis
    assert "manual" not in risk.basis.lower()


def test_missing_policy_id_is_unsupported_not_derived():
    rule = _policy()
    rule.pop("policy_id")
    result = _policy_result(rule)
    risk = _risk(rule)

    assert result.policy_id == ""
    assert result.condition.outcome == "unsupported"
    assert "requires explicit policy_id" in result.detail
    assert not risk.at_risk
    assert not risk.assessed


def test_missing_policy_status_is_unsupported_not_verified_by_default():
    rule = _policy()
    rule.pop("verification_status")
    result = _policy_result(rule)
    risk = _risk(rule)

    assert result.condition.outcome == "unsupported"
    assert result.effective_status == "unverified"
    assert "requires explicit verification_status" in result.detail
    assert not risk.at_risk
    assert not risk.assessed


def test_missing_consequence_is_unsupported_not_advisory_default():
    rule = _policy()
    rule.pop("consequence")
    result = _policy_result(rule)
    risk = _risk(rule)

    assert result.condition.outcome == "unsupported"
    assert result.consequence is None
    assert "requires explicit supported consequence" in result.detail
    assert "advisory" not in result.detail.lower()
    assert not risk.at_risk
    assert not risk.assessed


def test_unsupported_consequence_is_not_silently_interpreted():
    rule = _policy(consequence_type="excluded")
    result = _policy_result(rule)
    risk = _risk(rule)

    assert result.condition.outcome == "unsupported"
    assert result.consequence is None
    assert not risk.at_risk
    assert not risk.assessed
    assert "requires explicit supported consequence" in risk.basis


def test_flat_legacy_rule_semantics_are_not_mass_migrated():
    risk = _compute_exclusion_risk(
        _student(),
        _catalogue([_failed_child()]),
        "P-OMEGA",
        result_context_evidence=[_context()],
    )

    assert risk.at_risk
    assert risk.assessed
    assert risk.status == "verified"
    assert "policy_id" not in risk.reasons[0]


def test_progression_policy_architecture_guards():
    from engine import rule_engine

    policy_source = inspect.getsource(rule_engine._evaluate_progression_policy)
    all_of_source = inspect.getsource(_evaluate_progression_all_of)
    exclusion_source = inspect.getsource(_compute_exclusion_risk)

    assert "result.is_failed" not in policy_source
    assert "_credit_value" not in policy_source
    assert "_load_equivalent" not in policy_source
    assert "registration_period_key ==" not in policy_source
    assert "consequence" not in all_of_source
    assert "excluded" not in policy_source
    assert "readmitted" not in policy_source
    assert "probation" not in policy_source
    assert 'rule_type == "repeat_year_failure"' in exclusion_source
    assert 'rule_type == "any_of"' not in policy_source
    assert 'rule_type == "progression_policy"' in exclusion_source
