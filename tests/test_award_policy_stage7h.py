import inspect
from typing import Any

from engine import award_policy, rule_engine
from engine.catalogue import load_catalogue
from engine.models import Catalogue, CourseFact, CourseResult, MajorDefinition, StudentRecord
from engine.rule_engine import _compute_distinction, compute_report
from engine.scope import build_programme_scope


def _passed(code: str, mark: int) -> CourseResult:
    return CourseResult(code, code, 0, 0, mark, None, 2024)


def _politics_student(marks: dict[str, int]) -> StudentRecord:
    return StudentRecord(
        "POL1",
        "Politics Major Student",
        "Bachelor of Social Science",
        ["Politics & Governance"],
        [_passed(code, mark) for code, mark in marks.items()],
        faculty_key="uct_humanities",
        programme_key="bsocsc_regular",
        years_registered=3,
    )


def _politics_distinction(marks: dict[str, int]):
    full = load_catalogue("uct_humanities")
    scoped, _ = build_programme_scope("uct_humanities", full, "bsocsc_regular")
    report = compute_report(_politics_student(marks), scoped)
    return next(
        subject
        for subject in report.distinction.subjects
        if subject.major == "Politics & Governance"
    )


def _politics_marks() -> dict[str, int]:
    return {
        "POL1004F": 78,
        "POL1005S": 76,
        "POL2002F": 76,
        "POL2042S": 74,
        "POL3029F": 77,
        "POL3045S": 76,
    }


def test_humanities_fb1_1_is_governed_catalogue_award_policy():
    catalogue = load_catalogue("uct_humanities")
    rule = catalogue.award_rules[0]

    assert rule["id"] == "humanities_fb1_1_standard_subject_distinction"
    assert rule["type"] == "subject_selected_set_distinction"
    assert rule["applies_to"] == "standard_faculty_owned_major_without_award_rules"
    assert rule["required_load_equivalents"] == 4
    assert rule["required_advanced_load_equivalents"] == 2
    assert rule["minimum_average"] == 75
    assert rule["advanced_minimum_average"] == 75
    assert rule["minimum_individual_mark"] == 70
    assert rule["first_attempt_only"] is True
    assert rule["weighting"] == {"basis": "course_load_equivalent"}
    assert rule["selection_boundary"]["maximum"] == 4
    assert rule["selection_boundary"]["authority"] == "Head of Department"


def test_scoped_humanities_catalogue_preserves_fb1_1_policy():
    full = load_catalogue("uct_humanities")
    scoped, _ = build_programme_scope("uct_humanities", full, "bsocsc_regular")

    assert scoped.award_rules == full.award_rules


def test_governed_humanities_fb1_1_deterministic_qualifying_record():
    row = _politics_distinction(_politics_marks())

    assert row.eligible
    assert row.status == "verified"


def test_governed_humanities_fb1_1_deterministic_failure_below_minimum_mark():
    marks = _politics_marks()
    marks["POL2042S"] = 69

    row = _politics_distinction(marks)

    assert not row.eligible
    assert row.status == "verified"


def test_governed_humanities_fb1_1_deterministic_failure_repeated_attempt():
    marks = _politics_marks()
    student = _politics_student(marks)
    student.results.insert(2, CourseResult("POL2002F", "POL2002F", 0, 0, 45, "F", 2023))
    full = load_catalogue("uct_humanities")
    scoped, _ = build_programme_scope("uct_humanities", full, "bsocsc_regular")
    report = compute_report(student, scoped)
    row = next(
        subject
        for subject in report.distinction.subjects
        if subject.major == "Politics & Governance"
    )

    assert not row.eligible
    assert row.status == "verified"


class SyntheticLoadFramework:
    framework_id = "synthetic-load"
    institution_id = "synthetic"

    def __init__(self, values: dict[str, float]) -> None:
        self.values = values

    def load_equivalent(self, item: Any) -> float:
        code = item if isinstance(item, str) else item.code
        return self.values[code]


def _synthetic_catalogue(
    *,
    major_status: str = "verified",
    rule_status: str = "verified",
    extra_course: bool = False,
) -> Catalogue:
    codes = ["OPAQUE_A", "OPAQUE_B", "OPAQUE_C", "OPAQUE_D"]
    if extra_course:
        codes.append("OPAQUE_E")
    courses = {
        code: CourseFact(
            code,
            code,
            99,
            7 if code in {"OPAQUE_C", "OPAQUE_D", "OPAQUE_E"} else 6,
            [],
            [],
            "Synthetic Studies",
            verification_status="verified",
        )
        for code in codes
    }
    rule = {
        "id": "synthetic_subject_award",
        "name": "Synthetic selected-set subject distinction",
        "type": "subject_selected_set_distinction",
        "applies_to": "standard_faculty_owned_major_without_award_rules",
        "required_load_equivalents": 4,
        "advanced_level": 7,
        "required_advanced_load_equivalents": 2,
        "minimum_average": 75,
        "advanced_minimum_average": 75,
        "minimum_individual_mark": 70,
        "first_attempt_only": True,
        "weighting": {"basis": "course_load_equivalent"},
        "verification_status": rule_status,
        "selection_boundary": {
            "basis": "course_load_equivalent",
            "maximum": 4,
            "authority": "Authorised academic selector",
            "status": "discretionary",
            "message": "Authorised selection is required.",
        },
    }
    return Catalogue(
        courses,
        {
            "opaque_major": MajorDefinition(
                "opaque_major",
                "Opaque Major",
                "SYNTH",
                codes,
                verification_status=major_status,
            )
        },
        {},
        [],
        faculty_key="synthetic",
        award_rules=[rule],
    )


def _synthetic_student(marks: dict[str, int]) -> StudentRecord:
    return StudentRecord(
        "SYN1",
        "Synthetic Subject Student",
        "Synthetic Programme",
        ["Opaque Major"],
        [_passed(code, mark) for code, mark in marks.items()],
    )


def _synthetic_distinction(
    marks: dict[str, int],
    *,
    major_status: str = "verified",
    rule_status: str = "verified",
    load_values: dict[str, float] | None = None,
):
    values = load_values or {
        "OPAQUE_A": 1.0,
        "OPAQUE_B": 1.0,
        "OPAQUE_C": 1.0,
        "OPAQUE_D": 1.0,
        "OPAQUE_E": 1.0,
    }
    catalogue = _synthetic_catalogue(
        major_status=major_status,
        rule_status=rule_status,
        extra_course="OPAQUE_E" in marks,
    )
    return _compute_distinction(
        _synthetic_student(marks),
        catalogue,
        ["opaque_major"],
        course_load_framework=SyntheticLoadFramework(values),
    ).subjects[0]


def test_synthetic_exact_load_equivalents_deterministically_qualify():
    row = _synthetic_distinction(
        {"OPAQUE_A": 75, "OPAQUE_B": 75, "OPAQUE_C": 75, "OPAQUE_D": 75}
    )

    assert row.eligible
    assert row.status == "verified"


def test_synthetic_less_than_required_load_deterministically_fails():
    row = _synthetic_distinction(
        {"OPAQUE_A": 90, "OPAQUE_B": 90, "OPAQUE_C": 90},
        load_values={"OPAQUE_A": 1.0, "OPAQUE_B": 1.0, "OPAQUE_C": 1.0},
    )

    assert not row.eligible
    assert row.status == "verified"


def test_synthetic_excess_load_requires_authorised_selection_not_best_n():
    row = _synthetic_distinction(
        {
            "OPAQUE_A": 70,
            "OPAQUE_B": 70,
            "OPAQUE_C": 70,
            "OPAQUE_D": 70,
            "OPAQUE_E": 100,
        }
    )

    assert not row.eligible
    assert row.status == "discretionary"
    assert "Authorised selection is required" in row.reason


def test_synthetic_load_policy_ignores_credit_values():
    row = _synthetic_distinction(
        {"OPAQUE_A": 80, "OPAQUE_B": 80, "OPAQUE_C": 80, "OPAQUE_D": 80},
        load_values={
            "OPAQUE_A": 1.5,
            "OPAQUE_B": 0.5,
            "OPAQUE_C": 1.0,
            "OPAQUE_D": 1.0,
        },
    )

    assert row.eligible
    assert row.status == "verified"


def test_synthetic_provisional_rule_cannot_produce_verified_award():
    row = _synthetic_distinction(
        {"OPAQUE_A": 80, "OPAQUE_B": 80, "OPAQUE_C": 80, "OPAQUE_D": 80},
        rule_status="provisional",
    )

    assert not row.eligible
    assert row.status == "provisional"


def test_synthetic_provisional_major_cannot_produce_verified_award():
    row = _synthetic_distinction(
        {"OPAQUE_A": 80, "OPAQUE_B": 80, "OPAQUE_C": 80, "OPAQUE_D": 80},
        major_status="provisional",
    )

    assert not row.eligible
    assert row.status == "provisional"


def test_fb1_1_deterministic_policy_is_not_literal_generic_python_branch():
    source = inspect.getsource(rule_engine._compute_distinction) + "\n" + inspect.getsource(award_policy)

    assert "weights >= 4" not in source
    assert "level7_weights >= 2" not in source
    assert "min(marks) >= 70" not in source
    assert "weighted_average(senior_codes) >= 75" not in source
