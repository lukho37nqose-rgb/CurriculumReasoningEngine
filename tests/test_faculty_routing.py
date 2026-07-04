from fastapi.testclient import TestClient

from app import app, get_catalogue
from engine.models import (
    Catalogue,
    CourseFact,
    MajorDefinition,
    ProgrammeRules,
    StudentRecord,
)
from engine.rule_engine import _compute_eligible_courses, compute_report
from engine.scope import build_programme_scope

client = TestClient(app)


def _catalogue_for_scope() -> Catalogue:
    courses = {
        "AAA1001F": CourseFact(
            "AAA1001F", "Major A Intro", 18, 5, [], ["Semester 1"], "A"
        ),
        "AAA2001S": CourseFact(
            "AAA2001S", "Major A Senior", 18, 6, ["AAA1001F"], ["Semester 2"], "A"
        ),
        "BBB1001F": CourseFact(
            "BBB1001F", "Other Major Intro", 18, 5, [], ["Semester 1"], "B"
        ),
        "ELE1001S": CourseFact(
            "ELE1001S",
            "Approved Elective",
            18,
            5,
            [],
            ["Semester 2"],
            "Electives",
            verification_status="verified",
        ),
        "OUT1001F": CourseFact(
            "OUT1001F", "Outside Programme", 18, 5, [], ["Semester 1"], "Outside"
        ),
    }
    majors = {
        "major_a": MajorDefinition(
            "major_a", "Major A", "TEST", ["AAA1001F", "AAA2001S"]
        ),
        "major_b": MajorDefinition("major_b", "Major B", "TEST", ["BBB1001F"]),
    }
    programmes = {
        "degree_a": ProgrammeRules(
            key="degree_a",
            name="Degree A",
            total_nqf_credits=360,
            level_7_nqf_credits=120,
            semester_course_equivalents=20,
            senior_course_equivalents=10,
            humanities_course_equivalents=0,
            required_majors=1,
            required_humanities_majors=0,
            major_keys=["major_a"],
            elective_course_codes=["ELE1001S"],
            scope_verified=True,
        )
    }
    return Catalogue(courses, majors, programmes, [])


def test_landing_returns_all_faculty_destinations():
    response = client.get("/faculties")
    assert response.status_code == 200
    faculties = response.json()
    assert {faculty["key"] for faculty in faculties} == {
        "uct_commerce",
        "uct_ebe",
        "uct_health",
        "uct_humanities",
        "uct_law",
        "uct_science",
    }
    assert all("programmes" in faculty for faculty in faculties)


def test_faculty_destination_serves_frontend():
    response = client.get("/faculty/uct_humanities")
    assert response.status_code == 200
    assert "Which faculty governs your qualification?" in response.text
    assert "programmeSelect" in response.text


def test_analysis_rejects_missing_explicit_scope():
    response = client.post(
        "/analyse/json",
        json={
            "student_id": "T1",
            "name": "Student",
            "programme": "Bachelor of Social Science",
            "declared_majors": [],
            "results": [],
        },
    )
    assert response.status_code == 422
    assert "faculty selection is required" in response.json()["detail"].lower()


def test_unknown_programme_is_rejected_within_selected_faculty():
    response = client.post(
        "/analyse/json",
        json={
            "faculty": "uct_humanities",
            "programme_key": "not_a_programme",
            "student_id": "T1",
            "name": "Student",
            "programme": "Bachelor of Social Science",
            "declared_majors": [],
            "results": [],
        },
    )
    assert response.status_code == 422
    assert "Unknown programme" in response.json()["detail"]


def test_programme_scope_excludes_other_majors_and_outside_courses():
    scoped, scope = build_programme_scope(
        "test_faculty", _catalogue_for_scope(), "degree_a"
    )
    assert scope.status == "verified"
    assert set(scoped.majors) == {"major_a"}
    assert set(scoped.courses) == {"AAA1001F", "AAA2001S", "ELE1001S"}
    assert "BBB1001F" not in scoped.courses
    assert "OUT1001F" not in scoped.courses


def test_recommendations_use_declared_major_and_explicit_electives_only():
    scoped, _ = build_programme_scope(
        "test_faculty", _catalogue_for_scope(), "degree_a"
    )
    student = StudentRecord(
        "T2",
        "Student",
        "Degree A",
        ["Major A"],
        [],
        faculty_key="test_faculty",
        programme_key="degree_a",
    )
    eligible = _compute_eligible_courses(student, scoped)
    assert {course.code for course in eligible} == {"AAA1001F", "ELE1001S"}
    elective = next(course for course in eligible if course.code == "ELE1001S")
    assert elective.status == "verified"


def test_verified_scope_metadata_is_carried_into_report():
    scoped, _ = build_programme_scope(
        "test_faculty", _catalogue_for_scope(), "degree_a"
    )
    student = StudentRecord(
        "T3",
        "Student",
        "Degree A",
        ["Major A"],
        [],
        faculty_key="test_faculty",
        programme_key="degree_a",
    )
    report = compute_report(student, scoped)
    assert report.faculty_key == "test_faculty"
    assert report.programme_key == "degree_a"
    assert report.programme_name == "Degree A"
    assert report.scope_status == "verified"


def test_2026_humanities_catalogue_has_verified_programme_scope():
    full = get_catalogue("uct_humanities")
    scoped, scope = build_programme_scope("uct_humanities", full, "bsocsc_regular")
    assert scope.status == "verified"
    assert len(scoped.courses) < len(full.courses)
    assert scoped.elective_course_codes
    assert {"ba_regular", "bsocsc_regular", "ba_extended", "bsocsc_extended"} <= set(
        full.programmes
    )
    assert len(full.programmes) == 24
