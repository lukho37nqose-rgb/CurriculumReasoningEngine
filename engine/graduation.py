"""Governed graduation-eligibility facts, separate from approval and award."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GraduationClearanceEvidence:
    evidence_id: str
    student_id: str
    institution_id: str
    release_id: str
    clearance_id: str
    outcome: str
    authority: str
    verification_status: str = "unverified"
    source_reference: str = ""
    programme_key: str = ""


@dataclass(frozen=True)
class ClearanceAssessment:
    clearance_id: str
    outcome: str
    status: str
    source_reference: str = ""
    detail: str = ""


@dataclass(frozen=True)
class GraduationEligibilityAssessment:
    programme_key: str
    eligibility_spec_id: str
    outcome: str
    assessment_complete: bool
    status: str
    academic_completion_outcome: str
    clearance_assessments: tuple[ClearanceAssessment, ...] = ()
    unsatisfied_clearance_ids: tuple[str, ...] = ()
    unresolved_clearance_ids: tuple[str, ...] = ()
    source_reference: str = ""
    detail: str = ""


def _status(statuses: list[str]) -> str:
    order = {"conflict": 5, "unverified": 3, "provisional": 2, "verified": 1}
    return max(statuses or ["unverified"], key=lambda value: order.get(value, 3))


def evaluate_graduation_eligibility(
    *,
    student,
    institution_id: str,
    release_id: str,
    programme_key: str,
    spec: dict[str, Any] | None,
    academic_completion,
    clearances: tuple[GraduationClearanceEvidence, ...] = (),
) -> GraduationEligibilityAssessment | None:
    if not spec:
        return None
    spec_id = str(spec.get("eligibility_spec_id", "")).strip()
    required = tuple(dict.fromkeys(str(value).strip() for value in spec.get("required_clearance_ids", ()) if str(value).strip()))
    if not spec_id or not required:
        return GraduationEligibilityAssessment(programme_key, spec_id, "unsupported", False, "unverified", academic_completion.outcome, detail="Graduation eligibility specification is incomplete.")
    scoped = tuple(
        evidence for evidence in clearances
        if evidence.student_id == student.student_id
        and evidence.institution_id == institution_id
        and evidence.release_id == release_id
        and (not evidence.programme_key or evidence.programme_key == programme_key)
    )
    assessments = []
    for clearance_id in required:
        matches = [e for e in scoped if e.clearance_id == clearance_id]
        if not matches:
            assessments.append(ClearanceAssessment(clearance_id, "unresolved", "unverified", detail="No clearance decision evidence was supplied."))
        elif any(e.outcome == "conflict" for e in matches):
            assessments.append(ClearanceAssessment(clearance_id, "conflict", "conflict", detail="Clearance decisions conflict."))
        else:
            chosen = matches[0]
            outcome = chosen.outcome if chosen.outcome in {"satisfied", "not_satisfied", "unresolved"} else "unsupported"
            assessments.append(ClearanceAssessment(clearance_id, outcome, chosen.verification_status, chosen.source_reference))
    children = [academic_completion.outcome] if bool(spec.get("requires_academic_completion", True)) else []
    children.extend(item.outcome for item in assessments)
    if "not_satisfied" in children:
        outcome = "not_satisfied"
    elif "unsupported" in children:
        outcome = "unsupported"
    elif "conflict" in children:
        outcome = "conflict"
    elif "unresolved" in children:
        outcome = "unresolved"
    else:
        outcome = "satisfied"
    statuses = [str(spec.get("verification_status", "unverified")), str(academic_completion.status)]
    statuses.extend(item.status for item in assessments)
    status = _status(statuses)
    unresolved_ids = tuple(item.clearance_id for item in assessments if item.outcome in {"unresolved", "conflict", "unsupported"})
    unsatisfied_ids = tuple(item.clearance_id for item in assessments if item.outcome == "not_satisfied")
    complete = outcome == "satisfied" and status == "verified"
    if outcome == "not_satisfied" and unresolved_ids:
        complete = False
    return GraduationEligibilityAssessment(
        programme_key, spec_id, outcome, complete, status, academic_completion.outcome,
        tuple(assessments), unsatisfied_ids, unresolved_ids,
        str(spec.get("source_reference", "")),
        "Graduation eligibility is separate from formal approval and qualification award.",
    )
