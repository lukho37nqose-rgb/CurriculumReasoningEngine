import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import app
from engine.catalogue import load_catalogue
from engine.curriculum import CurriculumEvaluator
from engine.models import CourseResult, StudentRecord
from engine.rule_engine import compute_report
from engine.scope import build_programme_scope
from engine.utils import _infer_programme_key

client = TestClient(app)


def scoped(programme: str):
    full = load_catalogue("uct_commerce")
    return build_programme_scope("uct_commerce", full, programme, "")


def result(
    catalogue,
    code: str,
    mark: int | None = 80,
    year: int = 2026,
    grade: str | None = None,
):
    fact = catalogue.courses[code]
    return CourseResult(
        code,
        fact.name,
        fact.nqf_level,
        fact.nqf_credits,
        mark,
        grade or ("P" if mark is None or mark >= 50 else "F"),
        year,
    )


def choose_codes(rule):
    rule_type = rule.get("type")
    if rule_type == "course":
        return list(rule.get("course_codes", []))[:1]
    if rule_type == "all_courses":
        return list(rule.get("course_codes", []))
    if rule_type == "all_of":
        return [
            code for child in rule.get("children", []) for code in choose_codes(child)
        ]
    if rule_type == "any_of":
        children = rule.get("children", [])
        return choose_codes(children[0]) if children else []
    if rule_type == "choose_n":
        return list(rule.get("course_codes", []))[: int(rule.get("required", 1))]
    return []


def complete_closed_record(programme: str, mark: int = 80):
    catalogue, _ = scoped(programme)
    rules = catalogue.programmes[programme]
    codes: list[str] = []
    for rule in rules.curriculum_rules:
        codes.extend(choose_codes(rule))
    codes = list(dict.fromkeys(code for code in codes if code in catalogue.courses))
    rows = [result(catalogue, code, mark, 2026) for code in codes]
    student = StudentRecord(
        "COM001",
        "Commerce Student",
        rules.name,
        [],
        rows,
        faculty_key="uct_commerce",
        programme_key=programme,
        years_registered=rules.minimum_duration_years,
    )
    return catalogue, student


def test_commerce_catalogue_contains_every_published_undergraduate_route():
    catalogue = load_catalogue("uct_commerce")
    assert len(catalogue.programmes) == 71
    assert len(catalogue.courses) >= 316
    assert catalogue.data_issues == []
    assert {
        "cu020bus01",
        "cu021gsb48",
        "cu017acc01",
        "cb003bus01",
        "cb004eco01",
        "cb019bus01",
        "cb001acc04",
        "cb001phi03",
        "cb011bus06",
    } <= set(catalogue.programmes)


def test_every_commerce_programme_scope_loads_without_missing_references():
    catalogue = load_catalogue("uct_commerce")
    for programme_key in catalogue.programmes:
        scoped_catalogue, scope = build_programme_scope(
            "uct_commerce", catalogue, programme_key, ""
        )
        assert scope.status == "verified"
        assert scoped_catalogue.courses
        assert not scope.warnings


def test_programme_extraction_summary_contains_real_curriculum_rows():
    path = (
        Path(__file__).parents[1]
        / "data"
        / "uct_commerce"
        / "source_extraction"
        / "programme_extraction_summary.json"
    )
    summary = json.loads(path.read_text())
    assert len(summary) == 71
    assert all(item["course_rows"] > 0 for item in summary.values())
    assert summary["cb003bus01"]["course_rows"] >= 30
    assert summary["cu021gsb48"]["course_rows"] == 7


def test_published_course_fact_conflicts_are_preserved_for_review():
    path = (
        Path(__file__).parents[1]
        / "data"
        / "uct_commerce"
        / "source_extraction"
        / "course_fact_conflicts.json"
    )
    conflicts = json.loads(path.read_text())
    assert {row["course_code"] for row in conflicts} == {
        "BUS2016H",
        "BUS2033F",
        "BUS4028F",
        "ECO1111F",
        "ECO1111S",
    }
    assert all("faculty confirmation" in row["resolution"] for row in conflicts)


def test_commerce_is_enabled_on_faculty_endpoint():
    response = client.get("/faculties/uct_commerce")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "available"
    assert len(payload["programmes"]) == 71


def test_complete_management_development_diploma_can_be_eligible_and_distinguished():
    catalogue, student = complete_closed_record("cu021gsb48", 80)
    report = compute_report(student, catalogue)
    assert report.credits_completed == 120
    assert report.graduation_status == "eligible"
    assert report.distinction.qualification_eligible


def test_advanced_actuarial_diploma_requires_six_prescribed_and_two_electives():
    catalogue, _ = scoped("cu020bus01")
    programme = catalogue.programmes["cu020bus01"]
    elective = next(
        rule
        for rule in programme.curriculum_rules
        if rule.get("id") == "CU020BUS01_electives"
    )
    assert elective["type"] == "choose_n"
    assert elective["required"] == 2
    prescribed = {
        code
        for rule in programme.curriculum_rules
        if rule.get("type") in {"course", "any_of"}
        for code in rule.get("course_codes", [])
    }
    # The direct course rules are present even where substitutions are nested.
    text = json.dumps(programme.curriculum_rules)
    for code in (
        "STA3041F",
        "STA3045F",
        "STA3047S",
        "STA3048S",
        "BUS3018F",
        "BUS3024S",
    ):
        assert code in text


def test_advanced_actuarial_distinction_source_conflict_cannot_self_certify():
    catalogue, student = complete_closed_record("cu020bus01", 85)
    # Add two elective passes so the qualification curriculum itself is complete.
    elective_rule = next(
        rule
        for rule in catalogue.programmes["cu020bus01"].curriculum_rules
        if rule.get("id") == "CU020BUS01_electives"
    )
    for code in elective_rule["course_codes"][:2]:
        if not any(row.code == code for row in student.results):
            student.results.append(result(catalogue, code, 85))
    distinction = compute_report(student, catalogue).distinction
    assert not distinction.qualification_eligible
    assert distinction.status == "conflict"


def test_standard_and_extended_routes_do_not_share_the_same_scope():
    standard, _ = scoped("cb001eco02")
    extended, _ = scoped("cb011eco02")
    assert "DOC1103F" not in standard.courses
    assert "DOC1103F" in extended.courses
    assert standard.programmes["cb001eco02"].minimum_duration_years == 3
    assert extended.programmes["cb011eco02"].minimum_duration_years == 4


def test_chartered_accounting_courses_do_not_leak_into_management_studies():
    accounting, _ = scoped("cb001acc04")
    management, _ = scoped("cb001bus06")
    assert "ACC3009W" in accounting.courses
    assert "ACC3009W" not in management.courses


def test_actuarial_first_year_failure_is_flagged_as_progression_risk():
    catalogue, _ = scoped("cb019bus01")
    student = StudentRecord(
        "COM002",
        "Actuarial Student",
        "Bachelor of Commerce in Actuarial Science",
        [],
        [result(catalogue, "MAM1031F", 42, 2026, "F")],
        faculty_key="uct_commerce",
        programme_key="cb019bus01",
        years_registered=1,
    )
    risk = compute_report(student, catalogue).exclusion_risk
    assert risk.at_risk
    assert any("Actuarial first-year" in reason for reason in risk.reasons)


def test_twice_failed_required_course_is_flagged():
    catalogue, _ = scoped("cb001acc04")
    student = StudentRecord(
        "COM003",
        "Accounting Student",
        "BCom Financial Accounting",
        [],
        [
            result(catalogue, "ACC1006F", 40, 2025, "F"),
            result(catalogue, "ACC1006F", 45, 2026, "F"),
        ],
        faculty_key="uct_commerce",
        programme_key="cb001acc04",
        years_registered=2,
    )
    risk = compute_report(student, catalogue).exclusion_risk
    assert risk.at_risk
    assert any("more than 1 failed attempt" in reason for reason in risk.reasons)


def test_commerce_distinction_uses_the_first_attempt_not_the_later_pass():
    catalogue, _ = scoped("cb001eco02")
    student = StudentRecord(
        "COM004",
        "Economics Student",
        "BCom Economics and Finance",
        [],
        [
            result(catalogue, "ACC1021F", 40, 2025, "F"),
            result(catalogue, "ACC1021F", 95, 2026, "P"),
            result(catalogue, "ACC1022Z", 90, 2025, "P"),
        ],
        faculty_key="uct_commerce",
        programme_key="cb001eco02",
        years_registered=3,
    )
    award_rule = catalogue.programmes["cb001eco02"].award_rules[0]["curriculum_rules"][
        0
    ]
    evaluation = CurriculumEvaluator(student, catalogue).evaluate(award_rule)
    assert not evaluation.complete
    assert evaluation.current < 80
    assert "First-attempt" in evaluation.detail


def test_law_stream_keeps_competitive_course_allocation_as_discretionary():
    catalogue, student = complete_closed_record("cb001eco03", 85)
    report = compute_report(student, catalogue)
    allocation = next(
        row
        for row in report.requirements
        if row.id == "curriculum:law_place_allocation"
    )
    assert allocation.status == "discretionary"
    assert allocation.blocking
    assert report.graduation_status != "eligible"


def test_management_studies_source_credit_conflict_is_not_silently_resolved():
    catalogue, _ = scoped("cb001bus06")
    conflict = next(
        rule
        for rule in catalogue.programmes["cb001bus06"].curriculum_rules
        if rule.get("id") == "CB001BUS06_credit_conflict"
    )
    assert conflict["status"] == "conflict"
    assert conflict["blocking"]


def test_commerce_programme_code_inference_preserves_exact_route():
    assert _infer_programme_key("Bachelor of Commerce CB001ECO02") == "cb001eco02"
    assert _infer_programme_key("BBusSci CB25BUS09") == "cb025bus09"
