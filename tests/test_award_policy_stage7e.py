import inspect

from engine import rule_engine
from engine.catalogue import load_catalogue
from engine.models import CourseResult, StudentRecord
from engine.rule_engine import compute_report
from engine.scope import build_programme_scope

SECOND_YEAR_POOL = {"BUS2024F", "BUS2023S"}
THIRD_YEAR_POOL = {"BUS3003F", "BUS3004S"}


def _iop_student(marks: dict[str, int]) -> StudentRecord:
    return StudentRecord(
        "IOP1",
        "Industrial and Organisational Psychology Major Student",
        "Bachelor of Social Science",
        ["Industrial and Organisational Psychology"],
        [
            CourseResult(code, code, 0, 0, mark, None, 2024)
            for code, mark in marks.items()
        ],
        faculty_key="uct_humanities",
        programme_key="bsocsc_regular",
        years_registered=3,
    )


def _iop_distinction(marks: dict[str, int]):
    full = load_catalogue("uct_humanities")
    scoped, _ = build_programme_scope("uct_humanities", full, "bsocsc_regular")
    report = compute_report(_iop_student(marks), scoped)
    return next(
        subject
        for subject in report.distinction.subjects
        if subject.major == "Industrial And Organisational Psychology"
    )


def _base_marks() -> dict[str, int]:
    return {
        "PSY1009F": 60,
        "PSY1010S": 60,
        "BUS1007S": 60,
        "BUS2024F": 75,
        "BUS2023S": 75,
        "BUS3003F": 75,
        "BUS3004S": 75,
    }


def test_humanities_iop_fb1_2_is_governed_award_rule_data():
    catalogue = load_catalogue("uct_humanities")
    major = catalogue.majors["industrial_and_organisational_psychology"]
    rules = major.award_rules[0]["curriculum_rules"]

    assert major.award_rules
    assert [rule["id"] for rule in rules] == [
        "industrial_and_organisational_psychology_fb1_2_second_year",
        "industrial_and_organisational_psychology_fb1_2_third_year",
    ]
    assert rules[0]["type"] == "passed_mark_count"
    assert set(rules[0]["course_codes"]) == SECOND_YEAR_POOL
    assert rules[0]["required"] == 2
    assert rules[0]["minimum_mark"] == 75
    assert rules[1]["type"] == "passed_mark_count"
    assert set(rules[1]["course_codes"]) == THIRD_YEAR_POOL
    assert rules[1]["required"] == 2
    assert rules[1]["minimum_mark"] == 75


def test_migrated_iop_fb1_2_qualifying_record():
    row = _iop_distinction(_base_marks())

    assert row.eligible
    assert row.status == "verified"


def test_migrated_iop_fb1_2_requires_two_second_year_first_class_courses():
    marks = _base_marks()
    marks["BUS2023S"] = 74

    row = _iop_distinction(marks)

    assert not row.eligible


def test_migrated_iop_fb1_2_requires_two_third_year_first_class_courses():
    marks = _base_marks()
    marks["BUS3004S"] = 74

    row = _iop_distinction(marks)

    assert not row.eligible


def test_migrated_iop_fb1_2_rejects_below_threshold_course():
    marks = _base_marks()
    marks["BUS2024F"] = 74

    row = _iop_distinction(marks)

    assert not row.eligible


def test_migrated_iop_fb1_2_extra_second_year_courses_do_not_substitute():
    marks = _base_marks()
    marks["BUS2023S"] = 74
    marks["PSY2013F"] = 100
    marks["PSY2014S"] = 100

    row = _iop_distinction(marks)

    assert not row.eligible


def test_migrated_iop_fb1_2_extra_third_year_courses_do_not_substitute():
    marks = _base_marks()
    marks["BUS3004S"] = 74
    marks["PSY3005F"] = 100
    marks["PSY3009F"] = 100

    row = _iop_distinction(marks)

    assert not row.eligible


def test_migrated_iop_fb1_2_pool_excludes_unrelated_high_mark_courses():
    marks = _base_marks()
    marks["BUS2023S"] = 74
    marks["BUS3004S"] = 74
    marks["PHI3023F"] = 100
    marks["POL3029F"] = 100

    row = _iop_distinction(marks)

    assert not row.eligible


def test_migrated_iop_fb1_2_uses_governed_pools_not_hidden_level_parsing():
    marks = _base_marks()
    marks["BUS2023S"] = 74
    marks["BUS3004S"] = 74
    marks["ECO3020F"] = 100
    marks["PSY2013F"] = 100
    marks["PSY3007S"] = 100

    row = _iop_distinction(marks)

    assert not row.eligible


def test_iop_award_policy_is_not_hard_coded_in_compute_distinction():
    source = inspect.getsource(rule_engine._compute_distinction)

    assert 'key == "industrial_and_organisational_psychology"' not in source
    assert "BUS2024F" not in source
    assert "BUS3003F" not in source
    assert "two 2000-level and two 3000-level" not in source
