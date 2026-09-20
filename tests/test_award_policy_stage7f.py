import inspect

from engine import award_policy, rule_engine
from engine.catalogue import load_catalogue
from engine.models import Catalogue, CourseFact, CourseResult, MajorDefinition, StudentRecord
from engine.rule_engine import _compute_distinction, compute_report
from engine.scope import build_programme_scope

MANDATORY = {"INF2011S", "INF3011F", "INF3014F"}
ALTERNATIVES = {"INF2010S", "INF3012S"}


def _informatics_student(marks: dict[str, int]) -> StudentRecord:
    return StudentRecord(
        "INF1",
        "Informatics Major Student",
        "Bachelor of Social Science",
        ["Informatics"],
        [
            CourseResult(code, code, 0, 0, mark, None, 2024)
            for code, mark in marks.items()
        ],
        faculty_key="uct_humanities",
        programme_key="bsocsc_regular",
        years_registered=3,
    )


def _informatics_distinction(marks: dict[str, int]):
    full = load_catalogue("uct_humanities")
    scoped, _ = build_programme_scope("uct_humanities", full, "bsocsc_regular")
    report = compute_report(_informatics_student(marks), scoped)
    return next(
        subject for subject in report.distinction.subjects if subject.major == "Informatics"
    )


def _base_marks() -> dict[str, int]:
    return {
        "CSC1015F": 60,
        "CSC1016S": 60,
        "INF1002S": 60,
        "INF2003F": 60,
        "INF2008F": 60,
        "INF2009F": 60,
        "INF2011S": 80,
        "INF3011F": 80,
        "INF3014F": 80,
        "INF2010S": 80,
    }


def test_humanities_informatics_fb1_2_is_governed_award_rule_data():
    catalogue = load_catalogue("uct_humanities")
    major = catalogue.majors["informatics"]
    rule = major.award_rules[0]["curriculum_rules"][0]
    children = rule["children"]

    assert major.verification_status == "provisional"
    assert major.award_rules
    assert rule["type"] == "all_of"
    assert rule["verification_status"] == "provisional"
    assert {child["id"] for child in children} == {
        "informatics_fb1_2_inf2011s",
        "informatics_fb1_2_inf3011f",
        "informatics_fb1_2_inf3014f",
        "informatics_fb1_2_alternative_minimum",
        "informatics_fb1_2_overall_average",
        "informatics_fb1_2_level7_average",
    }
    assert {
        tuple(child["course_codes"])
        for child in children
        if child["type"] == "minimum_mark"
    } == {("INF2011S",), ("INF3011F",), ("INF3014F",)}
    alternative = next(
        child for child in children if child["id"] == "informatics_fb1_2_alternative_minimum"
    )
    assert set(alternative["course_codes"]) == ALTERNATIVES
    assert alternative["required"] == 1
    assert alternative["minimum_mark"] == 70
    overall = next(
        child for child in children if child["id"] == "informatics_fb1_2_overall_average"
    )
    assert set(overall["mandatory_course_codes"]) == MANDATORY
    assert set(overall["course_codes"]) == MANDATORY | ALTERNATIVES
    assert overall["required"] == 4
    assert overall["minimum_average"] == 75
    assert overall["minimum_mark_count"] == 4
    assert overall["minimum_mark"] == 70
    assert overall["weighting"] == {"basis": "equal"}


def test_migrated_informatics_fb1_2_computationally_qualifies_but_remains_provisional():
    row = _informatics_distinction(_base_marks())

    assert row.status == "provisional"
    assert not row.eligible
    assert "6 of 6 component requirements completed" in row.reason


def test_migrated_informatics_fb1_2_requires_mandatory_course():
    marks = _base_marks()
    marks.pop("INF3011F")

    row = _informatics_distinction(marks)

    assert row.status == "provisional"
    assert not row.eligible
    assert "INF3011F minimum mark" in row.reason


def test_migrated_informatics_fb1_2_requires_governed_alternative():
    marks = _base_marks()
    marks.pop("INF2010S")

    row = _informatics_distinction(marks)

    assert row.status == "provisional"
    assert not row.eligible


def test_migrated_informatics_fb1_2_requires_minimum_marks():
    marks = _base_marks()
    marks["INF3014F"] = 69

    row = _informatics_distinction(marks)

    assert row.status == "provisional"
    assert not row.eligible


def test_migrated_informatics_fb1_2_requires_overall_average():
    marks = _base_marks()
    marks["INF2011S"] = 70
    marks["INF3011F"] = 75
    marks["INF3014F"] = 75
    marks["INF2010S"] = 70

    row = _informatics_distinction(marks)

    assert row.status == "provisional"
    assert not row.eligible


def test_migrated_informatics_fb1_2_requires_level7_average():
    marks = _base_marks()
    marks["INF2011S"] = 100
    marks["INF3011F"] = 70
    marks["INF3014F"] = 74
    marks["INF2010S"] = 100

    row = _informatics_distinction(marks)

    assert row.status == "provisional"
    assert not row.eligible


def test_migrated_informatics_fb1_2_uses_governed_alternative_pool():
    marks = _base_marks()
    marks.pop("INF2010S")
    marks["PHI3023F"] = 100
    marks["POL3029F"] = 100

    row = _informatics_distinction(marks)

    assert row.status == "provisional"
    assert not row.eligible


def test_migrated_informatics_fb1_2_can_use_second_governed_alternative():
    marks = _base_marks()
    marks.pop("INF2010S")
    marks["INF3012S"] = 80

    row = _informatics_distinction(marks)

    assert row.status == "provisional"
    assert not row.eligible
    assert "6 of 6 component requirements completed" in row.reason


def _synthetic_catalogue(major_status: str, rule_status: str) -> Catalogue:
    courses = {
        code: CourseFact(
            code,
            code,
            10,
            6,
            [],
            [],
            "Synthetic Studies",
            verification_status="verified",
        )
        for code in ("OPAQUE_A", "OPAQUE_B")
    }
    major = MajorDefinition(
        "opaque_major",
        "Opaque Major",
        "SYNTH",
        ["OPAQUE_A", "OPAQUE_B"],
        verification_status=major_status,
        award_rules=[
            {
                "name": "Opaque subject distinction",
                "curriculum_rules": [
                    {
                        "type": "weighted_average",
                        "id": "opaque_average",
                        "label": "Opaque average",
                        "course_codes": ["OPAQUE_A", "OPAQUE_B"],
                        "minimum_average": 75,
                        "weighting": {"basis": "equal"},
                        "verification_status": rule_status,
                    }
                ],
            }
        ],
    )
    return Catalogue(
        courses,
        {"opaque_major": major},
        {},
        [],
        faculty_key="synthetic",
    )


def _synthetic_student() -> StudentRecord:
    return StudentRecord(
        "SYN1",
        "Synthetic Award Student",
        "Synthetic Programme",
        ["Opaque Major"],
        [
            CourseResult("OPAQUE_A", "OPAQUE_A", 10, 6, 80, None, 2024),
            CourseResult("OPAQUE_B", "OPAQUE_B", 10, 6, 80, None, 2024),
        ],
    )


def test_verified_synthetic_major_and_rule_can_produce_verified_award_status():
    row = _compute_distinction(
        _synthetic_student(),
        _synthetic_catalogue("verified", "verified"),
        ["opaque_major"],
    ).subjects[0]

    assert row.status == "verified"
    assert row.eligible


def test_provisional_synthetic_major_cannot_produce_verified_award_status():
    row = _compute_distinction(
        _synthetic_student(),
        _synthetic_catalogue("provisional", "verified"),
        ["opaque_major"],
    ).subjects[0]

    assert row.status == "provisional"
    assert not row.eligible


def test_unverified_synthetic_rule_cannot_produce_verified_award_status():
    row = _compute_distinction(
        _synthetic_student(),
        _synthetic_catalogue("verified", "unverified"),
        ["opaque_major"],
    ).subjects[0]

    assert row.status == "unverified"
    assert not row.eligible


def test_failed_synthetic_award_remains_failed_with_provisional_status():
    student = StudentRecord(
        "SYN2",
        "Synthetic Award Student",
        "Synthetic Programme",
        ["Opaque Major"],
        [
            CourseResult("OPAQUE_A", "OPAQUE_A", 10, 6, 60, None, 2024),
            CourseResult("OPAQUE_B", "OPAQUE_B", 10, 6, 60, None, 2024),
        ],
    )
    row = _compute_distinction(
        student,
        _synthetic_catalogue("provisional", "verified"),
        ["opaque_major"],
    ).subjects[0]

    assert row.status == "provisional"
    assert not row.eligible


def test_informatics_award_policy_is_not_hard_coded_in_compute_distinction():
    source = inspect.getsource(rule_engine._compute_distinction) + "\n" + inspect.getsource(award_policy)

    assert 'key == "informatics"' not in source
    assert "INF3011F" not in source
    assert "INF2010S" not in source
    assert "current Informatics major pathway itself remains provisional" not in source
