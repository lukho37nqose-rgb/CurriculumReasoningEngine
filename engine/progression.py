"""Progression-policy models, metric evaluation, and condition composition.

Report-level exclusion dispatch and legacy readmission thresholds remain in
rule_engine. This domain consumes explicit evidence and institutional frameworks.
"""

from dataclasses import dataclass, field
from typing import Any

from curriculum_reasoning_engine.institutions import (
    AcademicCreditFramework,
    CourseCodeScheme,
    CourseLoadFramework,
    GradingScheme,
)

from .completion import CourseCompletionRecognitionInput, CourseCompletionResolver
from .curriculum import _combine_status
from .framework_adapters import _credit_value, _is_senior_level, _load_equivalent
from .models import (
    AcademicRecordCoverageEvidence,
    Catalogue,
    CourseFact,
    CourseResult,
    ResultContextEvidence,
    StageRepeatEvidence,
    StudentRecord,
)
from .recognition import provisional_open_credit_results


@dataclass(frozen=True)
class AccumulatedProgressionMetricSpec:
    """Internal progression metric semantic shared by legacy aliases."""

    metric_basis: str
    temporal_scope: str
    minimum: float
    label: str
    filters: dict[str, Any] = field(default_factory=dict)
    concession_minimum: int | None = None
    legacy_rule_type: str = ""


@dataclass(frozen=True)
class AccumulatedProgressionMetricResult:
    value: float
    minimum: float
    academic_year: int | None = None
    evidence_available: bool = True


@dataclass(frozen=True)
class FailedProgressionMetricSpec:
    """Internal failed-evidence metric with explicit identity semantics."""

    metric_basis: str
    identity: str
    temporal_scope: str
    threshold: float
    label: str
    filters: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    legacy_rule_type: str = ""


@dataclass(frozen=True)
class FailedProgressionMetricResult:
    value: float
    threshold: float
    failed_codes: tuple[str, ...] = ()
    academic_year: int | None = None
    evidence_available: bool = True
    status: str = "verified"
    missing_context_attempt_ids: tuple[str, ...] = ()
    matched_context_attempt_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProgressionRatioSelectorSpec:
    metric_basis: str
    identity: str
    result_population: str
    evidence_population: str
    filters: dict[str, Any] = field(default_factory=dict)
    distinct_course_resolution: str | None = None


@dataclass(frozen=True)
class ProgressionRatioSpec:
    temporal_scope: str
    temporal_anchor: str
    numerator: ProgressionRatioSelectorSpec
    denominator: ProgressionRatioSelectorSpec
    comparison: str
    threshold: float
    label: str
    legacy_rule_type: str = ""


@dataclass(frozen=True)
class ProgressionRatioResult:
    numerator_value: float
    denominator_value: float
    threshold: float
    comparison: str
    ratio: float | None = None
    academic_year: int | None = None
    evidence_available: bool = True


@dataclass(frozen=True)
class RepeatedItemFailureSpec:
    """Attempt-history predicate with explicit repeated-item identity."""

    identity_basis: str
    temporal_scope: str
    maximum_failures: int
    label: str
    legacy_rule_type: str = ""


@dataclass(frozen=True)
class RepeatedItemFailureResult:
    maximum_failures: int
    failed_attempt_counts: dict[str, int]
    exceeded_items: tuple[str, ...]


@dataclass(frozen=True)
class FormalStageRepeatSpec:
    """Predicate over explicit institutional stage-repeat evidence."""

    programme_key: str
    pathway_key: str
    stage_key: str
    registration_period_key: str
    expected_repeat_state: str
    label: str


@dataclass(frozen=True)
class FormalStageRepeatResult:
    condition_established: bool | None
    status: str
    matched_evidence: tuple[StageRepeatEvidence, ...] = ()
    evidence_available: bool = True


@dataclass(frozen=True)
class RequiredCoursePoolCompletionSpec:
    """Predicate over existing governed course-completion semantics."""

    course_codes: tuple[str, ...]
    label: str
    rule_id: str = "required_course_pool"


@dataclass(frozen=True)
class CourseRequirementCompletionSpec:
    """Predicate over one existing governed course requirement."""

    course_codes: tuple[str, ...]
    required: int
    label: str
    rule_id: str = "course_requirement"


@dataclass(frozen=True)
class ProgressionConditionResult:
    """Neutral progression-condition result for shallow composition."""

    label: str
    outcome: str
    assessment_complete: bool
    status: str
    detail: str
    children: tuple["ProgressionConditionResult", ...] = ()


@dataclass(frozen=True)
class ProgressionConsequence:
    """Governed consequence assigned to an established progression condition."""

    consequence_type: str
    label: str


@dataclass(frozen=True)
class ProgressionPolicyResult:
    """Internal result for governed progression policy wrappers."""

    policy_id: str
    condition: ProgressionConditionResult
    consequence: ProgressionConsequence | None
    policy_status: str
    source_reference: str
    effective_status: str
    consequence_established: bool
    detail: str


@dataclass(frozen=True)
class ProgressionPolicyAssessment:
    """Structured report projection for a canonical progression policy."""

    policy_id: str
    consequence_type: str
    consequence_label: str
    condition_outcome: str
    consequence_established: bool
    assessment_complete: bool
    policy_status: str
    effective_status: str
    source_reference: str = ""
    detail: str = ""


def _accumulated_progression_metric_spec(
    raw: dict[str, Any], label: str
) -> AccumulatedProgressionMetricSpec | None:
    rule_type = str(raw.get("type", "")).strip().lower()
    if rule_type == "accumulated_metric":
        filters = raw.get("filters", {})
        return AccumulatedProgressionMetricSpec(
            metric_basis=str(raw.get("metric_basis", "credit_value")).strip().lower(),
            temporal_scope=str(raw.get("temporal_scope", "cumulative")).strip().lower(),
            minimum=float(raw.get("minimum", 0)),
            label=label,
            filters=filters if isinstance(filters, dict) else {},
            concession_minimum=(
                int(raw["concession_minimum"]) if raw.get("concession_minimum") is not None else None
            ),
            legacy_rule_type=rule_type,
        )
    aliases: dict[str, dict[str, Any]] = {
        "annual_credits": {
            "metric_basis": "credit_value",
            "temporal_scope": "latest_academic_year",
        },
        "annual_course_equivalents": {
            "metric_basis": "course_load_equivalent",
            "temporal_scope": "latest_academic_year",
            "filters": {"counts_towards_general_degree": True},
        },
        "cumulative_credits": {
            "metric_basis": "credit_value",
            "temporal_scope": "cumulative",
        },
        "science_cumulative_credits": {
            "metric_basis": "credit_value",
            "temporal_scope": "cumulative",
            "filters": {"science": True},
        },
        "senior_cumulative_credits": {
            "metric_basis": "credit_value",
            "temporal_scope": "cumulative",
            "filters": {"senior": True},
        },
        "course_equivalents_cumulative": {
            "metric_basis": "course_load_equivalent",
            "temporal_scope": "cumulative",
            "filters": {"counts_towards_general_degree": True},
        },
        "senior_course_equivalents_cumulative": {
            "metric_basis": "course_load_equivalent",
            "temporal_scope": "cumulative",
            "filters": {
                "counts_towards_general_degree": True,
                "senior": True,
            },
        },
    }
    alias = aliases.get(rule_type)
    if alias is None:
        return None
    return AccumulatedProgressionMetricSpec(
        metric_basis=alias["metric_basis"],
        temporal_scope=alias["temporal_scope"],
        minimum=float(raw.get("minimum", 0)),
        label=label,
        filters=alias.get("filters", {}),
        concession_minimum=(
            int(raw["concession_minimum"]) if raw.get("concession_minimum") is not None else None
        ),
        legacy_rule_type=rule_type,
    )


def _matches_accumulated_progression_filters(
    fact: CourseFact,
    spec: AccumulatedProgressionMetricSpec,
    credit_framework: AcademicCreditFramework | None,
) -> bool:
    filters = spec.filters
    if filters.get("senior") is True and not _is_senior_level(fact, credit_framework):
        return False
    if filters.get("science") is True and not fact.counts_as_science:
        return False
    if filters.get("counts_towards_general_degree") is True and not fact.counts_towards_general_degree:
        return False
    course_codes = {
        str(code).strip().upper() for code in filters.get("course_codes", []) if str(code).strip()
    }
    return not course_codes or fact.code in course_codes


def _accumulated_metric_value(
    result: CourseResult,
    fact: CourseFact | None,
    spec: AccumulatedProgressionMetricSpec,
    credit_framework: AcademicCreditFramework | None,
    course_load_framework: CourseLoadFramework | None,
) -> float:
    if spec.metric_basis == "credit_value":
        return float(_credit_value(fact if fact is not None else result, credit_framework))
    if spec.metric_basis == "course_load_equivalent":
        return _load_equivalent(fact if fact is not None else result, course_load_framework)
    raise ValueError(f"Unsupported accumulated progression metric: {spec.metric_basis}")


def _evaluate_accumulated_progression_metric(
    spec: AccumulatedProgressionMetricSpec,
    student: StudentRecord,
    catalogue: Catalogue,
    recognised: list[tuple[CourseResult, CourseFact]],
    provisional_progression: list[CourseResult],
    latest_year: int | None,
    grading_scheme: GradingScheme | None,
    credit_framework: AcademicCreditFramework | None,
    course_load_framework: CourseLoadFramework | None,
) -> AccumulatedProgressionMetricResult:
    if spec.temporal_scope == "cumulative":
        total = 0.0
        for result, fact in recognised:
            if _matches_accumulated_progression_filters(fact, spec, credit_framework):
                total += _accumulated_metric_value(
                    result, fact, spec, credit_framework, course_load_framework
                )
        if spec.metric_basis == "credit_value" and not spec.filters:
            total += sum(_credit_value(result, credit_framework) for result in provisional_progression)
        return AccumulatedProgressionMetricResult(total, spec.minimum)

    if spec.temporal_scope != "latest_academic_year":
        raise ValueError(f"Unsupported accumulated progression temporal scope: {spec.temporal_scope}")
    if latest_year is None:
        return AccumulatedProgressionMetricResult(0.0, spec.minimum, evidence_available=False)

    provisional_by_code = {result.code: result for result in provisional_progression}
    seen: set[str] = set()
    total = 0.0
    for result in student.results:
        if result.academic_year != latest_year or not result.is_passed(grading_scheme) or result.code in seen:
            continue
        fact = catalogue.courses.get(result.code)
        if fact is None and result.code in provisional_by_code:
            if spec.metric_basis != "credit_value" or spec.filters:
                continue
            total += _credit_value(result, credit_framework)
            seen.add(result.code)
            continue
        if fact is None or not _matches_accumulated_progression_filters(fact, spec, credit_framework):
            continue
        total += _accumulated_metric_value(result, fact, spec, credit_framework, course_load_framework)
        seen.add(result.code)
    return AccumulatedProgressionMetricResult(total, spec.minimum, latest_year)


def _accumulated_metric_messages(
    spec: AccumulatedProgressionMetricSpec,
    result: AccumulatedProgressionMetricResult,
) -> tuple[str | None, str | None, str | None]:
    label = spec.label
    minimum = spec.minimum
    value = result.value
    rule_type = spec.legacy_rule_type

    if not result.evidence_available:
        if rule_type == "annual_credits":
            return (
                None,
                None,
                f"{label}: the transcript does not expose academic-year labels needed to isolate annual credits.",
            )
        if rule_type == "annual_course_equivalents":
            return (
                None,
                None,
                f"{label}: academic-year labels are required to isolate annual course equivalents.",
            )
        return (
            None,
            None,
            f"{label}: academic-year labels are required to evaluate this progression metric.",
        )

    if value < minimum:
        if rule_type == "annual_credits":
            message = (
                f"{label}: {value:g} annual recognised credits passed; "
                f"at least {minimum:g} are ordinarily required."
            )
            if spec.concession_minimum is not None and value >= spec.concession_minimum:
                message += (
                    " This lies within the published concession-to-continue range "
                    f"(from {spec.concession_minimum} credits), but a concession is discretionary."
                )
            return message, None, None
        if rule_type == "annual_course_equivalents":
            return (
                f"{label}: {value:g} semester-course equivalent(s) passed in {result.academic_year}; "
                f"at least {minimum:g} are ordinarily required.",
                None,
                None,
            )
        if rule_type == "cumulative_credits":
            return (
                f"{label}: {value:g} cumulative recognised credits; at least {minimum:g} are required.",
                None,
                None,
            )
        if rule_type == "science_cumulative_credits":
            return (
                f"{label}: {value:g} recognised Science credits; at least {minimum:g} are required.",
                None,
                None,
            )
        if rule_type == "senior_cumulative_credits":
            return (
                f"{label}: {value:g} senior credits; at least {minimum:g} are required.",
                None,
                None,
            )
        if rule_type == "course_equivalents_cumulative":
            return (
                f"{label}: {value:g} full-course equivalents; at least {minimum:g} are required.",
                None,
                None,
            )
        if rule_type == "senior_course_equivalents_cumulative":
            return (
                f"{label}: {value:g} senior full-course equivalents; at least {minimum:g} are required.",
                None,
                None,
            )
        basis = spec.metric_basis.replace("_", " ")
        return (
            f"{label}: {value:g} accumulated {basis}; at least {minimum:g} are required.",
            None,
            None,
        )

    if rule_type == "annual_credits":
        return (
            None,
            f"{label}: annual recognised credits meet the {minimum:g}-credit threshold.",
            None,
        )
    if rule_type == "annual_course_equivalents":
        return (
            None,
            f"{label}: {value:g} annual course equivalent(s) meet {minimum:g}.",
            None,
        )
    if rule_type == "cumulative_credits":
        return (
            None,
            f"{label}: cumulative recognised credits meet the {minimum:g}-credit threshold.",
            None,
        )
    if rule_type == "science_cumulative_credits":
        return (
            None,
            f"{label}: Science credits meet the {minimum:g}-credit threshold.",
            None,
        )
    if rule_type == "senior_cumulative_credits":
        return (
            None,
            f"{label}: senior credits meet the {minimum:g}-credit threshold.",
            None,
        )
    if rule_type == "course_equivalents_cumulative":
        return None, f"{label}: full-course equivalents meet {minimum:g}.", None
    if rule_type == "senior_course_equivalents_cumulative":
        return None, f"{label}: senior full-course equivalents meet {minimum:g}.", None
    basis = spec.metric_basis.replace("_", " ")
    return None, f"{label}: accumulated {basis} meets {minimum:g}.", None


def _failed_progression_metric_spec(raw: dict[str, Any], label: str) -> FailedProgressionMetricSpec | None:
    rule_type = str(raw.get("type", "")).strip().lower()
    if rule_type == "failed_metric":
        if raw.get("threshold") is None and raw.get("minimum") is None:
            raise ValueError("failed_metric requires threshold or minimum")
        filters = raw.get("filters", {})
        context = raw.get("context", {})
        if context is not None and not isinstance(context, dict):
            raise ValueError("failed_metric context must be an object")
        return FailedProgressionMetricSpec(
            metric_basis=str(raw.get("metric_basis", "course_count")).strip().lower(),
            identity=str(raw.get("identity", "distinct_course")).strip().lower(),
            temporal_scope=str(raw.get("temporal_scope", "cumulative")).strip().lower(),
            threshold=float(raw.get("threshold", raw.get("minimum"))),
            label=label,
            filters=filters if isinstance(filters, dict) else {},
            context=context if isinstance(context, dict) else {},
            legacy_rule_type=rule_type,
        )

    aliases: dict[str, dict[str, Any]] = {
        "cumulative_failed_course_equivalents": {
            "metric_basis": "course_load_equivalent",
            "identity": "attempt",
            "temporal_scope": "cumulative",
            "threshold": raw.get("threshold", raw.get("minimum", 7)),
        },
        "failed_course_equivalents": {
            "metric_basis": "course_load_equivalent",
            "identity": "distinct_course",
            "temporal_scope": "latest_academic_year",
            "threshold": raw.get("threshold", raw.get("minimum", 4)),
        },
        "failed_course_count": {
            "metric_basis": "course_count",
            "identity": "distinct_course",
            "temporal_scope": "latest_academic_year",
            "threshold": raw.get("threshold", raw.get("minimum", 2)),
            "filters": {"course_codes": raw.get("course_codes", [])},
        },
        "failed_any": {
            "metric_basis": "course_count",
            "identity": "distinct_course",
            "temporal_scope": "cumulative",
            "threshold": 1,
            "filters": {"course_codes": raw.get("course_codes", [])},
        },
    }
    alias = aliases.get(rule_type)
    if alias is None:
        return None
    return FailedProgressionMetricSpec(
        metric_basis=alias["metric_basis"],
        identity=alias["identity"],
        temporal_scope=alias["temporal_scope"],
        threshold=float(alias["threshold"]),
        label=label,
        filters=alias.get("filters", {}),
        legacy_rule_type=rule_type,
    )


def _matches_failed_progression_filters(result: CourseResult, spec: FailedProgressionMetricSpec) -> bool:
    course_codes = {
        str(code).strip().upper() for code in spec.filters.get("course_codes", []) if str(code).strip()
    }
    return not course_codes or result.code in course_codes


def _failed_metric_value(
    results: list[CourseResult],
    spec: FailedProgressionMetricSpec,
    course_load_framework: CourseLoadFramework | None,
) -> float:
    if spec.metric_basis == "course_count":
        return float(len(results))
    if spec.metric_basis == "course_load_equivalent":
        return sum(_load_equivalent(result, course_load_framework) for result in results)
    raise ValueError(f"Unsupported failed progression metric: {spec.metric_basis}")


def _failed_metric_context_target(
    spec: FailedProgressionMetricSpec,
    *,
    programme_key: str,
    pathway_key: str,
) -> tuple[str, str, bool, str, str]:
    stage_key = str(spec.context.get("stage_key", "")).strip()
    registration_period_key = str(spec.context.get("registration_period_key", "")).strip()
    if not stage_key:
        raise ValueError("failed_metric context requires stage_key")
    if not registration_period_key:
        raise ValueError("failed_metric context requires registration_period_key")
    return (
        str(spec.context.get("programme_key", "")).strip() or programme_key,
        str(spec.context.get("pathway_key", "")).strip() or pathway_key,
        bool(str(spec.context.get("pathway_key", "")).strip()),
        stage_key,
        registration_period_key,
    )


def _result_context_evidence_matches_target(
    evidence: ResultContextEvidence,
    *,
    programme_key: str,
    pathway_key: str,
    pathway_required: bool,
    stage_key: str,
    registration_period_key: str,
) -> bool:
    if evidence.programme_key != programme_key:
        return False
    if evidence.stage_key != stage_key:
        return False
    if evidence.registration_period_key != registration_period_key:
        return False
    if pathway_required:
        return evidence.pathway_key == pathway_key
    if evidence.pathway_key:
        return bool(pathway_key) and evidence.pathway_key == pathway_key
    return True


def _result_context_pathway_applies(
    evidence: ResultContextEvidence,
    *,
    pathway_key: str,
    pathway_required: bool,
) -> bool:
    if pathway_required:
        return evidence.pathway_key == pathway_key
    return not evidence.pathway_key or not pathway_key or evidence.pathway_key == pathway_key


def _contextual_failed_metric_selection(
    scoped: list[CourseResult],
    spec: FailedProgressionMetricSpec,
    result_context_evidence: list[ResultContextEvidence] | None,
    *,
    programme_key: str,
    pathway_key: str,
) -> tuple[list[CourseResult], tuple[str, ...], str, tuple[str, ...]]:
    target_programme, target_pathway, pathway_required, target_stage, target_period = (
        _failed_metric_context_target(
            spec,
            programme_key=programme_key,
            pathway_key=pathway_key,
        )
    )
    evidence_by_attempt: dict[str, list[ResultContextEvidence]] = {}
    for evidence in result_context_evidence or []:
        evidence_by_attempt.setdefault(evidence.attempt_id, []).append(evidence)

    selected: list[CourseResult] = []
    selected_attempt_ids: list[str] = []
    missing_attempt_ids: list[str] = []
    statuses: list[str] = []
    conflict = False

    for result in scoped:
        if not result.attempt_id:
            missing_attempt_ids.append(f"{result.code}:<missing-attempt-id>")
            continue
        contexts = evidence_by_attempt.get(result.attempt_id, [])
        if not contexts:
            missing_attempt_ids.append(result.attempt_id)
            continue

        matching = [
            evidence
            for evidence in contexts
            if _result_context_evidence_matches_target(
                evidence,
                programme_key=target_programme,
                pathway_key=target_pathway,
                pathway_required=pathway_required,
                stage_key=target_stage,
                registration_period_key=target_period,
            )
        ]
        sibling_contexts = [
            evidence
            for evidence in contexts
            if evidence.programme_key == target_programme
            and evidence.registration_period_key == target_period
            and _result_context_pathway_applies(
                evidence,
                pathway_key=target_pathway,
                pathway_required=pathway_required,
            )
        ]
        sibling_keys = {
            (
                evidence.pathway_key,
                evidence.stage_key,
                evidence.registration_period_key,
            )
            for evidence in sibling_contexts
        }
        if matching and len(sibling_keys) > 1:
            conflict = True
            continue
        if matching:
            selected.append(result)
            selected_attempt_ids.append(result.attempt_id)
            statuses.extend(evidence.verification_status or "unverified" for evidence in matching)

    status = "conflict" if conflict else _combine_status(statuses)
    return selected, tuple(sorted(missing_attempt_ids)), status, tuple(selected_attempt_ids)


def _evaluate_failed_progression_metric(
    spec: FailedProgressionMetricSpec,
    student: StudentRecord,
    latest_year: int | None,
    grading_scheme: GradingScheme | None,
    course_load_framework: CourseLoadFramework | None,
    result_context_evidence: list[ResultContextEvidence] | None = None,
    programme_key: str = "",
    pathway_key: str = "",
) -> FailedProgressionMetricResult:
    if spec.temporal_scope == "latest_academic_year":
        if latest_year is None:
            return FailedProgressionMetricResult(0.0, spec.threshold, evidence_available=False)
        scoped = [
            result
            for result in student.results
            if result.academic_year == latest_year
            and result.is_failed(grading_scheme)
            and _matches_failed_progression_filters(result, spec)
        ]
    elif spec.temporal_scope == "institutional_context":
        scoped = [
            result
            for result in student.results
            if result.is_failed(grading_scheme) and _matches_failed_progression_filters(result, spec)
        ]
    elif spec.temporal_scope == "cumulative":
        scoped = [
            result
            for result in student.results
            if result.is_failed(grading_scheme) and _matches_failed_progression_filters(result, spec)
        ]
    else:
        raise ValueError(f"Unsupported failed progression temporal scope: {spec.temporal_scope}")

    missing_context_attempt_ids: tuple[str, ...] = ()
    matched_context_attempt_ids: tuple[str, ...] = ()
    status = "verified"
    if spec.context:
        scoped, missing_context_attempt_ids, status, matched_context_attempt_ids = (
            _contextual_failed_metric_selection(
                scoped,
                spec,
                result_context_evidence,
                programme_key=programme_key,
                pathway_key=pathway_key,
            )
        )
        if status == "conflict":
            return FailedProgressionMetricResult(
                0.0,
                spec.threshold,
                evidence_available=False,
                status="conflict",
            )

    if spec.identity == "attempt":
        selected = scoped
    elif spec.identity == "distinct_course":
        seen: set[str] = set()
        selected = []
        for result in scoped:
            if result.code in seen:
                continue
            seen.add(result.code)
            selected.append(result)
    else:
        raise ValueError(f"Unsupported failed progression identity: {spec.identity}")

    value = _failed_metric_value(selected, spec, course_load_framework)
    evidence_available = value >= spec.threshold or not missing_context_attempt_ids
    return FailedProgressionMetricResult(
        value,
        spec.threshold,
        tuple(sorted({result.code for result in selected})),
        latest_year if spec.temporal_scope == "latest_academic_year" else None,
        evidence_available,
        status,
        missing_context_attempt_ids,
        matched_context_attempt_ids,
    )


def _failed_metric_messages(
    spec: FailedProgressionMetricSpec,
    result: FailedProgressionMetricResult,
) -> tuple[str | None, str | None, str | None]:
    label = spec.label
    threshold = spec.threshold
    value = result.value
    rule_type = spec.legacy_rule_type

    if not result.evidence_available:
        if result.status == "conflict":
            return (
                None,
                None,
                f"{label}: conflicting institutional context evidence is recorded for a failed attempt.",
            )
        if result.missing_context_attempt_ids:
            return (
                None,
                None,
                f"{label}: institutional context evidence is unavailable for failed attempt(s): "
                + ", ".join(result.missing_context_attempt_ids)
                + ".",
            )
        if rule_type in {"failed_course_equivalents", "failed_course_count"}:
            return (
                None,
                None,
                f"{label}: academic-year labels are required to isolate failures in the latest year.",
            )
        return (
            None,
            None,
            f"{label}: academic-year labels are required to evaluate this failed progression metric.",
        )

    if rule_type == "failed_any":
        if value >= threshold:
            return (
                f"{label}: failed course(s): {', '.join(result.failed_codes)}.",
                None,
                None,
            )
        return None, None, None

    if value >= threshold:
        status_note = None
        if result.status != "verified":
            status_note = (
                f"{label}: matched institutional context evidence is "
                f"{result.status}; the failed-context fact cannot be verified."
            )
        if rule_type == "cumulative_failed_course_equivalents":
            return (
                f"{label}: {value:g} failed semester-course equivalent attempt(s) are recorded; the published threshold is {threshold:g}.",
                None,
                status_note,
            )
        if rule_type == "failed_course_equivalents":
            return (
                f"{label}: {value:g} half-course equivalent(s) failed in {result.academic_year}; "
                f"the published risk threshold is {threshold:g}.",
                None,
                status_note,
            )
        if rule_type == "failed_course_count":
            return (
                f"{label}: {value:g} distinct course(s) failed in {result.academic_year}; "
                f"the published risk threshold is {threshold:g}.",
                None,
                status_note,
            )
        basis = spec.metric_basis.replace("_", " ")
        return (
            f"{label}: failed {basis} is {value:g}; the configured threshold is {threshold:g}.",
            None,
            status_note,
        )

    if rule_type == "cumulative_failed_course_equivalents":
        return (
            None,
            f"{label}: {value:g} failed equivalent attempt(s) is below {threshold:g}.",
            None,
        )
    if rule_type == "failed_course_equivalents":
        return (
            None,
            f"{label}: {value:g} failed equivalent(s) is below {threshold:g}.",
            None,
        )
    if rule_type == "failed_course_count":
        return (
            None,
            f"{label}: {value:g} failed course(s) is below {threshold:g}.",
            None,
        )
    basis = spec.metric_basis.replace("_", " ")
    return (
        None,
        f"{label}: failed {basis} is {value:g}, below the {threshold:g} threshold.",
        None,
    )


def _progression_ratio_selector_spec(
    raw: dict[str, Any],
) -> ProgressionRatioSelectorSpec:
    filters = raw.get("filters", {})
    return ProgressionRatioSelectorSpec(
        metric_basis=str(raw.get("metric_basis", "course_count")).strip().lower(),
        identity=str(raw.get("identity", "attempt")).strip().lower(),
        result_population=str(raw.get("result_population", "")).strip().lower(),
        evidence_population=str(raw.get("evidence_population", "direct_results")).strip().lower(),
        filters=filters if isinstance(filters, dict) else {},
        distinct_course_resolution=(
            str(raw["distinct_course_resolution"]).strip().lower()
            if raw.get("distinct_course_resolution") is not None
            else None
        ),
    )


def _progression_ratio_spec(raw: dict[str, Any], label: str) -> ProgressionRatioSpec | None:
    rule_type = str(raw.get("type", "")).strip().lower()
    if rule_type == "progression_ratio":
        if raw.get("threshold") is None:
            raise ValueError("progression_ratio requires threshold")
        return ProgressionRatioSpec(
            temporal_scope=str(raw.get("temporal_scope", "latest_academic_year")).strip().lower(),
            temporal_anchor=str(raw.get("temporal_anchor", "selector_evidence")).strip().lower(),
            numerator=_progression_ratio_selector_spec(raw.get("numerator", {})),
            denominator=_progression_ratio_selector_spec(raw.get("denominator", {})),
            comparison=str(raw.get("comparison", "")).strip().lower(),
            threshold=float(raw["threshold"]),
            label=label,
            legacy_rule_type=rule_type,
        )
    if rule_type == "pass_rate":
        selector = {
            "metric_basis": "credit_value",
            "identity": "attempt",
            "evidence_population": "recognised_or_provisional",
        }
        return ProgressionRatioSpec(
            temporal_scope="latest_academic_year",
            temporal_anchor="recognised_or_provisional",
            numerator=_progression_ratio_selector_spec(selector | {"result_population": "passed"}),
            denominator=_progression_ratio_selector_spec(
                selector | {"result_population": "attempted_non_pending"}
            ),
            comparison="lt",
            threshold=float(raw.get("minimum", 0)),
            label=label,
            legacy_rule_type=rule_type,
        )
    if rule_type == "failed_course_fraction":
        filters = {"course_codes": raw.get("course_codes", [])}
        selector = {
            "metric_basis": "course_count",
            "identity": "distinct_course",
            "evidence_population": "direct_results",
            "distinct_course_resolution": "last_observed",
            "filters": filters,
        }
        return ProgressionRatioSpec(
            temporal_scope="latest_academic_year",
            temporal_anchor="recognised_or_provisional",
            numerator=_progression_ratio_selector_spec(selector | {"result_population": "failed"}),
            denominator=_progression_ratio_selector_spec(
                selector | {"result_population": "completed_non_pending"}
            ),
            comparison="gte",
            threshold=float(raw.get("threshold", raw.get("minimum", 0.5))),
            label=label,
            legacy_rule_type=rule_type,
        )
    return None


def _matches_progression_ratio_filters(result: CourseResult, selector: ProgressionRatioSelectorSpec) -> bool:
    course_codes = {
        str(code).strip().upper() for code in selector.filters.get("course_codes", []) if str(code).strip()
    }
    return not course_codes or result.code in course_codes


def _progression_ratio_base_items(
    selector: ProgressionRatioSelectorSpec,
    student: StudentRecord,
    catalogue: Catalogue,
    provisional_progression: list[CourseResult],
    academic_year: int,
) -> list[tuple[CourseResult, CourseFact | None]]:
    provisional_by_code = {result.code: result for result in provisional_progression}
    items: list[tuple[CourseResult, CourseFact | None]] = []
    for result in student.results:
        if result.academic_year != academic_year:
            continue
        if not _matches_progression_ratio_filters(result, selector):
            continue
        fact = catalogue.courses.get(result.code)
        if selector.evidence_population == "recognised_or_provisional":
            if fact is None and result.code not in provisional_by_code:
                continue
        elif selector.evidence_population != "direct_results":
            raise ValueError(
                f"Unsupported progression ratio evidence population: {selector.evidence_population}"
            )
        items.append((result, fact))
    return items


def _resolve_progression_ratio_identity(
    items: list[tuple[CourseResult, CourseFact | None]],
    selector: ProgressionRatioSelectorSpec,
) -> list[tuple[CourseResult, CourseFact | None]]:
    if selector.identity == "attempt":
        return items
    if selector.identity != "distinct_course":
        raise ValueError(f"Unsupported progression ratio identity: {selector.identity}")
    if selector.distinct_course_resolution != "last_observed":
        raise ValueError(
            "distinct_course progression ratios require distinct_course_resolution='last_observed'"
        )
    selected: dict[str, tuple[CourseResult, CourseFact | None]] = {}
    for result, fact in items:
        selected[result.code] = (result, fact)
    return list(selected.values())


def _matches_progression_ratio_population(
    result: CourseResult,
    selector: ProgressionRatioSelectorSpec,
    grading_scheme: GradingScheme | None,
) -> bool:
    if selector.result_population == "passed":
        return result.is_passed(grading_scheme)
    if selector.result_population == "failed":
        return result.is_failed(grading_scheme)
    if selector.result_population in {
        "attempted_non_pending",
        "completed_non_pending",
    }:
        return not result.is_pending(grading_scheme)
    raise ValueError(f"Unsupported progression ratio result population: {selector.result_population}")


def _progression_ratio_selector_value(
    selector: ProgressionRatioSelectorSpec,
    student: StudentRecord,
    catalogue: Catalogue,
    provisional_progression: list[CourseResult],
    academic_year: int,
    grading_scheme: GradingScheme | None,
    credit_framework: AcademicCreditFramework | None,
) -> float:
    items = _progression_ratio_base_items(
        selector, student, catalogue, provisional_progression, academic_year
    )
    resolved = _resolve_progression_ratio_identity(items, selector)
    matching = [
        (result, fact)
        for result, fact in resolved
        if _matches_progression_ratio_population(result, selector, grading_scheme)
    ]
    if selector.metric_basis == "course_count":
        return float(len(matching))
    if selector.metric_basis == "credit_value":
        return sum(
            float(_credit_value(fact if fact is not None else result, credit_framework))
            for result, fact in matching
        )
    raise ValueError(f"Unsupported progression ratio metric basis: {selector.metric_basis}")


def _evaluate_progression_ratio(
    spec: ProgressionRatioSpec,
    student: StudentRecord,
    catalogue: Catalogue,
    provisional_progression: list[CourseResult],
    latest_year: int | None,
    grading_scheme: GradingScheme | None,
    credit_framework: AcademicCreditFramework | None,
) -> ProgressionRatioResult:
    if spec.temporal_scope != "latest_academic_year":
        raise ValueError(f"Unsupported progression ratio temporal scope: {spec.temporal_scope}")
    if spec.temporal_anchor not in {
        "selector_evidence",
        "recognised_or_provisional",
    }:
        raise ValueError(f"Unsupported progression ratio temporal anchor: {spec.temporal_anchor}")
    if latest_year is None:
        return ProgressionRatioResult(
            0.0,
            0.0,
            spec.threshold,
            spec.comparison,
            evidence_available=False,
        )
    numerator = _progression_ratio_selector_value(
        spec.numerator,
        student,
        catalogue,
        provisional_progression,
        latest_year,
        grading_scheme,
        credit_framework,
    )
    denominator = _progression_ratio_selector_value(
        spec.denominator,
        student,
        catalogue,
        provisional_progression,
        latest_year,
        grading_scheme,
        credit_framework,
    )
    if denominator == 0:
        return ProgressionRatioResult(
            numerator,
            denominator,
            spec.threshold,
            spec.comparison,
            academic_year=latest_year,
            evidence_available=False,
        )
    return ProgressionRatioResult(
        numerator,
        denominator,
        spec.threshold,
        spec.comparison,
        numerator / denominator,
        latest_year,
    )


def _progression_ratio_triggers_risk(result: ProgressionRatioResult) -> bool:
    if result.ratio is None:
        return False
    if result.comparison == "lt":
        return result.ratio < result.threshold
    if result.comparison == "gte":
        return result.ratio >= result.threshold
    raise ValueError(f"Unsupported progression ratio comparison: {result.comparison}")


def _progression_ratio_messages(
    spec: ProgressionRatioSpec,
    result: ProgressionRatioResult,
) -> tuple[str | None, str | None, str | None]:
    label = spec.label
    threshold = spec.threshold
    rule_type = spec.legacy_rule_type

    if not result.evidence_available:
        if rule_type == "pass_rate":
            return None, None, f"{label}: annual attempted credits are unavailable."
        if rule_type == "failed_course_fraction":
            if result.academic_year is None:
                return (
                    None,
                    None,
                    f"{label}: academic-year labels are required to isolate the latest academic year.",
                )
            return (
                None,
                None,
                f"{label}: no completed course results are labelled for {result.academic_year}.",
            )
        return (
            None,
            None,
            f"{label}: ratio denominator evidence is unavailable.",
        )

    if result.ratio is None:
        raise ValueError("progression ratio message requested without a ratio")
    if _progression_ratio_triggers_risk(result):
        if rule_type == "pass_rate":
            return (
                f"{label}: {result.ratio * 100:.1f}% of annual attempted credits passed; "
                f"at least {threshold * 100:.0f}% is required.",
                None,
                None,
            )
        if rule_type == "failed_course_fraction":
            return (
                f"{label}: {result.numerator_value:g} of {result.denominator_value:g} course(s) failed in {result.academic_year} "
                f"({result.ratio * 100:.1f}%); the published threshold is {threshold * 100:.0f}%.",
                None,
                None,
            )
        return (
            f"{label}: ratio is {result.ratio * 100:.1f}%; the configured risk threshold is {threshold * 100:.0f}%.",
            None,
            None,
        )

    if rule_type == "pass_rate":
        return None, f"{label}: annual pass rate meets {threshold * 100:.0f}%.", None
    if rule_type == "failed_course_fraction":
        return (
            None,
            f"{label}: annual failed-course proportion is {result.ratio * 100:.1f}%.",
            None,
        )
    return None, f"{label}: ratio is {result.ratio * 100:.1f}%.", None


def _repeated_item_failure_spec(raw: dict[str, Any], label: str) -> RepeatedItemFailureSpec | None:
    rule_type = str(raw.get("type", "")).strip().lower()
    if rule_type == "repeated_item_failure":
        if raw.get("maximum_failures") is None:
            raise ValueError("repeated_item_failure requires maximum_failures")
        return RepeatedItemFailureSpec(
            identity_basis=str(raw.get("identity_basis", "")).strip().lower(),
            temporal_scope=str(raw.get("temporal_scope", "")).strip().lower(),
            maximum_failures=int(raw["maximum_failures"]),
            label=label,
            legacy_rule_type=rule_type,
        )
    if rule_type == "repeat_failure":
        return RepeatedItemFailureSpec(
            identity_basis="exact_course_code",
            temporal_scope="cumulative",
            maximum_failures=int(raw.get("maximum_failures", 1)),
            label=label,
            legacy_rule_type=rule_type,
        )
    return None


def _repeated_item_failure_identity(result: CourseResult, spec: RepeatedItemFailureSpec) -> str:
    if spec.identity_basis == "exact_course_code":
        return result.code
    raise ValueError(f"Unsupported repeated-item failure identity basis: {spec.identity_basis}")


def _evaluate_repeated_item_failure(
    spec: RepeatedItemFailureSpec,
    student: StudentRecord,
    grading_scheme: GradingScheme | None,
) -> RepeatedItemFailureResult:
    if spec.temporal_scope != "cumulative":
        raise ValueError(f"Unsupported repeated-item failure temporal scope: {spec.temporal_scope}")
    counts: dict[str, int] = {}
    for result in student.results:
        if not result.is_failed(grading_scheme):
            continue
        item_identity = _repeated_item_failure_identity(result, spec)
        counts[item_identity] = counts.get(item_identity, 0) + 1
    exceeded = tuple(sorted(item for item, count in counts.items() if count > spec.maximum_failures))
    return RepeatedItemFailureResult(spec.maximum_failures, counts, exceeded)


def _repeated_item_failure_messages(
    spec: RepeatedItemFailureSpec,
    result: RepeatedItemFailureResult,
) -> tuple[str | None, str | None, str | None]:
    if not result.exceeded_items:
        return None, None, None
    if spec.legacy_rule_type == "repeat_failure":
        return (
            f"{spec.label}: more than {result.maximum_failures} failed attempt(s) recorded for "
            f"{', '.join(result.exceeded_items)}.",
            None,
            None,
        )
    return (
        f"{spec.label}: repeated item(s) with more than {result.maximum_failures} failed attempt(s): "
        f"{', '.join(result.exceeded_items)}.",
        None,
        None,
    )


def _formal_stage_repeat_spec(raw: dict[str, Any], label: str) -> FormalStageRepeatSpec | None:
    rule_type = str(raw.get("type", "")).strip().lower()
    if rule_type not in {"formal_stage_repeat", "stage_repeat_state"}:
        return None
    stage_key = str(raw.get("stage_key", "")).strip()
    registration_period_key = str(raw.get("registration_period_key", "")).strip()
    if not stage_key:
        raise ValueError("formal_stage_repeat requires stage_key")
    if not registration_period_key:
        raise ValueError("formal_stage_repeat requires registration_period_key")
    expected = str(raw.get("expected_repeat_state", raw.get("repeat_state", "repeated"))).strip().lower()
    if expected not in {"repeated", "not_repeated"}:
        raise ValueError("formal_stage_repeat expected_repeat_state must be repeated or not_repeated")
    return FormalStageRepeatSpec(
        programme_key=str(raw.get("programme_key", "")).strip(),
        pathway_key=str(raw.get("pathway_key", "")).strip(),
        stage_key=stage_key,
        registration_period_key=registration_period_key,
        expected_repeat_state=expected,
        label=label,
    )


def _stage_repeat_evidence_matches(
    evidence: StageRepeatEvidence,
    spec: FormalStageRepeatSpec,
    *,
    programme_key: str,
    pathway_key: str,
) -> bool:
    target_programme = spec.programme_key or programme_key
    if evidence.programme_key != target_programme:
        return False
    if evidence.stage_key != spec.stage_key:
        return False
    if evidence.registration_period_key != spec.registration_period_key:
        return False
    if spec.pathway_key:
        return evidence.pathway_key == spec.pathway_key
    if evidence.pathway_key:
        return bool(pathway_key) and evidence.pathway_key == pathway_key
    return True


def _evaluate_formal_stage_repeat(
    spec: FormalStageRepeatSpec,
    stage_repeat_evidence: list[StageRepeatEvidence] | None,
    *,
    programme_key: str,
    pathway_key: str,
) -> FormalStageRepeatResult:
    matches = tuple(
        evidence
        for evidence in (stage_repeat_evidence or [])
        if _stage_repeat_evidence_matches(
            evidence,
            spec,
            programme_key=programme_key,
            pathway_key=pathway_key,
        )
    )
    if not matches:
        return FormalStageRepeatResult(
            condition_established=None,
            status="unverified",
            evidence_available=False,
        )

    states = {evidence.repeat_state.strip().lower() for evidence in matches}
    if not states <= {"repeated", "not_repeated"}:
        return FormalStageRepeatResult(
            condition_established=None,
            status="unverified",
            matched_evidence=matches,
            evidence_available=False,
        )
    if len(states) > 1:
        return FormalStageRepeatResult(
            condition_established=None,
            status="conflict",
            matched_evidence=matches,
        )

    status = _combine_status([evidence.verification_status or "unverified" for evidence in matches])
    state = next(iter(states))
    return FormalStageRepeatResult(
        condition_established=state == spec.expected_repeat_state,
        status=status,
        matched_evidence=matches,
    )


def _formal_stage_repeat_messages(
    spec: FormalStageRepeatSpec,
    result: FormalStageRepeatResult,
) -> tuple[str | None, str | None, str | None]:
    target = f"stage {spec.stage_key} in registration period {spec.registration_period_key}"
    if not result.evidence_available:
        return (
            None,
            None,
            f"{spec.label}: no matching formal stage-repeat evidence is available for {target}.",
        )
    if result.status == "conflict":
        return (
            None,
            None,
            f"{spec.label}: conflicting formal stage-repeat evidence is recorded for {target}.",
        )

    state = result.matched_evidence[0].repeat_state.strip().lower()
    status_note = None
    if result.status != "verified":
        status_note = (
            f"{spec.label}: formal stage-repeat evidence for {target} is "
            f"{result.status}; the progression fact cannot be verified."
        )

    if result.condition_established:
        reason = f"{spec.label}: institutional evidence establishes {state.replace('_', ' ')} for {target}."
        return reason, None, status_note

    note = f"{spec.label}: institutional evidence establishes {state.replace('_', ' ')} for {target}."
    return None, note, status_note


def _failed_metric_condition_result(
    spec: FailedProgressionMetricSpec,
    result: FailedProgressionMetricResult,
) -> ProgressionConditionResult:
    reason, note, unresolved = _failed_metric_messages(spec, result)
    detail = reason or note or unresolved or f"{spec.label}: no failed-metric condition."
    if result.status == "conflict":
        return ProgressionConditionResult(
            spec.label,
            "conflict",
            False,
            "conflict",
            detail,
        )
    if not result.evidence_available:
        return ProgressionConditionResult(
            spec.label,
            "unresolved",
            False,
            result.status if result.status != "verified" else "unverified",
            detail,
        )
    outcome = "satisfied" if result.value >= result.threshold else "not_satisfied"
    return ProgressionConditionResult(
        spec.label,
        outcome,
        result.status == "verified",
        result.status,
        detail,
    )


def _formal_stage_repeat_condition_result(
    spec: FormalStageRepeatSpec,
    result: FormalStageRepeatResult,
) -> ProgressionConditionResult:
    reason, note, unresolved = _formal_stage_repeat_messages(spec, result)
    detail = reason or note or unresolved or f"{spec.label}: no stage-repeat condition."
    if result.status == "conflict":
        return ProgressionConditionResult(
            spec.label,
            "conflict",
            False,
            "conflict",
            detail,
        )
    if not result.evidence_available or result.condition_established is None:
        return ProgressionConditionResult(
            spec.label,
            "unresolved",
            False,
            result.status if result.status != "verified" else "unverified",
            detail,
        )
    outcome = "satisfied" if result.condition_established else "not_satisfied"
    return ProgressionConditionResult(
        spec.label,
        outcome,
        result.status == "verified",
        result.status,
        detail,
    )


def _progression_ratio_condition_result(
    spec: ProgressionRatioSpec,
    result: ProgressionRatioResult,
) -> ProgressionConditionResult:
    reason, note, unresolved = _progression_ratio_messages(spec, result)
    detail = reason or note or unresolved or f"{spec.label}: no progression-ratio condition."
    if not result.evidence_available:
        return ProgressionConditionResult(
            spec.label,
            "unresolved",
            False,
            "unverified",
            detail,
        )
    outcome = "satisfied" if _progression_ratio_triggers_risk(result) else "not_satisfied"
    return ProgressionConditionResult(spec.label, outcome, True, "verified", detail)


def _required_course_pool_completion_spec(
    raw: dict[str, Any], label: str
) -> RequiredCoursePoolCompletionSpec | None:
    rule_type = str(raw.get("type", "")).strip().lower()
    if rule_type != "required_course_pool_incomplete":
        return None
    course_codes = tuple(
        dict.fromkeys(
            code for code in (str(value).strip().upper() for value in raw.get("course_codes", [])) if code
        )
    )
    return RequiredCoursePoolCompletionSpec(
        course_codes,
        label,
        str(raw.get("id", "required_course_pool")).strip() or "required_course_pool",
    )


def _course_requirement_completion_spec(
    raw: dict[str, Any], label: str
) -> CourseRequirementCompletionSpec | None:
    rule_type = str(raw.get("type", "")).strip().lower()
    if rule_type != "course_requirement_incomplete":
        return None
    course_codes = tuple(
        dict.fromkeys(
            code for code in (str(value).strip().upper() for value in raw.get("course_codes", [])) if code
        )
    )
    raw_required = raw.get("required", 1)
    try:
        required = int(raw_required)
    except (TypeError, ValueError):
        required = 0
    if isinstance(raw_required, bool) or required != raw_required:
        required = 0
    return CourseRequirementCompletionSpec(
        course_codes,
        required,
        label,
        str(raw.get("id", "course_requirement")).strip() or "course_requirement",
    )


def _completion_progression_result(
    label,
    codes,
    required,
    student,
    catalogue,
    grading_scheme,
    academic_record_coverage_evidence,
    completion_recognition,
):
    resolver = CourseCompletionResolver(student, catalogue, grading_scheme, completion_recognition)
    rows = [resolver.resolve(code, academic_record_coverage_evidence) for code in codes]
    witnesses = [row for row in rows if row.outcome == "satisfied"]
    if len(witnesses) >= required:
        selected = sorted(witnesses, key=lambda row: {"verified": 0, "provisional": 1}.get(row.status, 2))[
            :required
        ]
        status = _combine_status([row.status for row in selected])
        return ProgressionConditionResult(
            label,
            "not_satisfied",
            status == "verified",
            status,
            f"{label}: course requirement completed. " + " ".join(row.detail for row in selected),
        )
    status = _combine_status([row.status for row in rows])
    if any(row.outcome == "conflict" for row in rows):
        outcome = "conflict"
    elif sum(row.outcome != "not_satisfied" for row in rows) < required:
        outcome = "satisfied"
    else:
        outcome = "unresolved"
    return ProgressionConditionResult(
        label,
        outcome,
        all(row.assessment_complete for row in rows),
        status,
        f"{label}: " + " ".join(row.detail for row in rows),
    )


def _required_course_pool_condition_result(
    spec: RequiredCoursePoolCompletionSpec,
    *,
    student: StudentRecord,
    catalogue: Catalogue,
    grading_scheme: GradingScheme | None,
    credit_framework: AcademicCreditFramework | None,
    course_code_scheme: CourseCodeScheme | None,
    course_load_framework: CourseLoadFramework | None,
    academic_record_coverage_evidence: list[AcademicRecordCoverageEvidence] | None = None,
    completion_recognition: CourseCompletionRecognitionInput | None = None,
) -> ProgressionConditionResult:
    if not spec.course_codes:
        return ProgressionConditionResult(
            spec.label, "unsupported", False, "unverified", "Invalid completion requirement."
        )
    return _completion_progression_result(
        spec.label,
        spec.course_codes,
        len(spec.course_codes),
        student,
        catalogue,
        grading_scheme,
        academic_record_coverage_evidence,
        completion_recognition,
    )


def _course_requirement_condition_result(
    spec: CourseRequirementCompletionSpec,
    *,
    student: StudentRecord,
    catalogue: Catalogue,
    grading_scheme: GradingScheme | None,
    credit_framework: AcademicCreditFramework | None,
    course_code_scheme: CourseCodeScheme | None,
    course_load_framework: CourseLoadFramework | None,
    academic_record_coverage_evidence: list[AcademicRecordCoverageEvidence] | None = None,
    completion_recognition: CourseCompletionRecognitionInput | None = None,
) -> ProgressionConditionResult:
    if not spec.course_codes or spec.required != 1:
        return ProgressionConditionResult(
            spec.label,
            "unsupported",
            False,
            "unverified",
            "course_requirement_incomplete supports required=1 only.",
        )
    return _completion_progression_result(
        spec.label,
        spec.course_codes,
        spec.required,
        student,
        catalogue,
        grading_scheme,
        academic_record_coverage_evidence,
        completion_recognition,
    )


def _unsupported_progression_condition_result(label: str, rule_type: str) -> ProgressionConditionResult:
    return ProgressionConditionResult(
        label,
        "unsupported",
        False,
        "unverified",
        f"{label}: unsupported progression condition type {rule_type!r}.",
    )


def _evaluate_progression_condition(
    raw: dict[str, Any],
    *,
    student: StudentRecord,
    catalogue: Catalogue,
    latest_year: int | None,
    grading_scheme: GradingScheme | None,
    credit_framework: AcademicCreditFramework | None = None,
    course_code_scheme: CourseCodeScheme | None = None,
    course_load_framework: CourseLoadFramework | None,
    stage_repeat_evidence: list[StageRepeatEvidence] | None,
    result_context_evidence: list[ResultContextEvidence] | None,
    academic_record_coverage_evidence: list[AcademicRecordCoverageEvidence] | None = None,
    programme_key: str,
    pathway_key: str,
    completion_recognition: CourseCompletionRecognitionInput | None = None,
) -> ProgressionConditionResult:
    rule_type = str(raw.get("type", "")).strip().lower()
    label = str(raw.get("label", rule_type or "progression condition"))

    if rule_type == "all_of":
        return _evaluate_progression_all_of(
            raw,
            label,
            student=student,
            catalogue=catalogue,
            latest_year=latest_year,
            grading_scheme=grading_scheme,
            credit_framework=credit_framework,
            course_code_scheme=course_code_scheme,
            course_load_framework=course_load_framework,
            stage_repeat_evidence=stage_repeat_evidence,
            result_context_evidence=result_context_evidence,
            academic_record_coverage_evidence=academic_record_coverage_evidence,
            programme_key=programme_key,
            pathway_key=pathway_key,
            completion_recognition=completion_recognition,
        )

    failed_spec = _failed_progression_metric_spec(raw, label)
    if failed_spec is not None and failed_spec.legacy_rule_type == "failed_metric":
        failed_metric = _evaluate_failed_progression_metric(
            failed_spec,
            student,
            latest_year,
            grading_scheme,
            course_load_framework,
            result_context_evidence,
            programme_key,
            pathway_key,
        )
        return _failed_metric_condition_result(failed_spec, failed_metric)

    try:
        ratio_spec = _progression_ratio_spec(raw, label)
    except ValueError as exc:
        if rule_type == "progression_ratio":
            return ProgressionConditionResult(
                label,
                "unsupported",
                False,
                "unverified",
                f"{label}: {exc}",
            )
        raise
    if ratio_spec is not None and ratio_spec.legacy_rule_type == "progression_ratio":
        provisional_progression = provisional_open_credit_results(
            student, catalogue, grading_scheme, credit_framework, course_code_scheme
        )
        try:
            ratio = _evaluate_progression_ratio(
                ratio_spec,
                student,
                catalogue,
                provisional_progression,
                latest_year,
                grading_scheme,
                credit_framework,
            )
        except ValueError as exc:
            return ProgressionConditionResult(
                label,
                "unsupported",
                False,
                "unverified",
                f"{label}: {exc}",
            )
        return _progression_ratio_condition_result(ratio_spec, ratio)

    course_pool_spec = _required_course_pool_completion_spec(raw, label)
    if course_pool_spec is not None:
        return _required_course_pool_condition_result(
            course_pool_spec,
            student=student,
            catalogue=catalogue,
            grading_scheme=grading_scheme,
            credit_framework=credit_framework,
            course_code_scheme=course_code_scheme,
            course_load_framework=course_load_framework,
            academic_record_coverage_evidence=academic_record_coverage_evidence,
            completion_recognition=completion_recognition,
        )

    course_requirement_spec = _course_requirement_completion_spec(raw, label)
    if course_requirement_spec is not None:
        return _course_requirement_condition_result(
            course_requirement_spec,
            student=student,
            catalogue=catalogue,
            grading_scheme=grading_scheme,
            credit_framework=credit_framework,
            course_code_scheme=course_code_scheme,
            course_load_framework=course_load_framework,
            academic_record_coverage_evidence=academic_record_coverage_evidence,
            completion_recognition=completion_recognition,
        )

    stage_repeat_spec = _formal_stage_repeat_spec(raw, label)
    if stage_repeat_spec is not None:
        stage_repeat = _evaluate_formal_stage_repeat(
            stage_repeat_spec,
            stage_repeat_evidence,
            programme_key=programme_key,
            pathway_key=pathway_key,
        )
        return _formal_stage_repeat_condition_result(stage_repeat_spec, stage_repeat)

    return _unsupported_progression_condition_result(label, rule_type)


def _evaluate_progression_all_of(
    raw: dict[str, Any],
    label: str,
    *,
    student: StudentRecord,
    catalogue: Catalogue,
    latest_year: int | None,
    grading_scheme: GradingScheme | None,
    credit_framework: AcademicCreditFramework | None = None,
    course_code_scheme: CourseCodeScheme | None = None,
    course_load_framework: CourseLoadFramework | None,
    stage_repeat_evidence: list[StageRepeatEvidence] | None,
    result_context_evidence: list[ResultContextEvidence] | None,
    academic_record_coverage_evidence: list[AcademicRecordCoverageEvidence] | None = None,
    programme_key: str,
    pathway_key: str,
    completion_recognition: CourseCompletionRecognitionInput | None = None,
) -> ProgressionConditionResult:
    child_rules = raw.get("children", raw.get("rules", []))
    if not isinstance(child_rules, list) or not child_rules:
        return ProgressionConditionResult(
            label,
            "unsupported",
            False,
            "unverified",
            f"{label}: all_of requires child progression conditions.",
        )

    children: list[ProgressionConditionResult] = []
    for child in child_rules:
        if not isinstance(child, dict):
            children.append(_unsupported_progression_condition_result(label, "<malformed>"))
            continue
        child_type = str(child.get("type", "")).strip().lower()
        if child_type == "all_of":
            children.append(
                _unsupported_progression_condition_result(str(child.get("label", child_type)), child_type)
            )
            continue
        children.append(
            _evaluate_progression_condition(
                child,
                student=student,
                catalogue=catalogue,
                latest_year=latest_year,
                grading_scheme=grading_scheme,
                credit_framework=credit_framework,
                course_code_scheme=course_code_scheme,
                course_load_framework=course_load_framework,
                stage_repeat_evidence=stage_repeat_evidence,
                result_context_evidence=result_context_evidence,
                academic_record_coverage_evidence=academic_record_coverage_evidence,
                programme_key=programme_key,
                pathway_key=pathway_key,
                completion_recognition=completion_recognition,
            )
        )

    outcomes = [child.outcome for child in children]
    if "conflict" in outcomes:
        outcome = "conflict"
    elif "unsupported" in outcomes:
        outcome = "unsupported"
    elif "not_satisfied" in outcomes:
        outcome = "not_satisfied"
    elif "unresolved" in outcomes:
        outcome = "unresolved"
    else:
        outcome = "satisfied"
    assessment_complete = all(child.assessment_complete for child in children)
    status = _combine_status([child.status for child in children])
    detail = (
        f"{label}: {sum(child.outcome == 'satisfied' for child in children)} "
        f"of {len(children)} component progression condition(s) satisfied. "
        + " ".join(child.detail for child in children)
    )
    return ProgressionConditionResult(
        label,
        outcome,
        assessment_complete,
        status,
        detail,
        tuple(children),
    )


def _progression_condition_messages(
    result: ProgressionConditionResult,
) -> tuple[str | None, str | None, str | None]:
    unresolved_children = [
        child.detail
        for child in result.children
        if child.outcome in {"unresolved", "conflict", "unsupported"} or not child.assessment_complete
    ]
    unresolved_detail = " ".join(unresolved_children)

    if result.outcome == "satisfied":
        unresolved = None
        if not result.assessment_complete or result.status != "verified":
            unresolved = (
                f"{result.label}: condition is established but bounded by "
                f"{result.status} evidence; the progression fact cannot be verified."
            )
            if unresolved_detail:
                unresolved += " " + unresolved_detail
        return result.detail, None, unresolved

    if result.outcome == "not_satisfied":
        unresolved = unresolved_detail or None
        return None, result.detail, unresolved

    if result.outcome in {"unresolved", "conflict", "unsupported"}:
        return None, None, result.detail

    return None, None, f"{result.label}: unsupported progression outcome."


def _progression_policy_unsupported(raw: dict[str, Any], reason: str) -> ProgressionPolicyResult:
    label = str(raw.get("label", "progression policy"))
    policy_id = str(raw.get("policy_id", "")).strip()
    condition = ProgressionConditionResult(
        label,
        "unsupported",
        False,
        "unverified",
        f"{label}: {reason}",
    )
    return ProgressionPolicyResult(
        policy_id=policy_id,
        condition=condition,
        consequence=None,
        policy_status=str(raw.get("verification_status", "")).strip().lower(),
        source_reference=str(raw.get("source_reference", "")).strip(),
        effective_status="unverified",
        consequence_established=False,
        detail=condition.detail,
    )


def _progression_consequence(raw: Any) -> ProgressionConsequence | None:
    if not isinstance(raw, dict):
        return None
    consequence_type = str(raw.get("type", "")).strip().lower()
    if consequence_type not in {
        "advisory_risk",
        "review_required",
        "progression_ineligible",
    }:
        return None
    label = str(raw.get("label", consequence_type.replace("_", " "))).strip()
    return ProgressionConsequence(consequence_type, label or consequence_type)


def _evaluate_progression_policy(
    raw: dict[str, Any],
    *,
    student: StudentRecord,
    catalogue: Catalogue,
    latest_year: int | None,
    grading_scheme: GradingScheme | None,
    credit_framework: AcademicCreditFramework | None = None,
    course_code_scheme: CourseCodeScheme | None = None,
    course_load_framework: CourseLoadFramework | None = None,
    stage_repeat_evidence: list[StageRepeatEvidence] | None,
    result_context_evidence: list[ResultContextEvidence] | None,
    academic_record_coverage_evidence: list[AcademicRecordCoverageEvidence] | None = None,
    programme_key: str,
    pathway_key: str,
    completion_recognition: CourseCompletionRecognitionInput | None = None,
) -> ProgressionPolicyResult:
    policy_id = str(raw.get("policy_id", "")).strip()
    if not policy_id:
        return _progression_policy_unsupported(raw, "progression_policy requires explicit policy_id.")

    policy_status = str(raw.get("verification_status", "")).strip().lower()
    if not policy_status:
        return _progression_policy_unsupported(
            raw, f"{policy_id}: progression_policy requires explicit verification_status."
        )
    if policy_status not in {"verified", "provisional", "unverified", "conflict"}:
        return _progression_policy_unsupported(
            raw,
            f"{policy_id}: unsupported progression policy status {policy_status!r}.",
        )

    consequence = _progression_consequence(raw.get("consequence"))
    if consequence is None:
        return _progression_policy_unsupported(
            raw, f"{policy_id}: progression_policy requires explicit supported consequence."
        )

    condition_raw = raw.get("condition")
    if not isinstance(condition_raw, dict):
        return _progression_policy_unsupported(
            raw, f"{policy_id}: progression_policy requires a condition object."
        )

    condition = _evaluate_progression_condition(
        condition_raw,
        student=student,
        catalogue=catalogue,
        latest_year=latest_year,
        grading_scheme=grading_scheme,
        credit_framework=credit_framework,
        course_code_scheme=course_code_scheme,
        course_load_framework=course_load_framework,
        stage_repeat_evidence=stage_repeat_evidence,
        result_context_evidence=result_context_evidence,
        academic_record_coverage_evidence=academic_record_coverage_evidence,
        programme_key=programme_key,
        pathway_key=pathway_key,
        completion_recognition=completion_recognition,
    )
    effective_status = _combine_status([policy_status, condition.status])
    source_reference = str(raw.get("source_reference", "")).strip()
    consequence_established = condition.outcome == "satisfied" and effective_status != "conflict"
    source_detail = f" Source: {source_reference}." if source_reference else ""
    detail = (
        f"{policy_id}: {consequence.label} "
        f"({consequence.consequence_type}) under policy status {policy_status}. "
        f"{condition.detail}{source_detail}"
    )
    return ProgressionPolicyResult(
        policy_id=policy_id,
        condition=condition,
        consequence=consequence,
        policy_status=policy_status,
        source_reference=source_reference,
        effective_status=effective_status,
        consequence_established=consequence_established,
        detail=detail,
    )


def _progression_policy_messages(
    result: ProgressionPolicyResult,
) -> tuple[str | None, str | None, str | None]:
    if result.condition.outcome in {"unsupported", "unresolved", "conflict"}:
        return None, None, result.detail

    unresolved = None
    if result.effective_status != "verified" or not result.condition.assessment_complete:
        unresolved = (
            f"{result.policy_id}: policy consequence is bounded by "
            f"{result.effective_status} authority/status."
        )
        if not result.condition.assessment_complete:
            unresolved += " " + result.condition.detail

    if result.consequence_established and result.consequence is not None:
        return result.detail, None, unresolved

    note = (
        f"{result.policy_id}: configured condition did not trigger "
        "the governed progression consequence. " + result.condition.detail
    )
    return None, note, unresolved


def _progression_policy_assessment(
    result: ProgressionPolicyResult,
) -> ProgressionPolicyAssessment | None:
    if not result.policy_id or result.consequence is None:
        return None
    return ProgressionPolicyAssessment(
        policy_id=result.policy_id,
        consequence_type=result.consequence.consequence_type,
        consequence_label=result.consequence.label,
        condition_outcome=result.condition.outcome,
        consequence_established=result.consequence_established,
        assessment_complete=result.condition.assessment_complete,
        policy_status=result.policy_status,
        effective_status=result.effective_status,
        source_reference=result.source_reference,
        detail=result.detail,
    )
