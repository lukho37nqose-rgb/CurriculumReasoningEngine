"""Explicit institutional qualification-conferment evidence."""

from dataclasses import dataclass


@dataclass(frozen=True)
class QualificationAwardEvidence:
    award_evidence_id: str
    student_id: str
    institution_id: str
    qualification_key: str
    outcome: str
    authority: str
    verification_status: str = "unverified"
    source_reference: str = ""
    applicable_release_id: str = ""


@dataclass(frozen=True)
class QualificationAwardAssessment:
    qualification_key: str
    outcome: str
    assessment_complete: bool
    status: str
    award_evidence_id: str = ""
    authority: str = ""
    source_reference: str = ""
    detail: str = ""


def assess_qualification_award(*, student, institution_id: str, release_id: str, qualification_key: str, evidence: tuple[QualificationAwardEvidence, ...] = ()) -> QualificationAwardAssessment:
    # Award evidence is a historical institutional fact.  The release field is
    # provenance, not a gate against displaying an award under a later release.
    applicable = tuple(item for item in evidence if item.student_id == student.student_id and item.institution_id == institution_id and item.qualification_key == qualification_key)
    if not applicable:
        return QualificationAwardAssessment(qualification_key, "unresolved", False, "unverified", detail="Formal qualification award is not established by supplied institutional evidence.")
    outcomes = {item.outcome for item in applicable}
    if "conflict" in outcomes or ("awarded" in outcomes and ("not_awarded" in outcomes or "revoked" in outcomes)):
        return QualificationAwardAssessment(qualification_key, "conflict", False, "conflict", detail="Formal award evidence conflicts.")
    chosen = applicable[0]
    outcome = chosen.outcome if chosen.outcome in {"awarded", "not_awarded", "unresolved"} else "unresolved"
    return QualificationAwardAssessment(qualification_key, outcome, outcome in {"awarded", "not_awarded"} and chosen.verification_status == "verified", chosen.verification_status, chosen.award_evidence_id, chosen.authority, chosen.source_reference, "Formal qualification award state is supplied by institutional evidence; it is not inferred by CRE.")
