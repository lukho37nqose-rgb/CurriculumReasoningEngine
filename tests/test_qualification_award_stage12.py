from engine.award import QualificationAwardEvidence, assess_qualification_award
from engine.models import StudentRecord


def _student(student_id="S1"):
    return StudentRecord(student_id, "Student", "P", [], [], "northstar", "P")


def _award(student="S1", institution="northstar", qualification="P", outcome="awarded", status="verified", release=""):
    return QualificationAwardEvidence("AW-1", student, institution, qualification, outcome, "Northstar Registrar", status, "Synthetic conferment register", release)


def test_completion_or_eligibility_without_event_does_not_confer_award():
    result = assess_qualification_award(student=_student(), institution_id="northstar", release_id="r2", qualification_key="P")
    assert result.outcome == "unresolved"


def test_explicit_award_event_establishes_awarded_state():
    result = assess_qualification_award(student=_student(), institution_id="northstar", release_id="r2", qualification_key="P", evidence=(_award(),))
    assert result.outcome == "awarded"
    assert result.assessment_complete


def test_award_event_can_survive_current_release_change():
    result = assess_qualification_award(student=_student(), institution_id="northstar", release_id="r2", qualification_key="P", evidence=(_award(release="r1"),))
    assert result.outcome == "awarded"


def test_award_evidence_is_student_institution_and_qualification_bound():
    result = assess_qualification_award(student=_student("S2"), institution_id="northstar", release_id="r2", qualification_key="P", evidence=(_award(), _award(institution="uct"), _award(qualification="Q")))
    assert result.outcome == "unresolved"


def test_unverified_award_does_not_upgrade_authority_and_conflict_is_preserved():
    unverified = assess_qualification_award(student=_student(), institution_id="northstar", release_id="r2", qualification_key="P", evidence=(_award(status="unverified"),))
    assert unverified.outcome == "awarded"
    assert not unverified.assessment_complete
    conflict = assess_qualification_award(student=_student(), institution_id="northstar", release_id="r2", qualification_key="P", evidence=(_award(), _award(outcome="not_awarded")))
    assert conflict.outcome == "conflict"
