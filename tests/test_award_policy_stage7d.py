import inspect

from engine import rule_engine
from engine.catalogue import load_catalogue
from engine.models import CourseResult, StudentRecord
from engine.rule_engine import compute_report
from engine.scope import build_programme_scope

SECOND_YEAR_OPTIONS = {"PSY2013F", "PSY2014S"}
THIRD_YEAR_OPTIONS = {"PSY3005F", "PSY3009F", "PSY3010S", "PSY3011S"}


def _psychology_student(marks: dict[str, int]) -> StudentRecord:
    return StudentRecord(
        "PSY1",
        "Psychology Major Student",
        "Bachelor of Social Science",
        ["Psychology"],
        [
            CourseResult(code, code, 0, 0, mark, None, 2024)
            for code, mark in marks.items()
        ],
        faculty_key="uct_humanities",
        programme_key="bsocsc_regular",
        years_registered=3,
    )


def _psychology_distinction(marks: dict[str, int]):
    full = load_catalogue("uct_humanities")
    scoped, _ = build_programme_scope("uct_humanities", full, "bsocsc_regular")
    report = compute_report(_psychology_student(marks), scoped)
    return next(
        subject
        for subject in report.distinction.subjects
        if subject.major == "Psychology"
    )


def _base_marks() -> dict[str, int]:
    return {
        "PSY1009F": 60,
        "PSY1010S": 60,
        "PSY2015F": 75,
        "PSY2013F": 75,
        "PSY2014S": 60,
        "PSY3007S": 75,
        "PSY3005F": 75,
        "PSY3009F": 60,
        "PSY3010S": 60,
    }


def test_humanities_psychology_fb1_2_is_governed_award_rule_data():
    catalogue = load_catalogue("uct_humanities")
    psychology = catalogue.majors["psychology"]
    rules = psychology.award_rules[0]["curriculum_rules"]

    assert psychology.award_rules
    assert [rule["id"] for rule in rules] == [
        "psychology_fb1_2_psy2015f",
        "psychology_fb1_2_second_year_option",
        "psychology_fb1_2_psy3007s",
        "psychology_fb1_2_third_year_option",
    ]
    assert rules[0]["type"] == "minimum_mark"
    assert rules[0]["course_codes"] == ["PSY2015F"]
    assert rules[0]["minimum_mark"] == 75
    assert rules[1]["type"] == "passed_mark_count"
    assert set(rules[1]["course_codes"]) == SECOND_YEAR_OPTIONS
    assert rules[1]["required"] == 1
    assert rules[1]["minimum_mark"] == 75
    assert rules[2]["course_codes"] == ["PSY3007S"]
    assert rules[2]["minimum_mark"] == 75
    assert rules[3]["type"] == "passed_mark_count"
    assert set(rules[3]["course_codes"]) == THIRD_YEAR_OPTIONS
    assert rules[3]["required"] == 1
    assert rules[3]["minimum_mark"] == 75


def test_migrated_psychology_fb1_2_qualifying_record():
    row = _psychology_distinction(_base_marks())

    assert row.eligible
    assert row.status == "verified"


def test_migrated_psychology_fb1_2_requires_psy2015f():
    marks = _base_marks()
    marks.pop("PSY2015F")

    row = _psychology_distinction(marks)

    assert not row.eligible


def test_migrated_psychology_fb1_2_requires_psy3007s():
    marks = _base_marks()
    marks.pop("PSY3007S")

    row = _psychology_distinction(marks)

    assert not row.eligible


def test_migrated_psychology_fb1_2_requires_second_year_first_class_option():
    marks = _base_marks()
    marks["PSY2013F"] = 74
    marks["PSY2014S"] = 74

    row = _psychology_distinction(marks)

    assert not row.eligible


def test_migrated_psychology_fb1_2_requires_third_year_first_class_option():
    marks = _base_marks()
    marks["PSY3005F"] = 74
    marks["PSY3009F"] = 74
    marks["PSY3010S"] = 74

    row = _psychology_distinction(marks)

    assert not row.eligible


def test_migrated_psychology_fb1_2_requires_mandatory_thresholds():
    marks = _base_marks()
    marks["PSY2015F"] = 74
    marks["PSY3007S"] = 74

    row = _psychology_distinction(marks)

    assert not row.eligible


def test_migrated_psychology_fb1_2_counts_multiple_alternatives_without_selection():
    marks = _base_marks()
    marks["PSY2013F"] = 74
    marks["PSY2014S"] = 76
    marks["PSY3005F"] = 74
    marks["PSY3009F"] = 76
    marks["PSY3010S"] = 77

    row = _psychology_distinction(marks)

    assert row.eligible


def test_migrated_psychology_fb1_2_pool_excludes_unrelated_courses():
    marks = _base_marks()
    marks["PSY2013F"] = 74
    marks["PSY2014S"] = 74
    marks["PSY3005F"] = 74
    marks["PSY3009F"] = 74
    marks["PSY3010S"] = 74
    marks["PHI3023F"] = 100
    marks["POL3029F"] = 100

    row = _psychology_distinction(marks)

    assert not row.eligible


def test_psychology_award_policy_is_not_hard_coded_in_compute_distinction():
    source = inspect.getsource(rule_engine._compute_distinction)

    assert 'key == "psychology"' not in source
    assert "PSY2015F, one other second-year Psychology course" not in source
    assert "PSY3007S and one other third-year Psychology course" not in source
