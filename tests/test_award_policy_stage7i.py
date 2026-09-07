from typing import Any

from engine.catalogue import load_catalogue
from engine.models import (
    AuthorisedAwardCourseSelection,
    Catalogue,
    CourseFact,
    CourseResult,
    MajorDefinition,
    StudentRecord,
)
from engine.rule_engine import _compute_distinction, compute_report
from engine.scope import build_programme_scope

FB1_1_POLICY = "humanities_fb1_1_standard_subject_distinction"


def _passed(code: str, mark: int) -> CourseResult:
    return CourseResult(code, code, 0, 0, mark, None, 2024)


def _selection(
    policy_id: str,
    major_key: str,
    codes: list[str],
    *,
    status: str = "verified",
    catalogue_version: str = "2026.2-humanities-complete",
) -> AuthorisedAwardCourseSelection:
    return AuthorisedAwardCourseSelection(
        policy_id=policy_id,
        major_key=major_key,
        selected_course_codes=tuple(codes),
        authority="Head of Department",
        source_reference="test-selection",
        verification_status=status,
        catalogue_version=catalogue_version,
    )


def _anthropology_student(marks: dict[str, int]) -> StudentRecord:
    return StudentRecord(
        "ANT1",
        "Anthropology Student",
        "Bachelor of Social Science",
        ["Anthropology"],
        [_passed(code, mark) for code, mark in marks.items()],
        faculty_key="uct_humanities",
        programme_key="bsocsc_regular",
        years_registered=3,
    )


def _anthropology_marks() -> dict[str, int]:
    return {
        "ANS1400F": 60,
        "ANS2402S": 80,
        "ANS3400F": 80,
        "ANS3401S": 80,
        "ANS2400Z": 70,
        "ANS2401F": 80,
    }


def _anthropology_distinction(
    marks: dict[str, int],
    selections: list[AuthorisedAwardCourseSelection] | None = None,
):
    full = load_catalogue("uct_humanities")
    scoped, _ = build_programme_scope("uct_humanities", full, "bsocsc_regular")
    report = compute_report(
        _anthropology_student(marks),
        scoped,
        award_course_selections=selections,
    )
    return next(
        subject
        for subject in report.distinction.subjects
        if subject.major == "Anthropology"
    )


def test_uct_fb1_1_excess_senior_load_without_selection_remains_discretionary():
    row = _anthropology_distinction(_anthropology_marks())

    assert not row.eligible
    assert row.status == "discretionary"
    assert "Head of Department" in row.reason


def test_uct_fb1_1_verified_selection_can_unlock_deterministic_positive():
    selection = _selection(
        FB1_1_POLICY,
        "anthropology",
        ["ANS2402S", "ANS3400F", "ANS3401S", "ANS2401F"],
    )

    row = _anthropology_distinction(_anthropology_marks(), [selection])

    assert row.eligible
    assert row.status == "verified"
    assert row.senior_courses_assessed == 4


def test_uct_fb1_1_selected_set_can_deterministically_fail_threshold():
    marks = _anthropology_marks()
    marks["ANS2400Z"] = 69
    selection = _selection(
        FB1_1_POLICY,
        "anthropology",
        ["ANS2402S", "ANS3400F", "ANS3401S", "ANS2400Z"],
    )

    row = _anthropology_distinction(marks, [selection])

    assert not row.eligible
    assert row.status == "verified"


def test_uct_fb1_1_unverified_selection_cannot_produce_verified_positive():
    selection = _selection(
        FB1_1_POLICY,
        "anthropology",
        ["ANS2402S", "ANS3400F", "ANS3401S", "ANS2401F"],
        status="unverified",
    )

    row = _anthropology_distinction(_anthropology_marks(), [selection])

    assert not row.eligible
    assert row.status == "unverified"


def test_uct_fb1_1_rejects_non_major_selected_course():
    marks = _anthropology_marks()
    marks["POL3029F"] = 100
    selection = _selection(
        FB1_1_POLICY,
        "anthropology",
        ["ANS2402S", "ANS3400F", "ANS3401S", "POL3029F"],
    )

    row = _anthropology_distinction(marks, [selection])

    assert not row.eligible
    assert row.status == "unverified"
    assert "outside the governed major pool" in row.reason


def test_uct_fb1_1_selected_set_enforces_first_attempt_on_selected_courses():
    marks = _anthropology_marks()
    selection = _selection(
        FB1_1_POLICY,
        "anthropology",
        ["ANS2402S", "ANS3400F", "ANS3401S", "ANS2401F"],
    )
    student = _anthropology_student(marks)
    student.results.insert(
        1, CourseResult("ANS2402S", "ANS2402S", 0, 0, 45, "F", 2023)
    )
    full = load_catalogue("uct_humanities")
    scoped, _ = build_programme_scope("uct_humanities", full, "bsocsc_regular")
    report = compute_report(student, scoped, award_course_selections=[selection])
    row = next(
        subject
        for subject in report.distinction.subjects
        if subject.major == "Anthropology"
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


def _synthetic_catalogue() -> Catalogue:
    codes = ["OPAQUE_A", "OPAQUE_B", "OPAQUE_C", "OPAQUE_D", "OPAQUE_E"]
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
    return Catalogue(
        courses,
        {
            "opaque_major": MajorDefinition(
                "opaque_major",
                "Opaque Major",
                "SYNTH",
                codes,
                verification_status="verified",
            )
        },
        {},
        [],
        faculty_key="synthetic",
        catalogue_version="synthetic-2026",
        award_rules=[
            {
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
                "verification_status": "verified",
                "selection_boundary": {
                    "basis": "course_load_equivalent",
                    "maximum": 4,
                    "authority": "Authorised academic selector",
                    "status": "discretionary",
                    "message": "Authorised selection is required.",
                },
            }
        ],
    )


def _synthetic_student() -> StudentRecord:
    return StudentRecord(
        "SYN1",
        "Synthetic Subject Student",
        "Synthetic Programme",
        ["Opaque Major"],
        [
            _passed("OPAQUE_A", 80),
            _passed("OPAQUE_B", 80),
            _passed("OPAQUE_C", 80),
            _passed("OPAQUE_D", 80),
            _passed("OPAQUE_E", 60),
        ],
    )


def _synthetic_selection(
    codes: list[str],
    *,
    policy_id: str = "synthetic_subject_award",
    major_key: str = "opaque_major",
    status: str = "verified",
    catalogue_version: str = "synthetic-2026",
) -> AuthorisedAwardCourseSelection:
    return AuthorisedAwardCourseSelection(
        policy_id,
        major_key,
        tuple(codes),
        "Authorised academic selector",
        "synthetic-decision",
        status,
        catalogue_version,
    )


def _synthetic_distinction(
    selections: list[AuthorisedAwardCourseSelection] | None = None,
):
    return _compute_distinction(
        _synthetic_student(),
        _synthetic_catalogue(),
        ["opaque_major"],
        course_load_framework=SyntheticLoadFramework(
            {
                "OPAQUE_A": 1.5,
                "OPAQUE_B": 0.5,
                "OPAQUE_C": 1.0,
                "OPAQUE_D": 1.0,
                "OPAQUE_E": 1.0,
            }
        ),
        award_course_selections=selections,
    ).subjects[0]


def test_synthetic_excess_load_without_selection_requires_verification():
    row = _synthetic_distinction()

    assert not row.eligible
    assert row.status == "discretionary"


def test_synthetic_verified_selection_evaluates_exact_set():
    row = _synthetic_distinction(
        [_synthetic_selection(["OPAQUE_A", "OPAQUE_B", "OPAQUE_C", "OPAQUE_D"])]
    )

    assert row.eligible
    assert row.status == "verified"


def test_synthetic_different_authorised_selections_can_change_outcome():
    passing = _synthetic_distinction(
        [_synthetic_selection(["OPAQUE_A", "OPAQUE_B", "OPAQUE_C", "OPAQUE_D"])]
    )
    failing = _synthetic_distinction(
        [_synthetic_selection(["OPAQUE_A", "OPAQUE_B", "OPAQUE_C", "OPAQUE_E"])]
    )

    assert passing.eligible
    assert not failing.eligible
    assert failing.status == "verified"


def test_synthetic_unverified_selection_cannot_produce_verified_award():
    row = _synthetic_distinction(
        [
            _synthetic_selection(
                ["OPAQUE_A", "OPAQUE_B", "OPAQUE_C", "OPAQUE_D"],
                status="provisional",
            )
        ]
    )

    assert not row.eligible
    assert row.status == "provisional"


def test_synthetic_wrong_major_selection_is_not_reused():
    row = _synthetic_distinction(
        [
            _synthetic_selection(
                ["OPAQUE_A", "OPAQUE_B", "OPAQUE_C", "OPAQUE_D"],
                major_key="other_major",
            )
        ]
    )

    assert not row.eligible
    assert row.status == "discretionary"


def test_synthetic_wrong_policy_or_release_selection_is_not_reused():
    wrong_policy = _synthetic_distinction(
        [
            _synthetic_selection(
                ["OPAQUE_A", "OPAQUE_B", "OPAQUE_C", "OPAQUE_D"],
                policy_id="other_policy",
            )
        ]
    )
    wrong_release = _synthetic_distinction(
        [
            _synthetic_selection(
                ["OPAQUE_A", "OPAQUE_B", "OPAQUE_C", "OPAQUE_D"],
                catalogue_version="synthetic-2025",
            )
        ]
    )

    assert wrong_policy.status == "discretionary"
    assert wrong_release.status == "discretionary"


def test_synthetic_duplicate_selection_cannot_inflate_load():
    row = _synthetic_distinction(
        [_synthetic_selection(["OPAQUE_A", "OPAQUE_A", "OPAQUE_C", "OPAQUE_D"])]
    )

    assert not row.eligible
    assert row.status == "unverified"
    assert "duplicate" in row.reason


def test_synthetic_outside_pool_selection_is_rejected():
    student = _synthetic_student()
    catalogue = _synthetic_catalogue()
    catalogue.courses["OPAQUE_X"] = CourseFact(
        "OPAQUE_X", "OPAQUE_X", 99, 7, [], [], "Other", verification_status="verified"
    )
    student.results.append(_passed("OPAQUE_X", 100))
    row = _compute_distinction(
        student,
        catalogue,
        ["opaque_major"],
        course_load_framework=SyntheticLoadFramework(
            {
                "OPAQUE_A": 1.5,
                "OPAQUE_B": 0.5,
                "OPAQUE_C": 1.0,
                "OPAQUE_D": 1.0,
                "OPAQUE_E": 1.0,
                "OPAQUE_X": 1.0,
            }
        ),
        award_course_selections=[
            _synthetic_selection(["OPAQUE_A", "OPAQUE_B", "OPAQUE_C", "OPAQUE_X"])
        ],
    ).subjects[0]

    assert not row.eligible
    assert row.status == "unverified"
    assert "outside the governed major pool" in row.reason
