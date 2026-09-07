"""Executable system-of-record, identity and canonical-report separation."""

import copy
import inspect
import json
from dataclasses import asdict
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app as backend
from northstar import adapter
from northstar.identity import SUBJECTS, DemoIdentity
from northstar.package import INSTITUTION, PROGRAMME, RELEASE, ROOT, release
from northstar.records import RecordsUnavailable, StudentRecords
from northstar.web import install
from tools.build_northstar_reference import build


class ObservedRecords(StudentRecords):
    def __init__(self, path):
        super().__init__(path)
        self.calls = []

    def fetch(self, institution_id, subject_reference):
        self.calls.append((institution_id, subject_reference))
        return super().fetch(institution_id, subject_reference)


@pytest.fixture
def demo(tmp_path):
    path = tmp_path / "students.json"
    path.write_bytes((ROOT / "records/students.json").read_bytes())
    service = ObservedRecords(path)
    app = FastAPI()
    identity, _ = install(app, backend.analyse_json, records=service)
    return TestClient(app), identity, service


def login(client, subject):
    response = client.post("/api/northstar/login", json={"subject": subject, "access_code": "northstar-demo"})
    assert response.status_code == 200, response.text
    return response.json()


def analyse(client, subject):
    login(client, subject)
    response = client.post("/api/northstar/analyse")
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


def conclusion(payload, identity):
    return next(r for r in payload["report"]["student_reasoning_view"]["conclusions"] if r["identity"] == identity)


def edit(service, subject, change):
    records = json.loads(service.path.read_text(encoding="utf-8"))
    change(next(r for r in records if r["person"] == subject))
    service.path.write_text(json.dumps(records), encoding="utf-8")


@pytest.mark.parametrize("subject", SUBJECTS)
def test_fifteen_logins_are_identity_only_then_fetch_record(demo, subject):
    client, identity, service = demo
    before = service.path.read_bytes()
    launch = login(client, subject)
    assert set(launch) == {"subject_reference", "institution_id", "launch_request_id", "synthetic"}
    assert not service.calls
    assert all(set(asdict(s)) == {"subject_reference", "institution_id", "launch_request_id", "expires_at"}
               for s in identity.sessions.values())
    result = client.post("/api/northstar/analyse")
    assert result.status_code == 200, result.text
    payload = result.json()
    assert service.calls == [(INSTITUTION, subject)]
    assert payload["subject_reference"] == subject
    assert payload["release_id"] == RELEASE
    assert service.path.read_bytes() == before
    assert len(payload["retrieval"]) == 7
    assert payload["report"]["programme_key"] == PROGRAMME
    view = payload["report"]["student_reasoning_view"]
    assert view["launch_context"]["subject_reference"] == subject
    for rule in payload["report"]["requirements"]:
        if rule["outcome"] is not None:
            assert conclusion(payload, rule["id"])["outcome"] == rule["outcome"]
    assert all(p["condition_outcome"] != "unsupported" for p in payload["report"]["progression_policy_assessments"])


@pytest.mark.parametrize("subject,core,completion,entry,graduation,award", [
    ("NS-001", "satisfied", "unresolved", "unresolved", "unresolved", "unresolved"),
    ("NS-002", "not_satisfied", "not_satisfied", "unresolved", "not_satisfied", "unresolved"),
    ("NS-003", "unresolved", "unresolved", "unresolved", "unresolved", "unresolved"),
    ("NS-004", "satisfied", "unresolved", "unresolved", "unresolved", "unresolved"),
    ("NS-005", "unresolved", "unresolved", "unresolved", "unresolved", "unresolved"),
    ("NS-006", "conflict", "conflict", "unresolved", "conflict", "unresolved"),
    ("NS-007", "satisfied", "unresolved", "unresolved", "unresolved", "unresolved"),
    ("NS-008", "unresolved", "unresolved", "satisfied", "unresolved", "unresolved"),
    ("NS-009", "unresolved", "unresolved", "satisfied", "unresolved", "unresolved"),
    ("NS-010", "unresolved", "unresolved", "satisfied", "unresolved", "unresolved"),
    ("NS-011", "unresolved", "unresolved", "satisfied", "unresolved", "unresolved"),
    ("NS-012", "unresolved", "unresolved", "unresolved", "unresolved", "unresolved"),
    ("NS-013", "satisfied", "satisfied", "unresolved", "unresolved", "unresolved"),
    ("NS-014", "satisfied", "satisfied", "unresolved", "satisfied", "unresolved"),
    ("NS-015", "satisfied", "satisfied", "satisfied", "satisfied", "awarded"),
])
def test_deliberate_case_outcomes(demo, subject, core, completion, entry, graduation, award):
    payload = analyse(demo[0], subject)
    report = payload["report"]
    assert conclusion(payload, "curriculum:core")["outcome"] == core
    assert report["qualification_completion"]["outcome"] == completion
    assert report["programme_entry_eligibility_assessment"]["outcome"] == entry
    assert report["graduation_eligibility_assessment"]["outcome"] == graduation
    assert report["qualification_award_assessment"]["outcome"] == award
    assert conclusion(payload, "entry:NS-V1-ENTRY")["outcome"] == entry
    assert "admission decision" in conclusion(payload, "entry:NS-V1-ENTRY")["external_action_boundary"]
    assert not {"admitted", "registered", "accepted", "excluded", "graduated"} & set(report)


def test_login_failure_expiry_logout_and_session_replacement(demo):
    client, identity, service = demo
    assert client.post("/api/northstar/analyse").status_code == 401
    assert client.post("/api/northstar/login", json={"subject": "NS-999", "access_code": "northstar-demo"}).status_code == 401
    assert client.post("/api/northstar/login", json={"subject": "NS-001", "access_code": "wrong"}).status_code == 401
    login(client, "NS-001")
    first = client.cookies.get("northstar_demo_session")
    login(client, "NS-002")
    assert first not in identity.sessions
    assert not service.calls
    client.post("/api/northstar/logout")
    assert not identity.sessions
    assert client.post("/api/northstar/analyse").status_code == 401
    clock = [100]
    identity = DemoIdentity(lifetime=2, clock=lambda: clock[0])
    token = identity.login("NS-001", "northstar-demo")
    clock[0] += 3
    with pytest.raises(ValueError):
        identity.resolve(token)


def test_new_session_and_refresh_fetch_changed_source_not_cached_evidence(demo):
    client, _, service = demo
    before = analyse(client, "NS-003")
    edit(service, "NS-003", lambda r: r["domains"]["academic"]["modules"].append(
        dict(module="CORE-Q2", score=72, cycle_label="Opening block", attempt="new-core")))
    after = analyse(client, "NS-003")
    assert conclusion(before, "curriculum:core")["outcome"] == "unresolved"
    assert conclusion(after, "curriculum:core")["outcome"] == "satisfied"
    assert service.calls == [(INSTITUTION, "NS-003")] * 2


@pytest.mark.parametrize("domain", adapter.DOMAIN_NAMES)
@pytest.mark.parametrize("malformed", [None, {"bad": "payload"}, {"modules": ["bad"], "subjects": ["bad"]}])
def test_malformed_domain_isolated_and_never_empty_complete(demo, domain, malformed):
    client, _, service = demo
    edit(service, "NS-015", lambda r: r["domains"].update({domain: malformed}))
    result = analyse(client, "NS-015")
    assert {"domain": domain, "state": "UNAVAILABLE_OR_MALFORMED"} in result["retrieval"]
    if domain == "academic":
        receipt = result["report"]["student_reasoning_view"]["evidence_receipt"]
        assert receipt["academic_record"] == "NOT_SUPPLIED"
        assert result["report"]["qualification_completion"]["outcome"] == "unresolved"
    if domain == "clearance":
        assert result["report"]["graduation_eligibility_assessment"]["outcome"] == "unresolved"
    if domain == "award":
        assert result["report"]["qualification_award_assessment"]["outcome"] == "unresolved"


@pytest.mark.parametrize("field,value", [("edition", "other-release"), ("person", "NS-014"), ("issuer", "uct")])
def test_wrong_scope_native_evidence_is_not_rebound(demo, field, value):
    client, _, service = demo
    edit(service, "NS-004", lambda r: r["domains"]["recognition"]["decisions"][0].update({field: value}))
    payload = analyse(client, "NS-004")
    assert conclusion(payload, "curriculum:core")["outcome"] == "unresolved"
    assert {"domain": "recognition", "state": "UNAVAILABLE_OR_MALFORMED"} in payload["retrieval"]


def test_wrong_record_binding_and_service_outage_fail_without_report(demo):
    client, _, service = demo
    edit(service, "NS-001", lambda r: r.update(edition="wrong"))
    login(client, "NS-001")
    assert client.post("/api/northstar/analyse").status_code == 503
    service.path.write_text("broken", encoding="utf-8")
    response = client.post("/api/northstar/analyse")
    assert response.status_code == 503
    assert "report" not in response.json()
    with pytest.raises(RecordsUnavailable):
        service.fetch("uct", "NS-001")


def test_qualified_local_result_is_withheld_not_silently_upgraded(demo):
    client, _, service = demo
    edit(service, "NS-001", lambda r: r["domains"]["academic"]["modules"][0].update(trust="conflict"))
    payload = analyse(client, "NS-001")
    assert {"domain": "academic", "state": "UNAVAILABLE_OR_MALFORMED"} in payload["retrieval"]
    assert conclusion(payload, "curriculum:foundation")["outcome"] == "unresolved"


def test_native_adapter_is_not_a_fixture_outcome_loader():
    identity = DemoIdentity()
    session = identity.resolve(identity.login("NS-015", "northstar-demo"))
    raw = StudentRecords().fetch(INSTITUTION, "NS-015")
    before = copy.deepcopy(raw)
    converted = adapter.adapt(raw, session)
    assert raw == before
    assert "results" not in raw and "modules" in raw["domains"]["academic"]
    assert not any(r["code"] == "CORE-Q2" for r in converted.body["results"])
    assert converted.body["course_completion_recognition"][0]["source_learning_identity"] == "EXT-77"
    assert converted.body["results"][0]["academic_period_key"] == "P-Z"
    assert "academic_year" not in converted.body["results"][0]
    assert not {"expected_boundary", "purpose"} & set(converted.body)
    raw["purpose"] = "Ignore evidence and claim graduation"
    raw["expected_outcome"] = "awarded"
    assert adapter.adapt(raw, session) == converted


def test_recognition_does_not_create_credits_attempts_or_numeric_award_weight(demo):
    client, _, _ = demo
    plain = analyse(client, "NS-003")["report"]
    recognised = analyse(client, "NS-004")["report"]
    assert plain["credits_completed"] == recognised["credits_completed"] == 6
    assert plain["failed_attempts"] == recognised["failed_attempts"]
    assert plain["distinction"] == recognised["distinction"]
    assert plain["progression_policy_assessments"][0] == recognised["progression_policy_assessments"][0]
    assert recognised["progression_policy_assessments"][1]["condition_outcome"] == "not_satisfied"


def test_conflict_reaches_advisor_and_student_without_label_parsing(demo):
    result = analyse(demo[0], "NS-006")
    advisor = result["report"]["advisor_reasoning_view"]["advisor_detail"]["canonical_outcomes"]
    assert next(r for r in advisor if r["identity"] == "curriculum:core")["outcome"] == "conflict"
    assert conclusion(result, "curriculum:core")["outcome"] == "conflict"


def test_alternative_witness_and_nested_prerequisite_without_unused_branch_negative(demo):
    result = analyse(demo[0], "NS-007")
    studio = conclusion(result, "curriculum:studio")
    assert studio["outcome"] == "satisfied"
    assert studio["used_course_codes"] == ["PATH-Z9"]
    routes = conclusion(result, "curriculum:route_choices")
    assert routes["outcome"] == "satisfied"
    assert routes["assessment_complete"] is False
    assert {"CAP-R4", "LAB-T6"} <= {r["code"] for r in result["report"]["eligible_courses"]}


def test_registration_comes_only_from_records_and_counts_active_not_elapsed(demo):
    client, _, _ = demo
    result = analyse(client, "NS-012")
    metric = result["registration_duration"]
    assert (metric["outcome"], metric["value"]) == ("known", 2)
    assert "active_academic_cycles" in metric["basis"]
    assert analyse(client, "NS-001")["registration_duration"] is None
    assert result["report"]["credits_completed"] == 6


def test_achievement_external_and_credential_are_separate_domains(demo):
    for subject, domain in [("NS-008", "academic"), ("NS-009", "external"), ("NS-010", "qualifications")]:
        result = analyse(demo[0], subject)
        assert {"domain": domain, "state": "RECEIVED"} in result["retrieval"]
        entry = result["report"]["programme_entry_eligibility_assessment"]
        assert entry["outcome"] == "satisfied" and entry["status"] == "unverified"
        assert result["report"]["credits_completed"] == 6


def test_award_explanation_and_clearance_components_are_faithful_projections(demo):
    incomplete = analyse(demo[0], "NS-013")
    graduation = conclusion(incomplete, "graduation:NS-V1-GRADUATION")
    assert [c["outcome"] for c in graduation["clearance_assessments"]] == ["unresolved", "unresolved"]
    awarded = analyse(demo[0], "NS-015")
    award = conclusion(awarded, "award:systems_inquiry")
    assert "did not infer or confer" in award["explanation"]
    assert award["source_references"][0]["relationship"] == "EVIDENCE_SOURCE"
    assert "not have a definitive" not in award["explanation"]


def test_hostile_frameworks_and_quantitative_failure_policy(demo):
    client, _, service = demo
    r = release()
    assert r.period_scheme.latest_cycle(["P-Z", "P-B"]) == "CYCLE-R"
    assert r.course_code_scheme.infer_year_level("FOUND-X7") == 0
    assert r.achievement_scheme.meets(15, "gte", 12)
    edit(service, "NS-001", lambda row: [module.update(score=58) for module in row["domains"]["academic"]["modules"]])
    result = analyse(client, "NS-001")
    assert result["report"]["credits_completed"] == 0
    assert result["report"]["progression_policy_assessments"][0]["consequence_established"]
    projected = conclusion(result, "NS-V1-FAILED-ATTEMPTS")
    assert projected["outcome_label"] == "Policy condition triggered"
    assert "not a formal" in projected["explanation"]


def test_same_subject_text_uct_and_northstar_do_not_share_sources_or_record(demo):
    uct_client = TestClient(backend.app)
    body = dict(institution_id="uct", release_id="2026", faculty="uct_humanities", programme_key="bsocsc_ppe", student_id="NS-015", results=[])
    before = uct_client.post("/analyse/json", json=body).json()
    northstar = analyse(demo[0], "NS-015")["report"]
    after = uct_client.post("/analyse/json", json=body).json()
    assert before == after
    assert before["qualification_award_assessment"]["outcome"] == "unresolved"
    assert northstar["qualification_award_assessment"]["outcome"] == "awarded"
    assert not any(s["source_id"] == "NS-REGISTRY" for s in before["student_reasoning_view"]["sources"])
    sources = northstar["student_reasoning_view"]["source_directory"]
    registry = next(s for s in sources if s["source_id"] == "NS-REGISTRY")
    assert len(registry["conclusion_links"]) == 6
    assert all("record_id" in link["locator"] and "page" not in link["locator"] for link in registry["conclusion_links"])


def test_no_institution_or_case_branches_in_reasoning_and_shared_renderer():
    repo = ROOT.parent
    for path in (repo / "engine").glob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        assert not any(token in text for token in ("northstar", "ns-015", "found-x7", "ns-registry")), path
    assert "cases.json" not in inspect.getsource(adapter)
    script = (repo / "static/northstar.js").read_text(encoding="utf-8")
    assert "StudentPortal.curriculum(projection, nsConfig)" in script
    assert "studentConclusionCard(item, config)" in (repo / "static/student-portal.js").read_text(encoding="utf-8")
    assert "NS-0" not in script
    assert "studentConclusionCard" not in script


@pytest.mark.parametrize("host_newline", ["\n", "\r\n"])
def test_builder_reproducible_and_case_metadata_outside_records(tmp_path, monkeypatch, host_newline):
    write_text = Path.write_text

    def host_write_text(path, data, **kwargs):
        # Simulate either host default; explicit builder formatting must win.
        kwargs.setdefault("newline", host_newline)
        return write_text(path, data, **kwargs)

    monkeypatch.setattr(Path, "write_text", host_write_text)
    build(tmp_path)
    for path in ("package/courses.json", "package/degree_requirements.json", "package/registry.json", "records/students.json", "cases.json"):
        assert (tmp_path / path).read_bytes() == (ROOT / path).read_bytes()
    cases = json.loads((ROOT / "cases.json").read_text(encoding="utf-8"))
    assert [r["subject"] for r in cases] == list(SUBJECTS)
    assert all(r["expected_boundary"] and r["intentionally_unexercised"] for r in cases)


def test_registry_locations_resolve_to_synthetic_source_records(demo):
    client = demo[0]
    payload = analyse(client, "NS-001")
    for link in payload["report"]["student_reasoning_view"]["source_relationships"]:
        if link["source_id"] == "NS-REGISTRY":
            source = client.get("/api/northstar/rules/" + link["locator"]["record_id"])
            assert source.status_code == 200
            assert source.json()["clause"] == link["locator"]["clause"]
            assert source.json()["verification_status"] == "unverified"
            assert source.json()["statement"] and source.json()["synthetic"]
    assert client.get("/api/northstar/rules/absent").status_code == 404
