import dataclasses
import inspect
from pathlib import Path
from typing import Any

from app import _to_dict
from engine.catalogue import load_catalogue
from engine.models import (
    Catalogue,
    CourseResult,
    ProgrammeRules,
    ResultContextEvidence,
    StageRepeatEvidence,
    StudentRecord,
)
from engine.rule_engine import (
    ExclusionRisk,
    ProgressionPolicyAssessment,
    Report,
    compute_report,
)

LAW_POLICY_ID_PREFIX = "UCT-LAW-2026-ANNUAL-FAILED-LOAD-"
EBE_BAS_POLICY_ID = "UCT-EBE-2026-BAS-ANNUAL-PASS-RATE"


def _synthetic_failed_child() -> dict[str, Any]:
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


def _synthetic_repeat_child() -> dict[str, Any]:
    return {
        "type": "formal_stage_repeat",
        "label": "Formal repeated stage",
        "stage_key": "PROFESSIONAL",
        "registration_period_key": "R-C",
    }


def _synthetic_condition() -> dict[str, Any]:
    return {
        "type": "all_of",
        "label": "Repeat-stage failure condition",
        "children": [_synthetic_repeat_child(), _synthetic_failed_child()],
    }


def _synthetic_policy(
    consequence_type: str,
    *,
    policy_id: str | None = None,
    verification_status: str = "verified",
    source_reference: str | None = "Synthetic Regulation 1",
    condition: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rule: dict[str, Any] = {
        "type": "progression_policy",
        "label": f"Synthetic {consequence_type} policy",
        "policy_id": policy_id or f"SYN-{consequence_type.upper()}",
        "verification_status": verification_status,
        "condition": condition or _synthetic_condition(),
        "consequence": {
            "type": consequence_type,
            "label": consequence_type.replace("_", " ").title(),
        },
    }
    if source_reference is not None:
        rule["source_reference"] = source_reference
    return rule


def _synthetic_catalogue(rules: list[dict[str, Any]]) -> Catalogue:
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


def _synthetic_student(results: list[CourseResult] | None = None) -> StudentRecord:
    return StudentRecord(
        "STAGE8W",
        "Policy Assessment Student",
        "P-OMEGA",
        [],
        results
        or [
            CourseResult(
                "X",
                "X",
                0,
                0,
                40,
                "RAW",
                academic_year=2026,
                attempt_id="X-2",
            )
        ],
        faculty_key="synthetic_university",
        programme_key="P-OMEGA",
        years_registered=3,
    )


def _synthetic_stage_repeat(
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


def _synthetic_result_context(
    *,
    attempt_id: str = "X-2",
    stage_key: str = "PROFESSIONAL",
    registration_period_key: str = "R-C",
    verification_status: str = "verified",
) -> ResultContextEvidence:
    return ResultContextEvidence(
        attempt_id=attempt_id,
        programme_key="P-OMEGA",
        stage_key=stage_key,
        registration_period_key=registration_period_key,
        source_reference="result-context",
        authority="registrar",
        verification_status=verification_status,
    )


def _synthetic_report(
    rules: list[dict[str, Any]],
    *,
    repeat_evidence: list[StageRepeatEvidence] | None = None,
    context_evidence: list[ResultContextEvidence] | None = None,
) -> Report:
    return compute_report(
        _synthetic_student(),
        _synthetic_catalogue(rules),
        stage_repeat_evidence=(
            [_synthetic_stage_repeat()]
            if repeat_evidence is None
            else repeat_evidence
        ),
        result_context_evidence=(
            [_synthetic_result_context()]
            if context_evidence is None
            else context_evidence
        ),
    )


def _law_catalogue() -> Catalogue:
    return load_catalogue("uct_law")


def _law_result(catalogue: Catalogue, code: str, mark: int) -> CourseResult:
    fact = catalogue.courses[code]
    return CourseResult(code, fact.name, fact.nqf_level, fact.nqf_credits, mark, None, 2026)


def _law_report(codes: list[str], *, mark: int = 40) -> Report:
    catalogue = _law_catalogue()
    student = StudentRecord(
        "LAW-8W",
        "Law Assessment Student",
        "LLB",
        [],
        [_law_result(catalogue, code, mark) for code in codes],
        "uct_law",
        "llb_three_year_graduate",
        "",
        3,
    )
    return compute_report(student, catalogue)


def _ebe_catalogue() -> Catalogue:
    return load_catalogue("uct_ebe")


def _ebe_result(catalogue: Catalogue, code: str, mark: int | None) -> CourseResult:
    fact = catalogue.courses[code]
    return CourseResult(code, fact.name, fact.nqf_level, fact.nqf_credits, mark, None, 2026)


def _ebe_report(results: list[CourseResult]) -> Report:
    return compute_report(
        StudentRecord(
            "EBE-8W",
            "BAS Assessment Student",
            "BAS",
            [],
            results,
            "uct_ebe",
            "bas",
            "",
            3,
        ),
        _ebe_catalogue(),
    )


def test_report_has_empty_progression_policy_assessments_by_default():
    report = compute_report(
        _synthetic_student(),
        _synthetic_catalogue([_synthetic_failed_child()]),
        result_context_evidence=[_synthetic_result_context()],
    )

    assert report.progression_policy_assessments == []
    assert "progression_policy_assessments" in {field.name for field in dataclasses.fields(Report)}


def test_real_law_triggered_policy_assessment_preserves_structured_fields():
    report = _law_report(["CML4004S", "PBL4801F", "PBL4802F", "PVL4008H"])
    assessments = report.progression_policy_assessments

    assert len(assessments) == 1
    assessment = assessments[0]
    assert isinstance(assessment, ProgressionPolicyAssessment)
    assert assessment.policy_id.startswith(LAW_POLICY_ID_PREFIX)
    assert assessment.consequence_type == "advisory_risk"
    assert assessment.condition_outcome == "satisfied"
    assert assessment.consequence_established
    assert assessment.assessment_complete
    assert assessment.policy_status == "unverified"
    assert assessment.effective_status == "unverified"
    assert "Faculty of Law Handbook" in assessment.source_reference
    assert report.exclusion_risk.at_risk


def test_real_law_non_triggered_policy_assessment_is_still_reported():
    report = _law_report(["CML4004S", "PBL4801F", "PBL4802F"], mark=75)
    assessments = report.progression_policy_assessments

    assert len(assessments) == 1
    assessment = assessments[0]
    assert assessment.policy_id.startswith(LAW_POLICY_ID_PREFIX)
    assert assessment.condition_outcome == "not_satisfied"
    assert not assessment.consequence_established
    assert not report.exclusion_risk.at_risk


def test_real_ebe_bas_triggered_policy_assessment():
    catalogue = _ebe_catalogue()
    report = _ebe_report(
        [
            _ebe_result(catalogue, "APG1003W", 75),
            _ebe_result(catalogue, "APG2021W", 40),
            _ebe_result(catalogue, "APG1020W", 40),
        ]
    )

    assessment = report.progression_policy_assessments[0]
    assert len(report.progression_policy_assessments) == 1
    assert assessment.policy_id == EBE_BAS_POLICY_ID
    assert assessment.consequence_type == "advisory_risk"
    assert assessment.condition_outcome == "satisfied"
    assert assessment.consequence_established
    assert assessment.policy_status == "unverified"
    assert assessment.effective_status == "unverified"
    assert "page 22" in assessment.source_reference


def test_real_ebe_bas_non_triggered_policy_assessment():
    catalogue = _ebe_catalogue()
    report = _ebe_report(
        [
            _ebe_result(catalogue, "APG1003W", 75),
            _ebe_result(catalogue, "APG1020W", 75),
        ]
    )

    assessment = report.progression_policy_assessments[0]
    assert assessment.policy_id == EBE_BAS_POLICY_ID
    assert assessment.condition_outcome == "not_satisfied"
    assert not assessment.consequence_established


def test_real_ebe_bas_zero_denominator_unresolved_assessment():
    catalogue = _ebe_catalogue()
    report = _ebe_report(
        [
            _ebe_result(catalogue, "APG1003W", None),
            _ebe_result(catalogue, "APG1020W", None),
        ]
    )

    assessment = report.progression_policy_assessments[0]
    assert assessment.policy_id == EBE_BAS_POLICY_ID
    assert assessment.condition_outcome == "unresolved"
    assert not assessment.consequence_established
    assert not assessment.assessment_complete
    assert "ratio denominator evidence is unavailable" in assessment.detail


def test_synthetic_consequence_types_are_distinguishable_structurally():
    rules = [
        _synthetic_policy("advisory_risk", policy_id="U2-ADVISORY"),
        _synthetic_policy("review_required", policy_id="U2-REVIEW"),
        _synthetic_policy("progression_ineligible", policy_id="U2-INELIGIBLE"),
    ]
    report = _synthetic_report(rules)

    assert [a.policy_id for a in report.progression_policy_assessments] == [
        "U2-ADVISORY",
        "U2-REVIEW",
        "U2-INELIGIBLE",
    ]
    assert [a.consequence_type for a in report.progression_policy_assessments] == [
        "advisory_risk",
        "review_required",
        "progression_ineligible",
    ]
    assert all(a.consequence_established for a in report.progression_policy_assessments)
    assert report.exclusion_risk.at_risk
    assert len(report.exclusion_risk.reasons) == 3


def test_review_required_and_progression_ineligible_do_not_create_formal_acts():
    report = _synthetic_report(
        [
            _synthetic_policy("review_required", policy_id="U2-REVIEW"),
            _synthetic_policy("progression_ineligible", policy_id="U3-INELIGIBLE"),
        ]
    )

    by_id = {a.policy_id: a for a in report.progression_policy_assessments}
    assert by_id["U2-REVIEW"].consequence_type == "review_required"
    assert by_id["U3-INELIGIBLE"].consequence_type == "progression_ineligible"
    serialized = _to_dict(report)
    text = str(serialized).lower()
    assert "excluded" not in text
    assert "readmitted" not in text
    assert "probation" not in text
    assert "continuation approved" not in text


def test_unverified_policy_is_distinct_from_satisfied_condition():
    report = _synthetic_report(
        [_synthetic_policy("advisory_risk", verification_status="unverified")]
    )
    assessment = report.progression_policy_assessments[0]

    assert assessment.condition_outcome == "satisfied"
    assert assessment.consequence_established
    assert assessment.assessment_complete
    assert assessment.policy_status == "unverified"
    assert assessment.effective_status == "unverified"


def test_verified_policy_with_weaker_evidence_exposes_effective_status():
    report = _synthetic_report(
        [_synthetic_policy("review_required", verification_status="verified")],
        context_evidence=[_synthetic_result_context(verification_status="provisional")],
    )
    assessment = report.progression_policy_assessments[0]

    assert assessment.condition_outcome == "satisfied"
    assert assessment.consequence_established
    assert not assessment.assessment_complete
    assert assessment.policy_status == "verified"
    assert assessment.effective_status == "provisional"


def test_conflict_preserved_in_structured_assessment():
    report = _synthetic_report(
        [_synthetic_policy("review_required", verification_status="verified")],
        repeat_evidence=[
            _synthetic_stage_repeat("repeated"),
            _synthetic_stage_repeat("not_repeated"),
        ],
    )
    assessment = report.progression_policy_assessments[0]

    assert assessment.condition_outcome == "conflict"
    assert not assessment.consequence_established
    assert not assessment.assessment_complete
    assert assessment.effective_status == "conflict"
    assert report.exclusion_risk.status == "conflict"


def test_source_reference_preserved_and_missing_source_serializes_empty():
    sourced = _synthetic_report(
        [_synthetic_policy("advisory_risk", source_reference="University Rule 9")]
    )
    unsourced = _synthetic_report(
        [_synthetic_policy("advisory_risk", source_reference=None)]
    )

    assert sourced.progression_policy_assessments[0].source_reference == "University Rule 9"
    assert unsourced.progression_policy_assessments[0].source_reference == ""
    serialized = _to_dict(unsourced)
    assert serialized["progression_policy_assessments"][0]["source_reference"] == ""


def test_public_report_serialization_includes_assessment_primitives():
    report = _synthetic_report(
        [_synthetic_policy("progression_ineligible", policy_id="U3-INELIGIBLE")]
    )
    serialized = _to_dict(report)
    assessment = serialized["progression_policy_assessments"][0]

    assert serialized["exclusion_risk"]["at_risk"]
    assert assessment == {
        "policy_id": "U3-INELIGIBLE",
        "consequence_type": "progression_ineligible",
        "consequence_label": "Progression Ineligible",
        "condition_outcome": "satisfied",
        "consequence_established": True,
        "assessment_complete": True,
        "policy_status": "verified",
        "effective_status": "verified",
        "source_reference": "Synthetic Regulation 1",
        "detail": report.progression_policy_assessments[0].detail,
    }


def test_backward_compatible_exclusion_risk_shape_is_unchanged():
    assert [field.name for field in dataclasses.fields(ExclusionRisk)] == [
        "at_risk",
        "reasons",
        "assessed",
        "status",
        "confidence",
        "basis",
    ]

    report = _synthetic_report([_synthetic_policy("review_required")])
    serialized = _to_dict(report)
    assert set(serialized["exclusion_risk"]) == {
        "at_risk",
        "reasons",
        "assessed",
        "status",
        "confidence",
        "basis",
    }


def test_legacy_flat_rule_does_not_receive_fake_policy_assessment():
    report = compute_report(
        _synthetic_student(),
        _synthetic_catalogue([_synthetic_failed_child()]),
        result_context_evidence=[_synthetic_result_context()],
    )

    assert report.exclusion_risk.at_risk
    assert report.progression_policy_assessments == []
    assert "policy_id" not in report.exclusion_risk.reasons[0]


def test_policy_assessments_preserve_governed_evaluation_order():
    rules = [
        _synthetic_policy("review_required", policy_id="POLICY-C"),
        _synthetic_policy("advisory_risk", policy_id="POLICY-A"),
        _synthetic_policy("progression_ineligible", policy_id="POLICY-B"),
    ]

    report = _synthetic_report(rules)

    assert [a.policy_id for a in report.progression_policy_assessments] == [
        "POLICY-C",
        "POLICY-A",
        "POLICY-B",
    ]


def test_policy_evaluation_runs_once_and_feeds_assessment_and_legacy_messages(monkeypatch):
    from engine import rule_engine

    calls = 0
    original = rule_engine._evaluate_progression_policy

    def counting_evaluator(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(rule_engine, "_evaluate_progression_policy", counting_evaluator)

    report = _synthetic_report(
        [
            _synthetic_policy("advisory_risk", policy_id="ONE"),
            _synthetic_policy("review_required", policy_id="TWO"),
            _synthetic_policy("progression_ineligible", policy_id="THREE"),
        ]
    )

    assert calls == 3
    assert len(report.progression_policy_assessments) == 3
    assert len(report.exclusion_risk.reasons) == 3


def test_progression_policy_assessment_projector_has_no_evaluation_logic():
    from engine import rule_engine

    projector_source = inspect.getsource(rule_engine._progression_policy_assessment)
    compute_source = inspect.getsource(rule_engine._compute_exclusion_risk)
    static_app = Path("static/app.js").read_text(encoding="utf-8")

    assert "_evaluate_progression_policy" not in projector_source
    assert "StudentRecord" not in projector_source
    assert "is_failed" not in projector_source
    assert "_credit_value" not in projector_source
    assert "faculty_key" not in projector_source
    assert "consequence_type" in projector_source
    assert "_progression_policy_assessment(policy)" in compute_source
    assert "_progression_policy_messages(policy)" in compute_source
    assert "progression_policy_assessments" not in static_app


def test_no_gov_data_or_builder_changes_are_needed_for_stage8w_projection():
    law_text = Path("data/uct_law/degree_requirements.json").read_text(encoding="utf-8")
    ebe_text = Path("data/uct_ebe/degree_requirements.json").read_text(encoding="utf-8")
    health_text = Path("data/uct_health/degree_requirements.json").read_text(
        encoding="utf-8"
    )

    assert LAW_POLICY_ID_PREFIX in law_text
    assert EBE_BAS_POLICY_ID in ebe_text
    assert "repeat_year_failure" in health_text
    assert "ProgressionPolicyAssessment" not in law_text
    assert "ProgressionPolicyAssessment" not in ebe_text
