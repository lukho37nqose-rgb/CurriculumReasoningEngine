from fastapi.testclient import TestClient

from app import app
from engine.catalogue import load_catalogue
from engine.models import CourseResult, StudentRecord
from engine.rule_engine import compute_report
from engine.scope import build_programme_scope

client = TestClient(app)


def scoped(programme="bsc_science", pathway="current_2023_plus"):
    full = load_catalogue("uct_science")
    catalogue, scope = build_programme_scope("uct_science", full, programme, pathway)
    return catalogue, scope


def result(catalogue, code, mark=65, year=2026):
    fact = catalogue.courses[code]
    return CourseResult(
        code, fact.name, fact.nqf_level, fact.nqf_credits, mark, "P", year
    )


def chemistry_record(mark=65, years=3):
    catalogue, _ = scoped()
    required = [
        "CEM1000W",
        "MAM1031F",
        "MAM1032S",
        "PHY1031F",
        "PHY1032S",
        "CEM2005W",
        "CEM3005W",
    ]
    selected = list(required)
    credits = sum(catalogue.courses[c].nqf_credits for c in selected)
    level7 = sum(
        catalogue.courses[c].nqf_credits
        for c in selected
        if catalogue.courses[c].nqf_level == 7
    )
    for code, fact in sorted(catalogue.courses.items()):
        if code in selected or not fact.general_elective or not fact.credit_bearing:
            continue
        selected.append(code)
        credits += fact.nqf_credits
        if fact.nqf_level == 7:
            level7 += fact.nqf_credits
        if credits >= 360 and level7 >= 120:
            break
    rows = [
        result(catalogue, code, mark, 2024 + min(index // 8, 2))
        for index, code in enumerate(selected)
    ]
    student = StudentRecord(
        "SCI001",
        "Science Student",
        "Bachelor of Science",
        ["Chemistry"],
        rows,
        faculty_key="uct_science",
        programme_key="bsc_science",
        pathway_key="current_2023_plus",
        years_registered=years,
    )
    return catalogue, student


def test_science_catalogue_routes_and_majors_are_complete():
    catalogue = load_catalogue("uct_science")
    assert set(catalogue.programmes) == {"bsc_science", "bsc_science_edp"}
    assert len(catalogue.majors) == 22
    assert len(catalogue.courses) >= 240
    assert catalogue.data_issues == []


def test_all_science_cohort_scopes_are_verified():
    catalogue = load_catalogue("uct_science")
    for programme in catalogue.programmes:
        for pathway in catalogue.programmes[programme].pathways:
            scoped_catalogue, scope = build_programme_scope(
                "uct_science", catalogue, programme, pathway
            )
            assert scope.status == "verified"
            assert len(scoped_catalogue.majors) == 22
            assert not scope.warnings


def test_science_is_enabled_on_faculty_endpoint():
    response = client.get("/faculties/uct_science")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "available"
    assert len(payload["programmes"]) == 2
    assert {p["key"] for p in payload["programmes"]} == {
        "bsc_science",
        "bsc_science_edp",
    }


def test_complete_verified_chemistry_record_can_be_eligible():
    catalogue, student = chemistry_record()
    report = compute_report(student, catalogue)
    assert report.credits_completed >= 360
    assert report.level_7_credits >= 120
    assert report.majors[0].complete
    assert report.majors[0].status == "verified"
    assert report.graduation_status == "eligible"


def test_computer_engineering_requires_computer_science_co_major():
    catalogue, _ = scoped()
    student = StudentRecord(
        "SCI002",
        "Student",
        "Bachelor of Science",
        ["Computer Engineering"],
        [],
        faculty_key="uct_science",
        programme_key="bsc_science",
        pathway_key="current_2023_plus",
        years_registered=1,
    )
    report = compute_report(student, catalogue)
    row = next(
        r
        for r in report.requirements
        if r.id == "major_co_requirement:computer_engineering"
    )
    assert not row.complete
    assert "computer_science" in row.detail


def test_statistics_major_combinations_are_forbidden():
    catalogue, _ = scoped()
    student = StudentRecord(
        "SCI003",
        "Student",
        "Bachelor of Science",
        ["Applied Statistics", "Mathematical Statistics"],
        [],
        faculty_key="uct_science",
        programme_key="bsc_science",
        pathway_key="current_2023_plus",
        years_registered=1,
    )
    report = compute_report(student, catalogue)
    row = next(r for r in report.requirements if r.id == "major_combination")
    assert not row.complete


def test_limited_major_completion_still_requires_admission_verification():
    catalogue, _ = scoped()
    major = catalogue.majors["biochemistry"]
    codes = sorted({code for rule in major.curriculum_rules for code in _codes(rule)})
    rows = [result(catalogue, code) for code in codes if code in catalogue.courses]
    student = StudentRecord(
        "SCI004",
        "Student",
        "Bachelor of Science",
        ["Biochemistry"],
        rows,
        faculty_key="uct_science",
        programme_key="bsc_science",
        pathway_key="current_2023_plus",
        years_registered=3,
    )
    report = compute_report(student, catalogue)
    assert report.majors[0].status == "unverified"
    assert any("capacity-limited" in warning for warning in report.warnings)


def test_current_regular_first_year_progression_uses_science_credits():
    catalogue, _ = scoped()
    rows = [
        result(catalogue, "BIO1000F"),
        result(catalogue, "AGE1002S"),
        result(catalogue, "GEO1009F"),
    ]
    student = StudentRecord(
        "SCI005",
        "Student",
        "Bachelor of Science",
        ["Biology"],
        rows,
        faculty_key="uct_science",
        programme_key="bsc_science",
        pathway_key="current_2023_plus",
        years_registered=1,
    )
    risk = compute_report(student, catalogue).exclusion_risk
    assert risk.at_risk
    assert any("72" in reason for reason in risk.reasons)


def test_non_science_transcript_only_elective_is_provisional():
    catalogue, student = chemistry_record()
    student.results.append(
        CourseResult("POL1004F", "Introduction to Politics", 5, 18, 70, "P", 2024)
    )
    report = compute_report(student, catalogue)
    assert report.credits_completed >= 378
    assert report.graduation_status == "requires_verification"
    assert any("POL1004F" in warning for warning in report.warnings)


def test_science_distinction_excludes_supplementary_passes():
    catalogue, student = chemistry_record(mark=80)
    for row in student.results:
        if row.code == "CEM3005W":
            row.grade = "SP"
    distinction = compute_report(student, catalogue).distinction
    chemistry = next(
        subject for subject in distinction.subjects if subject.major == "Chemistry"
    )
    assert not chemistry.eligible
    assert "supplementary" in chemistry.reason.lower()


def _codes(rule):
    output = set(rule.get("course_codes", []))
    for child in rule.get("children", []):
        output.update(_codes(child))
    return output
