"""
First-class reasoning primitives for academic conclusions.

This layer keeps facts, rules, and explanations together so the engine can
show why it reached a conclusion instead of only returning a boolean result.
"""
from dataclasses import dataclass, field
from typing import Any, Optional

from .models import Catalogue, CourseResult, MajorDefinition, StudentRecord
from .recognition import recognised_credited_pairs


@dataclass
class Evidence:
    """A fact used to support a conclusion."""
    source_type: str
    source_id: str
    claim: str
    confidence: float = 1.0


@dataclass
class AcademicRule:
    """A regulation or policy rule that can be evaluated against a metric."""
    id: str
    label: str
    metric: str
    operator: str
    required_value: float
    source: dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricResult:
    """A computed academic metric plus the evidence used to compute it."""
    id: str
    label: str
    value: float
    evidence: list[Evidence]
    supporting_conclusions: list["ReasonedConclusion"] = field(default_factory=list)


@dataclass
class ReasonedConclusion:
    """The result of applying one or more rules to facts and metrics."""
    id: str
    fact_key: str
    layer: str
    claim: str
    result: bool
    current: float
    required: float
    evidence: list[Evidence]
    applied_rules: list[str]
    explanation: str
    missing: float = 0.0
    status: str = "verified"
    confidence: float = 1.0
    assumptions: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)


class ReasoningGraph:
    """A directed graph of conclusions and the conclusions they depend on."""
    def __init__(self) -> None:
        self.conclusions: dict[str, ReasonedConclusion] = {}

    def add(self, conclusion: ReasonedConclusion) -> ReasonedConclusion:
        self.conclusions[conclusion.id] = conclusion
        return conclusion

    def add_many(self, conclusions: list[ReasonedConclusion]) -> list[ReasonedConclusion]:
        for conclusion in conclusions:
            self.add(conclusion)
        return conclusions

    def dependency_ids(self, conclusion_id: str) -> list[str]:
        conclusion = self.conclusions.get(conclusion_id)
        if not conclusion:
            return []
        return conclusion.depends_on

    def by_layer(self, layer: str) -> list[ReasonedConclusion]:
        return [
            conclusion for conclusion in self.conclusions.values()
            if conclusion.layer == layer
        ]

    def detect_conflicts(self) -> list[ReasonedConclusion]:
        conflicts = detect_conflicts(list(self.conclusions.values()))
        self.add_many(conflicts)
        return conflicts


def _combine_confidence(
    dependencies: list[ReasonedConclusion],
    assumptions: list[str] | None = None,
) -> float:
    if any(d.status == "conflict" for d in dependencies):
        return 0.0
    confidence = min((d.confidence for d in dependencies), default=1.0)
    if assumptions:
        confidence *= 0.95
    return round(confidence, 4)


def _combine_status(
    dependencies: list[ReasonedConclusion],
    assumptions: list[str] | None = None,
) -> str:
    if any(d.status == "conflict" for d in dependencies):
        return "conflict"
    if assumptions:
        return "provisional"
    if any(d.status != "verified" for d in dependencies):
        return "provisional"
    return "verified"


def course_pass_conclusion(result: CourseResult) -> ReasonedConclusion:
    """Represent a transcript result as a pass/fail academic conclusion."""
    passed = result.is_passed()
    failed = result.is_failed()
    recorded = result.mark if result.mark is not None else (result.grade or "no result")
    if passed:
        status = "verified"
        confidence = 1.0
        explanation = f"Transcript verifies that {result.code} was passed ({recorded})."
    elif failed:
        status = "verified"
        confidence = 1.0
        explanation = f"Transcript records a fail result for {result.code} ({recorded})."
    else:
        status = "unverified"
        confidence = 0.0
        explanation = f"The recorded result for {result.code} is pending or does not verify a pass ({recorded})."

    evidence = Evidence(
        source_type="transcript",
        source_id=result.code,
        claim=f"{result.code} result: {recorded}",
        confidence=confidence,
    )

    return ReasonedConclusion(
        id=f"course_pass:{result.code}",
        fact_key=f"course_completion:{result.code}",
        layer="academic_fact",
        claim=f"Course pass: {result.code}",
        result=passed,
        current=1.0 if passed else 0.0,
        required=1.0,
        evidence=[evidence],
        applied_rules=["TRANSCRIPT_PASS_MARK_50"],
        explanation=explanation,
        status=status,
        confidence=confidence,
    )


def credit_awarded_conclusion(
    result: CourseResult,
    course_pass: ReasonedConclusion,
) -> ReasonedConclusion:
    """Derive awarded credits from a verified course-pass conclusion."""
    credits_awarded = result.nqf_credits if course_pass.result else 0
    explanation = (
        f"{result.code} awards {credits_awarded:g} NQF credits "
        f"because the course pass conclusion is {course_pass.status}."
    )

    return ReasonedConclusion(
        id=f"credit_awarded:{result.code}",
        fact_key=f"credit_awarded:{result.code}",
        layer="academic_fact",
        claim=f"Credit awarded: {result.code}",
        result=course_pass.result,
        current=float(credits_awarded),
        required=float(result.nqf_credits),
        evidence=course_pass.evidence,
        applied_rules=[*course_pass.applied_rules, "PASSED_COURSE_AWARDS_CREDITS"],
        explanation=explanation,
        status=course_pass.status,
        confidence=course_pass.confidence,
        depends_on=[course_pass.id],
    )


def build_credit_reasoning_graph(student: StudentRecord) -> ReasoningGraph:
    """Build the pass -> credit-awarded portion of the reasoning graph."""
    graph = ReasoningGraph()
    # One academic fact per course code.  Prefer a passing attempt because a
    # course completed once continues to award its credits; otherwise use the
    # latest recorded attempt.
    ordered_codes = list(dict.fromkeys(result.code for result in student.results))
    for code in ordered_codes:
        result = student.passed_result_for(code) or student.result_for(code)
        if result is None:
            continue
        course_pass = graph.add(course_pass_conclusion(result))
        graph.add(credit_awarded_conclusion(result, course_pass))
    return graph


def imported_course_completion_conclusion(
    course_code: str,
    completed: bool,
    source_type: str,
    source_id: str,
    confidence: float = 1.0,
) -> ReasonedConclusion:
    """Represent a course-completion claim imported from another system."""
    state = "completed" if completed else "not completed"
    return ReasonedConclusion(
        id=f"{source_type}:{source_id}:course_completion:{course_code}",
        fact_key=f"course_completion:{course_code}",
        layer="academic_fact",
        claim=f"Imported course completion: {course_code}",
        result=completed,
        current=1.0 if completed else 0.0,
        required=1.0,
        evidence=[Evidence(
            source_type=source_type,
            source_id=source_id,
            claim=f"{source_type} says {course_code} is {state}",
            confidence=confidence,
        )],
        applied_rules=["IMPORTED_COURSE_COMPLETION"],
        explanation=f"{source_type} reports {course_code} as {state}.",
        status="verified" if confidence >= 1.0 else "provisional",
        confidence=confidence,
    )


def detect_conflicts(conclusions: list[ReasonedConclusion]) -> list[ReasonedConclusion]:
    """Find contradictory conclusions about the same academic fact."""
    by_fact: dict[str, list[ReasonedConclusion]] = {}
    for conclusion in conclusions:
        if not conclusion.fact_key or conclusion.status in {"conflict", "unverified"}:
            continue
        by_fact.setdefault(conclusion.fact_key, []).append(conclusion)

    conflicts: list[ReasonedConclusion] = []
    for fact_key, fact_conclusions in by_fact.items():
        result_values = {c.result for c in fact_conclusions}
        if len(result_values) < 2:
            continue

        positive = [c for c in fact_conclusions if c.result]
        negative = [c for c in fact_conclusions if not c.result]
        evidence = []
        for conclusion in fact_conclusions:
            evidence.extend(conclusion.evidence)

        conflicts.append(ReasonedConclusion(
            id=f"conflict:{fact_key}",
            fact_key=fact_key,
            layer="academic_fact",
            claim=f"Conflicting evidence for {fact_key}",
            result=False,
            current=0.0,
            required=1.0,
            evidence=evidence,
            applied_rules=["CONFLICTING_EVIDENCE_REQUIRES_MANUAL_VERIFICATION"],
            explanation=(
                f"Manual verification required: {len(positive)} source(s) support "
                f"{fact_key} as true and {len(negative)} source(s) support it as false."
            ),
            status="conflict",
            confidence=0.0,
            depends_on=[c.id for c in fact_conclusions],
        ))

    return conflicts


def passed_nqf_credits(student: StudentRecord) -> MetricResult:
    """Calculate passed NQF credits and preserve course-level evidence."""
    graph = build_credit_reasoning_graph(student)
    supporting = [
        conclusion for conclusion in graph.conclusions.values()
        if conclusion.id.startswith("credit_awarded:") and conclusion.result
    ]
    evidence: list[Evidence] = []
    total = 0.0

    for conclusion in supporting:
        total += conclusion.current
        evidence.extend(conclusion.evidence)

    return MetricResult(
        id="passed_nqf_credits",
        label="Passed NQF credits",
        value=total,
        evidence=evidence,
        supporting_conclusions=supporting,
    )


def total_nqf_credits_rule(
    required_credits: float,
    programme_key: str,
    programme_name: str,
) -> AcademicRule:
    """Build the graduation rule for minimum total NQF credits."""
    return AcademicRule(
        id=f"{programme_key.upper()}_TOTAL_NQF_CREDITS",
        label="Minimum NQF credits",
        metric="passed_nqf_credits",
        operator=">=",
        required_value=float(required_credits),
        source={
            "source_type": "catalogue",
            "programme_key": programme_key,
            "programme_name": programme_name,
            "field": "total_nqf_credits",
        },
    )


def evaluate_threshold_rule(
    metric: MetricResult,
    rule: AcademicRule,
    assumptions: list[str] | None = None,
) -> ReasonedConclusion:
    """Apply a simple numeric threshold rule to a metric."""
    if rule.operator != ">=":
        raise ValueError(f"Unsupported threshold operator: {rule.operator}")

    assumptions = assumptions or []
    complete = metric.value >= rule.required_value
    missing = max(rule.required_value - metric.value, 0.0)
    source_name = rule.source.get("programme_name", rule.source.get("programme_key", "programme rules"))
    dependencies = metric.supporting_conclusions

    if complete:
        explanation = (
            f"{metric.label} requirement met: {metric.value:g} credits "
            f"meets the {rule.required_value:g} credits required by {source_name}."
        )
    else:
        explanation = (
            f"{metric.label} requirement incomplete: {metric.value:g} credits "
            f"proved by the transcript, {missing:g} more needed to reach "
            f"{rule.required_value:g} credits required by {source_name}."
        )

    rule_evidence = Evidence(
        source_type=rule.source.get("source_type", "rule"),
        source_id=rule.id,
        claim=(
            f"{rule.label}: {metric.id} must be {rule.operator} "
            f"{rule.required_value:g}"
        ),
    )

    return ReasonedConclusion(
        id=rule.id,
        fact_key=f"requirement:{rule.id}",
        layer="requirement",
        claim=rule.label,
        result=complete,
        current=metric.value,
        required=rule.required_value,
        evidence=[rule_evidence, *metric.evidence],
        applied_rules=[rule.id],
        explanation=explanation,
        missing=missing,
        status=_combine_status(dependencies, assumptions),
        confidence=_combine_confidence(dependencies, assumptions),
        assumptions=assumptions,
        depends_on=[d.id for d in dependencies],
    )


def evaluate_total_nqf_credits(
    student: StudentRecord,
    required_credits: float,
    programme_key: str,
    programme_name: str,
    assumptions: list[str] | None = None,
) -> ReasonedConclusion:
    """Evaluate the total-credit graduation requirement with a trace."""
    metric = passed_nqf_credits(student)
    rule = total_nqf_credits_rule(required_credits, programme_key, programme_name)
    return evaluate_threshold_rule(metric, rule, assumptions=assumptions)


def build_total_nqf_credits_graph(
    student: StudentRecord,
    required_credits: float,
    programme_key: str,
    programme_name: str,
    assumptions: list[str] | None = None,
    catalogue: Catalogue | None = None,
    provisional_results: list[CourseResult] | None = None,
) -> ReasoningGraph:
    """Build Layer 2 credit facts and the Layer 3 total-credit requirement.

    When a selected catalogue is supplied, its recognition rules and credit
    values are authoritative. Transcript-extracted values remain evidence of
    the attempt, but cannot alter the programme total.
    """
    graph = build_credit_reasoning_graph(student)
    supporting = [
        conclusion for conclusion in graph.conclusions.values()
        if conclusion.id.startswith("credit_awarded:") and conclusion.result
    ]
    evidence: list[Evidence] = []
    total = 0.0

    provisional_results = provisional_results or []
    provisional_codes = {result.code for result in provisional_results}
    if catalogue is not None:
        recognised, _ = recognised_credited_pairs(student, catalogue)
        recognised_codes = {result.code for result, _ in recognised} | provisional_codes
        facts_by_code = {result.code: fact for result, fact in recognised}
    else:
        recognised_codes = {
            conclusion.id.split(":", 1)[1] for conclusion in supporting
        }
        facts_by_code = {}

    used_supporting = []
    for conclusion in supporting:
        code = conclusion.id.split(":", 1)[1]
        if code not in recognised_codes:
            continue
        fact = facts_by_code.get(code)
        awarded = float(fact.nqf_credits) if fact is not None else conclusion.current
        total += awarded
        used_supporting.append(conclusion)
        evidence.extend(conclusion.evidence)
        if fact is not None:
            evidence.append(Evidence(
                source_type="catalogue", source_id=code,
                claim=f"{code} carries {fact.nqf_credits} NQF credits at level {fact.nqf_level}.",
                confidence=1.0 if fact.verification_status == "verified" else 0.6,
            ))
        elif code in provisional_codes:
            evidence.append(Evidence(
                source_type="transcript", source_id=code,
                claim=(
                    f"{code} contributes {awarded:g} transcript credits provisionally under an "
                    "approved/open elective pool; faculty approval is not verified."
                ),
                confidence=0.35,
            ))

    metric = MetricResult(
        id="passed_nqf_credits",
        label="Passed NQF credits",
        value=total,
        evidence=evidence,
        supporting_conclusions=used_supporting,
    )
    rule = total_nqf_credits_rule(required_credits, programme_key, programme_name)
    graph.add(evaluate_threshold_rule(metric, rule, assumptions=assumptions))
    return graph


def major_required_course_conclusion(
    major: MajorDefinition,
    course_code: str,
    course_pass: ReasonedConclusion | None,
) -> ReasonedConclusion:
    """Evaluate one required course inside a major."""
    passed = bool(course_pass and course_pass.result)
    dependencies = [course_pass] if course_pass else []
    evidence = course_pass.evidence if course_pass else [
        Evidence(
            source_type="catalogue",
            source_id=major.key,
            claim=f"{course_code} is required for the {major.name} major",
        )
    ]
    explanation = (
        f"{course_code} satisfies a compulsory requirement for {major.name}."
        if passed
        else f"{course_code} is still required for {major.name}."
    )

    return ReasonedConclusion(
        id=f"major_required_course:{major.key}:{course_code}",
        fact_key=f"major_requirement:{major.key}:required:{course_code}",
        layer="requirement",
        claim=f"{major.name}: pass {course_code}",
        result=passed,
        current=1.0 if passed else 0.0,
        required=1.0,
        evidence=evidence,
        applied_rules=["MAJOR_REQUIRED_COURSE_MUST_BE_PASSED"],
        explanation=explanation,
        missing=0.0 if passed else 1.0,
        status=_combine_status(dependencies),
        confidence=_combine_confidence(dependencies),
        depends_on=[d.id for d in dependencies],
    )


def major_choice_group_conclusion(
    major: MajorDefinition,
    group_index: int,
    course_passes: dict[str, ReasonedConclusion],
) -> ReasonedConclusion:
    """Evaluate one choose-N group inside a major."""
    group = major.choice_groups[group_index]
    passed_options = [
        course_code for course_code in group.courses
        if course_passes.get(course_code) and course_passes[course_code].result
    ]
    dependencies = [
        course_passes[course_code] for course_code in group.courses
        if course_code in course_passes
    ]
    definition_valid = group.required > 0 and group.required <= len(group.courses)
    complete = definition_valid and len(passed_options) >= group.required
    label = group.label or f"Choice group {group_index + 1}"
    evidence = []
    for dependency in dependencies:
        evidence.extend(dependency.evidence)
    if not evidence:
        evidence.append(Evidence(
            source_type="catalogue",
            source_id=major.key,
            claim=f"{label} requires {group.required} from {group.courses}",
        ))

    return ReasonedConclusion(
        id=f"major_choice_group:{major.key}:{group_index}",
        fact_key=f"major_requirement:{major.key}:choice_group:{group_index}",
        layer="requirement",
        claim=f"{major.name}: {label}",
        result=complete,
        current=float(len(passed_options)),
        required=float(group.required),
        evidence=evidence,
        applied_rules=["MAJOR_CHOICE_GROUP_REQUIRES_N_PASSED_OPTIONS"],
        explanation=(
            f"{label} has an invalid catalogue definition and requires manual verification."
            if not definition_valid
            else (
                f"{label} complete for {major.name}: "
                f"{len(passed_options)}/{group.required} options passed."
                if complete
                else f"{label} incomplete for {major.name}: "
                f"{len(passed_options)}/{group.required} options passed."
            )
        ),
        missing=max(float(group.required - len(passed_options)), 0.0),
        status=_combine_status(dependencies) if definition_valid else "unverified",
        confidence=_combine_confidence(dependencies) if definition_valid else 0.0,
        depends_on=[d.id for d in dependencies],
    )


def major_completion_conclusion(
    major: MajorDefinition,
    requirement_conclusions: list[ReasonedConclusion],
) -> ReasonedConclusion:
    """Evaluate the whole major from its requirement conclusions."""
    has_requirements = bool(requirement_conclusions)
    complete = has_requirements and all(
        conclusion.result and conclusion.status == "verified"
        for conclusion in requirement_conclusions
    )
    missing = sum(
        1 for conclusion in requirement_conclusions
        if not conclusion.result or conclusion.status != "verified"
    )
    evidence = []
    for conclusion in requirement_conclusions:
        evidence.extend(conclusion.evidence)

    return ReasonedConclusion(
        id=f"major_complete:{major.key}",
        fact_key=f"major_complete:{major.key}",
        layer="requirement",
        claim=f"Complete major: {major.name}",
        result=complete,
        current=float(len(requirement_conclusions) - missing),
        required=float(len(requirement_conclusions)),
        evidence=evidence,
        applied_rules=["MAJOR_COMPLETE_WHEN_ALL_MAJOR_REQUIREMENTS_COMPLETE"],
        explanation=(
            f"{major.name} major has no encoded requirements and cannot be verified."
            if not has_requirements
            else (
                f"{major.name} major complete."
                if complete
                else f"{major.name} major incomplete or unverified: {missing} requirement(s) outstanding."
            )
        ),
        missing=float(missing),
        status=(
            "unverified" if not has_requirements
            else _combine_status(requirement_conclusions)
        ),
        confidence=(
            0.0 if not has_requirements
            else _combine_confidence(requirement_conclusions)
        ),
        depends_on=[conclusion.id for conclusion in requirement_conclusions],
    )


def build_major_completion_graph(
    student: StudentRecord,
    major: MajorDefinition,
    base_graph: Optional[ReasoningGraph] = None,
) -> ReasoningGraph:
    """Build Layer 2 facts and Layer 3 requirements for a major."""
    if base_graph is None:
        graph = build_credit_reasoning_graph(student)
    else:
        # A shallow copy of the conclusions dict is sufficient and much faster than deepcopy.
        # ReasonedConclusion objects are treated as immutable, and ReasoningGraph only has
        # the `conclusions` dict. We only append new conclusions for this major.
        graph = ReasoningGraph()
        graph.conclusions = base_graph.conclusions.copy()

    course_passes = {
        conclusion.id.split(":", 1)[1]: conclusion
        for conclusion in graph.conclusions.values()
        if conclusion.id.startswith("course_pass:")
    }

    requirement_conclusions: list[ReasonedConclusion] = []
    for course_code in major.required_courses:
        requirement = major_required_course_conclusion(
            major=major,
            course_code=course_code,
            course_pass=course_passes.get(course_code),
        )
        graph.add(requirement)
        requirement_conclusions.append(requirement)

    for group_index in range(len(major.choice_groups)):
        requirement = major_choice_group_conclusion(
            major=major,
            group_index=group_index,
            course_passes=course_passes,
        )
        graph.add(requirement)
        requirement_conclusions.append(requirement)

    graph.add(major_completion_conclusion(major, requirement_conclusions))
    return graph
