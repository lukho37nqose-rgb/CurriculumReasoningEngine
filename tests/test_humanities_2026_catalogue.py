from fastapi.testclient import TestClient

from app import app
from engine.catalogue import load_catalogue
from engine.models import CourseResult, StudentRecord
from engine.rule_engine import _compute_eligible_courses, compute_report
from engine.scope import build_programme_scope
from engine.utils import _course_weight

client = TestClient(app)


def test_humanities_catalogue_has_all_routes_and_four_general_degrees():
    catalogue = load_catalogue("uct_humanities")
    general = {"ba_regular", "bsocsc_regular", "ba_extended", "bsocsc_extended"}
    assert general <= set(catalogue.programmes)
    assert len(catalogue.programmes) == 24
    assert len(catalogue.majors) == 42
    assert not catalogue.data_issues
    for key in general:
        _, scope = build_programme_scope("uct_humanities", catalogue, key)
        assert scope.status == "verified"


def test_regular_and_extended_route_rules_match_2026_handbook_structure():
    catalogue = load_catalogue("uct_humanities")
    regular = catalogue.programmes["bsocsc_regular"]
    extended = catalogue.programmes["bsocsc_extended"]
    assert (regular.minimum_duration_years, regular.maximum_registration_years) == (3, 4)
    assert (extended.minimum_duration_years, extended.maximum_registration_years) == (4, 5)
    assert regular.semester_course_equivalents == extended.semester_course_equivalents == 20
    assert regular.senior_course_equivalents == extended.senior_course_equivalents == 10
    assert regular.humanities_course_equivalents == extended.humanities_course_equivalents == 12
    assert extended.introductory_courses_required == 2
    assert extended.augmenting_courses_required == 3
    assert extended.max_courses_per_semester == 3


def test_half_course_taught_through_year_counts_as_one_semester_equivalent():
    assert _course_weight("MUZ1201H") == 1.0
    assert _course_weight("PVL1003W") == 2.0
    assert _course_weight("PHI1024F") == 1.0


def test_status_only_results_follow_general_rules_failure_classification():
    for grade in ("AB", "DPR", "INC"):
        result = CourseResult("AAA1001F", "Course", 5, 15, None, grade)
        assert result.is_failed()
        assert not result.is_passed()
    for grade in ("PA", "UP", "SP"):
        result = CourseResult("AAA1001F", "Course", 5, 15, None, grade)
        assert result.is_passed()


def test_not_offered_course_is_never_recommended():
    full = load_catalogue("uct_humanities")
    scoped, _ = build_programme_scope("uct_humanities", full, "bsocsc_regular")
    student = StudentRecord(
        "T1", "Student", "Bachelor of Social Science", ["Anthropology"], [],
        faculty_key="uct_humanities", programme_key="bsocsc_regular",
    )
    suggested = {course.code for course in _compute_eligible_courses(student, scoped)}
    assert "ANS2404S" not in suggested


def test_degree_title_rejects_two_ba_humanities_majors_for_bsocsc():
    full = load_catalogue("uct_humanities")
    scoped, _ = build_programme_scope("uct_humanities", full, "bsocsc_regular")
    student = StudentRecord(
        "T2", "Student", "Bachelor of Social Science", ["History", "Literary Studies"], [],
        faculty_key="uct_humanities", programme_key="bsocsc_regular", years_registered=3,
    )
    report = compute_report(student, scoped)
    identity = next(req for req in report.requirements if req.id == "degree_major_identity")
    assert not identity.complete


def test_mixed_ba_and_bsocsc_humanities_majors_fit_either_general_degree_title():
    full = load_catalogue("uct_humanities")
    scoped, _ = build_programme_scope("uct_humanities", full, "bsocsc_regular")
    student = StudentRecord(
        "T3", "Student", "Bachelor of Social Science", ["History", "Philosophy"], [],
        faculty_key="uct_humanities", programme_key="bsocsc_regular", years_registered=3,
    )
    report = compute_report(student, scoped)
    identity = next(req for req in report.requirements if req.id == "degree_major_identity")
    assert identity.complete


def test_extended_report_contains_introductory_and_augmenting_requirements():
    full = load_catalogue("uct_humanities")
    scoped, _ = build_programme_scope("uct_humanities", full, "ba_extended")
    student = StudentRecord(
        "T4", "Student", "Bachelor of Arts Extended", ["History", "Literary Studies"], [],
        faculty_key="uct_humanities", programme_key="ba_extended", years_registered=4,
    )
    report = compute_report(student, scoped)
    requirement_ids = {req.id for req in report.requirements}
    assert {"extended_introductory", "extended_augmenting"}.issubset(requirement_ids)


def test_programme_endpoint_exposes_verified_humanities_route():
    response = client.get(
        "/programme",
        params={"faculty_key": "uct_humanities", "programme_key": "ba_regular"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["scope"]["status"] == "verified"
    assert data["programme"]["qualification_codes"] == ["HB003"]
    assert data["major_count"] == 42


def test_unknown_science_programme_is_rejected():
    response = client.post(
        "/analyse/json",
        json={
            "faculty": "uct_science", "programme_key": "generic_undergraduate",
            "student_id": "T5", "name": "Student", "programme": "BSc",
            "declared_majors": [], "results": [],
        },
    )
    assert response.status_code == 422
    assert "Unknown programme" in response.json()["detail"]


def _passed(code: str, mark: int = 65) -> CourseResult:
    return CourseResult(code, code, 0, 0, mark, None)


def test_tdp_recognition_boundary_matches_fb5_2_and_keeps_the_major_pathway():
    catalogue = load_catalogue("uct_humanities")
    recognised = {
        code for code, fact in catalogue.courses.items()
        if code.startswith("TDP") and fact.counts_towards_general_degree
    }
    assert recognised == {
        "TDP1017H", "TDP1018H", "TDP1027F", "TDP1045S",
        "TDP2010F", "TDP2014S", "TDP3010F", "TDP3018S",
    }
    assert catalogue.courses["TDP1027F"].department == "Centre for Theatre, Dance and Performance Studies"


def test_extended_support_courses_add_credits_but_not_twenty_subject_course_equivalents():
    full = load_catalogue("uct_humanities")
    scoped, _ = build_programme_scope("uct_humanities", full, "bsocsc_extended")
    student = StudentRecord(
        "T6", "Student", "Bachelor of Social Science Extended", [],
        [_passed("DOH1002F"), _passed("MAM1022F"), _passed("ANS1403S")],
        faculty_key="uct_humanities", programme_key="bsocsc_extended", years_registered=1,
    )
    report = compute_report(student, scoped)
    assert report.credits_completed == 66
    assert report.semester_course_equivalents == 0
    assert any("not toward the 20 semester subject-course requirement" in warning for warning in report.warnings)


def test_music_recognition_limit_prevents_credit_inflation():
    full = load_catalogue("uct_humanities")
    scoped, _ = build_programme_scope("uct_humanities", full, "ba_regular")
    codes = ["MUZ1201H", "MUZ1204H", "MUZ1207H", "MUZ1211H", "MUZ1215H"]
    student = StudentRecord(
        "T7", "Student", "Bachelor of Arts", [], [_passed(code) for code in codes],
        faculty_key="uct_humanities", programme_key="ba_regular", years_registered=1,
    )
    report = compute_report(student, scoped)
    assert report.credits_completed == 120
    assert report.semester_course_equivalents == 4
    assert any("Music-course recognition limit applied" in warning for warning in report.warnings)
    assert any("MUZ1215H" in warning for warning in report.warnings)


def test_first_year_non_humanities_course_is_only_recommended_inside_selected_external_major():
    full = load_catalogue("uct_humanities")
    scoped, _ = build_programme_scope("uct_humanities", full, "bsocsc_regular")
    no_major = StudentRecord(
        "T8", "Student", "Bachelor of Social Science", [], [],
        faculty_key="uct_humanities", programme_key="bsocsc_regular",
    )
    no_major_suggestions = {course.code for course in _compute_eligible_courses(no_major, scoped)}
    assert "BUS1007S" not in no_major_suggestions

    external_major = StudentRecord(
        "T9", "Student", "Bachelor of Social Science",
        ["Industrial and Organisational Psychology"], [],
        faculty_key="uct_humanities", programme_key="bsocsc_regular",
    )
    suggestions = {course.code for course in _compute_eligible_courses(external_major, scoped)}
    assert "BUS1007S" in suggestions


def test_only_extended_routes_expose_introductory_and_augmenting_support_courses():
    full = load_catalogue("uct_humanities")
    regular, _ = build_programme_scope("uct_humanities", full, "ba_regular")
    extended, _ = build_programme_scope("uct_humanities", full, "ba_extended")
    assert "DOH1002F" not in regular.courses
    assert "ANS1403S" not in regular.courses
    assert "DOH1002F" in extended.courses
    assert "ANS1403S" in extended.courses


def test_standard_major_distinction_applies_first_attempt_and_mark_thresholds():
    full = load_catalogue("uct_humanities")
    scoped, _ = build_programme_scope("uct_humanities", full, "bsocsc_regular")
    codes_and_marks = {
        "POL1004F": 78, "POL1005S": 76,
        "POL2002F": 76, "POL2042S": 74,
        "POL3029F": 77, "POL3045S": 76,
    }
    student = StudentRecord(
        "T10", "Student", "Bachelor of Social Science", ["Politics & Governance"],
        [_passed(code, mark) for code, mark in codes_and_marks.items()],
        faculty_key="uct_humanities", programme_key="bsocsc_regular", years_registered=3,
    )
    report = compute_report(student, scoped)
    politics = next(subject for subject in report.distinction.subjects if subject.major == "Politics & Governance")
    assert politics.eligible
    assert politics.status == "verified"

    repeated = StudentRecord(
        "T11", "Student", "Bachelor of Social Science", ["Politics & Governance"],
        [
            _passed("POL1004F", 78), _passed("POL1005S", 76),
            CourseResult("POL2002F", "POL2002F", 0, 0, 45, "F"),
            _passed("POL2002F", 76), _passed("POL2042S", 74),
            _passed("POL3029F", 77), _passed("POL3045S", 76),
        ],
        faculty_key="uct_humanities", programme_key="bsocsc_regular", years_registered=3,
    )
    repeated_report = compute_report(repeated, scoped)
    repeated_politics = next(subject for subject in repeated_report.distinction.subjects if subject.major == "Politics & Governance")
    assert not repeated_politics.eligible
