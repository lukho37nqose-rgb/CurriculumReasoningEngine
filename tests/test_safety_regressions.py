import json

import pytest
from fastapi.testclient import TestClient

from app import app
from engine.catalogue import load_catalogue
from engine.knowledge_graph import KnowledgeGraph
from engine.models import (
    Catalogue,
    CourseFact,
    CourseResult,
    MajorDefinition,
    ProgrammeRules,
    StudentRecord,
)
from engine.rule_engine import (
    _compute_eligible_courses,
    _compute_major_progress,
    _prereqs_met,
    compute_report,
)
from engine.simulator import SimulationEngine


client = TestClient(app)


def _programme(**overrides):
    values = dict(
        key="bsocsc_regular",
        name="Test Programme",
        total_nqf_credits=18,
        level_7_nqf_credits=0,
        semester_course_equivalents=1,
        senior_course_equivalents=0,
        humanities_course_equivalents=0,
        required_majors=0,
        required_humanities_majors=0,
        minimum_duration_years=1,
    )
    values.update(overrides)
    return ProgrammeRules(**values)


def _catalogue(courses=None, majors=None, programmes=None):
    if courses is None:
        courses = {
            "AAA1001F": CourseFact("AAA1001F", "Course", 18, 5, [], ["Semester 1"], "Test")
        }
    return Catalogue(
        courses=courses,
        majors=majors or {},
        programmes=programmes if programmes is not None else {"bsocsc_regular": _programme()},
        forbidden_combinations=[],
    )


def test_catalogue_loader_prefers_explicit_nqf_level(tmp_path):
    courses_path = tmp_path / "courses.json"
    requirements_path = tmp_path / "degree_requirements.json"
    courses_path.write_text(json.dumps([{
        "code": "CML4504S",
        "name": "Trademarks",
        "credits": 18,
        "nqf_level": 8,
        "prerequisites": [],
        "offered": ["Semester 2"],
        "department": "Commercial Law",
    }]))
    requirements_path.write_text(json.dumps({"programmes": {}, "majors": {}}))

    catalogue = load_catalogue(
        "unused",
        courses_path=courses_path,
        requirements_path=requirements_path,
    )

    assert catalogue.courses["CML4504S"].nqf_level == 8


def test_duplicate_passing_rows_award_credits_once():
    student = StudentRecord(
        student_id="T1",
        name="Duplicate Student",
        programme="Test",
        declared_majors=[],
        results=[
            CourseResult("AAA1001F", "Course", 5, 18, 60, "2-"),
            CourseResult("AAA1001F", "Course", 5, 18, 70, "2+"),
        ],
        programme_key="bsocsc_regular",
    )

    report = compute_report(student, _catalogue())

    assert report.credits_completed == 18
    assert report.semester_course_equivalents == 1


def test_later_pass_is_used_after_earlier_failure():
    student = StudentRecord(
        student_id="T2",
        name="Repeat Student",
        programme="Test",
        declared_majors=[],
        results=[
            CourseResult("AAA1001F", "Course", 5, 18, 40, "F"),
            CourseResult("AAA1001F", "Course", 5, 18, 65, "2-"),
        ],
        programme_key="bsocsc_regular",
    )

    assert student.result_for("AAA1001F").mark == 65
    assert student.passed_result_for("AAA1001F").mark == 65
    assert compute_report(student, _catalogue()).credits_completed == 18


def test_empty_major_definition_never_counts_as_complete():
    major = MajorDefinition(
        key="empty",
        name="Empty Major",
        qualification="HUMANITIES",
        required_courses=[],
        choice_groups=[],
    )
    student = StudentRecord("T3", "Student", "Test", ["Empty Major"], [])

    progress = _compute_major_progress(major, student)

    assert progress.complete is False
    assert progress.status == "unverified"


def test_unsuffixed_handbook_prerequisite_matches_transcript_variant():
    course = CourseFact(
        code="ECO2008S",
        name="Course",
        nqf_credits=24,
        nqf_level=6,
        prerequisites=["ECO1010"],
        offered=["Semester 2"],
        department="Economics",
    )

    assert _prereqs_met(course, {"ECO1010F"}) is True
    assert _prereqs_met(course, {"ECO1009F"}) is False


def test_unrelated_postgraduate_course_is_not_suggested_as_elective():
    courses = {
        "AAA1001F": CourseFact("AAA1001F", "Undergrad", 18, 5, [], ["Semester 1"], "Dept"),
        "AAA5001F": CourseFact("AAA5001F", "Postgrad", 24, 9, [], ["Semester 1"], "Dept"),
    }
    student = StudentRecord("T4", "Student", "Test", [], [])

    suggested = _compute_eligible_courses(student, _catalogue(courses=courses))

    assert [course.code for course in suggested] == ["AAA1001F"]
    assert suggested[0].status == "provisional"
    assert suggested[0].limitations


def test_unknown_programme_cannot_produce_positive_graduation_result():
    student = StudentRecord(
        "T5",
        "Student",
        "Unmapped Specialist Degree",
        [],
        [CourseResult("AAA1001F", "Course", 5, 18, 75, "1")],
    )
    catalogue = _catalogue(programmes={})

    report = compute_report(student, catalogue)

    assert report.graduation_eligible is False
    assert report.graduation_status == "not_eligible"
    programme_check = next(r for r in report.requirements if r.id == "qualification_match")
    assert programme_check.complete is False
    assert programme_check.status == "unverified"


def test_generic_programme_never_becomes_definitively_eligible():
    student = StudentRecord(
        "T6",
        "Student",
        "Bachelor of Social Science",
        [],
        [CourseResult("AAA1001F", "Course", 5, 18, 75, "1")],
    )

    report = compute_report(student, _catalogue())

    assert all(r.complete for r in report.requirements if r.blocking)
    assert report.graduation_eligible is False
    assert report.graduation_status == "requires_verification"


def test_simulation_rejects_unknown_course():
    catalogue = _catalogue(courses={
        "AAA1001F": CourseFact("AAA1001F", "Course", 18, 5, [], ["Semester 1"], "Dept")
    })
    student = StudentRecord("T7", "Student", "Test", [], [])
    engine = SimulationEngine(student, catalogue, KnowledgeGraph(catalogue))

    with pytest.raises(ValueError, match="not present"):
        engine.simulate_pass_course("FAKE1000F", 70)


def test_invalid_faculty_does_not_fall_back_to_humanities():
    response = client.post(
        "/analyse/json",
        json={
            "faculty": "../../uct_humanities",
            "student_id": "T8",
            "name": "Student",
            "programme": "Bachelor of Social Science",
            "declared_majors": [],
            "results": [],
        },
    )

    assert response.status_code == 422
    assert "Unknown faculty selection" in response.json()["detail"]


def test_unknown_programme_does_not_implicitly_route_to_humanities():
    response = client.post(
        "/analyse/json",
        json={
            "student_id": "T8B",
            "name": "Student",
            "programme": "Unmapped Specialist Credential",
            "declared_majors": [],
            "results": [],
        },
    )

    assert response.status_code == 422
    assert "faculty selection is required" in response.json()["detail"].lower()


def test_api_rejects_out_of_range_mark():
    response = client.post(
        "/analyse/json",
        json={
            "student_id": "T9",
            "name": "Student",
            "programme": "Bachelor of Social Science",
            "declared_majors": [],
            "results": [{
                "code": "AAA1001F",
                "name": "Course",
                "nqf_level": 5,
                "nqf_credits": 18,
                "mark": 101,
            }],
        },
    )

    assert response.status_code == 422
    assert "outside 0-100" in response.json()["detail"]


def test_knowledge_graph_links_suffixless_prerequisite_variants():
    courses = {
        "ECO1010F": CourseFact("ECO1010F", "Econ 1", 18, 5, [], ["Semester 1"], "Economics"),
        "ECO1010S": CourseFact("ECO1010S", "Econ 1", 18, 5, [], ["Semester 2"], "Economics"),
        "ECO2008S": CourseFact("ECO2008S", "Econ 2", 24, 6, ["ECO1010"], ["Semester 2"], "Economics"),
    }
    graph = KnowledgeGraph(_catalogue(courses=courses))

    assert "ECO2008S" in graph.get_unlocked_courses("ECO1010F")
    assert "ECO2008S" in graph.get_unlocked_courses("ECO1010S")
    assert graph.get_prerequisites("ECO2008S") == {"ECO1010"}
