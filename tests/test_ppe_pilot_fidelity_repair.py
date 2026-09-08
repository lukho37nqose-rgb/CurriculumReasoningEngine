"""Technical fidelity only: no institutional interpretation of the PPE pools."""
import inspect
import json
import subprocess
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import app as backend
from curriculum_advisor import presentation
from engine.completion import (
    CourseCompletionRecognitionEvidence,
    CourseCompletionRecognitionInput,
    CourseCompletionResolver,
)
from engine.models import StudentRecord
from engine.rule_engine import Requirement

IDS = ("ppe_year1", "ppe_year2_fixed", "ppe_year2_politics", "ppe_year2_other", "ppe_eco3025", "ppe_phi3", "ppe_pol3")
ROOT = Path(__file__).resolve().parents[1]


def body(**extra):
    return {"faculty": "uct_humanities", "programme_key": "bsocsc_ppe", "student_id": "PPE-REPAIR", "results": [], **extra}


def report(**extra):
    response = TestClient(backend.app).post("/analyse/json", json=body(**extra))
    assert response.status_code == 200, response.text
    return response.json()


def rule_data():
    catalogue = backend.get_catalogue("uct_humanities")
    return {rule["id"]: rule for rule in catalogue.programmes["bsocsc_ppe"].curriculum_rules}


def projections(payload, identity):
    key = "curriculum:" + identity
    return (
        next(r for r in payload["requirements"] if r["id"] == key),
        next(r for r in payload["student_reasoning_view"]["conclusions"] if r["identity"] == key),
        next(r for r in payload["advisor_reasoning_view"]["advisor_detail"]["canonical_outcomes"] if r["identity"] == key),
    )


@pytest.mark.parametrize("identity", IDS)
@pytest.mark.parametrize("state", ["unknown", "negative", "positive"])
def test_seven_rules_backend_fidelity(identity, state):
    rule = rule_data()[identity]
    codes = rule["course_codes"]
    extra = {}
    if state == "negative":
        extra = {"academic_record_coverage": [{"course_codes": codes, "coverage_state": "complete", "authority": "Test registry", "source_reference": "Synthetic scoped record"}],
                 "recognition_coverage": [{"course_codes": codes, "authority": "Test registry", "source_reference": "Synthetic decision snapshot", "verification_status": "verified"}]}
    if state == "positive":
        selected = codes if rule["type"] == "all_courses" else codes[:1]
        extra = {"results": [{"code": code, "mark": 70} for code in selected]}
    payload = report(**extra)
    canonical, student, advisor = projections(payload, identity)
    expected = {"unknown": "unresolved", "negative": "not_satisfied", "positive": "satisfied"}[state]
    for item in (canonical, student, advisor):
        assert item["outcome"] == expected
        assert item["assessment_complete"] == (state != "unknown")
        assert item["status"] == ("unverified" if state == "unknown" else "verified")
    assert student["outcome_label"] == presentation.OUTCOME_LABELS[expected]
    assert student["source_references"][0]["locator"] == {k: v for k, v in rule["source"].items() if k != "document"}
    if state == "unknown":
        assert "not met" not in student["explanation"].lower()
        assert student["next_action"] == "SUPPLY_EVIDENCE"
    if rule["type"] == "all_courses":
        assert "choices" not in student["detail"]
        assert "options" not in student["detail"]
    if state == "positive":
        assert student["used_course_codes"]


@pytest.mark.parametrize("outcome", list(presentation.OUTCOME_EXPLANATIONS))
def test_projection_never_reconstructs_truth(outcome, monkeypatch):
    requirement = Requirement("R", "Rule", False, 0, 1, outcome=outcome, assessment_complete=False)
    raw = SimpleNamespace(requirements=[requirement])
    assert presentation.student_reasoning_view(raw)["conclusions"][0]["outcome"] == outcome
    monkeypatch.setattr(presentation, "student_reasoning_view", lambda *a, **k: {"conclusions": []})
    advisor = presentation.advisor_reasoning_view(raw)["advisor_detail"]["canonical_outcomes"][0]
    assert advisor["outcome"] == outcome
    assert not advisor["assessment_complete"]


@pytest.mark.parametrize("complete", [True, False])
def test_legacy_boolean_is_not_canonical(complete):
    raw = SimpleNamespace(requirements=[Requirement("R", "Legacy", complete, 0, 1)])
    assert presentation.student_reasoning_view(raw)["conclusions"][0]["outcome"] == "unresolved"


def test_recognition_and_conflict_survive_backend():
    decision = {"recognition_id": "TEST-R", "target_course_code": "POL2039F", "source_learning_identity": "TEST-EXT", "authority": "Test registry", "source_reference": "Synthetic record", "verification_status": "verified"}
    positive = report(course_completion_recognition=[decision])
    assert projections(positive, "ppe_year2_politics")[0]["outcome"] == "satisfied"
    assert positive["credits_completed"] == 0
    conflict = report(course_completion_recognition=[{**decision, "verification_status": "conflict"}])
    student = projections(conflict, "ppe_year2_politics")[1]
    assert student["outcome"] == "conflict"
    assert student["next_action"] == "REVIEW_CONFLICT"


@pytest.mark.parametrize("release_id", ["2026", "2026.2-humanities-complete", "2026-other", "northstar-fixture-2027"])
def test_release_not_catalogue_build_binding(release_id):
    catalogue = backend.get_catalogue("uct_humanities")
    student = StudentRecord("S", "", "", [], [], programme_key="bsocsc_ppe")
    evidence = CourseCompletionRecognitionEvidence("R", "S", "ECO3025S", "EXT", "uct", release_id, "Registry", "Synthetic", "verified")
    resolver = CourseCompletionResolver(student, catalogue, recognition=CourseCompletionRecognitionInput((evidence,)))
    assert (resolver.resolve("ECO3025S").outcome == "satisfied") == (release_id == "2026")
    other = replace(catalogue, institution_release_id="2027")
    assert CourseCompletionResolver(student, other, recognition=CourseCompletionRecognitionInput((evidence,))).resolve("ECO3025S").outcome == "unresolved"


@pytest.mark.parametrize("coverage_key,scope_key,category", [("academic_record_coverage", "course_codes", "academic_record"), ("recognition_coverage", "course_codes", "course_completion_recognition"), ("requirement_recognition_coverage", "requirement_ids", "requirement_recognition")])
@pytest.mark.parametrize("state", ["complete", "partial", "unknown"])
def test_scoped_receipt(coverage_key, scope_key, category, state):
    supplied = {coverage_key: [{scope_key: ["ECO3025S"], "coverage_state": state}]}
    entry = next(e for e in presentation.presentation_context_from_request(supplied, academic_record_supplied=True).evidence_receipt["entries"] if e["category"] == category)
    assert entry["coverage_state"] == "SCOPED"
    assert entry["coverage_scopes"][0][scope_key] == ["ECO3025S"]
    assert entry["coverage_scopes"][0]["coverage_state"] == {"complete": "COVERAGE_COMPLETE_FOR_SCOPE", "partial": "COVERAGE_PARTIAL", "unknown": "COVERAGE_UNKNOWN"}[state]


def test_frontend_and_projection_architecture():
    js = (ROOT / "static/app.js").read_text(encoding="utf-8")
    assert "conclusions.slice(0, 8)" not in js
    assert 'StudentWorkspace.renderSection(report, workspaceConfig(), "curriculum")' in js
    assert "if (projected) return studentConclusionCard(projected)" in js
    assert "esc(link.conclusion_id)" not in js
    assert "StudentLanguage.card" in js
    assert "institutionally confirmed" in (ROOT / "static/student-language.js").read_text(encoding="utf-8")
    source = inspect.getsource(presentation)
    assert "CurriculumEvaluator" not in source
    assert "CourseCompletionResolver" not in source
    assert "requirement.complete" not in source


def test_award_remains_reachable_and_not_inferred():
    payload = report()
    item = next(c for c in payload["student_reasoning_view"]["conclusions"] if c["identity"].startswith("award:"))
    assert item["outcome"] == "unresolved"


def test_explicit_award_is_visible_without_inference():
    payload = report(qualification_award_evidence=[{
        "award_evidence_id": "TEST-AWARD", "outcome": "awarded", "authority": "Test registrar",
        "verification_status": "verified", "source_reference": "Synthetic award register"}])
    item = next(c for c in payload["student_reasoning_view"]["conclusions"] if c["identity"].startswith("award:"))
    assert item["outcome"] == "awarded"
    assert item["outcome_label"] == "Qualification awarded"


@pytest.mark.parametrize("key,category", [("course_completion_recognition", "course_completion_recognition"), ("requirement_recognition_evidence", "requirement_recognition")])
def test_receipt_received_does_not_claim_contribution(key, category):
    context = presentation.presentation_context_from_request({key: [{"recognition_id": "R"}]}, academic_record_supplied=False)
    receipt = context.evidence_receipt
    assert receipt["recognition"] == "RECEIVED"
    entry = next(e for e in receipt["entries"] if e["category"] == category)
    assert entry["receipt_state"] == "RECEIVED"
    assert entry["coverage_state"] == "COVERAGE_UNKNOWN"
    assert "used" not in entry
    assert receipt["academic_record"] == "NOT_SUPPLIED"


def test_wrong_release_request_evidence_is_not_rebound():
    payload = report(course_completion_recognition=[{
        "recognition_id": "WRONG", "target_course_code": "ECO3025S", "source_learning_identity": "EXT",
        "authority": "Test registry", "source_reference": "Synthetic", "verification_status": "verified",
        "release_id": "2026-unrelated"}])
    assert projections(payload, "ppe_eco3025")[0]["outcome"] == "unresolved"


def test_requirement_recognition_release_domain_and_report_plumbing():
    from test_requirement_targeted_recognition_stage14 import Grading, _catalogue, _recognition, _student

    from engine.curriculum import CurriculumEvaluator
    from engine.rule_engine import compute_report

    catalogue = replace(_catalogue(), institution_release_id="release-one")
    recognition = replace(_recognition(), release_id="release-one")
    result = compute_report(_student(), catalogue, grading_scheme=Grading(), requirement_recognition_evidence=[recognition])
    requirement = next(r for r in result.requirements if r.id == "curriculum:foundation_block")
    assert requirement.outcome == "satisfied"
    rejected = CurriculumEvaluator(_student(), catalogue, Grading(), requirement_recognition_evidence=[_recognition()]).evaluate_many(catalogue.programmes["p"].curriculum_rules)
    assert rejected[0].outcome == "unresolved"


def test_actual_frontend_renderers_preserve_seven_cards_and_scopes():
    payload = report(academic_record_coverage=[{"course_codes": ["ECO3025S"], "coverage_state": "complete"}])
    script = r'''
const fs = require('fs');
const vm = require('vm');
const data = JSON.parse(fs.readFileSync(0, 'utf8'));
const src = fs.readFileSync('static/app.js', 'utf8');
const names = ['workspaceConfig', 'studentConclusionCard', 'renderStudentReasoningView', 'requirementCard', 'requirementsSection'];
const context = {state: {report: data}, asArray: x => Array.isArray(x) ? x : [],
 esc: x => String(x ?? '').replaceAll('<', '&lt;'), statusKey: x => x,
 titleCase: x => x, sourceLocator: x => JSON.stringify(x)};
vm.createContext(context);
vm.runInContext(fs.readFileSync('static/student-language.js', 'utf8'), context);
vm.runInContext(fs.readFileSync('static/student-portal.js', 'utf8'), context);
vm.runInContext(fs.readFileSync('static/student-workspace.js', 'utf8'), context);
for (const name of names) {
 const start = src.indexOf('function ' + name + '(');
 const end = src.indexOf('\nfunction ', start + 1);
 vm.runInContext(src.slice(start, end < 0 ? undefined : end), context);
}
context.data = data;
process.stdout.write(JSON.stringify({curriculum: context.renderStudentReasoningView(data), requirements: context.requirementsSection(), evidence: vm.runInContext('StudentWorkspace.renderSection(data, workspaceConfig(), "evidence")', context)}));
'''
    process = subprocess.run(["node", "-e", script], input=json.dumps(payload), text=True, encoding="utf-8", capture_output=True, cwd=ROOT, check=True)
    rendered = json.loads(process.stdout)
    for key in IDS:
        student = projections(payload, key)[1]
        for html in [rendered['curriculum'], rendered['requirements']]:
            assert student["title"] in html
            assert student["outcome_label"] in html
    assert "Complete information was supplied for the specific items below" in rendered["evidence"]
    assert "ECO3025S" in rendered["evidence"]
    assert "Formal award" in rendered["curriculum"]
    assert "does not mean the institution has formally confirmed" in rendered["requirements"]


def test_backend_receipt_uses_ingested_normalised_scope():
    payload = report(academic_record_coverage=[{"course_codes": [" eco3025s "], "coverage_state": "complete"}])
    entry = payload["student_reasoning_view"]["evidence_receipt"]["entries"][0]
    assert entry["coverage_scopes"][0]["course_codes"] == ["ECO3025S"]
    assert entry["coverage_scopes"][0]["coverage_state"] == "COVERAGE_COMPLETE_FOR_SCOPE"
    assert projections(payload, "ppe_eco3025")[0]["outcome"] == "unresolved"


@pytest.mark.parametrize("identity", IDS)
def test_applicable_recognition_conflict_cannot_be_masked_by_shortfall(identity):
    code = rule_data()[identity]["course_codes"][0]
    payload = report(course_completion_recognition=[{
        "recognition_id": "CONFLICT", "target_course_code": code, "source_learning_identity": "EXT",
        "authority": "Synthetic registry", "source_reference": "Synthetic conflict", "verification_status": "conflict"}])
    for item in projections(payload, identity):
        assert item["outcome"] == "conflict"
        assert item["status"] == "conflict"
        assert not item["assessment_complete"]
