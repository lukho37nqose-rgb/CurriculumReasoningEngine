from engine.graduation import GraduationClearanceEvidence, evaluate_graduation_eligibility
from engine.models import StudentRecord
from engine.rule_engine import QualificationCompletionAssessment


def _student():
    return StudentRecord("S1", "Student", "P", [], [], "northstar", "P")


def _academic(outcome="satisfied", status="verified"):
    return QualificationCompletionAssessment("P", outcome, status == "verified", status)


def _spec(status="verified"):
    return {
        "eligibility_spec_id": "NS-GRAD-1",
        "requires_academic_completion": True,
        "required_clearance_ids": ["NS-CLEARANCE-A", "NS-CLEARANCE-Z"],
        "verification_status": status,
        "source_reference": "Synthetic Northstar eligibility contract",
    }


def _clearance(clearance_id, outcome="satisfied", status="verified", student="S1"):
    return GraduationClearanceEvidence(
        f"E-{clearance_id}", student, "northstar", "r1", clearance_id,
        outcome, "registrar", status, "Synthetic clearance register", "P",
    )


def test_complete_academic_and_clearances_are_eligible_but_not_awarded():
    result = evaluate_graduation_eligibility(
        student=_student(), institution_id="northstar", release_id="r1", programme_key="P",
        spec=_spec(), academic_completion=_academic(),
        clearances=(_clearance("NS-CLEARANCE-A"), _clearance("NS-CLEARANCE-Z")),
    )
    assert result.outcome == "satisfied"
    assert not hasattr(result, "qualification_awarded")


def test_missing_clearance_is_unresolved_not_failed():
    result = evaluate_graduation_eligibility(
        student=_student(), institution_id="northstar", release_id="r1", programme_key="P",
        spec=_spec(), academic_completion=_academic(), clearances=(_clearance("NS-CLEARANCE-A"),),
    )
    assert result.outcome == "unresolved"
    assert "NS-CLEARANCE-Z" in result.unresolved_clearance_ids


def test_explicit_failure_is_decisive_even_with_unresolved_sibling():
    result = evaluate_graduation_eligibility(
        student=_student(), institution_id="northstar", release_id="r1", programme_key="P",
        spec=_spec(), academic_completion=_academic(),
        clearances=(_clearance("NS-CLEARANCE-A", "not_satisfied"),),
    )
    assert result.outcome == "not_satisfied"
    assert not result.assessment_complete


def test_academic_completion_is_a_separate_mandatory_child():
    result = evaluate_graduation_eligibility(
        student=_student(), institution_id="northstar", release_id="r1", programme_key="P",
        spec=_spec(), academic_completion=_academic("not_satisfied"),
        clearances=(_clearance("NS-CLEARANCE-A"), _clearance("NS-CLEARANCE-Z")),
    )
    assert result.outcome == "not_satisfied"
    assert result.academic_completion_outcome == "not_satisfied"


def test_scope_mismatch_does_not_apply_clearance_evidence():
    result = evaluate_graduation_eligibility(
        student=_student(), institution_id="northstar", release_id="r1", programme_key="P",
        spec=_spec(), academic_completion=_academic(),
        clearances=(_clearance("NS-CLEARANCE-A", student="OTHER"), _clearance("NS-CLEARANCE-Z")),
    )
    assert result.outcome == "unresolved"

