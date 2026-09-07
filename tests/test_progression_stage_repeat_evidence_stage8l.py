import inspect
from typing import Any

from engine.models import (
    Catalogue,
    CourseResult,
    PathwayDefinition,
    ProgrammeRules,
    StageRepeatEvidence,
    StudentRecord,
)
from engine.rule_engine import _compute_exclusion_risk


def _rule(**overrides: Any) -> dict[str, Any]:
    rule = {
        "type": "formal_stage_repeat",
        "label": "Formal repeat evidence",
        "stage_key": "PROFESSIONAL",
        "registration_period_key": "R-C",
    }
    rule.update(overrides)
    return rule


def _programme(
    rules: list[dict[str, Any]],
    *,
    key: str = "P-OMEGA",
    pathways: dict[str, PathwayDefinition] | None = None,
) -> ProgrammeRules:
    return ProgrammeRules(
        key=key,
        name=key,
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


def _catalogue(
    rules: list[dict[str, Any]],
    *,
    programme_key: str = "P-OMEGA",
    pathways: dict[str, PathwayDefinition] | None = None,
) -> Catalogue:
    programme = _programme(rules, key=programme_key, pathways=pathways)
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
    *,
    programme_key: str = "P-OMEGA",
    pathway_key: str = "",
    results: list[CourseResult] | None = None,
) -> StudentRecord:
    return StudentRecord(
        "UTWO-STAGE",
        "Opaque Student",
        programme_key,
        [],
        results or [],
        faculty_key="university_two",
        programme_key=programme_key,
        pathway_key=pathway_key,
        years_registered=3,
    )


def _risk(
    rules: list[dict[str, Any]],
    evidence: list[StageRepeatEvidence] | None = None,
    *,
    programme_key: str = "P-OMEGA",
    pathway_key: str = "",
    pathways: dict[str, PathwayDefinition] | None = None,
    results: list[CourseResult] | None = None,
):
    return _compute_exclusion_risk(
        _student(
            programme_key=programme_key,
            pathway_key=pathway_key,
            results=results,
        ),
        _catalogue(rules, programme_key=programme_key, pathways=pathways),
        programme_key,
        stage_repeat_evidence=evidence,
    )


def _evidence(
    repeat_state: str,
    *,
    programme_key: str = "P-OMEGA",
    pathway_key: str = "",
    stage_key: str = "PROFESSIONAL",
    registration_period_key: str = "R-C",
    verification_status: str = "verified",
    authority: str = "registrar",
) -> StageRepeatEvidence:
    return StageRepeatEvidence(
        programme_key=programme_key,
        pathway_key=pathway_key,
        stage_key=stage_key,
        registration_period_key=registration_period_key,
        repeat_state=repeat_state,
        source_reference="staff-entry:case-1",
        authority=authority,
        verification_status=verification_status,
    )


def test_student_a_verified_formal_repeat_establishes_condition():
    risk = _risk([_rule()], [_evidence("repeated")])

    assert risk.at_risk
    assert risk.assessed
    assert risk.status == "verified"
    assert risk.reasons == [
        "Formal repeat evidence: institutional evidence establishes repeated "
        "for stage PROFESSIONAL in registration period R-C."
    ]


def test_student_b_verified_not_repeated_is_distinct_from_missing_evidence():
    risk = _risk([_rule()], [_evidence("not_repeated")])

    assert not risk.at_risk
    assert risk.assessed
    assert risk.status == "verified"
    assert "institutional evidence establishes not repeated" in risk.basis


def test_student_c_interruption_return_can_be_supplied_as_not_repeated():
    risk = _risk(
        [_rule(stage_key="CORE")],
        [_evidence("not_repeated", stage_key="CORE")],
    )

    assert not risk.at_risk
    assert risk.assessed
    assert "stage CORE" in risk.basis


def test_student_d_programme_scope_prevents_reusing_another_programme_fact():
    wrong_programme = _evidence("repeated", programme_key="P-ALPHA", stage_key="CORE")

    missing = _risk([_rule(stage_key="CORE")], [wrong_programme])
    assert not missing.at_risk
    assert not missing.assessed
    assert missing.status == "unverified"
    assert "no matching formal stage-repeat evidence" in missing.basis

    matched_not_repeat = _risk(
        [_rule(stage_key="CORE")],
        [
            wrong_programme,
            _evidence("not_repeated", programme_key="P-OMEGA", stage_key="CORE"),
        ],
    )
    assert not matched_not_repeat.at_risk
    assert matched_not_repeat.assessed
    assert "not repeated" in matched_not_repeat.basis


def test_student_e_missing_evidence_is_not_treated_as_not_repeated():
    risk = _risk([_rule()])

    assert not risk.at_risk
    assert not risk.assessed
    assert risk.status == "unverified"
    assert "no matching formal stage-repeat evidence" in risk.basis
    assert "not repeated" not in risk.basis


def test_pathway_scoped_evidence_does_not_apply_to_another_pathway():
    pathways = {
        "TRACK-A": PathwayDefinition(
            key="TRACK-A",
            name="Track A",
            progression_rules=[_rule(pathway_key="TRACK-A")],
        ),
        "TRACK-B": PathwayDefinition(
            key="TRACK-B",
            name="Track B",
            progression_rules=[_rule(pathway_key="TRACK-B")],
        ),
    }

    wrong_pathway = _risk(
        [],
        [_evidence("repeated", pathway_key="TRACK-A")],
        pathway_key="TRACK-B",
        pathways=pathways,
    )
    assert not wrong_pathway.at_risk
    assert wrong_pathway.status == "unverified"

    matched_pathway = _risk(
        [],
        [_evidence("not_repeated", pathway_key="TRACK-B")],
        pathway_key="TRACK-B",
        pathways=pathways,
    )
    assert not matched_pathway.at_risk
    assert matched_pathway.assessed
    assert matched_pathway.status == "verified"
    assert "not repeated" in matched_pathway.basis


def test_manual_pilot_entry_is_evidence_not_discretionary_policy():
    risk = _risk(
        [_rule()],
        [
            _evidence(
                "repeated",
                authority="authorised-advisor",
                verification_status="verified",
            )
        ],
    )

    assert risk.at_risk
    assert risk.status == "verified"
    assert "discretion" not in risk.basis.lower()
    assert "manual" not in risk.basis.lower()


def test_unverified_repeat_evidence_does_not_upgrade_to_verified_fact():
    risk = _risk([_rule()], [_evidence("repeated", verification_status="provisional")])

    assert risk.at_risk
    assert not risk.assessed
    assert risk.status == "unverified"
    assert "provisional" in risk.basis
    assert "cannot be verified" in risk.basis


def test_conflicting_repeat_evidence_is_not_resolved_by_list_order():
    risk = _risk([_rule()], [_evidence("repeated"), _evidence("not_repeated")])

    assert not risk.at_risk
    assert not risk.assessed
    assert risk.status == "conflict"
    assert "conflicting formal stage-repeat evidence" in risk.basis


def test_formal_stage_repeat_never_infers_from_transcript_recurrence_or_years():
    results = [
        CourseResult("OPAQUE-A", "Opaque A", 0, 0, 70, "PASS", 2025),
        CourseResult("OPAQUE-A", "Opaque A", 0, 0, 40, "FAIL", 2026),
    ]

    risk = _risk([_rule()], results=results)

    assert not risk.at_risk
    assert not risk.assessed
    assert "no matching formal stage-repeat evidence" in risk.basis


def test_health_repeat_year_failure_heuristic_remains_separate_compatibility_debt():
    source = inspect.getsource(_compute_exclusion_risk)

    assert 'rule_type == "repeat_year_failure"' in source
    assert "formal_stage_repeat" in source
