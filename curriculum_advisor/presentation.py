"""Audience-facing projections over canonical reasoning reports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from curriculum_reasoning_engine.institutions.provenance import ReleaseProvenance, plain

OUTCOME_LABELS = {
    "awarded": "Qualification awarded",
    "not_awarded": "Qualification not awarded",
    "satisfied": "Met",
    "not_satisfied": "Not met",
    "unresolved": "Not enough information yet",
    "unsupported": "Not assessed by CRE",
    "conflict": "Conflicting evidence",
}

OUTCOME_EXPLANATIONS = {
    "awarded": "Supplied institutional evidence records a qualification award. CRE did not infer or confer it.",
    "not_awarded": "Supplied institutional evidence explicitly records that the qualification was not awarded.",
    "satisfied": "This represented requirement is met.",
    "not_satisfied": "This represented requirement is not met based on the evidence available to CRE.",
    "unresolved": "We do not yet have enough information to determine this.",
    "unsupported": "CRE does not assess this rule.",
    "conflict": "The represented evidence conflicts, so CRE cannot give a definitive result.",
}

SOURCE_RELATIONSHIPS = {
    "direct_rule_source": "DIRECT_RULE_SOURCE",
    "inherited_policy_source": "INHERITED_POLICY_SOURCE",
    "package_source": "PACKAGE_SOURCE",
    "evidence_source": "EVIDENCE_SOURCE",
    "source_not_represented": "SOURCE_NOT_REPRESENTED",
}


@dataclass(frozen=True)
class PresentationContext:
    """Request-derived presentation facts, never canonical academic evidence."""

    evidence_receipt: dict[str, Any]
    launch_context: dict[str, Any]
    provenance: ReleaseProvenance | None = None


def presentation_context_from_request(
    body: dict[str, Any],
    *,
    academic_record_supplied: bool,
    academic_record_coverage: str = "unknown",
    institution_id: str | None = None,
    release_id: str | None = None,
    provenance: ReleaseProvenance | None = None,
) -> PresentationContext:
    def supplied(name: str) -> bool:
        value = body.get(name)
        return bool(value)

    receipt = {
        "academic_record": "RECEIVED" if academic_record_supplied else "NOT_SUPPLIED",
        "academic_record_coverage": "SCOPED" if supplied("academic_record_coverage") else "COVERAGE_UNKNOWN",
        "recognition": "RECEIVED" if supplied("requirement_recognition_evidence") or supplied("course_completion_recognition") else "NOT_SUPPLIED",
        "recognition_coverage": "SCOPED" if supplied("requirement_recognition_coverage") or supplied("recognition_coverage") else "COVERAGE_UNKNOWN",
        "external_subject_achievement": "RECEIVED" if supplied("external_subject_achievement_evidence") else "NOT_SUPPLIED",
        "prior_qualification": "RECEIVED" if supplied("prior_qualification_evidence") else "NOT_SUPPLIED",
        "clearance": "RECEIVED" if supplied("graduation_clearances") or supplied("graduation_clearance_evidence") else "NOT_SUPPLIED",
        "qualification_award": "RECEIVED" if supplied("qualification_award_evidence") else "NOT_SUPPLIED",
    }
    # Receipt scopes describe supplied snapshots, not applicability or contribution.
    entries = []
    for category, evidence_key, coverage_key, scope_key in (
        ("academic_record", "results", "academic_record_coverage", "course_codes"),
        ("course_completion_recognition", "course_completion_recognition", "recognition_coverage", "course_codes"),
        ("requirement_recognition", "requirement_recognition_evidence", "requirement_recognition_coverage", "requirement_ids"),
        ("external_subject_achievement", "external_subject_achievement_evidence", "external_subject_achievement_coverage", "subject_ids"),
        ("prior_qualification", "prior_qualification_evidence", "prior_qualification_coverage", "qualification_ids"),
        ("registration_history", "registration_history", "registration_history_coverage", "academic_period_keys"),
        ("graduation_clearance", "graduation_clearances", "clearance_coverage", "clearance_ids"),
        ("qualification_award", "qualification_award_evidence", "award_coverage", "qualification_ids"),
    ):
        scopes = []
        for coverage in body.get(coverage_key, []):
            state = coverage.get("coverage_state", "complete" if coverage_key == "recognition_coverage" else "unknown")
            scopes.append({
                "coverage_state": "COVERAGE_COMPLETE_FOR_SCOPE" if state == "complete" else (
                    "COVERAGE_PARTIAL" if state == "partial" else "COVERAGE_UNKNOWN"),
                scope_key: list(coverage.get(scope_key, [])),
                **{key: coverage[key] for key in ("programme_key", "pathway_key", "source_reference", "verification_status") if key in coverage},
            })
        entries.append({
            "category": category,
            "supplied": academic_record_supplied if category == "academic_record" else supplied(evidence_key),
            "receipt_state": "RECEIVED" if (academic_record_supplied if category == "academic_record" else supplied(evidence_key)) else "NOT_SUPPLIED",
            "coverage_state": "SCOPED" if scopes else "COVERAGE_UNKNOWN",
            "coverage_scopes": scopes,
        })
    receipt["entries"] = entries
    receipt["achievement_observations"] = [
        {"course_code": row.get("code", ""), "value": row["achievement_value"]}
        for row in body.get("results", []) if row.get("achievement_value") is not None
    ]
    launch = {
        "institution_id": body.get("institution_id") or institution_id,
        "release_id": body.get("release_id") or release_id,
        "programme_context": body.get("programme_key"),
        "pathway_context": body.get("pathway_key"),
        "subject_reference": body.get("subject_reference"),
        "launch_request_id": body.get("launch_request_id"),
        "context_provenance": body.get("context_provenance", "USER_SELECTED"),
        "return_context": body.get("return_context"),
    }
    return PresentationContext(receipt, {key: value for key, value in launch.items() if value is not None}, provenance)


def _requirement_sources(report, requirement, context):
    if context is None or context.provenance is None:
        return []
    index = context.provenance
    programme = getattr(report, "programme_key", "")
    # Report construction explicitly namespaces governed curriculum rule IDs.
    key = requirement.id.removeprefix("curriculum:")
    result = []
    for relation in index.for_requirement(programme, key):
        if relation.relationship_type == "PACKAGE_SOURCE":
            continue
        source = index.source(relation.source_id)
        result.append({
            "source_id": source.source_id, "title": source.title,
            "relationship_id": relation.relationship_id,
            "relationship": relation.relationship_type,
            "locator": plain(relation.locator),
            "institution_id": source.institution_id, "release_id": source.release_id,
            "source_status": source.source_status,
            "relationship_status": relation.relationship_status,
            "rule_status": relation.rule_status,
            "status_language": "This source representation has not yet been institutionally confirmed.",
        })
    return result


def _action(outcome: str, detail: str = "") -> str:
    text = detail.casefold()
    if outcome == "conflict":
        return "REVIEW_CONFLICT"
    if outcome == "unsupported":
        return "POLICY_NOT_SUPPORTED"
    if outcome == "unresolved":
        if "without complete academic-record coverage" in text or "missing evidence" in text:
            return "SUPPLY_EVIDENCE"
        if "recogn" in text:
            return "REVIEW_RECOGNITION"
        if "decision" in text or "discretion" in text or "faculty" in text:
            return "SEEK_INSTITUTIONAL_DECISION"
        if any(word in text for word in ("evidence", "coverage", "missing", "completed")):
            return "SUPPLY_EVIDENCE"
        return "UNRESOLVED_NEXT_STEP"
    return "NO_ACTION_REPRESENTED"


def _source(reference: str, source_id: str, relationship: str) -> dict[str, str]:
    return {
        "source_id": source_id,
        "relationship": relationship,
        "title": reference,
        "locator": reference,
        "status_language": "The represented source has not yet been institutionally confirmed.",
    }


def _assessment_view(item: Any, identity: str, title: str, kind: str = "assessment") -> dict[str, Any]:
    outcome = str(getattr(item, "outcome", getattr(item, "condition_outcome", "unresolved")))
    detail = str(getattr(item, "detail", ""))
    status = str(getattr(item, "status", getattr(item, "effective_status", "unverified")))
    source_reference = str(getattr(item, "source_reference", ""))
    relationships = []
    if source_reference:
        relationships.append(_source(source_reference, f"source:{source_reference}", "DIRECT_RULE_SOURCE"))
    return {
        "identity": identity,
        "kind": kind,
        "title": title,
        "outcome": outcome,
        "outcome_label": OUTCOME_LABELS.get(outcome, "Not assessed by CRE"),
        "complete": bool(getattr(item, "assessment_complete", False)),
        "assessment_complete": bool(getattr(item, "assessment_complete", False)),
        "status": status,
        "explanation": OUTCOME_EXPLANATIONS.get(outcome, "CRE does not have a definitive represented conclusion."),
        "detail": detail,
        "next_action": _action(outcome, detail),
        "source_references": relationships,
        "source_missing": not bool(relationships),
        "external_action_boundary": (
            "CRE explains the represented rule; it cannot make the institutional decision."
            if outcome in {"unresolved", "unsupported", "conflict"} else ""
        ),
    }


def student_reasoning_view(
    report: Any,
    *,
    context: PresentationContext | None = None,
    evidence_receipt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Project a Report without reevaluating any canonical result."""
    conclusions = []
    for requirement in getattr(report, "requirements", []):
        outcome = getattr(requirement, "outcome", None) or "unresolved"
        item = {
            "identity": requirement.id,
            "kind": "curriculum",
            "legacy_compatibility": getattr(requirement, "outcome", None) is None,
            "title": requirement.label,
            "outcome": outcome,
            "outcome_label": OUTCOME_LABELS[outcome],
            "complete": bool(getattr(requirement, "assessment_complete", False)),
            "assessment_complete": getattr(requirement, "assessment_complete", None),
            "used_course_codes": list(getattr(requirement, "used_course_codes", [])),
            "status": requirement.status,
            "explanation": OUTCOME_EXPLANATIONS[outcome],
            "detail": requirement.detail or requirement.explanation,
            "next_action": _action(outcome, requirement.detail or requirement.explanation),
            "source_references": _requirement_sources(report, requirement, context),
            "source_missing": not bool(_requirement_sources(report, requirement, context)),
            "external_action_boundary": "",
        }
        conclusions.append(item)
    for assessment in getattr(report, "progression_policy_assessments", []):
        projected = _assessment_view(assessment, assessment.policy_id, assessment.consequence_label, "progression")
        if not hasattr(assessment, "condition_outcome"):
            conclusions.append(projected)
            continue
        projected.update(condition_outcome=assessment.condition_outcome,
                         consequence_type=assessment.consequence_type,
                         consequence_established=assessment.consequence_established)
        projected["outcome_label"] = {
            "satisfied": "Policy condition triggered", "not_satisfied": "Policy condition not triggered",
        }.get(assessment.condition_outcome, projected["outcome_label"])
        projected["explanation"] = (
            f"Represented consequence: {assessment.consequence_type.replace('_', ' ')}. "
            + ("The condition triggers this consequence; this is not a formal institutional decision."
               if assessment.consequence_established else "This consequence is not established by this assessment.")
        )
        conclusions.append(projected)
    entry = getattr(report, "programme_entry_eligibility_assessment", None)
    if entry:
        projected = _assessment_view(entry, f"entry:{entry.eligibility_spec_id}", "Programme entry eligibility", "entry")
        condition = getattr(entry, "condition_result", None)
        projected["used_course_codes"] = list(getattr(condition, "witness_course_codes", ()))
        def supporting_details(result):
            if result is None or result.outcome != "satisfied":
                return []
            children = getattr(result, "child_results", ())
            return ([detail for child in children for detail in supporting_details(child)]
                    if children else [result.detail])

        projected["supporting_details"] = supporting_details(condition)
        projected["external_action_boundary"] = "Entry eligibility is not an admission decision or applicant acceptance."
        conclusions.append(projected)
    completion = getattr(report, "qualification_completion", None)
    if completion:
        conclusions.append(_assessment_view(completion, f"qualification:{completion.programme_key}", "Academic qualification completion", "completion"))
    graduation = getattr(report, "graduation_eligibility_assessment", None)
    if graduation:
        projected = _assessment_view(graduation, f"graduation:{graduation.eligibility_spec_id}", "Graduation eligibility", "graduation")
        projected["clearance_assessments"] = [
            {"clearance_id": child.clearance_id, "outcome": child.outcome,
             "outcome_label": OUTCOME_LABELS.get(child.outcome, "Not assessed by CRE"),
             "status": child.status, "detail": child.detail}
            for child in getattr(graduation, "clearance_assessments", ())
        ]
        conclusions.append(projected)
    award = getattr(report, "qualification_award_assessment", None)
    if award:
        projected = _assessment_view(award, f"award:{award.qualification_key}", "Formal qualification award", "award")
        for source in projected["source_references"]:
            source["relationship"] = "EVIDENCE_SOURCE"
        conclusions.append(projected)
    sources = []
    seen = set()
    for conclusion in conclusions:
        for source in conclusion["source_references"]:
            if source["source_id"] not in seen:
                seen.add(source["source_id"])
                sources.append(source)
    receipt = evidence_receipt or (context.evidence_receipt if context else {
        "academic_record": "COVERAGE_UNKNOWN",
        "recognition": "NOT_SUPPLIED",
        "coverage": "COVERAGE_UNKNOWN",
    })
    source_directory = []
    source_links = []
    for conclusion in conclusions:
        for source in conclusion["source_references"]:
            source_links.append({"conclusion_id": conclusion["identity"], **source})
            if source["source_id"] not in {item["source_id"] for item in source_directory}:
                source_directory.append({**source, "conclusion_links": []})
            entry = next(item for item in source_directory if item["source_id"] == source["source_id"])
            entry["conclusion_links"].append({"conclusion_id": conclusion["identity"], "title": conclusion["title"], "locator": source["locator"], "relationship": source["relationship"]})
    return {
        "conclusions": conclusions,
        "sources": sources,
        "source_directory": source_directory,
        "source_relationships": source_links,
        "evidence_receipt": receipt,
        "launch_context": context.launch_context if context else {},
        "limitations": [
            "CRE evaluates represented rules against supplied evidence.",
            "CRE does not make admission, registration, waiver, Faculty-discretion or award decisions.",
        ],
    }


def advisor_reasoning_view(report: Any, *, context: PresentationContext | None = None) -> dict[str, Any]:
    """Minimal advisor depth over the same projection, without authorization logic."""
    view = student_reasoning_view(report, context=context)
    return {
        **view,
        "advisor_detail": {
            "canonical_outcomes": [
                {"identity": item.id, "outcome": getattr(item, "outcome", None),
                 "status": item.status, "assessment_complete": getattr(item, "assessment_complete", None),
                 "source_references": _requirement_sources(report, item, context),
                 "detail": item.detail, "used_course_codes": list(getattr(item, "used_course_codes", []))}
                for item in getattr(report, "requirements", [])
            ] + [
                {"identity": identity,
                 "outcome": getattr(item, "outcome", getattr(item, "condition_outcome", None)),
                 "assessment_complete": item.assessment_complete,
                 "status": getattr(item, "status", getattr(item, "effective_status", None)),
                 "source_reference": getattr(item, "source_reference", None), "detail": item.detail}
                for identity, item in (
                    *[(item.policy_id, item) for item in getattr(report, "progression_policy_assessments", [])],
                    *[(name, getattr(report, name, None)) for name in (
                        "programme_entry_eligibility_assessment", "qualification_completion", "graduation_eligibility_assessment", "qualification_award_assessment")],
                ) if item is not None
            ],
            "note": "Advisor access and case authority are outside this projection.",
        },
    }
