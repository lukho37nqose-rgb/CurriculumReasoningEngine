"""Governed academic entry eligibility, never an admission or registration act."""

from dataclasses import dataclass
from typing import Any

from .models import Catalogue
from .prerequisites import AcademicConditionEvaluator, AcademicConditionResult, _weaker_status


@dataclass(frozen=True)
class ProgrammeEntryEligibilitySpec:
    eligibility_spec_id: str
    programme_key: str
    condition: dict[str, Any]
    source_reference: str
    verification_status: str
    pathway_key: str = ""

    @classmethod
    def from_package(cls, raw, catalogue: Catalogue, programme_key: str, pathway_key: str = ""):
        if not isinstance(raw, dict):
            raise ValueError("Entry specification must be an object.")
        for field in ("eligibility_spec_id", "programme_key", "source_reference", "verification_status"):
            if not isinstance(raw.get(field), str) or not raw[field].strip():
                raise ValueError(f"Entry specification requires {field}.")
        programme = catalogue.programmes.get(programme_key)
        if programme is None or raw["programme_key"] != programme_key:
            raise ValueError("Entry specification must target the selected governed programme.")
        scope = raw.get("pathway_key", "")
        if not isinstance(scope, str) or scope != pathway_key or (scope and scope not in programme.pathways):
            raise ValueError("Entry specification must target the selected governed pathway.")
        if raw["verification_status"] not in {"verified", "unverified", "provisional", "discretionary", "conflict"}:
            raise ValueError("Unknown entry policy verification status.")
        if not isinstance(raw.get("condition"), dict):
            raise ValueError("Entry specification requires a condition expression.")
        return cls(raw["eligibility_spec_id"], programme_key, raw["condition"],
                   raw["source_reference"], raw["verification_status"], scope)


@dataclass(frozen=True)
class ProgrammeEntryEligibilityAssessment:
    programme_key: str
    pathway_key: str
    eligibility_spec_id: str
    outcome: str
    assessment_complete: bool
    status: str
    condition_result: AcademicConditionResult | None
    source_reference: str
    detail: str


def evaluate_programme_entry(
    catalogue: Catalogue, programme_key: str, pathway_key: str,
    evaluator: AcademicConditionEvaluator,
) -> ProgrammeEntryEligibilityAssessment | None:
    """Select one scope, evaluate once, and bound authority by the governed spec.

    No coverage inspection, curriculum evaluation, routing mutation or formal
    admission inference belongs in this projection.
    """
    programme = catalogue.programmes.get(programme_key)
    raw = None
    try:
        if type(evaluator) is not AcademicConditionEvaluator:
            raise ValueError("Entry eligibility requires the current-evidence academic evaluator, not a planning adapter.")
        if programme is None:
            raise ValueError("Unknown programme for entry assessment.")
        if pathway_key and pathway_key not in programme.pathways:
            raise ValueError("Unknown pathway for entry assessment.")
        overrides = programme.pathway_entry_eligibility
        if not isinstance(overrides, dict) or any(key not in programme.pathways for key in overrides):
            raise ValueError("Entry overrides must target governed pathways.")
        # A pathway override replaces, never merges with, programme conditions.
        overridden = pathway_key in overrides
        raw = overrides[pathway_key] if overridden else programme.programme_entry_eligibility
        if raw == {} and not overridden:
            return None
        spec = ProgrammeEntryEligibilitySpec.from_package(
            raw, catalogue, programme_key, pathway_key if overridden else "",
        )
    except ValueError as exc:
        return ProgrammeEntryEligibilityAssessment(
            programme_key, pathway_key,
            str(raw.get("eligibility_spec_id", "")) if isinstance(raw, dict) else "",
            "unsupported", False, "unverified", None, "", str(exc),
        )
    # Expression-level authority is optional here: the containing spec owns it.
    condition = evaluator.evaluate({"verification_status": spec.verification_status, **spec.condition})
    status = _weaker_status(spec.verification_status, condition.status)
    policy_conflict = spec.verification_status == "conflict"
    return ProgrammeEntryEligibilityAssessment(
        programme_key, pathway_key, spec.eligibility_spec_id,
        "conflict" if policy_conflict else condition.outcome,
        condition.assessment_complete and not policy_conflict,
        status, condition, spec.source_reference,
        "Assessment of governed academic entry conditions only; institutional selection, "
        "offers, admission decisions and registration are not established by this result.",
    )
