"""Programme-entry portability and evidence boundaries through the public report."""

import copy
import inspect
import json
from dataclasses import asdict, replace

import pytest
from fastapi.testclient import TestClient
from fixtures.northstar import catalogue_for, frameworks, select_release

import app as backend
from curriculum_reasoning_engine.institutions import (
    register_institution_release,
    unregister_institution_release,
)
from engine.completion import (
    CourseCompletionRecognitionEvidence,
    CourseCompletionRecognitionInput,
    RecognitionEvidenceCoverage,
)
from engine.entry import ProgrammeEntryEligibilitySpec, evaluate_programme_entry
from engine.models import (
    AcademicRecordCoverageEvidence,
    CourseAttemptCoverageEvidence,
    CourseResult,
    ExternalSubjectAchievementCoverage,
    ExternalSubjectAchievementEvidence,
    PriorQualificationCoverage,
    PriorQualificationEvidence,
    StudentRecord,
)
from engine.prerequisites import AcademicConditionEvaluator, PrerequisiteEvaluator, ProjectedCourseCompletions
from engine.rule_engine import compute_report

Q = {"type": "qualification_held", "qualification_system_id": "ORION-CERT", "qualification_id": "ORA-K7"}
M = {"type": "external_subject_achievement", "qualification_system_id": "ORION-CERT", "subject_id": "OR-MATH", "comparator": "gte", "threshold": 7}
C = {"type": "course_completed", "course_code": "FOUND-X7"}
A = {"type": "course_achievement", "course_code": "FOUND-X7", "comparator": "gte", "threshold": 15, "attempt_selection": "any_qualifying_attempt"}


@pytest.fixture
def context():
    release = select_release("northstar", "northstar-fixture-2027")
    release = replace(release, external_qualification_systems=tuple(
        replace(system, verification_status="verified") for system in release.external_qualification_systems
    ))
    catalogue = catalogue_for(release)
    catalogue.pathway_key = "advanced_inquiry"
    student = StudentRecord("ENTRY-S", "Applicant", "Systems / Inquiry diploma", [],
                            programme_key="systems_inquiry", pathway_key="advanced_inquiry")
    return release, catalogue, student


def qualification(status="verified", student="ENTRY-S"):
    return PriorQualificationEvidence("Q1", student, "ORION-CERT", "ORA-K7", "Registry", "Synthetic credential", status)


def math(value=8, status="verified", student="ENTRY-S"):
    return ExternalSubjectAchievementEvidence("M1", student, "ORION-CERT", "OR-MATH", value, "Registry", "Synthetic subject", status)


def q_coverage(status="verified"):
    return PriorQualificationCoverage("ENTRY-S", "ORION-CERT", ("ORA-K7",), "complete", "Registry", "Synthetic snapshot", status)


def m_coverage(status="verified"):
    return ExternalSubjectAchievementCoverage("ENTRY-S", "ORION-CERT", ("OR-MATH",), "complete", "Registry", "Synthetic snapshot", status)


def spec(context, expression=None, status="verified"):
    raw = context[1].programmes["systems_inquiry"].pathway_entry_eligibility["advanced_inquiry"]
    raw["verification_status"] = status
    if expression is not None:
        raw["condition"] = copy.deepcopy(expression)
    return raw


def evaluator(context, **evidence):
    release, catalogue, student = context
    return AcademicConditionEvaluator(student, catalogue, **frameworks(release),
        achievement_scheme=release.achievement_scheme,
        external_qualification_systems=release.external_qualification_systems, **evidence)


def assess(context, **evidence):
    return evaluate_programme_entry(context[1], "systems_inquiry", "advanced_inquiry", evaluator(context, **evidence))


@pytest.mark.parametrize("field,value", [
    ("eligibility_spec_id", ""), ("programme_key", "other"), ("pathway_key", "other"),
    ("source_reference", ""), ("verification_status", "certain"), ("condition", []),
])
def test_invalid_spec_is_unsupported(context, field, value):
    spec(context)[field] = value
    assert assess(context).outcome == "unsupported"


def test_spec_scope_validation_and_no_implicit_programme(context):
    raw = spec(context)
    valid = ProgrammeEntryEligibilitySpec.from_package(raw, context[1], "systems_inquiry", "advanced_inquiry")
    assert valid.eligibility_spec_id == raw["eligibility_spec_id"]
    with pytest.raises(ValueError):
        ProgrammeEntryEligibilitySpec.from_package(raw, context[1], "absent")
    assert evaluate_programme_entry(context[1], "absent", "", evaluator(context)).outcome == "unsupported"
    assert evaluate_programme_entry(context[1], "systems_inquiry", "", evaluator(context)) is None


def test_pathway_replaces_programme_not_merges(context):
    spec(context, Q)
    context[1].programmes["systems_inquiry"].programme_entry_eligibility = {
        **spec(context), "pathway_key": "", "condition": {"type": "permission"},
    }
    assert assess(context, prior_qualification_evidence=[qualification()]).outcome == "satisfied"


@pytest.mark.parametrize("local,prior,score,coverage,outcome,complete", [
    (False, True, 8, False, "satisfied", False),
    (True, False, 8, False, "satisfied", False),
    (False, True, None, False, "unresolved", False),
    (False, True, 5, True, "not_satisfied", False),
    (False, False, 8, False, "unresolved", False),
])
def test_northstar_mixed_routes(context, local, prior, score, coverage, outcome, complete):
    spec(context)
    if local:
        context[2].results.append(CourseResult("FOUND-X7", "Foundation", 1, 6, 72, None))
    result = assess(context,
        prior_qualification_evidence=[qualification()] if prior else [],
        external_subject_achievement_evidence=[math(score)] if score is not None else [],
        external_subject_achievement_coverage=[m_coverage()] if coverage else [])
    assert (result.outcome, result.assessment_complete) == (outcome, complete)
    if outcome in {"satisfied", "not_satisfied"}:
        assert result.status == "verified"


@pytest.mark.parametrize("expression,evidence,outcome,complete", [
    (Q, {"prior_qualification_evidence": [qualification()]}, "satisfied", True),
    (Q, {}, "unresolved", False),
    (Q, {"prior_qualification_coverage": [q_coverage()]}, "not_satisfied", True),
    (M, {"external_subject_achievement_evidence": [math()]}, "satisfied", True),
    (M, {"external_subject_achievement_evidence": [math(4)]}, "unresolved", False),
    (M, {"external_subject_achievement_evidence": [math(4)], "external_subject_achievement_coverage": [m_coverage()]}, "not_satisfied", True),
    ({"type": "all_of", "conditions": [Q, M]}, {"prior_qualification_coverage": [q_coverage()]}, "not_satisfied", False),
    ({"type": "one_of", "conditions": [Q, M]}, {"prior_qualification_evidence": [qualification()]}, "satisfied", False),
    (Q, {"prior_qualification_evidence": [qualification("conflict")]}, "conflict", False),
    (M, {"external_subject_achievement_evidence": [math(status="conflict")]}, "conflict", False),
    ({"type": "permission"}, {}, "unsupported", False),
])
def test_condition_truth_completeness(context, expression, evidence, outcome, complete):
    spec(context, expression)
    result = assess(context, **evidence)
    assert (result.outcome, result.assessment_complete) == (outcome, complete)


@pytest.mark.parametrize("expression,evidence", [
    (Q, {"prior_qualification_evidence": [qualification("unverified")]}),
    (Q, {"prior_qualification_coverage": [q_coverage("unverified")]}),
    (M, {"external_subject_achievement_evidence": [math(status="unverified")]}),
    (M, {"external_subject_achievement_coverage": [m_coverage("unverified")]}),
])
def test_evidence_authority_preserved(context, expression, evidence):
    spec(context, expression)
    assert assess(context, **evidence).status == "unverified"


def test_policy_authority_and_conflict(context):
    spec(context, Q, "unverified")
    result = assess(context, prior_qualification_evidence=[qualification()])
    assert result.outcome == "satisfied" and result.status == "unverified"
    spec(context, Q, "conflict")
    assert assess(context, prior_qualification_evidence=[qualification()]).outcome == "conflict"


@pytest.mark.parametrize("marks,coverage,outcome", [
    ([16], False, "satisfied"), ([13], False, "unresolved"),
    ([13], True, "not_satisfied"), ([13, None], True, "unresolved"),
    ([None], True, "unresolved"), ([16, 13], False, "satisfied"),
])
def test_local_achievement_attempt_boundary(context, marks, coverage, outcome):
    spec(context, A)
    context[2].results = [CourseResult("FOUND-X7", "Foundation", 1, 6, mark, None) for mark in marks]
    result = assess(context, course_attempt_coverage_evidence=[CourseAttemptCoverageEvidence(("FOUND-X7",), "complete")] if coverage else [])
    assert result.outcome == outcome


def test_course_coverage_cannot_replace_attempt_coverage(context):
    spec(context, A)
    assert assess(context, academic_record_coverage_evidence=[AcademicRecordCoverageEvidence(("FOUND-X7",), "complete")]).outcome == "unresolved"


def test_local_completion_and_projection_isolation(context):
    spec(context, C)
    projected = ProjectedCourseCompletions(("FOUND-X7",))
    assert assess(context, projected_course_completions=projected).outcome == "unresolved"
    current = evaluator(context, projected_course_completions=projected)
    prerequisite = PrerequisiteEvaluator(context[2], context[1], **frameworks(context[0]), projected_course_completions=projected)
    assert current.evaluate(C).outcome == "unresolved"
    assert prerequisite.evaluate(C).outcome == "satisfied"
    assert evaluate_programme_entry(context[1], "systems_inquiry", "advanced_inquiry", prerequisite).outcome == "unsupported"
    context[2].results = [CourseResult("FOUND-X7", "Foundation", 1, 6, 72, None)]
    assert assess(context).outcome == "satisfied"


def test_exact_recognition_positive_without_local_attempt(context):
    spec(context, C)
    recognition = CourseCompletionRecognitionInput((CourseCompletionRecognitionEvidence(
        "REC-1", "ENTRY-S", "FOUND-X7", "external learning", "northstar", "northstar-fixture-2027",
        "Registrar", "Synthetic recognition", "verified", "systems_inquiry", "advanced_inquiry",
    ),))
    before = copy.deepcopy(context[2])
    assert assess(context, completion_recognition=recognition).outcome == "satisfied"
    assert context[2] == before


def test_negative_course_requires_both_evidence_domains(context):
    spec(context, C)
    result_coverage = [AcademicRecordCoverageEvidence(("FOUND-X7",), "complete")]
    assert assess(context, academic_record_coverage_evidence=result_coverage).outcome == "unresolved"
    recognition = CourseCompletionRecognitionInput(coverage=(RecognitionEvidenceCoverage(
        "ENTRY-S", "northstar", "northstar-fixture-2027", ("FOUND-X7",), "Registrar", "Synthetic snapshot",
        "verified", "systems_inquiry", "advanced_inquiry",
    ),))
    assert assess(context, academic_record_coverage_evidence=result_coverage, completion_recognition=recognition).outcome == "not_satisfied"


@pytest.mark.parametrize("expression", [
    {**Q, "qualification_id": ""}, {**Q, "qualification_system_id": "UNKNOWN"},
    {**M, "threshold": 99}, {**A, "threshold": "15"},
    {**A, "attempt_selection": "latest"},
    {"type": "all_of", "conditions": []},
    {"type": "all_of", "conditions": [{"type": "one_of", "conditions": [{"type": "all_of", "conditions": [Q]}]}]},
])
def test_unsupported_conditions_not_invented(context, expression):
    spec(context, expression)
    assert assess(context).outcome == "unsupported"


def test_unused_conflict_does_not_erase_or_witness(context):
    spec(context, {"type": "one_of", "conditions": [Q, M]})
    result = assess(context, prior_qualification_evidence=[qualification()],
                    external_subject_achievement_evidence=[math(status="conflict")])
    assert (result.outcome, result.status, result.assessment_complete) == ("satisfied", "verified", False)


def test_compatible_qualification_witnesses_not_status_conflict(context):
    spec(context, Q)
    result = assess(context, prior_qualification_evidence=[qualification("unverified"), qualification()])
    assert (result.outcome, result.status) == ("satisfied", "verified")


def test_attempt_coverage_ingestion_preserves_domain_and_authority():
    values = backend._course_attempt_coverage_from_body({"course_attempt_coverage": [{
        "course_codes": ["FOUND-X7"], "coverage_state": "complete", "authority": "Registry",
        "source_reference": "Synthetic attempts", "verification_status": "unverified",
    }]})
    assert values == (CourseAttemptCoverageEvidence(("FOUND-X7",), "complete", "Synthetic attempts", "Registry", "unverified"),)


def test_wrong_student_ignored(context):
    spec(context, Q)
    assert assess(context, prior_qualification_evidence=[qualification(student="OTHER")]).outcome == "unresolved"


def test_report_has_no_effect_on_routing_results_or_registration(context):
    release, catalogue, student = context
    before = copy.deepcopy(student)
    report = compute_report(student, catalogue, **frameworks(release),
        external_qualification_systems=release.external_qualification_systems,
        prior_qualification_evidence=(qualification(),), external_subject_achievement_evidence=(math(),))
    result = backend._to_dict(report)["programme_entry_eligibility_assessment"]
    assert result["outcome"] == "satisfied"
    assert result["eligibility_spec_id"].startswith("NORTHSTAR-")
    assert result["source_reference"].startswith("Synthetic")
    assert student == before
    assert report.credits_completed == 0 and report.failed_attempts == {}
    assert not {"admitted", "rejected", "registration_history"} & result.keys()


def test_single_shared_evaluation_no_duplicate_leaves(context, monkeypatch):
    spec(context, Q)
    current = evaluator(context, prior_qualification_evidence=[qualification()])
    calls = []
    original = current.evaluate
    def evaluate(expression):
        calls.append(expression)
        return original(expression)
    monkeypatch.setattr(current, "evaluate", evaluate)
    assert evaluate_programme_entry(context[1], "systems_inquiry", "advanced_inquiry", current).outcome == "satisfied"
    assert len(calls) == 1
    for name in ("_achievement_leaf", "_external_achievement_leaf", "_qualification_held_leaf", "_all_of", "_one_of"):
        assert getattr(PrerequisiteEvaluator, name) is getattr(AcademicConditionEvaluator, name)
    source = inspect.getsource(evaluate_programme_entry)
    for forbidden in ("student.results", "coverage_state", "years_registered", "CourseResult(", "RegistrationHistoryEvidence(", "northstar", "uct"):
        assert forbidden not in source


@pytest.fixture
def client(context):
    release = context[0]
    register_institution_release(release)
    try:
        yield TestClient(backend.app)
    finally:
        unregister_institution_release(release.institution_id, release.release_id)


def body():
    return {"institution_id": "northstar", "release_id": "northstar-fixture-2027",
        "faculty": "systems", "programme_key": "systems_inquiry", "pathway_key": "advanced_inquiry",
        "student_id": "ENTRY-S", "programme": "Systems / Inquiry diploma", "declared_majors": [], "results": [],
        "prior_qualification_evidence": [asdict(qualification())],
        "external_subject_achievement_evidence": [asdict(math())]}


@pytest.mark.parametrize("case,expected", [("external", "satisfied"), ("local", "satisfied"), ("missing", "unresolved"), ("negative", "not_satisfied")])
def test_backend_end_to_end(client, case, expected):
    request = body()
    if case == "local":
        request["prior_qualification_evidence"] = []
        request["results"] = [{"code": "FOUND-X7", "mark": 72, "nqf_level": 1, "nqf_credits": 6}]
    if case == "missing":
        request["external_subject_achievement_evidence"] = []
    if case == "negative":
        request["external_subject_achievement_evidence"] = [asdict(math(5))]
        request["external_subject_achievement_coverage"] = [asdict(m_coverage())]
    response = client.post("/analyse/json", json=request)
    assert response.status_code == 200, response.text
    result = response.json()["programme_entry_eligibility_assessment"]
    assert result["outcome"] == expected
    assert result["status"] == "unverified"
    assert "admitted" not in result


def test_backend_alternating_releases_and_requests(client):
    first = client.post("/analyse/json", json=body()).json()
    uct = client.post("/analyse/json", json={"faculty": "uct_humanities", "programme_key": "bsocsc_regular",
        "student_id": "UCT-S", "programme": "Bachelor of Social Science", "results": [], "declared_majors": []})
    assert uct.status_code == 200, uct.text
    assert uct.json()["programme_entry_eligibility_assessment"] is None
    missing = body()
    missing["external_subject_achievement_evidence"] = []
    assert client.post("/analyse/json", json=missing).json()["programme_entry_eligibility_assessment"]["outcome"] == "unresolved"
    assert client.post("/analyse/json", json=body()).json() == first


def test_backend_text_adapter_preserves_entry_evidence(client):
    request = body()
    request["text"] = json.dumps({"person": "ENTRY-S", "route": "Systems / Inquiry diploma", "modules": []})
    response = client.post("/analyse/text", json=request)
    assert response.status_code == 200, response.text
    assert response.json()["programme_entry_eligibility_assessment"]["outcome"] == "satisfied"


def test_backend_numeric_entry_uses_attempt_coverage(client, monkeypatch):
    original = backend._context_from_body
    def context_from_body(*args, **kwargs):
        student, catalogue, release, scope = original(*args, **kwargs)
        catalogue = copy.deepcopy(catalogue)
        catalogue.programmes["systems_inquiry"].pathway_entry_eligibility["advanced_inquiry"]["condition"] = A
        return student, catalogue, release, scope
    monkeypatch.setattr(backend, "_context_from_body", context_from_body)
    request = body()
    request["results"] = [{"code": "FOUND-X7", "mark": 13, "nqf_level": 1, "nqf_credits": 6}]
    before = client.post("/analyse/json", json=request)
    assert before.status_code == 200, before.text
    assert before.json()["programme_entry_eligibility_assessment"]["outcome"] == "unresolved"
    request["course_attempt_coverage"] = [{"course_codes": ["FOUND-X7"], "coverage_state": "complete",
                                         "authority": "Registry", "verification_status": "verified"}]
    after = client.post("/analyse/json", json=request)
    assert after.status_code == 200, after.text
    assert after.json()["programme_entry_eligibility_assessment"]["outcome"] == "not_satisfied"
