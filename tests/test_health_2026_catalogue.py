from fastapi.testclient import TestClient

from app import app
from engine.catalogue import load_catalogue
from engine.models import CourseResult, StudentRecord
from engine.rule_engine import compute_report
from engine.scope import build_programme_scope

client = TestClient(app)


def scoped(programme: str, pathway: str = ""):
    full = load_catalogue("uct_health")
    return build_programme_scope("uct_health", full, programme, pathway)


def result(
    catalogue,
    code: str,
    mark: int | None = 75,
    year: int = 2026,
    grade: str | None = None,
):
    fact = catalogue.courses[code]
    return CourseResult(
        code,
        fact.name,
        fact.nqf_level,
        fact.nqf_credits,
        mark if fact.nqf_credits else None,
        grade or ("P" if fact.nqf_credits else "PA"),
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


def complete_structured_record(programme: str, pathway: str = "", mark: int = 80):
    catalogue, _ = scoped(programme, pathway)
    programme_rules = catalogue.programmes[programme]
    codes = list(programme_rules.required_courses)
    for rule in programme_rules.curriculum_rules:
        codes.extend(choose_codes(rule))
    if pathway:
        for rule in programme_rules.pathways[pathway].curriculum_rules:
            codes.extend(choose_codes(rule))
    codes = list(dict.fromkeys(code for code in codes if code in catalogue.courses))
    rows = [
        result(catalogue, code, mark, 2024 + index // 10)
        for index, code in enumerate(codes)
    ]
    student = StudentRecord(
        "HLT001",
        "Health Student",
        programme_rules.name,
        [],
        rows,
        faculty_key="uct_health",
        programme_key=programme,
        pathway_key=pathway,
        years_registered=programme_rules.minimum_duration_years,
    )
    return catalogue, student


def test_health_catalogue_contains_all_undergraduate_routes():
    catalogue = load_catalogue("uct_health")
    assert len(catalogue.programmes) == 14
    assert len(catalogue.courses) >= 400
    assert catalogue.data_issues == []
    assert {
        "mbchb",
        "mbchb_fundamentals",
        "bsc_medicine",
        "bsc_audiology",
        "bsc_speech_language_pathology",
        "bsc_occupational_therapy",
        "bsc_physiotherapy",
        "higher_certificate_disability_practice",
        "advanced_diploma_cosmetic_formulation",
        "nmfc_medical_training",
    } <= set(catalogue.programmes)


def test_all_health_scopes_load_without_missing_course_references():
    catalogue = load_catalogue("uct_health")
    for programme_key, programme in catalogue.programmes.items():
        pathways = list(programme.pathways) or [""]
        for pathway in pathways:
            scoped_catalogue, scope = build_programme_scope(
                "uct_health", catalogue, programme_key, pathway
            )
            assert scope.status == "verified"
            assert scoped_catalogue.courses
            assert not scope.warnings


def test_health_is_enabled_on_faculty_endpoint():
    response = client.get("/faculties/uct_health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "available"
    assert len(payload["programmes"]) == 14


def test_complete_cosmetic_diploma_record_can_be_eligible_and_distinguished():
    catalogue, student = complete_structured_record(
        "advanced_diploma_cosmetic_formulation"
    )
    report = compute_report(student, catalogue)
    assert report.credits_completed == 120
    assert report.graduation_status == "eligible"
    assert report.distinction.qualification_eligible


def test_complete_audiology_record_still_requires_clinical_verification():
    catalogue, student = complete_structured_record("bsc_audiology")
    report = compute_report(student, catalogue)
    assert report.credits_completed >= 480
    assert report.graduation_status == "requires_verification"
    assert any(
        row.id == "curriculum:clinical_professional_confirmation"
        and row.status == "unverified"
        for row in report.requirements
    )


def test_fundamentals_route_requires_fundamentals_course():
    catalogue, student = complete_structured_record("bsc_physiotherapy_fundamentals")
    student.results = [
        row for row in student.results if row.code not in {"HSE1001F", "HSE1001S"}
    ]
    report = compute_report(student, catalogue)
    row = next(
        item
        for item in report.requirements
        if item.id == "curriculum:fundamentals_course"
    )
    assert not row.complete
    assert report.graduation_status == "not_eligible"


def test_audiology_and_speech_language_routes_are_isolated():
    audiology, _ = scoped("bsc_audiology")
    speech, _ = scoped("bsc_speech_language_pathology")
    assert "AHS4008H" in audiology.courses
    assert "AHS4008H" not in speech.courses
    assert "AHS4005H" in speech.courses
    assert "AHS4005H" not in audiology.courses


def test_complete_mbchb_record_cannot_self_certify_clinical_conditions():
    catalogue, student = complete_structured_record("mbchb", "gpa_2024_plus")
    report = compute_report(student, catalogue)
    assert report.credits_completed >= 1214
    assert report.graduation_status == "requires_verification"
    assert report.distinction.qualification_eligible


def test_bsc_medicine_credit_and_level_rules_can_be_satisfied():
    catalogue, _ = scoped("bsc_medicine")
    codes = [
        "HUB1006F",
        "IBS1007S",
        "PHY1025F",
        "PTY2000S",
        "HUB2017H",
        "MDN2001S",
        "FCE2000W",
        "SLL2002H",
        "PTY3009F",
        "HUB3006F",
        "HUB3007S",
        "IBS3020W",
        "AHS3078H",
    ]
    rows = [result(catalogue, code, 80) for code in codes]
    student = StudentRecord(
        "HLT002",
        "BSc Medicine Student",
        "BSc Medicine",
        [],
        rows,
        faculty_key="uct_health",
        programme_key="bsc_medicine",
        years_registered=1,
    )
    report = compute_report(student, catalogue)
    assert report.credits_completed >= 360
    assert report.level_7_credits >= 120
    assert report.graduation_status == "eligible"


def test_nmfc_route_never_claims_a_uct_medical_qualification_from_static_record():
    catalogue, student = complete_structured_record("nmfc_medical_training")
    report = compute_report(student, catalogue)
    assert report.credits_completed >= 281
    assert report.graduation_status == "requires_verification"
    assert any(
        row.id == "curriculum:nmfc_external_award" for row in report.requirements
    )


def test_first_year_health_failure_group_is_flagged():
    catalogue, _ = scoped("bsc_occupational_therapy")
    rows = [
        result(catalogue, "PPH1001F", 40, 2026, "F"),
        result(catalogue, "HUB1019F", 42, 2026, "F"),
        result(catalogue, "AHS1035F", 65, 2026),
    ]
    student = StudentRecord(
        "HLT003",
        "OT Student",
        "BSc Occupational Therapy",
        [],
        rows,
        faculty_key="uct_health",
        programme_key="bsc_occupational_therapy",
        years_registered=1,
    )
    risk = compute_report(student, catalogue).exclusion_risk
    assert risk.at_risk
    assert any("first-year semester" in reason.lower() for reason in risk.reasons)


def test_failure_during_repeat_year_is_flagged():
    catalogue, _ = scoped("bsc_physiotherapy")
    rows = [
        result(catalogue, "PPH1001F", 40, 2025, "F"),
        result(catalogue, "PPH1001F", 55, 2026, "P"),
        result(catalogue, "HUB1019F", 40, 2026, "F"),
    ]
    student = StudentRecord(
        "HLT004",
        "Physio Student",
        "BSc Physiotherapy",
        [],
        rows,
        faculty_key="uct_health",
        programme_key="bsc_physiotherapy",
        years_registered=2,
    )
    risk = compute_report(student, catalogue).exclusion_risk
    assert risk.at_risk
    assert any("repeat year" in reason.lower() for reason in risk.reasons)


def test_mbchb_equivalent_block_code_satisfies_canonical_course_rule():
    catalogue, student = complete_structured_record("mbchb", "gpa_2024_plus")
    student.results = [row for row in student.results if row.code != "AAE4002W"]
    student.results.append(result(catalogue, "AAE4102X", 70, 2027))
    report = compute_report(student, catalogue)
    row = next(
        item
        for item in report.requirements
        if item.id == "curriculum:mbchb_y4_aae4002w"
    )
    assert row.complete


def test_disability_certificate_accepts_combined_course_layout():
    catalogue, _ = scoped("higher_certificate_disability_practice")
    codes = ["AHS1068W", "AHS1062F", "AHS1069W", "AHS1065F", "AHS1070W"]
    student = StudentRecord(
        "HLT005",
        "Certificate Student",
        "Higher Certificate in Disability Practice",
        [],
        [result(catalogue, code, 70) for code in codes],
        faculty_key="uct_health",
        programme_key="higher_certificate_disability_practice",
        years_registered=1,
    )
    report = compute_report(student, catalogue)
    curriculum = next(
        row
        for row in report.requirements
        if row.id == "curriculum:disability_curriculum"
    )
    assert curriculum.complete
    assert report.credits_completed == 120
