import inspect

from engine import award_policy, rule_engine
from engine.catalogue import load_catalogue
from engine.models import CourseResult, StudentRecord
from engine.rule_engine import compute_report
from engine.scope import build_programme_scope

ECONOMICS_POOL = {
    "ECO3009F",
    "ECO3016F",
    "ECO3020F",
    "ECO3021S",
    "ECO3022S",
    "ECO3023S",
    "ECO3024F",
    "ECO3025S",
}


def _economics_student(marks: dict[str, int]) -> StudentRecord:
    return StudentRecord(
        "ECO1",
        "Economics Major Student",
        "Bachelor of Social Science",
        ["Economics"],
        [
            CourseResult(code, code, 0, 0, mark, None, 2024)
            for code, mark in marks.items()
        ],
        faculty_key="uct_humanities",
        programme_key="bsocsc_regular",
        years_registered=3,
    )


def _economics_distinction(marks: dict[str, int]):
    full = load_catalogue("uct_humanities")
    scoped, _ = build_programme_scope("uct_humanities", full, "bsocsc_regular")
    report = compute_report(_economics_student(marks), scoped)
    return next(
        subject
        for subject in report.distinction.subjects
        if subject.major == "Economics"
    )


def test_humanities_economics_fb1_2_is_governed_award_rule_data():
    catalogue = load_catalogue("uct_humanities")
    economics = catalogue.majors["economics"]

    assert economics.award_rules
    rule = economics.award_rules[0]["curriculum_rules"][0]
    assert rule["type"] == "best_n_average"
    assert set(rule["course_codes"]) == ECONOMICS_POOL
    assert rule["mandatory_course_codes"] == ["ECO3020F"]
    assert rule["required"] == 3
    assert rule["minimum_average"] == 80
    assert rule["minimum_mark_count"] == 2
    assert rule["minimum_mark"] == 75
    assert rule["weighting"] == {"basis": "credit_value"}


def test_migrated_economics_fb1_2_qualifying_record():
    row = _economics_distinction(
        {
            "ECO1010F": 60,
            "ECO1011S": 60,
            "STA1000S": 60,
            "MAM1010F": 60,
            "ECO2003F": 60,
            "ECO2004S": 60,
            "ECO2007S": 60,
            "ECO3020F": 80,
            "ECO3009F": 81,
            "ECO3016F": 79,
        }
    )

    assert row.eligible
    assert row.status == "verified"
    assert row.average == 80


def test_migrated_economics_fb1_2_non_qualifying_average():
    row = _economics_distinction(
        {
            "ECO1010F": 60,
            "ECO1011S": 60,
            "STA1000S": 60,
            "MAM1010F": 60,
            "ECO2003F": 60,
            "ECO2004S": 60,
            "ECO2007S": 60,
            "ECO3020F": 78,
            "ECO3009F": 78,
            "ECO3016F": 78,
        }
    )

    assert not row.eligible
    assert row.average == 78


def test_migrated_economics_fb1_2_requires_two_first_class_marks():
    row = _economics_distinction(
        {
            "ECO1010F": 60,
            "ECO1011S": 60,
            "STA1000S": 60,
            "MAM1010F": 60,
            "ECO2003F": 60,
            "ECO2004S": 60,
            "ECO2007S": 60,
            "ECO3020F": 90,
            "ECO3009F": 74,
            "ECO3016F": 74,
        }
    )

    assert not row.eligible
    assert row.average == 79.3


def test_migrated_economics_fb1_2_requires_mandatory_eco3020f():
    row = _economics_distinction(
        {
            "ECO1010F": 60,
            "ECO1011S": 60,
            "STA1000S": 60,
            "MAM1010F": 60,
            "ECO2003F": 60,
            "ECO2004S": 60,
            "ECO2007S": 60,
            "ECO3009F": 90,
            "ECO3016F": 90,
            "ECO3021S": 90,
        }
    )

    assert not row.eligible
    assert row.average == 90


def test_migrated_economics_fb1_2_uses_best_two_additional_courses():
    row = _economics_distinction(
        {
            "ECO1010F": 60,
            "ECO1011S": 60,
            "STA1000S": 60,
            "MAM1010F": 60,
            "ECO2003F": 60,
            "ECO2004S": 60,
            "ECO2007S": 60,
            "ECO3020F": 80,
            "ECO3009F": 60,
            "ECO3016F": 82,
            "ECO3021S": 78,
            "ECO3022S": 50,
        }
    )

    assert row.eligible
    assert row.average == 80


def test_migrated_economics_fb1_2_pool_excludes_unrelated_courses():
    row = _economics_distinction(
        {
            "ECO1010F": 60,
            "ECO1011S": 60,
            "STA1000S": 60,
            "MAM1010F": 60,
            "ECO2003F": 60,
            "ECO2004S": 60,
            "ECO2007S": 60,
            "ECO3020F": 80,
            "ECO3009F": 60,
            "ECO3016F": 60,
            "PHI3023F": 100,
            "POL3029F": 100,
        }
    )

    assert not row.eligible
    assert row.average == 66.7


def test_economics_award_policy_is_not_hard_coded_in_compute_distinction():
    source = inspect.getsource(rule_engine._compute_distinction) + "\n" + inspect.getsource(award_policy)

    assert 'key == "economics"' not in source
    assert "ECO3020F and two other 3000-level ECO courses" not in source
    assert "code.startswith(\"ECO\")" not in source
