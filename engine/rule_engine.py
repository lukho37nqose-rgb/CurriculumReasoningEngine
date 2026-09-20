"""
Rule Engine — the core of CurriculumAdvisor.

"Store facts, compute views."

This module takes raw facts (StudentRecord + Catalogue) and computes
everything: graduation eligibility, major progress, eligible courses,
exclusion risk, distinction eligibility, and warnings.

No conclusions are stored in the JSON. Everything is derived here.
"""

import re
from dataclasses import dataclass, field, replace
from typing import Any

from curriculum_reasoning_engine.institutions import (
    AcademicCreditFramework,
    AcademicPeriodScheme,
    CourseCodeScheme,
    CourseLoadFramework,
    GradingScheme,
)

from .award import QualificationAwardAssessment, QualificationAwardEvidence, assess_qualification_award
from .completion import CourseCompletionRecognitionInput, CourseCompletionResolver
from .curriculum import (
    CurriculumEvaluator,
    RuleEvaluation,
    _combine_status,
    collect_curriculum_course_codes,
)
from .entry import ProgrammeEntryEligibilityAssessment, evaluate_programme_entry
from .evaluation_context import EvaluationContext
from .framework_adapters import _credit_value, _is_senior_level, _load_equivalent
from .graduation import (
    GraduationClearanceEvidence,
    GraduationEligibilityAssessment,
    evaluate_graduation_eligibility,
)
from .models import (
    AcademicRecordCoverageEvidence,
    AuthorisedAwardCourseSelection,
    Catalogue,
    CourseAttemptCoverageEvidence,
    CourseFact,
    CourseResult,
    ExternalSubjectAchievementCoverage,
    ExternalSubjectAchievementEvidence,
    MajorDefinition,
    PriorQualificationCoverage,
    PriorQualificationEvidence,
    RequirementRecognitionCoverage,
    RequirementRecognitionEvidence,
    ResultContextEvidence,
    StageRepeatEvidence,
    StudentRecord,
)
from .prerequisites import (
    AcademicConditionEvaluator,
    PrerequisiteEvaluator,
    legacy_prereqs_met,
    legacy_prerequisite_satisfied,
)
from .reasoning import (
    Evidence,
    ReasoningGraph,
    build_credit_reasoning_graph,
    build_major_completion_graph,
    build_total_nqf_credits_graph,
)
from .recognition import provisional_open_credit_results, recognised_credited_pairs
from .registration import RegistrationHistoryCoverage, RegistrationHistoryEvidence
from .utils import (
    _course_weight,
    _infer_programme_key,
    _normalise_major_keys,
)

# ---------------------------------------------------------------------------
# Output types — these are the "views" computed from facts
# ---------------------------------------------------------------------------


@dataclass
class Requirement:
    id: str
    label: str
    complete: bool
    current: float
    required: float
    detail: str = ""
    evidence: list[Evidence] = field(default_factory=list)
    applied_rules: list[str] = field(default_factory=list)
    explanation: str = ""
    status: str = "verified"
    confidence: float = 1.0
    assumptions: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    blocking: bool = True
    outcome: str | None = None
    assessment_complete: bool | None = None
    used_course_codes: list[str] = field(default_factory=list)


@dataclass
class MajorProgress:
    key: str
    name: str
    complete: bool
    completed_requirements: list[str]
    outstanding_requirements: list[str]
    status: str = "verified"
    confidence: float = 1.0
    used_course_codes: list[str] = field(default_factory=list)


@dataclass
class EligibleCourse:
    code: str
    name: str
    credits: int
    department: str
    offered: list[str]
    is_major_requirement: bool = False
    major_key: str | None = None
    major_name: str | None = None
    reason: str = ""
    status: str = "provisional"
    confidence: float = 0.75
    limitations: list[str] = field(default_factory=list)


@dataclass
class ExclusionRisk:
    at_risk: bool
    reasons: list[str]
    assessed: bool = True
    status: str = "provisional"
    confidence: float = 0.6
    basis: str = ""


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


@dataclass(frozen=True)
class QualificationCompletionAssessment:
    """Academic requirement completion, deliberately separate from graduation."""

    programme_key: str
    outcome: str
    assessment_complete: bool
    status: str
    required_requirement_ids: tuple[str, ...] = ()
    incomplete_requirement_ids: tuple[str, ...] = ()
    unresolved_requirement_ids: tuple[str, ...] = ()
    source_reference: str = ""
    detail: str = ""


@dataclass
class SubjectDistinction:
    major: str
    average: float
    senior_courses_assessed: int
    eligible: bool = False
    status: str = "provisional"
    reason: str = ""
    major_key: str = ""
    policy_id: str = ""


@dataclass
class Distinction:
    qualification_eligible: bool
    provisional: bool
    subjects: list[SubjectDistinction]
    status: str = "provisional"
    confidence: float = 0.5
    reason: str = ""


@dataclass
class Report:
    """The complete computed view for a student. Matches the app_2.py DEMO contract."""

    graduation_eligible: bool
    credits_completed: int
    level_7_credits: int
    semester_course_equivalents: float
    requirements: list[Requirement]
    majors: list[MajorProgress]
    eligible_courses: list[EligibleCourse]
    exclusion_risk: ExclusionRisk
    distinction: Distinction
    warnings: list[str]
    failed_attempts: dict[str, int]  # code -> number of failures
    student_name: str = ""  # for display in the UI
    graduation_status: str = "not_eligible"
    verification_messages: list[str] = field(default_factory=list)
    faculty_key: str = ""
    programme_key: str = ""
    programme_name: str = ""
    pathway_key: str = ""
    pathway_name: str = ""
    scope_status: str = "unscoped"
    qualification_completion: QualificationCompletionAssessment | None = None
    graduation_eligibility_assessment: GraduationEligibilityAssessment | None = None
    qualification_award_assessment: QualificationAwardAssessment | None = None
    progression_policy_assessments: list[ProgressionPolicyAssessment] = field(default_factory=list)
    programme_entry_eligibility_assessment: ProgrammeEntryEligibilityAssessment | None = None


def _academic_level(
    item: CourseFact | CourseResult,
    credit_framework: AcademicCreditFramework | None,
) -> int:
    return credit_framework.academic_level(item) if credit_framework is not None else item.nqf_level


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


# ---------------------------------------------------------------------------
# Major progress computation
# ---------------------------------------------------------------------------


def _compute_major_progress(
    major_def: MajorDefinition,
    student: StudentRecord,
    base_graph: ReasoningGraph | None = None,
    catalogue: Catalogue | None = None,
    grading_scheme: GradingScheme | None = None,
    credit_framework: AcademicCreditFramework | None = None,
    course_code_scheme: CourseCodeScheme | None = None,
    course_load_framework: CourseLoadFramework | None = None,
    completion_recognition: CourseCompletionRecognitionInput | None = None,
) -> MajorProgress:
    completed_reqs: list[str] = []
    outstanding_reqs: list[str] = []
    used_codes: list[str] = []

    if completion_recognition is not None and catalogue is not None and not major_def.curriculum_rules:
        rules = [
            {"type": "course", "course_codes": [code], "label": f"Pass {code}"}
            for code in major_def.required_courses
        ]
        rules.extend(
            {
                "type": "choose_n",
                "course_codes": group.courses,
                "required": group.required,
                "label": group.label,
            }
            for group in major_def.choice_groups
        )
        if rules:
            major_def = replace(major_def, curriculum_rules=rules)

    if major_def.curriculum_rules and catalogue is not None:
        evaluator = CurriculumEvaluator(
            student,
            catalogue,
            grading_scheme,
            credit_framework,
            course_code_scheme,
            completion_recognition=completion_recognition,
        )
        evaluations = evaluator.evaluate_many(major_def.curriculum_rules)
        for row in evaluations:
            target = completed_reqs if row.complete else outstanding_reqs
            target.append(f"{row.label}: {row.detail}")
            used_codes.extend(row.used_course_codes)
        blocking = [row for row in evaluations if row.blocking]
        complete = bool(blocking) and all(row.complete for row in blocking)
        statuses = [row.status for row in blocking]
        if major_def.verification_status != "verified":
            status = "unverified"
        elif any(value == "conflict" for value in statuses):
            status = "conflict"
        elif any(value in {"unverified", "discretionary", "provisional"} for value in statuses):
            status = "unverified"
        else:
            status = "verified"
        if major_def.admission_limited:
            status = "unverified"
            outstanding_reqs.append(
                major_def.admission_note or "Formal admission to this major must be confirmed."
            )
        return MajorProgress(
            key=major_def.key,
            name=major_def.name,
            complete=complete,
            completed_requirements=completed_reqs,
            outstanding_requirements=outstanding_reqs,
            status=status,
            confidence=1.0 if status == "verified" else 0.45,
            used_course_codes=sorted(set(used_codes)),
        )

    if not major_def.required_courses and not major_def.choice_groups:
        return MajorProgress(
            key=major_def.key,
            name=major_def.name,
            complete=False,
            completed_requirements=[],
            outstanding_requirements=[
                "Requirements are not representable in the current catalogue; manual verification is required."
            ],
            status="unverified",
            confidence=0.0,
            used_course_codes=[],
        )

    graph = build_major_completion_graph(student, major_def, base_graph, grading_scheme, credit_framework)
    passed = student.passed_codes(grading_scheme)
    for code in major_def.required_courses:
        requirement = graph.conclusions[f"major_required_course:{major_def.key}:{code}"]
        if requirement.result:
            completed_reqs.append(f"Pass {code}")
            used_codes.append(code)
        else:
            outstanding_reqs.append(f"Pass {code}")

    for index, group in enumerate(major_def.choice_groups):
        requirement = graph.conclusions[f"major_choice_group:{major_def.key}:{index}"]
        selected = [code for code in group.courses if code in passed][: group.required]
        used_codes.extend(selected)
        satisfied = int(requirement.current)
        if requirement.result:
            completed_reqs.append(f"{group.label}: {satisfied}/{group.required}")
        else:
            outstanding_reqs.append(
                f"{group.label}: {satisfied}/{group.required} - need {group.required - satisfied} more from {group.courses}"
            )

    complete = bool(graph.conclusions[f"major_complete:{major_def.key}"].result)
    status = "verified" if major_def.verification_status == "verified" else "unverified"
    if status != "verified":
        outstanding_reqs.extend(
            major_def.verification_notes
            or ["This major has conditional pathways that require handbook or advisor verification."]
        )
    return MajorProgress(
        key=major_def.key,
        name=major_def.name,
        complete=complete,
        completed_requirements=completed_reqs,
        outstanding_requirements=outstanding_reqs,
        status=status,
        confidence=1.0 if status == "verified" else 0.45,
        used_course_codes=used_codes,
    )


# ---------------------------------------------------------------------------
# Eligible courses computation (prerequisites met, not yet passed)
# ---------------------------------------------------------------------------


def _prerequisite_satisfied(prerequisite: str, passed: set[str]) -> bool:
    """Compatibility wrapper for legacy UCT-shaped prerequisite lists."""
    return legacy_prerequisite_satisfied(prerequisite, passed)


def _prereqs_met(course: CourseFact, passed: set[str]) -> bool:
    """Compatibility wrapper retained for existing callers and tests."""
    return legacy_prereqs_met(course, passed)


def _curriculum_option_labels(rules: list[dict]) -> dict[str, str]:
    labels: dict[str, str] = {}

    def walk(rule: dict, optional_context: bool = False) -> None:
        rule_type = str(rule.get("type", "")).strip().lower()
        optional_here = optional_context or rule_type in {
            "choose_n",
            "credit_pool",
            "approved_credit_pool",
            "same_department_credit_pool",
            "maximum_credit_pool",
            "any_of",
        }
        if optional_here:
            label = str(rule.get("label", "Programme option"))
            for code in collect_curriculum_course_codes([rule]):
                labels.setdefault(code, label)
        for child in rule.get("children", []):
            if isinstance(child, dict):
                walk(child, optional_here)

    for rule in rules:
        if isinstance(rule, dict):
            walk(rule)
    return labels


def _compute_eligible_courses(
    student: StudentRecord,
    catalogue: Catalogue,
    grading_scheme: GradingScheme | None = None,
    credit_framework: AcademicCreditFramework | None = None,
    course_code_scheme: CourseCodeScheme | None = None,
    course_load_framework: CourseLoadFramework | None = None,
    academic_record_coverage_evidence: list[AcademicRecordCoverageEvidence] | None = None,
    completion_recognition: CourseCompletionRecognitionInput | None = None,
    achievement_scheme=None,
    course_attempt_coverage_evidence: list[CourseAttemptCoverageEvidence] | None = None,
    external_qualification_systems=(),
    external_subject_achievement_evidence: list[ExternalSubjectAchievementEvidence] | None = None,
    external_subject_achievement_coverage: list[ExternalSubjectAchievementCoverage] | None = None,
    prior_qualification_evidence: list[PriorQualificationEvidence] | None = None,
    prior_qualification_coverage: list[PriorQualificationCoverage] | None = None,
) -> list[EligibleCourse]:
    passed = CourseCompletionResolver(
        student, catalogue, grading_scheme, completion_recognition
    ).completed_codes()
    prerequisite_evaluator = PrerequisiteEvaluator(
        student,
        catalogue,
        grading_scheme,
        credit_framework,
        course_code_scheme,
        course_load_framework,
        academic_record_coverage_evidence,
        completion_recognition=completion_recognition,
        achievement_scheme=achievement_scheme,
        course_attempt_coverage_evidence=course_attempt_coverage_evidence,
        external_qualification_systems=external_qualification_systems,
        external_subject_achievement_evidence=external_subject_achievement_evidence,
        external_subject_achievement_coverage=external_subject_achievement_coverage,
        prior_qualification_evidence=prior_qualification_evidence,
        prior_qualification_coverage=prior_qualification_coverage,
    )
    major_keys = _normalise_major_keys(student.declared_majors, catalogue)

    major_defs = []
    for m_key in major_keys:
        m_def = catalogue.majors.get(m_key)
        if m_def:
            major_defs.append((m_key, m_def))

    major_course_codes = {
        code
        for _, major_def in major_defs
        for code in (
            list(major_def.required_courses)
            + [course for group in major_def.choice_groups for course in group.courses]
            + list(collect_curriculum_course_codes(major_def.curriculum_rules, catalogue))
            + [
                course
                for stage_rules in major_def.stage_rules.values()
                for course in collect_curriculum_course_codes(stage_rules, catalogue)
            ]
        )
    }
    major_option_labels: dict[tuple[str, str], str] = {}
    for m_key, m_def in major_defs:
        labels = _curriculum_option_labels(m_def.curriculum_rules)
        for stage_rules in m_def.stage_rules.values():
            labels.update(_curriculum_option_labels(stage_rules))
        for code, label in labels.items():
            major_option_labels[(m_key, code)] = label
    programme = catalogue.programmes.get(student.programme_key or _infer_programme_key(student.programme))
    programme_required_codes = set(programme.required_courses) if programme else set()
    programme_support_codes = set(programme.support_course_codes) if programme else set()
    option_labels: dict[str, str] = {}
    if programme:
        programme_rule_codes = collect_curriculum_course_codes(programme.curriculum_rules, catalogue)
        programme_required_codes.update(programme_rule_codes)
        option_labels.update(_curriculum_option_labels(programme.curriculum_rules))
        pathway = programme.pathways.get(student.pathway_key or catalogue.pathway_key)
        if pathway:
            programme_required_codes.update(pathway.required_courses)
            programme_required_codes.update(
                collect_curriculum_course_codes(pathway.curriculum_rules, catalogue)
            )
            option_labels.update(_curriculum_option_labels(pathway.curriculum_rules))
            programme_support_codes.update(pathway.support_course_codes)
    explicitly_allowed_codes = (
        major_course_codes
        | programme_required_codes
        | programme_support_codes
        | set(catalogue.elective_course_codes)
    )
    highest_observed_level = max(
        (
            _academic_level(r, credit_framework)
            for r in student.results
            if _academic_level(r, credit_framework) > 0
        ),
        default=7,
    )
    max_elective_level = max(7, highest_observed_level)

    # Augmenting course facts are stored separately from their regular
    # co-requisite.  This reverse map lets the engine recommend them only when
    # the linked subject course belongs to the student's selected route.
    augmenting_parents: dict[str, list[str]] = {}
    for parent_code, parent in catalogue.courses.items():
        if parent.augmenting_course:
            augmenting_parents.setdefault(parent.augmenting_course, []).append(parent_code)

    eligible = []
    for code, course in catalogue.courses.items():
        if catalogue.programme_key and code not in explicitly_allowed_codes:
            continue  # outside the selected programme/major/elective boundary
        if code in passed:
            continue  # already passed
        course_credit = _credit_value(course, credit_framework)
        course_level = _academic_level(course, credit_framework)
        if (course.credit_bearing and course_credit <= 0) or course_level <= 0:
            continue  # malformed catalogue fact cannot support advice

        is_major_code = code in major_course_codes
        is_programme_required = code in programme_required_codes
        is_support_course = code in programme_support_codes
        is_general_elective = course.general_elective and (
            code in catalogue.elective_course_codes or not catalogue.programme_key
        )
        if not (is_major_code or is_programme_required or is_support_course or is_general_elective):
            continue
        if not course.counts_towards_general_degree and not is_programme_required:
            continue
        if not course.offering_verified or not course.offered:
            continue
        prerequisite = prerequisite_evaluator.evaluate_for_course(course)
        if prerequisite.outcome != "satisfied":
            continue  # recorded prerequisites not met or not verified
        # FB5.1 ordinarily prevents first-year non-Humanities courses unless
        # they are required by a recognised non-Humanities major.  A transcript
        # does not prove the student's registration year, so the safe default is
        # to recommend them only inside a selected major pathway.
        if (
            catalogue.faculty_key == "uct_humanities"
            and not course.counts_as_humanities
            and course_level == 5
            and not is_major_code
            and not is_programme_required
        ):
            continue

        if course.augmenting:
            parents = augmenting_parents.get(code, [])
            if not parents or not any(
                parent in major_course_codes or parent in catalogue.elective_course_codes
                for parent in parents
            ):
                continue

        # Do not present unrelated postgraduate courses as general electives.
        if course_level > max_elective_level and not is_major_code:
            continue
        if not is_major_code and not is_support_course and course_level > 5 and not course.prerequisites:
            # An advanced course with no recorded prerequisites may genuinely
            # be open, but it may equally reflect incomplete extraction.
            continue

        is_major = False
        major_key = None
        major_name = None
        reason = "Recorded prerequisites are met"
        status = "provisional"
        confidence = 0.75

        for m_key, m_def in major_defs:
            curriculum_codes = collect_curriculum_course_codes(m_def.curriculum_rules, catalogue)
            if code in curriculum_codes:
                is_major = True
                major_key = m_key
                major_name = m_def.name
                option_label = major_option_labels.get((m_key, code))
                reason = (
                    f"Option for {option_label} ({m_def.name} major)"
                    if option_label
                    else f"Required for {m_def.name} major"
                )
                status = (
                    "verified"
                    if (m_def.verification_status == "verified" and course.verification_status == "verified")
                    else "provisional"
                )
                if m_def.admission_limited and _is_senior_level(course, credit_framework):
                    status = "discretionary"
                    reason += "; formal admission to the limited major must be confirmed"
                confidence = 0.9 if status == "verified" else 0.5
                break
            if code in m_def.required_courses:
                is_major = True
                major_key = m_key
                major_name = m_def.name
                reason = f"Required for {m_def.name} major"
                status = (
                    "verified"
                    if (m_def.verification_status == "verified" and course.verification_status == "verified")
                    else "provisional"
                )
                confidence = 0.95 if status == "verified" else 0.7
                break
            for group in m_def.choice_groups:
                if code in group.courses:
                    is_major = True
                    major_key = m_key
                    major_name = m_def.name
                    reason = f"{group.label} ({m_def.name} major), pick {group.required}"
                    status = (
                        "verified"
                        if (
                            m_def.verification_status == "verified"
                            and course.verification_status == "verified"
                        )
                        else "provisional"
                    )
                    confidence = 0.9 if status == "verified" else 0.7
                    break
            if is_major:
                break

        if not is_major and is_programme_required:
            if code in option_labels:
                reason = f"Option for {option_labels[code]}"
                status = "verified" if course.verification_status == "verified" else "provisional"
                confidence = 0.9 if status == "verified" else 0.65
            else:
                reason = f"Compulsory for {programme.name}" if programme else "Compulsory programme course"
                status, confidence = "verified", 0.95
        elif not is_major and is_support_course:
            if course.augmenting:
                parents = augmenting_parents.get(code, [])
                reason = "Extended-programme augmenting course; take concurrently with " + ", ".join(parents)
            else:
                reason = "One of the additional introductory courses for the extended programme"
            status, confidence = "verified", 0.9
        elif not is_major and is_general_elective:
            reason = "Recognised general-degree elective; recorded prerequisites are met"
            status = "verified" if course.verification_status == "verified" else "provisional"
            confidence = 0.9 if status == "verified" else 0.6

        status = _combine_status([status, prerequisite.status])
        if prerequisite.status != "verified":
            confidence = min(confidence, 0.45)
            reason += "; " + prerequisite.detail
        eligible.append(
            EligibleCourse(
                code=code,
                name=course.name,
                credits=course_credit,
                department=course.department,
                offered=course.offered,
                is_major_requirement=is_major,
                major_key=major_key,
                major_name=major_name,
                reason=reason,
                status=status,
                confidence=confidence,
                limitations=[
                    "This checks only prerequisites recorded in the catalogue.",
                    *(
                        [
                            "Co-requisite course(s) must be taken with this course: "
                            + ", ".join(course.co_requisites)
                        ]
                        if course.co_requisites
                        else []
                    ),
                    *([course.recognition_note] if course.recognition_note else []),
                    "Timetable clashes, class limits, concessions, and faculty approval are not verified.",
                ],
            )
        )

    eligible.sort(
        key=lambda c: (
            not c.is_major_requirement,
            c.status != "verified",
            not _is_senior_level(catalogue.courses[c.code], credit_framework),
            c.code,
        )
    )
    return eligible


# ---------------------------------------------------------------------------
# Exclusion risk
# ---------------------------------------------------------------------------


def _compute_exclusion_risk(
    student: StudentRecord,
    catalogue: Catalogue,
    programme_key: str,
    grading_scheme: GradingScheme | None = None,
    credit_framework: AcademicCreditFramework | None = None,
    course_code_scheme: CourseCodeScheme | None = None,
    course_load_framework: CourseLoadFramework | None = None,
    stage_repeat_evidence: list[StageRepeatEvidence] | None = None,
    result_context_evidence: list[ResultContextEvidence] | None = None,
    academic_record_coverage_evidence: list[AcademicRecordCoverageEvidence] | None = None,
    progression_policy_assessments: list[ProgressionPolicyAssessment] | None = None,
    completion_recognition: CourseCompletionRecognitionInput | None = None,
) -> ExclusionRisk:
    """Evaluate faculty-specific progression/readmission indicators.

    The result is an indicator rather than a prediction of a Faculty
    Examinations Committee or Senate decision.  Annual-credit rules require
    either academic-year labels parsed from the transcript or an explicitly
    supplied registration-year context; missing temporal evidence is surfaced
    as unverified rather than silently inferred.
    """
    prog = catalogue.programmes.get(programme_key)
    if not prog:
        return ExclusionRisk(
            at_risk=False,
            reasons=[
                "No verified readmission threshold table is available because no programme rules were identified."
            ],
            assessed=False,
            status="unverified",
            confidence=0.0,
            basis="Programme-specific progression rules are missing.",
        )

    recognised, _ = recognised_credited_pairs(student, catalogue, grading_scheme, course_code_scheme)
    provisional_progression = provisional_open_credit_results(
        student, catalogue, grading_scheme, credit_framework, course_code_scheme
    )
    provisional_by_code = {result.code: result for result in provisional_progression}
    cumulative_credits = sum(_credit_value(fact, credit_framework) for _, fact in recognised) + sum(
        _credit_value(result, credit_framework) for result in provisional_progression
    )
    passed_by_year: dict[int, int] = {}
    attempted_by_year: dict[int, int] = {}
    for result in student.results:
        if result.academic_year is None:
            continue
        fact = catalogue.courses.get(result.code)
        if fact is not None:
            credits = _credit_value(fact, credit_framework)
        elif result.code in provisional_by_code:
            credits = _credit_value(result, credit_framework)
        else:
            continue
        if not result.is_pending(grading_scheme):
            attempted_by_year[result.academic_year] = attempted_by_year.get(result.academic_year, 0) + credits
        if result.is_passed(grading_scheme):
            passed_by_year[result.academic_year] = passed_by_year.get(result.academic_year, 0) + credits

    active_progression_rules = list(prog.progression_rules)
    active_pathway_key = student.pathway_key or catalogue.pathway_key
    active_pathway = prog.pathways.get(active_pathway_key)
    if active_pathway:
        active_progression_rules.extend(active_pathway.progression_rules)

    if active_progression_rules:
        reasons: list[str] = []
        unknown: list[str] = []
        notes: list[str] = []
        conflict_notes: list[str] = []
        years = student.years_registered
        latest_year = max(attempted_by_year or passed_by_year, default=None)

        for raw in active_progression_rules:
            rule_type = str(raw.get("type", "")).strip().lower()
            label = str(raw.get("label", rule_type or "progression rule"))
            rule_year = raw.get("year")
            if rule_year is not None and years is not None and int(rule_year) != years:
                continue
            if rule_year is not None and years is None:
                unknown.append(f"{label}: years registered are required.")
                continue

            if rule_type == "progression_policy":
                policy = _evaluate_progression_policy(
                    raw,
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
                    pathway_key=active_pathway_key,
                    completion_recognition=completion_recognition,
                )
                assessment = _progression_policy_assessment(policy)
                if assessment is not None and progression_policy_assessments is not None:
                    progression_policy_assessments.append(assessment)
                reason, note, unresolved = _progression_policy_messages(policy)
                if reason is not None:
                    reasons.append(reason)
                if note is not None:
                    notes.append(note)
                if unresolved is not None:
                    unknown.append(unresolved)
                if policy.effective_status == "conflict":
                    conflict_notes.append(unresolved or label)
                continue

            if rule_type == "all_of":
                condition = _evaluate_progression_condition(
                    raw,
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
                    pathway_key=active_pathway_key,
                    completion_recognition=completion_recognition,
                )
                reason, note, unresolved = _progression_condition_messages(condition)
                if reason is not None:
                    reasons.append(reason)
                if note is not None:
                    notes.append(note)
                if unresolved is not None:
                    unknown.append(unresolved)
                if condition.outcome == "conflict":
                    conflict_notes.append(unresolved or label)
                continue

            accumulated_spec = _accumulated_progression_metric_spec(raw, label)
            if accumulated_spec is not None:
                accumulated = _evaluate_accumulated_progression_metric(
                    accumulated_spec,
                    student,
                    catalogue,
                    recognised,
                    provisional_progression,
                    latest_year,
                    grading_scheme,
                    credit_framework,
                    course_load_framework,
                )
                reason, note, unresolved = _accumulated_metric_messages(accumulated_spec, accumulated)
                if reason is not None:
                    reasons.append(reason)
                if note is not None:
                    notes.append(note)
                if unresolved is not None:
                    unknown.append(unresolved)

            else:
                failed_spec = _failed_progression_metric_spec(raw, label)
                if failed_spec is not None:
                    if failed_spec.legacy_rule_type == "failed_metric":
                        condition = _evaluate_progression_condition(
                            raw,
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
                            pathway_key=active_pathway_key,
                            completion_recognition=completion_recognition,
                        )
                        reason, note, unresolved = _progression_condition_messages(condition)
                        if reason is not None:
                            reasons.append(reason)
                        if note is not None:
                            notes.append(note)
                        if unresolved is not None:
                            unknown.append(unresolved)
                        if condition.outcome == "conflict":
                            conflict_notes.append(unresolved or label)
                        continue
                    failed_metric = _evaluate_failed_progression_metric(
                        failed_spec,
                        student,
                        latest_year,
                        grading_scheme,
                        course_load_framework,
                        result_context_evidence,
                        programme_key,
                        active_pathway_key,
                    )
                    reason, note, unresolved = _failed_metric_messages(failed_spec, failed_metric)
                    if reason is not None:
                        reasons.append(reason)
                    if note is not None:
                        notes.append(note)
                    if unresolved is not None:
                        unknown.append(unresolved)
                    continue
                ratio_spec = _progression_ratio_spec(raw, label)
                if ratio_spec is not None:
                    ratio = _evaluate_progression_ratio(
                        ratio_spec,
                        student,
                        catalogue,
                        provisional_progression,
                        latest_year,
                        grading_scheme,
                        credit_framework,
                    )
                    reason, note, unresolved = _progression_ratio_messages(ratio_spec, ratio)
                    if reason is not None:
                        reasons.append(reason)
                    if note is not None:
                        notes.append(note)
                    if unresolved is not None:
                        unknown.append(unresolved)
                    continue
                repeated_spec = _repeated_item_failure_spec(raw, label)
                if repeated_spec is not None:
                    repeated = _evaluate_repeated_item_failure(
                        repeated_spec,
                        student,
                        grading_scheme,
                    )
                    reason, note, unresolved = _repeated_item_failure_messages(repeated_spec, repeated)
                    if reason is not None:
                        reasons.append(reason)
                    if note is not None:
                        notes.append(note)
                    if unresolved is not None:
                        unknown.append(unresolved)
                    continue
                stage_repeat_spec = _formal_stage_repeat_spec(raw, label)
                if stage_repeat_spec is not None:
                    condition = _evaluate_progression_condition(
                        raw,
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
                        pathway_key=active_pathway_key,
                        completion_recognition=completion_recognition,
                    )
                    reason, note, unresolved = _progression_condition_messages(condition)
                    if reason is not None:
                        reasons.append(reason)
                    if note is not None:
                        notes.append(note)
                    if unresolved is not None:
                        unknown.append(unresolved)
                    if condition.outcome == "conflict":
                        conflict_notes.append(unresolved or label)
                    continue

            if rule_type == "selected_major_stage_complete":
                stage = str(raw.get("stage", "year1"))
                required_count = int(
                    raw.get(
                        "required",
                        len(_normalise_major_keys(student.declared_majors, catalogue)) or 1,
                    )
                )
                selected = _normalise_major_keys(student.declared_majors, catalogue)
                if not selected:
                    unknown.append(f"{label}: no intended Science major was supplied.")
                else:
                    evaluator = CurriculumEvaluator(
                        student,
                        catalogue,
                        grading_scheme,
                        credit_framework,
                        course_code_scheme,
                        course_load_framework,
                        completion_recognition=completion_recognition,
                    )
                    completed_count = 0
                    for key in selected:
                        major = catalogue.majors.get(key)
                        if major is None or stage not in major.stage_rules:
                            continue
                        rows = evaluator.evaluate_many(major.stage_rules[stage])
                        if rows and all(row.complete for row in rows if row.blocking):
                            completed_count += 1
                    if completed_count < required_count:
                        reasons.append(
                            f"{label}: {completed_count} of {required_count} selected-major stage requirement(s) completed."
                        )
                    else:
                        notes.append(f"{label}: selected-major stage requirements are complete.")

            elif rule_type == "qualification_expected":
                if years is None:
                    unknown.append(f"{label}: years registered are required.")
                else:
                    evaluator = CurriculumEvaluator(
                        student,
                        catalogue,
                        grading_scheme,
                        credit_framework,
                        course_code_scheme,
                        course_load_framework,
                        completion_recognition=completion_recognition,
                    )
                    selected = _normalise_major_keys(student.declared_majors, catalogue)
                    majors_done = [
                        _compute_major_progress(
                            catalogue.majors[key],
                            student,
                            catalogue=catalogue,
                            grading_scheme=grading_scheme,
                            credit_framework=credit_framework,
                            course_code_scheme=course_code_scheme,
                            course_load_framework=course_load_framework,
                            completion_recognition=completion_recognition,
                        ).complete
                        for key in selected
                        if key in catalogue.majors
                    ]
                    if cumulative_credits < prog.total_nqf_credits or not any(majors_done):
                        reasons.append(f"{label}: the degree requirements are not yet complete.")
                    else:
                        notes.append(f"{label}: the recorded requirements appear complete.")

            elif rule_type == "failed_courses_by_group":
                groups = [group for group in raw.get("groups", []) if isinstance(group, dict)]
                if latest_year is None:
                    unknown.append(
                        f"{label}: academic-year labels are required to isolate the latest academic year."
                    )
                else:
                    triggered: list[str] = []
                    for group in groups:
                        group_codes = {
                            str(code).strip().upper()
                            for code in group.get("course_codes", [])
                            if str(code).strip()
                        }
                        threshold = int(group.get("threshold", 2))
                        group_spec = FailedProgressionMetricSpec(
                            metric_basis="course_count",
                            identity="distinct_course",
                            temporal_scope="latest_academic_year",
                            threshold=float(threshold),
                            label=str(group.get("label", "course group")),
                            filters={"course_codes": sorted(group_codes)},
                            legacy_rule_type="failed_courses_by_group",
                        )
                        group_result = _evaluate_failed_progression_metric(
                            group_spec,
                            student,
                            latest_year,
                            grading_scheme,
                            course_load_framework,
                        )
                        if group_result.value >= threshold:
                            triggered.append(
                                f"{group.get('label', 'course group')} ({group_result.value:g} failed: {', '.join(group_result.failed_codes)})"
                            )
                    if triggered:
                        reasons.append(f"{label}: " + "; ".join(triggered) + ".")
                    else:
                        notes.append(f"{label}: no published course-group failure threshold was reached.")

            elif rule_type == "curriculum_stage_complete":
                rules = [item for item in raw.get("rules", []) if isinstance(item, dict)]
                if not rules:
                    unknown.append(f"{label}: no stage rules were supplied.")
                else:
                    evaluations = CurriculumEvaluator(
                        student,
                        catalogue,
                        grading_scheme,
                        credit_framework,
                        course_code_scheme,
                        course_load_framework,
                        completion_recognition=completion_recognition,
                    ).evaluate_many(rules)
                    blocking_rows = [row for row in evaluations if row.blocking]
                    incomplete = [row.label for row in blocking_rows if not row.complete]
                    unresolved = [row.label for row in blocking_rows if row.status != "verified"]
                    if incomplete:
                        reasons.append(
                            f"{label}: outstanding: "
                            + "; ".join(incomplete[:8])
                            + ("…" if len(incomplete) > 8 else "")
                            + "."
                        )
                    elif unresolved:
                        unknown.append(
                            f"{label}: completion depends on unresolved rule(s): "
                            + ", ".join(unresolved[:8])
                            + "."
                        )
                    else:
                        notes.append(f"{label}: the supplied stage requirements are complete.")

            elif rule_type == "repeat_year_failure":
                if latest_year is None:
                    unknown.append(f"{label}: academic-year labels are required to identify a repeat year.")
                else:
                    earlier_codes = {
                        result.code
                        for result in student.results
                        if result.academic_year is not None
                        and result.academic_year < latest_year
                        and not result.is_pending(grading_scheme)
                    }
                    repeated_in_latest = {
                        result.code
                        for result in student.results
                        if result.academic_year == latest_year
                        and result.code in earlier_codes
                        and not result.is_pending(grading_scheme)
                    }
                    failed_latest = sorted(
                        {
                            result.code
                            for result in student.results
                            if result.academic_year == latest_year and result.is_failed(grading_scheme)
                        }
                    )
                    if repeated_in_latest and failed_latest:
                        reasons.append(
                            f"{label}: the latest year includes repeated course(s) ({', '.join(sorted(repeated_in_latest))}) "
                            f"and failed course(s) ({', '.join(failed_latest)})."
                        )
                    else:
                        notes.append(
                            f"{label}: no repeat-year failure pattern is evident from the labelled results."
                        )

            elif rule_type == "maximum_years":
                maximum = int(raw.get("maximum", prog.maximum_registration_years or 0))
                if years is None:
                    unknown.append(f"{label}: years registered are required.")
                elif maximum and years > maximum:
                    reasons.append(
                        f"{label}: {years} years registered exceeds the ordinary {maximum}-year limit."
                    )
                else:
                    notes.append(f"{label}: supplied registration period is within {maximum} years.")

            elif rule_type == "manual":
                unknown.append(str(raw.get("note", label + " requires Faculty confirmation.")))

        if provisional_progression:
            unknown.append(
                "Annual/cumulative totals include transcript-only approved/open elective credits whose programme approval is not verified: "
                + ", ".join(result.code for result in provisional_progression)
                + "."
            )
        assessed = not unknown
        status = "conflict" if conflict_notes else ("verified" if assessed else "unverified")
        basis_parts = []
        if years is not None:
            basis_parts.append(f"{years} explicitly supplied year(s) of registration")
        if latest_year is not None:
            basis_parts.append(f"academic-year-labelled results through {latest_year}")
        if notes:
            basis_parts.extend(notes[:3])
        if unknown:
            basis_parts.append("Unresolved: " + " ".join(unknown[:4]))
        return ExclusionRisk(
            at_risk=bool(reasons),
            reasons=reasons,
            assessed=assessed,
            status=status,
            confidence=0.95 if assessed else 0.35,
            basis="; ".join(basis_parts)
            or "Insufficient temporal evidence for the published progression rules.",
        )

    # Compatibility path for the general Humanities course-equivalent tables.
    if not prog.readmission_thresholds:
        return ExclusionRisk(
            at_risk=False,
            reasons=["No verified readmission threshold table is available for this programme."],
            assessed=False,
            status="unverified",
            confidence=0.0,
            basis="Programme-specific readmission rules are missing.",
        )

    credited = [(result, fact) for result, fact in recognised if fact.counts_towards_course_equivalents]
    passed_count = sum(_load_equivalent(result, course_load_framework) for result, _ in credited)
    senior_passed = sum(
        _load_equivalent(result, course_load_framework)
        for result, fact in credited
        if _is_senior_level(fact, credit_framework)
    )

    if student.years_registered is not None and student.years_registered > 0:
        year = student.years_registered
        status, confidence = "verified", 0.95
        basis = f"Assessed using {year} explicitly supplied year(s) of registration."
    else:
        attempted = len(student.attempted_codes(grading_scheme))
        year = max(1, min(5, (attempted + 7) // 8))
        status, confidence = "provisional", 0.55
        basis = (
            f"Estimated year {year} from {attempted} distinct attempted courses; "
            "the transcript does not prove years of registration."
        )

    applicable = [t for t in prog.readmission_thresholds if t.year <= year]
    threshold = max(applicable, key=lambda t: t.year) if applicable else None
    if threshold is None:
        return ExclusionRisk(False, [], False, "unverified", 0.0, "No threshold applies.")

    reasons: list[str] = []
    if passed_count < threshold.minimum_passed_courses:
        reasons.append(
            f"By the end of year {threshold.year}, the handbook requires at least "
            f"{threshold.minimum_passed_courses} semester-course equivalents passed; "
            f"the record shows {passed_count:.1f}."
        )
    if senior_passed < threshold.minimum_senior_courses:
        reasons.append(
            f"By the end of year {threshold.year}, the handbook requires at least "
            f"{threshold.minimum_senior_courses} senior semester-course equivalents; "
            f"the record shows {senior_passed:.1f}."
        )
    return ExclusionRisk(
        at_risk=bool(reasons),
        reasons=reasons,
        assessed=True,
        status=status,
        confidence=confidence,
        basis=basis,
    )


# ---------------------------------------------------------------------------
# Distinction computation
# ---------------------------------------------------------------------------


def _compute_distinction(
    student: StudentRecord,
    catalogue: Catalogue,
    major_keys: list[str],
    grading_scheme: GradingScheme | None = None,
    credit_framework: AcademicCreditFramework | None = None,
    course_code_scheme: CourseCodeScheme | None = None,
    course_load_framework: CourseLoadFramework | None = None,
    award_course_selections: list[AuthorisedAwardCourseSelection] | None = None,
) -> Distinction:
    """Evaluate the general BA/BSocSc distinction rules in FB1.1-FB1.4.

    Standard Humanities subjects use the four-senior-course rule in FB1.1.
    Economics, Law, Industrial and Organisational Psychology, Psychology and
    Informatics use the subject-specific tests in FB1.2. Science-major
    distinctions remain unverified until the Science handbook is loaded.
    """

    programme = catalogue.programmes.get(student.programme_key or catalogue.programme_key)

    def major_award_policy_id(major: MajorDefinition) -> str:
        ids = [
            str(rule.get("id", "")).strip() for rule in major.award_rules if str(rule.get("id", "")).strip()
        ]
        if len(ids) == 1:
            return ids[0]
        if ids:
            return f"{major.key}:award_rules:{'|'.join(ids)}"
        return f"{major.key}:award_rules"

    def has_applicable_catalogue_qualification_awards() -> bool:
        if programme is None:
            return any(rule.get("type") == "qualification_distinction" for rule in catalogue.award_rules)
        programme_type = str(programme.programme_type).strip()
        for rule in catalogue.award_rules:
            if rule.get("type") != "qualification_distinction":
                continue
            applies_to = str(rule.get("applies_to", "")).strip()
            if not applies_to and major_keys:
                return True
            if programme_type and programme_type in applies_to:
                return True
        return False

    def governed_award_policy_id(
        award: dict[str, Any],
        *,
        owner_kind: str,
        owner_key: str,
    ) -> str:
        explicit = str(award.get("id", "")).strip()
        if explicit:
            return f"{owner_kind}:{owner_key}:{explicit}"
        child_ids = [
            str(rule.get("id", "")).strip()
            for rule in award.get("curriculum_rules", [])
            if isinstance(rule, dict) and str(rule.get("id", "")).strip()
        ]
        if child_ids:
            return f"{owner_kind}:{owner_key}:award:{'|'.join(child_ids)}"
        name_slug = re.sub(
            r"[^a-z0-9]+",
            "_",
            str(award.get("name", "award")).strip().lower(),
        ).strip("_")
        return f"{owner_kind}:{owner_key}:award:{name_slug or 'award'}"

    def evaluate_governed_award(
        award: dict[str, Any],
        *,
        owner_status: str = "verified",
    ) -> tuple[bool, str, float, str, list[str]]:
        evaluator = CurriculumEvaluator(
            student,
            catalogue,
            grading_scheme,
            credit_framework,
            course_code_scheme,
            course_load_framework,
        )
        checks = evaluator.evaluate_many(award.get("curriculum_rules", []))
        complete = all(check.complete for check in checks)
        status = _combine_status(
            [
                owner_status,
                str(award.get("verification_status", award.get("status", "verified"))),
                *[check.status for check in checks],
            ]
        )

        min_time = award.get("complete_within_years")
        duration_detail = ""
        if min_time is not None:
            required_years = (
                programme.minimum_duration_years
                if str(min_time).strip() == "programme_minimum_duration" and programme is not None
                else int(min_time)
            )
            if student.years_registered is None:
                status = _combine_status([status, "unverified"])
                duration_detail = (
                    f" Completion within {required_years} years cannot be verified without years registered."
                )
            elif student.years_registered > required_years:
                complete = False
                duration_detail = (
                    f" The record states {student.years_registered} years registered; "
                    f"the award requires completion within {required_years}."
                )
            else:
                duration_detail = (
                    f" Completion time ({student.years_registered} years) meets the "
                    f"{required_years}-year limit."
                )

        numeric = [check.current for check in checks if check.required and check.current]
        display_average = round(max(numeric), 1) if numeric else 0.0
        detail = "; ".join(check.detail for check in checks) + duration_detail
        used_codes = sorted({code for check in checks for code in check.used_course_codes})
        return complete, status, display_average, detail, used_codes

    def structured_programme_awards() -> list[tuple[dict[str, Any], str, str]]:
        if programme is None:
            return []
        programme_status = "verified" if programme.scope_verified else "unverified"
        awards = [
            (
                award,
                governed_award_policy_id(
                    award,
                    owner_kind="programme",
                    owner_key=programme.key,
                ),
                programme_status,
            )
            for award in programme.award_rules
        ]
        active_pathway = programme.pathways.get(student.pathway_key or catalogue.pathway_key)
        if active_pathway is not None:
            pathway_status = _combine_status([programme_status, active_pathway.verification_status])
            awards.extend(
                (
                    award,
                    governed_award_policy_id(
                        award,
                        owner_kind="pathway",
                        owner_key=f"{programme.key}:{active_pathway.key}",
                    ),
                    pathway_status,
                )
                for award in active_pathway.award_rules
            )
        return awards

    if (
        programme is not None
        and programme.programme_type != "general_degree"
        and not has_applicable_catalogue_qualification_awards()
    ):
        structured_award_rules = structured_programme_awards()
        if not structured_award_rules:
            return Distinction(
                qualification_eligible=False,
                provisional=True,
                subjects=[],
                status="unverified",
                confidence=0.0,
                reason=(
                    "This structured qualification has programme-specific award rules, "
                    "but no machine-checkable award rule set has been verified."
                ),
            )

        award_rows: list[SubjectDistinction] = []
        verified_award = False
        possible_award = False
        overall_status = "verified"
        explanations: list[str] = []
        for award, policy_id, owner_status in structured_award_rules:
            name = str(award.get("name", "Programme award"))
            complete, status, display_average, reason, used_codes = evaluate_governed_award(
                award,
                owner_status=owner_status,
            )
            award_rows.append(
                SubjectDistinction(
                    major=name,
                    average=display_average,
                    senior_courses_assessed=len(used_codes),
                    eligible=complete and status == "verified",
                    status=status,
                    reason=reason,
                    policy_id=policy_id,
                )
            )
            possible_award = possible_award or complete
            verified_award = verified_award or (complete and status == "verified")
            explanations.append(f"{name}: " + ("thresholds met" if complete else "thresholds not met"))
            if status != "verified" and overall_status == "verified":
                overall_status = status

        return Distinction(
            qualification_eligible=verified_award,
            provisional=not verified_award and possible_award or overall_status != "verified",
            subjects=award_rows,
            status="verified" if verified_award else overall_status,
            confidence=0.95 if verified_award else (0.5 if possible_award else 0.8),
            reason="Programme-specific award assessment. " + "; ".join(explanations),
        )

    def marked_result(code: str) -> CourseResult | None:
        result = student.passed_result_for(code, grading_scheme)
        return result if result is not None and result.mark is not None else None

    def first_attempt_pass(code: str) -> bool:
        attempts = [
            result
            for result in student.results
            if result.code == code and not result.is_pending(grading_scheme)
        ]
        return len(attempts) == 1 and attempts[0].is_passed(grading_scheme)

    def weighted_average(codes: list[str]) -> float:
        weighted_total = 0.0
        weight_total = 0.0
        for code in codes:
            result = marked_result(code)
            if result is None:
                continue
            weight = _course_weight(code)
            weighted_total += result.mark * weight
            weight_total += weight
        return weighted_total / weight_total if weight_total else 0.0

    def subject_record(
        major_name: str,
        codes: list[str],
        eligible: bool,
        status: str,
        reason: str,
        *,
        major_key: str = "",
        policy_id: str = "",
    ) -> SubjectDistinction:
        return SubjectDistinction(
            major=major_name,
            average=round(weighted_average(codes), 1),
            senior_courses_assessed=len(codes),
            eligible=eligible,
            status=status,
            reason=reason,
            major_key=major_key,
            policy_id=policy_id,
        )

    def average_for_basis(codes: list[str], basis: str) -> float:
        weighted_total = 0.0
        weight_total = 0.0
        for code in codes:
            result = marked_result(code)
            fact = catalogue.courses.get(code)
            if result is None or fact is None:
                continue
            if basis == "equal":
                weight = 1.0
            elif basis == "credit_value":
                weight = float(_credit_value(fact, credit_framework))
            else:
                weight = _load_equivalent(result, course_load_framework)
            weighted_total += result.mark * weight
            weight_total += weight
        return weighted_total / weight_total if weight_total else 0.0

    selections = award_course_selections or []

    def standard_subject_award(
        rule: dict[str, Any],
        major_def: MajorDefinition,
        progress: MajorProgress,
        senior_codes: list[str],
    ) -> SubjectDistinction:
        rule_status = str(rule.get("verification_status", rule.get("status", "verified")))
        status = _combine_status([major_def.verification_status, rule_status])
        basis = str(
            rule.get("weighting", {}).get("basis", "course_load_equivalent")
            if isinstance(rule.get("weighting", {}), dict)
            else "course_load_equivalent"
        )
        required_load = float(rule.get("required_load_equivalents", 0))
        advanced_level = int(rule.get("advanced_level", 7))
        required_advanced = float(rule.get("required_advanced_load_equivalents", 0))
        minimum_average = float(rule.get("minimum_average", 0))
        advanced_average = float(rule.get("advanced_minimum_average", 0))
        minimum_mark = float(rule.get("minimum_individual_mark", 0))
        first_attempt_only = bool(rule.get("first_attempt_only", False))
        policy_id = str(rule.get("id", ""))
        boundary = (
            rule.get("selection_boundary", {}) if isinstance(rule.get("selection_boundary", {}), dict) else {}
        )
        selection_max = float(boundary.get("maximum", required_load))
        matching_selections = [
            selection
            for selection in selections
            if selection.policy_id == policy_id
            and selection.major_key == major_def.key
            and (
                not selection.catalogue_version or selection.catalogue_version == catalogue.catalogue_version
            )
        ]
        selection_status = "verified"
        selected_codes = list(senior_codes)
        governed_major_pool = set(major_def.required_courses)
        for group in major_def.choice_groups:
            governed_major_pool.update(group.courses)
        if len(matching_selections) > 1:
            return subject_record(
                major_def.name,
                senior_codes,
                False,
                "conflict",
                "Multiple authorised course selections match this award context; manual reconciliation is required.",
                major_key=major_def.key,
                policy_id=policy_id,
            )
        if matching_selections:
            selection = matching_selections[0]
            selected_codes = [code.strip().upper() for code in selection.selected_course_codes]
            selection_status = selection.verification_status
            if len(set(selected_codes)) != len(selected_codes):
                return subject_record(
                    major_def.name,
                    sorted(set(selected_codes)),
                    False,
                    _combine_status([status, selection_status, "unverified"]),
                    "Authorised selection contains duplicate course codes and cannot be used to inflate course-load totals.",
                    major_key=major_def.key,
                    policy_id=policy_id,
                )
            unknown = [code for code in selected_codes if code not in catalogue.courses]
            if unknown:
                return subject_record(
                    major_def.name,
                    selected_codes,
                    False,
                    _combine_status([status, selection_status, "unverified"]),
                    "Authorised selection includes unknown course(s): " + ", ".join(sorted(unknown)) + ".",
                    major_key=major_def.key,
                    policy_id=policy_id,
                )
            selected_outside_pool = [code for code in selected_codes if code not in governed_major_pool]
            if selected_outside_pool:
                return subject_record(
                    major_def.name,
                    selected_codes,
                    False,
                    _combine_status([status, selection_status, "unverified"]),
                    "Authorised selection includes course(s) outside the governed major pool: "
                    + ", ".join(sorted(selected_outside_pool))
                    + ".",
                    major_key=major_def.key,
                    policy_id=policy_id,
                )
            non_senior = [
                code
                for code in selected_codes
                if not (
                    credit_framework.is_senior_level(catalogue.courses[code])
                    if credit_framework is not None
                    else catalogue.courses[code].nqf_level >= 6
                )
            ]
            if non_senior:
                return subject_record(
                    major_def.name,
                    selected_codes,
                    False,
                    _combine_status([status, selection_status, "unverified"]),
                    "Authorised selection includes non-senior course(s): "
                    + ", ".join(sorted(non_senior))
                    + ".",
                    major_key=major_def.key,
                    policy_id=policy_id,
                )
            status = _combine_status([status, selection_status])
        senior_load = sum(
            _load_equivalent(catalogue.courses[code], course_load_framework)
            for code in selected_codes
            if code in catalogue.courses
        )
        advanced_codes = [
            code
            for code in selected_codes
            if (
                credit_framework.is_level(catalogue.courses[code], advanced_level)
                if credit_framework is not None
                else catalogue.courses[code].nqf_level == advanced_level
            )
        ]
        advanced_load = sum(
            _load_equivalent(catalogue.courses[code], course_load_framework)
            for code in advanced_codes
            if code in catalogue.courses
        )
        marked = [marked_result(code) for code in selected_codes]
        marks = [result.mark for result in marked if result is not None and result.mark is not None]
        first_attempt = (not first_attempt_only) or all(first_attempt_pass(code) for code in senior_codes)
        if senior_load > selection_max and not matching_selections:
            boundary_status = str(boundary.get("status", "discretionary"))
            return subject_record(
                major_def.name,
                selected_codes,
                False,
                _combine_status([status, boundary_status]),
                str(
                    boundary.get(
                        "message",
                        "Authorised selection is required before this award can be verified.",
                    )
                ),
                major_key=major_def.key,
                policy_id=policy_id,
            )

        complete = (
            progress.complete
            and senior_load >= required_load
            and advanced_load >= required_advanced
            and len(marks) == len(selected_codes)
            and bool(marks)
            and min(marks) >= minimum_mark
            and average_for_basis(selected_codes, basis) >= minimum_average
            and average_for_basis(advanced_codes, basis) >= advanced_average
            and first_attempt
        )
        reason = (
            f"{rule.get('source', {}).get('rule', rule.get('id', 'Subject award'))} "
            f"requires {required_load:g} senior load equivalents including "
            f"{required_advanced:g} at the advanced level, an overall average of "
            f"at least {minimum_average:g}%, an advanced-level average of at least "
            f"{advanced_average:g}%, no mark below {minimum_mark:g}%, and "
            "first-attempt passes."
        )
        return subject_record(
            major_def.name,
            selected_codes,
            complete and status == "verified",
            status,
            reason,
            major_key=major_def.key,
            policy_id=policy_id,
        )

    def _status_meets_minimum(status: str, minimum: str) -> bool:
        order = {
            "verified": 4,
            "provisional": 3,
            "unverified": 2,
            "discretionary": 1,
            "conflict": 0,
        }
        return order.get(status, 0) >= order.get(minimum, 4)

    def evaluate_award_dependency(rule: dict[str, Any]) -> RuleEvaluation:
        rule_id = str(rule.get("id", rule.get("type", "award_dependency")))
        label = str(rule.get("label", rule.get("name", "Award dependency")))
        source = rule.get("source", {}) if isinstance(rule.get("source", {}), dict) else {}
        status = str(rule.get("verification_status", rule.get("status", "verified")))
        award_scope = str(rule.get("award_scope", "")).strip()
        required_outcome = str(rule.get("required_outcome", "eligible")).strip()
        minimum_count = int(rule.get("minimum_count", 1))
        minimum_status = str(rule.get("minimum_verification_status", "verified")).strip()
        if award_scope != "subject_distinction" or required_outcome != "eligible":
            return RuleEvaluation(
                rule_id,
                label,
                False,
                0.0,
                float(minimum_count),
                "This award dependency shape is not yet supported.",
                _combine_status([status, "unverified"]),
                0.0,
                bool(rule.get("blocking", True)),
                source=source,
            )

        eligible_subjects = [subject for subject in subjects if subject.eligible]
        witnesses = [
            subject for subject in eligible_subjects if _status_meets_minimum(subject.status, minimum_status)
        ]
        selected_witnesses = witnesses[:minimum_count]
        complete = len(witnesses) >= minimum_count
        if complete:
            dependency_status = _combine_status([status, *[subject.status for subject in selected_witnesses]])
            witness_detail = ", ".join(
                sorted(subject.major_key or subject.major for subject in selected_witnesses)
            )
            detail = (
                f"{len(witnesses)} qualifying subject distinction(s) meet the "
                f"{minimum_status} authority requirement. Satisfied by: "
                f"{witness_detail}."
            )
            assumptions = [f"Satisfied by: {witness_detail}."]
        elif eligible_subjects:
            dependency_status = _combine_status([status, *[subject.status for subject in eligible_subjects]])
            detail = (
                "Eligible subject distinction(s) exist, but none meet the required "
                f"{minimum_status} authority level."
            )
            assumptions = [
                "Available subject award status(es): "
                + ", ".join(sorted({subject.status for subject in eligible_subjects}))
                + "."
            ]
        else:
            unresolved_subject_statuses = [
                subject.status for subject in subjects if subject.status != "verified"
            ]
            dependency_status = _combine_status([status, *unresolved_subject_statuses])
            detail = "No qualifying subject distinction has been established."
            assumptions = []

        return RuleEvaluation(
            rule_id,
            label,
            complete,
            float(len(witnesses)),
            float(minimum_count),
            detail,
            dependency_status,
            1.0 if dependency_status == "verified" else 0.0,
            bool(rule.get("blocking", True)),
            assumptions=assumptions,
            source=source,
        )

    def evaluate_qualification_award(rule: dict[str, Any]) -> tuple[bool, str, list[RuleEvaluation]]:
        rule_status = str(rule.get("verification_status", rule.get("status", "verified")))
        evaluator = CurriculumEvaluator(
            student,
            catalogue,
            grading_scheme,
            credit_framework,
            course_code_scheme,
            course_load_framework,
        )
        checks: list[RuleEvaluation] = []
        for child in rule.get("curriculum_rules", []):
            if not isinstance(child, dict):
                continue
            if child.get("type") == "award_dependency":
                checks.append(evaluate_award_dependency(child))
            else:
                checks.append(evaluator.evaluate(child))
        complete = all(check.complete for check in checks if check.blocking)
        status = _combine_status([rule_status, *[check.status for check in checks]])
        min_time = rule.get("complete_within_years")
        if min_time is not None:
            required_years = (
                programme.minimum_duration_years
                if str(min_time).strip() == "programme_minimum_duration" and programme is not None
                else int(min_time)
            )
            duration_id = f"{rule.get('id', 'qualification_distinction')}:duration"
            if student.years_registered is None:
                status = _combine_status([status, "unverified"])
                checks.append(
                    RuleEvaluation(
                        duration_id,
                        "Completion time",
                        True,
                        0.0,
                        float(required_years),
                        (
                            f"Completion within {required_years} years cannot be "
                            "verified without years registered."
                        ),
                        "unverified",
                        0.0,
                        True,
                    )
                )
            elif student.years_registered > required_years:
                complete = False
                checks.append(
                    RuleEvaluation(
                        duration_id,
                        "Completion time",
                        False,
                        float(student.years_registered),
                        float(required_years),
                        (
                            f"The record states {student.years_registered} years "
                            f"registered; the award requires completion within "
                            f"{required_years}."
                        ),
                        "verified",
                        1.0,
                        True,
                    )
                )
            else:
                checks.append(
                    RuleEvaluation(
                        duration_id,
                        "Completion time",
                        True,
                        float(student.years_registered),
                        float(required_years),
                        (
                            f"Completion time ({student.years_registered} years) "
                            f"meets the {required_years}-year limit."
                        ),
                        "verified",
                        1.0,
                        True,
                    )
                )
        return complete, status, checks

    standard_subject_rules = [
        rule
        for rule in catalogue.award_rules
        if rule.get("type") == "subject_selected_set_distinction"
        and rule.get("applies_to") == "standard_faculty_owned_major_without_award_rules"
    ]

    subjects: list[SubjectDistinction] = []
    for key in major_keys:
        major_def = catalogue.majors.get(key)
        if not major_def:
            continue
        progress = _compute_major_progress(major_def, student, catalogue=catalogue)
        used = progress.used_course_codes
        senior_codes = [
            code for code in used if (fact := catalogue.courses.get(code)) is not None and fact.nqf_level >= 6
        ]

        # FB1.2 subject-specific rules.
        if major_def.award_rules:
            evaluator = CurriculumEvaluator(
                student,
                catalogue,
                grading_scheme,
                credit_framework,
                course_code_scheme,
                course_load_framework,
            )
            for award in major_def.award_rules:
                award_rules = (
                    award.get("curriculum_rules", [])
                    if isinstance(award.get("curriculum_rules", []), list)
                    else []
                )
                checks = evaluator.evaluate_many(award_rules) if award_rules else [evaluator.evaluate(award)]
                complete = progress.complete and all(check.complete for check in checks)
                status = _combine_status(
                    [
                        major_def.verification_status,
                        str(award.get("verification_status", award.get("status", "verified"))),
                        *[check.status for check in checks],
                    ]
                )
                display_status = (
                    "unverified"
                    if programme is not None
                    and programme.programme_type != "general_degree"
                    and status == "provisional"
                    else status
                )
                numeric = [check.current for check in checks if check.required and check.current]
                used = sorted({code for check in checks for code in check.used_course_codes})
                subjects.append(
                    SubjectDistinction(
                        major=major_def.name,
                        average=round(max(numeric), 1) if numeric else 0.0,
                        senior_courses_assessed=len(used),
                        eligible=complete and display_status == "verified",
                        status=display_status,
                        reason="; ".join(check.detail for check in checks),
                        major_key=major_def.key,
                        policy_id=str(award.get("id", "")),
                    )
                )
            continue

        if not major_def.faculty_owned:
            subjects.append(
                subject_record(
                    major_def.name,
                    senior_codes,
                    False,
                    "unverified",
                    "The distinction rule is controlled by the major's home faculty and is not yet loaded.",
                    major_key=major_def.key,
                )
            )
            continue

        if standard_subject_rules:
            subjects.append(
                standard_subject_award(
                    standard_subject_rules[0],
                    major_def,
                    progress,
                    senior_codes,
                )
            )
            continue

        if catalogue.award_rules and programme is not None and programme.programme_type != "general_degree":
            subjects.append(
                subject_record(
                    major_def.name,
                    senior_codes,
                    False,
                    "unverified",
                    "No machine-checkable subject distinction rule set is available for this major.",
                    major_key=major_def.key,
                    policy_id=major_award_policy_id(major_def),
                )
            )
            continue

        if major_def.verification_status != "verified":
            subjects.append(
                subject_record(
                    major_def.name,
                    senior_codes,
                    False,
                    "unverified",
                    "The major pathway is provisional, so its distinction cannot be verified.",
                    major_key=major_def.key,
                )
            )
            continue

    qualification_awards = [
        rule for rule in catalogue.award_rules if rule.get("type") == "qualification_distinction"
    ]
    if qualification_awards:
        path_results = [(rule, *evaluate_qualification_award(rule)) for rule in qualification_awards]
        verified_witness = next(
            (result for result in path_results if result[1] and result[2] == "verified"),
            None,
        )
        computational_witness = next(
            (result for result in path_results if result[1]),
            None,
        )
        qualification_eligible = verified_witness is not None
        if verified_witness is not None:
            selected_rule, _, status, checks = verified_witness
            reason = (
                f"{selected_rule.get('name', selected_rule.get('id', 'Qualification path'))}: "
                + "; ".join(check.detail for check in checks)
            )
        elif computational_witness is not None:
            statuses = [path_status for _, _, path_status, _ in path_results]
            status = _combine_status(statuses)
            reason = " ".join(
                f"{rule.get('name', rule.get('id', 'Qualification path'))}: "
                + "; ".join(check.detail for check in checks)
                for rule, _, _, checks in path_results
            )
        else:
            statuses = [path_status for _, _, path_status, _ in path_results]
            status = _combine_status(statuses)
            reason = " ".join(
                f"{rule.get('name', rule.get('id', 'Qualification path'))}: "
                + "; ".join(check.detail for check in checks)
                for rule, _, _, checks in path_results
            )
        confidence = 0.95 if qualification_eligible else (0.65 if status != "verified" else 0.85)
    else:
        qualification_eligible = False
        status = "unverified"
        reason = "No governed qualification-distinction rule is available."
        confidence = 0.0
    return Distinction(
        qualification_eligible=qualification_eligible,
        provisional=status != "verified",
        subjects=subjects,
        status=status,
        confidence=confidence,
        reason=reason,
    )


# ---------------------------------------------------------------------------
# Warnings
# ---------------------------------------------------------------------------


def _compute_warnings(
    student: StudentRecord,
    catalogue: Catalogue,
    major_keys: list[str],
    grading_scheme: GradingScheme | None = None,
    credit_framework: AcademicCreditFramework | None = None,
    course_code_scheme: CourseCodeScheme | None = None,
) -> list[str]:
    """Compatibility entry point using a short-lived evaluation context."""
    return _compute_warnings_with_context(
        EvaluationContext(student, catalogue, grading_scheme, credit_framework, course_code_scheme, None), major_keys
    )


def _compute_warnings_with_context(
    context: EvaluationContext, major_keys: list[str],
) -> list[str]:
    student = context.student
    catalogue = context.catalogue
    grading_scheme = context.grading_scheme
    warnings = []

    # Warn about failed courses
    for result in student.results:
        if result.is_failed(grading_scheme):
            recorded = f"{result.mark}%" if result.mark is not None else (result.grade or "fail")
            warnings.append(
                f"{result.code} ({result.name}): fail result {recorded} — "
                "this attempt counts under the faculty repetition rules."
            )

    # Warn about forbidden major combinations
    for a, b in catalogue.forbidden_combinations:
        if a in major_keys and b in major_keys:
            warnings.append(f"Forbidden major combination: {a} and {b} cannot be taken together.")

    # Warn if declared majors could not be matched.  Previously unmatched
    # names were silently dropped during normalisation, so this loop never ran.
    catalogue_keys_lower = {key.lower() for key in catalogue.majors}
    for declared_name in student.declared_majors:
        direct_key = re.sub(r"_+", "_", declared_name.lower().strip().replace(" ", "_"))
        if (
            direct_key not in catalogue_keys_lower
            and declared_name.lower().strip() not in catalogue_keys_lower
            and not _normalise_major_keys([declared_name], catalogue)
        ):
            warnings.append(
                f"Major '{declared_name}' is not in the course catalogue and could not be matched. "
                "Check spelling or contact your faculty advisor."
            )

    provisional_codes = {
        result.code
        for result in context.provisional_results
    }
    unknown_passes = sorted(
        result.code
        for result in student.credited_results(grading_scheme)
        if result.code not in catalogue.courses and result.code not in provisional_codes
    )
    if unknown_passes:
        warnings.append(
            "The following passed course(s) are outside the selected programme catalogue and "
            "were not counted automatically: " + ", ".join(unknown_passes) + "."
        )

    failed_attempts = _compute_failed_attempts(student, grading_scheme)
    for code, attempts in sorted(failed_attempts.items()):
        if attempts >= 2:
            if catalogue.faculty_key == "uct_humanities":
                message = (
                    f"{code} has {attempts} recorded fail attempts. Humanities rule F5 ordinarily "
                    "prevents a third registration without Senate permission; if it is required, a "
                    "programme change or concession may be necessary."
                )
            elif catalogue.faculty_key == "uct_law":
                message = (
                    f"{code} has {attempts} recorded fail attempts. Law progression and readmission "
                    "rules FP7-FP11 require the full pattern of failed course equivalents and any "
                    "permission to carry courses to be assessed by the Faculty."
                )
            else:
                message = (
                    f"{code} has {attempts} recorded fail attempts. The selected faculty's programme-specific "
                    "progression and readmission rules may restrict further registration."
                )
            warnings.append(message)

    if catalogue.faculty_key == "uct_science":
        warnings.append(
            "Science-major acceptance is confirmed only at second-year registration; completing first-year prerequisites does not itself guarantee a place in a limited major."
        )
        for key in major_keys:
            major = catalogue.majors.get(key)
            if major is not None and major.admission_limited:
                warnings.append(
                    major.admission_note
                    or f"Admission to {major.name} must be confirmed by the relevant department."
                )

    recognised, recognition_exclusions = context.recognition
    if recognition_exclusions:
        warnings.append(
            "Music-course recognition limit applied: "
            + "; ".join(f"{item.code}: {item.reason}" for item in recognition_exclusions)
            + " Final course allocation should be confirmed with Humanities Undergraduate Administration."
        )
    additional_codes = [
        result.code for result, fact in recognised if not fact.counts_towards_course_equivalents
    ]
    if additional_codes and catalogue.faculty_key == "uct_humanities":
        warnings.append(
            "Additional introductory/augmenting course(s) counted toward NQF credits but not toward "
            "the 20 semester subject-course requirement: " + ", ".join(sorted(additional_codes)) + "."
        )

    if catalogue.data_issues:
        warnings.append(
            f"Catalogue validation found {len(catalogue.data_issues)} unresolved data issue(s). "
            "Malformed entries are excluded from positive advice; consult the handbook or faculty office for affected courses."
        )
        attempted = student.attempted_codes(grading_scheme)
        for issue in catalogue.data_issues:
            if any(issue.startswith(code) for code in attempted):
                warnings.append(issue)

    return warnings


# ---------------------------------------------------------------------------
# Failed attempts tracking
# ---------------------------------------------------------------------------


def _compute_failed_attempts(
    student: StudentRecord, grading_scheme: GradingScheme | None = None
) -> dict[str, int]:
    """Count how many times each course was failed."""
    counts: dict[str, int] = {}
    for result in student.results:
        if result.is_failed(grading_scheme):
            counts[result.code] = counts.get(result.code, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Programme key inference
# ---------------------------------------------------------------------------

# Imported from utils


# ---------------------------------------------------------------------------
# Major key normalisation
# ---------------------------------------------------------------------------

# Imported from utils


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def _compute_credits(
    student: StudentRecord,
    catalogue: Catalogue,
    grading_scheme: GradingScheme | None = None,
    credit_framework: AcademicCreditFramework | None = None,
    course_code_scheme: CourseCodeScheme | None = None,
) -> tuple[int, int, list[CourseResult]]:
    """Compatibility entry point using a short-lived evaluation context."""
    return _compute_credits_with_context(
        EvaluationContext(student, catalogue, grading_scheme, credit_framework, course_code_scheme, None)
    )


def _compute_credits_with_context(
    context: EvaluationContext,
) -> tuple[int, int, list[CourseResult]]:
    """Count verified catalogue credits plus explicitly permitted provisional electives.

    Catalogue values outrank transcript-extracted fields for known courses.
    Transcript-only credits are considered only where the active programme has
    an ``approved_credit_pool`` rule (for example, an open elective or a live
    complementary-studies list). Those credits remain provisional and therefore
    cannot support a fully verified graduation conclusion.
    """
    credit_framework = context.credit_framework
    recognised, _ = context.recognition
    provisional = list(context.provisional_results)
    credits_completed = sum(_credit_value(fact, credit_framework) for _, fact in recognised) + sum(
        _credit_value(result, credit_framework) for result in provisional
    )
    level_7_credits = sum(
        _credit_value(fact, credit_framework)
        for _, fact in recognised
        if (credit_framework.is_level(fact, 7) if credit_framework is not None else fact.nqf_level == 7)
    ) + sum(
        _credit_value(result, credit_framework)
        for result in provisional
        if (credit_framework.is_level(result, 7) if credit_framework is not None else result.nqf_level == 7)
    )
    return credits_completed, level_7_credits, provisional


def _compute_course_equivalents(
    student: StudentRecord,
    catalogue: Catalogue,
    grading_scheme: GradingScheme | None = None,
    credit_framework: AcademicCreditFramework | None = None,
    course_code_scheme: CourseCodeScheme | None = None,
    course_load_framework: CourseLoadFramework | None = None,
) -> tuple[float, float, float]:
    """Compatibility entry point using a short-lived evaluation context."""
    return _compute_course_equivalents_with_context(
        EvaluationContext(student, catalogue, grading_scheme, credit_framework, course_code_scheme, course_load_framework)
    )


def _compute_course_equivalents_with_context(
    context: EvaluationContext,
) -> tuple[float, float, float]:
    credit_framework = context.credit_framework
    course_load_framework = context.course_load_framework
    recognised, _ = context.recognition
    credited = [(result, fact) for result, fact in recognised if fact.counts_towards_course_equivalents]
    sce_total = sum(_load_equivalent(result, course_load_framework) for result, _ in credited)
    senior_sce = sum(
        _load_equivalent(result, course_load_framework)
        for result, fact in credited
        if _is_senior_level(fact, credit_framework)
    )
    humanities_sce = sum(
        _load_equivalent(result, course_load_framework)
        for result, fact in credited
        if fact.counts_as_humanities
    )
    return sce_total, senior_sce, humanities_sce


def _compute_all_major_progresses(
    student: StudentRecord,
    catalogue: Catalogue,
    major_keys: list[str],
    grading_scheme: GradingScheme | None = None,
    credit_framework: AcademicCreditFramework | None = None,
    course_code_scheme: CourseCodeScheme | None = None,
    course_load_framework: CourseLoadFramework | None = None,
    completion_recognition: CourseCompletionRecognitionInput | None = None,
) -> tuple[list[MajorProgress], int, int]:
    major_progresses = []
    base_graph = None
    for key in major_keys:
        major_def = catalogue.majors.get(key)
        if major_def:
            if base_graph is None:
                base_graph = build_credit_reasoning_graph(student, grading_scheme, credit_framework)
            major_progresses.append(
                _compute_major_progress(
                    major_def,
                    student,
                    base_graph,
                    catalogue,
                    grading_scheme,
                    credit_framework,
                    course_code_scheme,
                    course_load_framework,
                    completion_recognition=completion_recognition,
                )
            )

    majors_complete = sum(1 for m in major_progresses if m.complete)
    humanities_majors_complete = sum(
        1
        for m in major_progresses
        if m.complete and catalogue.majors.get(m.key) and catalogue.majors[m.key].faculty_owned
    )
    return major_progresses, majors_complete, humanities_majors_complete


def _check_forbidden_combinations(catalogue: Catalogue, major_keys: list[str]) -> bool:
    for a, b in catalogue.forbidden_combinations:
        if a in major_keys and b in major_keys:
            return False
    return True


def _evaluate_qualification_completion(
    student: StudentRecord,
    catalogue: Catalogue,
    programme_key: str,
    prog,
    grading_scheme: GradingScheme | None,
    credit_framework: AcademicCreditFramework | None,
    course_code_scheme: CourseCodeScheme | None,
    course_load_framework: CourseLoadFramework | None,
    completion_recognition: CourseCompletionRecognitionInput | None,
    academic_record_coverage_evidence: list[AcademicRecordCoverageEvidence] | None = None,
    requirement_recognition_evidence: list[RequirementRecognitionEvidence] | None = None,
    requirement_recognition_coverage: list[RequirementRecognitionCoverage] | None = None,
) -> QualificationCompletionAssessment | None:
    raw = prog.qualification_completion if prog else {}
    if not raw:
        return None
    ids = tuple(str(value).strip() for value in raw.get("required_requirement_ids", ()) if str(value).strip())
    rules = {str(rule.get("id", rule.get("label", ""))).strip(): rule for rule in prog.curriculum_rules}
    selected = [rules[rule_id] for rule_id in ids if rule_id in rules]
    if len(selected) != len(ids):
        return QualificationCompletionAssessment(
            programme_key,
            "unsupported",
            False,
            "unverified",
            ids,
            detail="The completion policy references a missing governed curriculum requirement.",
        )
    evaluator = CurriculumEvaluator(
        student,
        catalogue,
        grading_scheme,
        credit_framework,
        course_code_scheme,
        course_load_framework,
        completion_recognition=completion_recognition,
        academic_record_coverage_evidence=academic_record_coverage_evidence,
        requirement_recognition_evidence=requirement_recognition_evidence,
        requirement_recognition_coverage=requirement_recognition_coverage,
        institution_id=getattr(grading_scheme, "institution_id", student.faculty_key),
    )
    rows = evaluator.evaluate_many(selected)
    incomplete = tuple(row.id for row in rows if row.outcome == "not_satisfied")
    unresolved = tuple(row.id for row in rows if row.outcome in {"unresolved", "conflict", "unsupported"})
    policy_status = str(raw.get("verification_status", "unverified"))
    status = _combine_status([policy_status, *(row.status for row in rows)] or ["unverified"])
    if any(row.status == "conflict" for row in rows):
        outcome = "conflict"
    elif incomplete:
        outcome = "not_satisfied"
    elif unresolved:
        outcome = "unresolved"
    else:
        outcome = "satisfied"
    return QualificationCompletionAssessment(
        programme_key,
        outcome,
        not unresolved and status == "verified",
        status,
        ids,
        incomplete,
        unresolved,
        str(raw.get("source_reference", "")),
        "All governed academic completion requirements are satisfied."
        if outcome == "satisfied"
        else "Academic completion requires the listed governed requirements to be satisfied.",
    )


def _build_requirements(
    student: StudentRecord,
    catalogue: Catalogue,
    programme_key: str,
    prog,
    sce_total: float,
    senior_sce: float,
    humanities_sce: float,
    credits_completed: int,
    level_7_credits: int,
    provisional_credit_results: list[CourseResult],
    major_progresses: list[MajorProgress],
    majors_complete: int,
    humanities_majors_complete: int,
    forbidden_ok: bool,
    grading_scheme: GradingScheme | None = None,
    credit_framework: AcademicCreditFramework | None = None,
    course_code_scheme: CourseCodeScheme | None = None,
    course_load_framework: CourseLoadFramework | None = None,
    completion_recognition: CourseCompletionRecognitionInput | None = None,
    academic_record_coverage_evidence: list[AcademicRecordCoverageEvidence] | None = None,
    requirement_recognition_evidence: list[RequirementRecognitionEvidence] | None = None,
    requirement_recognition_coverage: list[RequirementRecognitionCoverage] | None = None,
) -> list[Requirement]:
    """Build handbook-grounded graduation requirements."""
    min_years = prog.minimum_duration_years if prog else 3
    total_nqf_credits = prog.total_nqf_credits if prog else 360
    level_7_nqf_credits = prog.level_7_nqf_credits if prog else 120
    semester_course_equivalents = prog.semester_course_equivalents if prog else 20
    senior_course_equivalents = prog.senior_course_equivalents if prog else 10
    humanities_course_equivalents = prog.humanities_course_equivalents if prog else 0
    required_majors = prog.required_majors if prog else 0
    required_humanities_majors = prog.required_humanities_majors if prog else 0

    if not prog:
        programme_status, programme_confidence = "unverified", 0.0
        programme_assumptions = ["No matching programme rule set was found."]
    elif catalogue.scope_status != "verified":
        programme_status, programme_confidence = "unverified", 0.5
        programme_assumptions = ["The selected programme scope contains unresolved catalogue references."]
    else:
        programme_status, programme_confidence = "verified", 1.0
        programme_assumptions = []

    if student.years_registered is None:
        duration_complete = True
        duration_current = 0.0
        duration_status = "unverified"
        duration_detail = (
            "The transcript does not state years of registration; duration requires confirmation."
        )
    else:
        duration_complete = student.years_registered >= min_years
        duration_current = float(student.years_registered)
        duration_status = "verified"
        duration_detail = f"{student.years_registered} year(s) registered; minimum duration is {min_years}."

    requirements: list[Requirement] = [
        Requirement(
            id="duration",
            label=f"Minimum {min_years} years of study",
            complete=duration_complete,
            current=duration_current,
            required=float(min_years),
            detail=duration_detail,
            status=duration_status,
            confidence=1.0 if duration_status == "verified" else 0.0,
        ),
    ]
    if prog and prog.maximum_registration_years:
        if student.years_registered is None:
            max_complete = True
            max_current = 0.0
            max_status = "unverified"
            max_detail = (
                f"The transcript does not establish years of registration. The ordinary maximum is "
                f"{prog.maximum_registration_years} years; continuation beyond it requires Senate permission."
            )
        else:
            max_complete = student.years_registered <= prog.maximum_registration_years
            max_current = float(student.years_registered)
            max_status = "verified" if max_complete else "discretionary"
            max_detail = (
                f"{student.years_registered} year(s) registered; the ordinary maximum is "
                f"{prog.maximum_registration_years}."
                + (" Senate permission may be required to continue." if not max_complete else "")
            )
        requirements.append(
            Requirement(
                id="maximum_registration",
                label="Maximum registration period",
                complete=max_complete,
                current=max_current,
                required=float(prog.maximum_registration_years),
                detail=max_detail,
                status=max_status,
                confidence=1.0 if student.years_registered is not None else 0.0,
                blocking=False,
            )
        )
    if semester_course_equivalents:
        requirements.append(
            Requirement(
                id="courses",
                label="Semester course equivalents",
                complete=sce_total >= semester_course_equivalents,
                current=sce_total,
                required=float(semester_course_equivalents),
                detail=f"{sce_total:.1f} of {semester_course_equivalents} required semester-course equivalents passed",
                status=programme_status,
                confidence=programme_confidence,
            )
        )
    if senior_course_equivalents:
        requirements.append(
            Requirement(
                id="senior",
                label="Senior semester courses",
                complete=senior_sce >= senior_course_equivalents,
                current=senior_sce,
                required=float(senior_course_equivalents),
                detail=f"{senior_sce:.1f} of {senior_course_equivalents} required senior courses passed",
                status=programme_status,
                confidence=programme_confidence,
            )
        )

    if humanities_course_equivalents:
        requirements.append(
            Requirement(
                id="humanities",
                label="Humanities semester courses",
                complete=humanities_sce >= humanities_course_equivalents,
                current=humanities_sce,
                required=float(humanities_course_equivalents),
                detail=f"{humanities_sce:.1f} of {humanities_course_equivalents} required Humanities courses passed",
                status=programme_status,
                confidence=programme_confidence,
            )
        )

    credit_assumptions = list(programme_assumptions)
    if provisional_credit_results:
        credit_assumptions.append(
            "Includes transcript-only credits provisionally allocated to a published approved/open elective pool; faculty approval is not verified."
        )
    total_credits_graph = build_total_nqf_credits_graph(
        student=student,
        required_credits=total_nqf_credits,
        programme_key=programme_key,
        programme_name=prog.name if prog else programme_key,
        assumptions=credit_assumptions,
        catalogue=catalogue,
        provisional_results=provisional_credit_results,
        grading_scheme=grading_scheme,
        credit_framework=credit_framework,
        course_code_scheme=course_code_scheme,
    )
    credit_conclusion = total_credits_graph.conclusions[f"{programme_key.upper()}_TOTAL_NQF_CREDITS"]
    requirements.extend(
        [
            Requirement(
                id="credits",
                label="NQF credits",
                complete=credits_completed >= total_nqf_credits,
                current=float(credits_completed),
                required=float(total_nqf_credits),
                detail=(
                    f"{credits_completed} of {total_nqf_credits} NQF credits completed"
                    + (
                        "; includes provisional approved/open elective credit(s): "
                        + ", ".join(result.code for result in provisional_credit_results)
                        if provisional_credit_results
                        else ""
                    )
                ),
                evidence=credit_conclusion.evidence,
                applied_rules=credit_conclusion.applied_rules,
                explanation=credit_conclusion.explanation,
                status="unverified" if provisional_credit_results else programme_status,
                confidence=0.35 if provisional_credit_results else programme_confidence,
                assumptions=credit_assumptions,
                depends_on=credit_conclusion.depends_on,
            ),
        ]
    )
    if level_7_nqf_credits:
        requirements.append(
            Requirement(
                id="level7",
                label="NQF Level 7 credits",
                complete=level_7_credits >= level_7_nqf_credits,
                current=float(level_7_credits),
                required=float(level_7_nqf_credits),
                detail=f"{level_7_credits} of {level_7_nqf_credits} NQF Level 7 credits completed",
                status=programme_status,
                confidence=programme_confidence,
            )
        )
    if required_majors:
        requirements.append(
            Requirement(
                id="majors",
                label="Completed majors",
                complete=majors_complete >= required_majors,
                current=float(majors_complete),
                required=float(required_majors),
                detail=f"{majors_complete} of {required_majors} majors completed",
                status=(
                    "unverified"
                    if any(m.status != "verified" for m in major_progresses)
                    else programme_status
                ),
                confidence=(
                    0.4 if any(m.status != "verified" for m in major_progresses) else programme_confidence
                ),
            )
        )

    # Some Science majors are valid only when paired with Computer Science.
    if catalogue.faculty_key == "uct_science":
        selected_major_keys = set(_normalise_major_keys(student.declared_majors, catalogue))
        for key in sorted(selected_major_keys):
            major = catalogue.majors.get(key)
            if major is None or not major.required_co_majors:
                continue
            missing = [
                required for required in major.required_co_majors if required not in selected_major_keys
            ]
            requirements.append(
                Requirement(
                    id=f"major_co_requirement:{key}",
                    label=f"Required co-major for {major.name}",
                    complete=not missing,
                    current=float(len(major.required_co_majors) - len(missing)),
                    required=float(len(major.required_co_majors)),
                    detail=(
                        f"{major.name} must be taken with "
                        + ", ".join(
                            catalogue.majors[m].name if m in catalogue.majors else m
                            for m in major.required_co_majors
                        )
                        + "."
                        + ((" Missing: " + ", ".join(missing) + ".") if missing else "")
                    ),
                    status="verified",
                    confidence=1.0,
                )
            )

    if required_humanities_majors:
        requirements.append(
            Requirement(
                id="humanities_major",
                label="At least one Humanities major",
                complete=humanities_majors_complete >= required_humanities_majors,
                current=float(humanities_majors_complete),
                required=float(required_humanities_majors),
                detail="At least one major must be offered by a department established in Humanities, including Economics.",
                status=programme_status,
                confidence=programme_confidence,
            )
        )

    # BA/BSocSc identity follows the category of the Humanities major(s).
    declared_keys = _normalise_major_keys(student.declared_majors, catalogue)
    faculty_categories = {
        catalogue.majors[key].qualification
        for key in declared_keys
        if key in catalogue.majors and catalogue.majors[key].faculty_owned
    }
    degree_match = bool(faculty_categories)
    if prog and prog.degree_category == "BA" and faculty_categories == {"BSocSc"}:
        degree_match = False
    if prog and prog.degree_category == "BSocSc" and faculty_categories == {"BA"}:
        degree_match = False
    if prog and prog.required_majors > 0 and prog.degree_category in {"BA", "BSocSc"}:
        requirements.append(
            Requirement(
                id="degree_major_identity",
                label="Majors match the selected degree title",
                complete=degree_match,
                current=1.0 if degree_match else 0.0,
                required=1.0,
                detail=(
                    "Mixed BA and BSocSc Humanities majors may lead to either degree title."
                    if degree_match
                    else "The selected degree title does not match the category of the declared Humanities major(s), or no Humanities major was identified."
                ),
                status=programme_status,
                confidence=programme_confidence,
            )
        )

    if prog:
        evaluator = CurriculumEvaluator(
            student,
            catalogue,
            grading_scheme,
            credit_framework,
            course_code_scheme,
            course_load_framework,
            completion_recognition,
            academic_record_coverage_evidence=academic_record_coverage_evidence,
            requirement_recognition_evidence=requirement_recognition_evidence,
            requirement_recognition_coverage=requirement_recognition_coverage,
        )
        completion = evaluator.completion
        passed = completion.completed_codes()
        for code in prog.required_courses:
            requirements.append(
                Requirement(
                    id=f"programme_course:{code}",
                    label=f"Required programme course: {code}",
                    complete=code in passed,
                    current=1.0 if code in passed else 0.0,
                    required=1.0,
                    detail=f"{code} is compulsory for {prog.name}. " + completion.resolve(code).detail,
                    status=_combine_status([programme_status, completion.resolve(code).status]),
                    confidence=programme_confidence,
                )
            )
        if prog.introductory_courses_required:
            intro = evaluator.evaluate(
                {
                    "type": "choose_n",
                    "course_codes": prog.introductory_course_options,
                    "required": prog.introductory_courses_required,
                }
            )
            intro_done = int(intro.current)
            requirements.append(
                Requirement(
                    id="extended_introductory",
                    label="Extended-programme introductory courses",
                    complete=intro_done >= prog.introductory_courses_required,
                    current=float(intro_done),
                    required=float(prog.introductory_courses_required),
                    detail=f"Complete {prog.introductory_courses_required} from {prog.introductory_course_options}.",
                    status=_combine_status([programme_status, intro.status]),
                    confidence=programme_confidence,
                )
            )
        if prog.augmenting_courses_required:
            augmenting = evaluator.evaluate(
                {
                    "type": "choose_n",
                    "course_codes": [code for code, fact in catalogue.courses.items() if fact.augmenting],
                    "required": prog.augmenting_courses_required,
                }
            )
            augmenting_done = int(augmenting.current)
            requirements.append(
                Requirement(
                    id="extended_augmenting",
                    label="Extended-programme augmenting courses",
                    complete=augmenting_done >= prog.augmenting_courses_required,
                    current=float(augmenting_done),
                    required=float(prog.augmenting_courses_required),
                    detail=f"At least {prog.augmenting_courses_required} augmenting courses are required.",
                    status=_combine_status([programme_status, augmenting.status]),
                    confidence=programme_confidence,
                )
            )

        structured_rules = list(prog.curriculum_rules)
        pathway = prog.pathways.get(student.pathway_key or catalogue.pathway_key)
        if pathway:
            structured_rules.extend(pathway.curriculum_rules)
        for evaluated in evaluator.evaluate_many(structured_rules):
            requirements.append(
                Requirement(
                    id=f"curriculum:{evaluated.id}",
                    outcome=evaluated.outcome,
                    assessment_complete=evaluated.assessment_complete,
                    used_course_codes=evaluated.used_course_codes,
                    label=evaluated.label,
                    complete=evaluated.complete,
                    current=evaluated.current,
                    required=evaluated.required,
                    detail=evaluated.detail,
                    status=evaluated.status,
                    confidence=evaluated.confidence,
                    assumptions=evaluated.assumptions,
                    blocking=evaluated.blocking,
                )
            )

        # Four-year and professional qualifications may prescribe credits at
        # NQF levels other than level 7. These requirements are independent of
        # the legacy level-7 field retained for general degrees.
        for level, required_credits in sorted(prog.level_credit_requirements.items()):
            current = evaluator.credits_by_level.get(level, 0)
            if level == 7 and level_7_nqf_credits == required_credits:
                continue
            requirements.append(
                Requirement(
                    id=f"level{level}",
                    label=f"NQF Level {level} credits",
                    complete=current >= required_credits,
                    current=float(current),
                    required=float(required_credits),
                    detail=f"{current} of {required_credits} NQF Level {level} credits completed",
                    status=programme_status,
                    confidence=programme_confidence,
                )
            )

        if prog.availability != "open":
            requirements.append(
                Requirement(
                    id="programme_availability",
                    label="Programme intake status",
                    complete=True,
                    current=1.0,
                    required=1.0,
                    detail=prog.availability_note or f"Programme status: {prog.availability}.",
                    status=("unverified" if prog.availability == "continuing_only" else "discretionary"),
                    confidence=1.0,
                    blocking=False,
                )
            )

    # The same senior course may not be recognised as part of two majors.
    usage: dict[str, list[str]] = {}
    for major in major_progresses:
        for code in major.used_course_codes:
            fact = catalogue.courses.get(code)
            if fact is not None and _is_senior_level(fact, credit_framework):
                usage.setdefault(code, []).append(major.name)
    overlaps = {code: names for code, names in usage.items() if len(names) > 1}
    if catalogue.faculty_key == "uct_science":
        overlap_credits = sum(
            catalogue.courses[code].nqf_credits
            for code in overlaps
            if code in catalogue.courses and catalogue.courses[code].nqf_level == 7
        )
        selected_count = len(_normalise_major_keys(student.declared_majors, catalogue))
        if not overlaps:
            overlap_complete, overlap_status = True, "verified"
            overlap_detail = "No level-7 course overlap was detected between selected Science majors."
        elif overlap_credits <= 36:
            overlap_complete, overlap_status = True, "discretionary"
            overlap_detail = (
                f"{overlap_credits} level-7 credits overlap between majors. FB7.7 permits up to 36 shared credits only with Deputy Dean approval: "
                + "; ".join(f"{code} ({', '.join(names)})" for code, names in overlaps.items())
            )
        elif selected_count >= 3 and level_7_credits >= 180:
            overlap_complete, overlap_status = True, "discretionary"
            overlap_detail = f"{overlap_credits} level-7 credits overlap. A three-major allocation may be approved where at least 180 level-7 credits are completed; Deputy Dean approval is required."
        else:
            overlap_complete, overlap_status = False, "verified"
            overlap_detail = f"{overlap_credits} overlapping level-7 credits exceed the ordinary 36-credit shared-major allowance."
        requirements.append(
            Requirement(
                id="major_course_allocation",
                label="Distinct level-7 credits across Science majors",
                complete=overlap_complete,
                current=float(overlap_credits),
                required=36.0,
                detail=overlap_detail,
                status=overlap_status,
                confidence=1.0 if overlap_status == "verified" else 0.0,
            )
        )
        requirements.append(
            Requirement(
                id="major_combination",
                label="Valid Science major combination",
                complete=forbidden_ok,
                current=1.0 if forbidden_ok else 0.0,
                required=1.0,
                detail=(
                    ""
                    if forbidden_ok
                    else "Applied Statistics, Mathematical Statistics, and Statistics & Data Science may not be combined with one another."
                ),
                status="verified",
                confidence=1.0,
            )
        )
    elif prog is None or prog.programme_type == "general_degree":
        requirements.append(
            Requirement(
                id="major_course_allocation",
                label="No senior course double-counted across majors",
                complete=True,
                current=0.0 if overlaps else 1.0,
                required=1.0,
                detail=(
                    "Manual allocation is required for: "
                    + "; ".join(f"{code} ({', '.join(names)})" for code, names in overlaps.items())
                    if overlaps
                    else "No senior-course overlap was detected in the courses allocated by the engine."
                ),
                status="unverified" if overlaps else "verified",
                confidence=0.4 if overlaps else 1.0,
            )
        )
        requirements.append(
            Requirement(
                id="major_combination",
                label="Valid major combination",
                complete=forbidden_ok,
                current=1.0 if forbidden_ok else 0.0,
                required=1.0,
                detail=(
                    "" if forbidden_ok else "The selected majors are a forbidden combination under FB3(e)."
                ),
                status="verified",
                confidence=1.0,
            )
        )
    requirements.append(
        Requirement(
            id="qualification_match",
            label="Programme rules identified",
            complete=prog is not None,
            current=1.0 if prog else 0.0,
            required=1.0,
            detail=(f"Using {prog.name}." if prog else f"No rule set matched {student.programme!r}."),
            status=programme_status,
            confidence=programme_confidence,
        )
    )
    return requirements


def compute_report(
    student: StudentRecord,
    catalogue: Catalogue,
    grading_scheme: GradingScheme | None = None,
    credit_framework: AcademicCreditFramework | None = None,
    course_code_scheme: CourseCodeScheme | None = None,
    course_load_framework: CourseLoadFramework | None = None,
    award_course_selections: list[AuthorisedAwardCourseSelection] | None = None,
    stage_repeat_evidence: list[StageRepeatEvidence] | None = None,
    result_context_evidence: list[ResultContextEvidence] | None = None,
    academic_record_coverage_evidence: list[AcademicRecordCoverageEvidence] | None = None,
    completion_recognition: CourseCompletionRecognitionInput | None = None,
    academic_period_scheme: AcademicPeriodScheme | None = None,
    registration_history: tuple[RegistrationHistoryEvidence, ...] | None = None,
    registration_history_coverage: tuple[RegistrationHistoryCoverage, ...] | None = None,
    graduation_clearance_evidence: tuple[GraduationClearanceEvidence, ...] | None = None,
    qualification_award_evidence: tuple[QualificationAwardEvidence, ...] | None = None,
    achievement_scheme=None,
    course_attempt_coverage_evidence: tuple[CourseAttemptCoverageEvidence, ...] | None = None,
    external_qualification_systems=(),
    requirement_recognition_evidence: tuple[RequirementRecognitionEvidence, ...] | None = None,
    requirement_recognition_coverage: tuple[RequirementRecognitionCoverage, ...] | None = None,
    external_subject_achievement_evidence: tuple[ExternalSubjectAchievementEvidence, ...] | None = None,
    external_subject_achievement_coverage: tuple[ExternalSubjectAchievementCoverage, ...] | None = None,
    prior_qualification_evidence: tuple[PriorQualificationEvidence, ...] | None = None,
    prior_qualification_coverage: tuple[PriorQualificationCoverage, ...] | None = None,
) -> Report:
    """
    Compute the full graduation report from raw facts.
    This is the only place where conclusions are drawn.
    """
    programme_key = student.programme_key or _infer_programme_key(student.programme)
    if academic_period_scheme is not None:
        for result in student.results:
            if result.academic_period_key:
                academic_period_scheme.validate(result.academic_period_key)
        context_evidence = [*(stage_repeat_evidence or ()), *(result_context_evidence or ())]
        for evidence in context_evidence:
            if evidence.registration_period_key:
                academic_period_scheme.validate(evidence.registration_period_key)
        for entry in registration_history or ():
            entry.validate(academic_period_scheme)
        for item in registration_history_coverage or ():
            item.validate(academic_period_scheme)
    prog = catalogue.programmes.get(programme_key)

    major_keys = _normalise_major_keys(student.declared_majors, catalogue)

    context = EvaluationContext(
        student, catalogue, grading_scheme, credit_framework,
        course_code_scheme, course_load_framework,
    )
    credits_completed, level_7_credits, provisional_credit_results = _compute_credits_with_context(context)
    sce_total, senior_sce, humanities_sce = _compute_course_equivalents_with_context(context)
    major_progresses, majors_complete, humanities_majors_complete = _compute_all_major_progresses(
        student,
        catalogue,
        major_keys,
        grading_scheme,
        credit_framework,
        course_code_scheme,
        course_load_framework,
        completion_recognition=completion_recognition,
    )
    forbidden_ok = _check_forbidden_combinations(catalogue, major_keys)

    requirements = _build_requirements(
        student,
        catalogue,
        programme_key,
        prog,
        sce_total,
        senior_sce,
        humanities_sce,
        credits_completed,
        level_7_credits,
        provisional_credit_results,
        major_progresses,
        majors_complete,
        humanities_majors_complete,
        forbidden_ok,
        grading_scheme,
        credit_framework,
        course_code_scheme,
        course_load_framework,
        completion_recognition=completion_recognition,
        academic_record_coverage_evidence=academic_record_coverage_evidence,
        requirement_recognition_evidence=list(requirement_recognition_evidence or ()),
        requirement_recognition_coverage=list(requirement_recognition_coverage or ()),
    )
    qualification_completion = _evaluate_qualification_completion(
        student,
        catalogue,
        programme_key,
        prog,
        grading_scheme,
        credit_framework,
        course_code_scheme,
        course_load_framework,
        completion_recognition,
        academic_record_coverage_evidence,
        list(requirement_recognition_evidence or ()),
        list(requirement_recognition_coverage or ()),
    )
    graduation_eligibility_assessment = evaluate_graduation_eligibility(
        student=student,
        institution_id=getattr(grading_scheme, "institution_id", student.faculty_key),
        release_id=catalogue.catalogue_version,
        programme_key=programme_key,
        spec=getattr(prog, "graduation_eligibility", {}) if prog else {},
        academic_completion=qualification_completion or type("Completion", (), {"outcome": "unsupported", "status": "unverified"})(),
        clearances=graduation_clearance_evidence or (),
    )
    qualification_award_assessment = assess_qualification_award(
        student=student,
        institution_id=getattr(grading_scheme, "institution_id", student.faculty_key),
        release_id=catalogue.catalogue_version,
        qualification_key=programme_key,
        evidence=qualification_award_evidence or (),
    )

    blocking_requirements = [r for r in requirements if r.blocking]
    if any(not r.complete for r in blocking_requirements):
        graduation_status = "not_eligible"
    elif any(r.status != "verified" for r in blocking_requirements):
        graduation_status = "requires_verification"
    else:
        graduation_status = "eligible"
    graduation_eligible = graduation_status == "eligible"

    entry_assessment = evaluate_programme_entry(
        catalogue, programme_key, catalogue.pathway_key,
        AcademicConditionEvaluator(
            student, catalogue, grading_scheme, credit_framework,
            course_code_scheme, course_load_framework,
            academic_record_coverage_evidence=academic_record_coverage_evidence,
            completion_recognition=completion_recognition,
            achievement_scheme=achievement_scheme,
            course_attempt_coverage_evidence=course_attempt_coverage_evidence,
            external_qualification_systems=external_qualification_systems,
            external_subject_achievement_evidence=external_subject_achievement_evidence,
            external_subject_achievement_coverage=external_subject_achievement_coverage,
            prior_qualification_evidence=prior_qualification_evidence,
            prior_qualification_coverage=prior_qualification_coverage,
        ),
    )
    eligible_courses = _compute_eligible_courses(
        student,
        catalogue,
        grading_scheme,
        credit_framework,
        course_code_scheme,
        course_load_framework,
        academic_record_coverage_evidence,
        completion_recognition=completion_recognition,
        achievement_scheme=achievement_scheme,
        course_attempt_coverage_evidence=list(course_attempt_coverage_evidence or ()),
        external_qualification_systems=external_qualification_systems,
        external_subject_achievement_evidence=list(external_subject_achievement_evidence or ()),
        external_subject_achievement_coverage=list(external_subject_achievement_coverage or ()),
        prior_qualification_evidence=list(prior_qualification_evidence or ()),
        prior_qualification_coverage=list(prior_qualification_coverage or ()),
    )
    progression_policy_assessments: list[ProgressionPolicyAssessment] = []
    exclusion_risk = _compute_exclusion_risk(
        student,
        catalogue,
        programme_key,
        grading_scheme,
        credit_framework,
        course_code_scheme,
        course_load_framework,
        stage_repeat_evidence,
        result_context_evidence,
        academic_record_coverage_evidence,
        progression_policy_assessments,
        completion_recognition=completion_recognition,
    )
    distinction = _compute_distinction(
        student,
        catalogue,
        major_keys,
        grading_scheme,
        credit_framework,
        course_code_scheme,
        course_load_framework,
        award_course_selections,
    )
    warnings = _compute_warnings_with_context(context, major_keys)
    if prog is None:
        warnings.append(
            f"No programme rule set matched {student.programme!r}; graduation cannot be verified."
        )
    warnings.append(
        "Course suggestions are provisional: they do not verify timetable clashes, co-requisites, class limits, concessions, or faculty approval."
    )
    if prog:
        warnings.extend(note for note in prog.admission_notes if note not in warnings)
        warnings.extend(note for note in prog.progression_notes if note not in warnings)
        warnings.extend(note for note in prog.award_notes if note not in warnings)
    if provisional_credit_results:
        warnings.append(
            "The credit total provisionally includes transcript-only approved/open elective course(s): "
            + ", ".join(result.code for result in provisional_credit_results)
            + ". Faculty approval must be confirmed before these credits are treated as definitive."
        )

    failed_attempts = _compute_failed_attempts(student, grading_scheme)

    verification_messages = [
        r.detail or r.label for r in blocking_requirements if r.complete and r.status != "verified"
    ]

    return Report(
        graduation_eligible=graduation_eligible,
        credits_completed=credits_completed,
        level_7_credits=level_7_credits,
        semester_course_equivalents=sce_total,
        requirements=requirements,
        majors=major_progresses,
        eligible_courses=eligible_courses,
        exclusion_risk=exclusion_risk,
        distinction=distinction,
        warnings=warnings,
        failed_attempts=failed_attempts,
        student_name=student.name,
        graduation_status=graduation_status,
        verification_messages=verification_messages,
        faculty_key=student.faculty_key or catalogue.faculty_key,
        programme_key=programme_key,
        programme_name=prog.name if prog else student.programme,
        pathway_key=student.pathway_key or catalogue.pathway_key,
        pathway_name=(
            prog.pathways[student.pathway_key or catalogue.pathway_key].name
            if prog and (student.pathway_key or catalogue.pathway_key) in prog.pathways
            else ""
        ),
        scope_status=catalogue.scope_status,
        progression_policy_assessments=progression_policy_assessments,
        qualification_completion=qualification_completion,
        graduation_eligibility_assessment=graduation_eligibility_assessment,
        programme_entry_eligibility_assessment=entry_assessment,
        qualification_award_assessment=qualification_award_assessment,
    )
