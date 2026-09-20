import inspect
from typing import Any

from engine import award_policy
from engine.catalogue import load_catalogue
from engine.models import (
    AuthorisedAwardCourseSelection,
    Catalogue,
    CourseFact,
    CourseResult,
    MajorDefinition,
    StudentRecord,
)
from engine.rule_engine import _compute_distinction
from engine.scope import build_programme_scope

FB1_1_POLICY = "humanities_fb1_1_standard_subject_distinction"


def _passed(code: str, mark: int) -> CourseResult:
    return CourseResult(code, code, 0, 0, mark, None, 2024)


def _selection(
    major_key: str,
    codes: list[str],
    *,
    status: str = "verified",
) -> AuthorisedAwardCourseSelection:
    return AuthorisedAwardCourseSelection(
        policy_id=FB1_1_POLICY,
        major_key=major_key,
        selected_course_codes=tuple(codes),
        authority="Head of Department",
        source_reference="test-selection",
        verification_status=status,
        catalogue_version="2026.2-humanities-complete",
    )


def _humanities_catalogue() -> Catalogue:
    full = load_catalogue("uct_humanities")
    scoped, _ = build_programme_scope("uct_humanities", full, "bsocsc_regular")
    return scoped


def _distinction(
    student: StudentRecord,
    major_keys: list[str],
    selections: list[AuthorisedAwardCourseSelection] | None = None,
):
    return _compute_distinction(
        student,
        _humanities_catalogue(),
        major_keys,
        award_course_selections=selections,
    )


def _law_results(mark: int = 80) -> list[CourseResult]:
    return [
        _passed("PVL1003W", mark),
        _passed("PVL1004F", mark),
        _passed("PVL1008H", mark),
        _passed("PBL2000W", mark),
        _passed("PVL2002H", mark),
        _passed("PVL2003H", mark),
    ]


def _first_class_electives() -> list[CourseResult]:
    return [
        _passed("PBL2800F", 80),
        _passed("POL3029F", 80),
        _passed("POL3030F", 80),
        _passed("POL3045S", 80),
    ]


def _student(
    majors: list[str],
    results: list[CourseResult],
) -> StudentRecord:
    return StudentRecord(
        "7J",
        "Stage 7J Student",
        "Bachelor of Social Science",
        majors,
        results,
        faculty_key="uct_humanities",
        programme_key="bsocsc_regular",
        years_registered=3,
    )


def _anthropology_results(mark: int = 80) -> list[CourseResult]:
    return [
        _passed("ANS1400F", 60),
        _passed("ANS2402S", mark),
        _passed("ANS3400F", mark),
        _passed("ANS3401S", mark),
        _passed("ANS2400Z", 70),
        _passed("ANS2401F", mark),
    ]


def test_uct_fb1_4_policy_is_governed_catalogue_rule():
    rules = _humanities_catalogue().award_rules
    rule = next(
        rule
        for rule in rules
        if rule.get("id") == "humanities_fb1_4_qualification_distinction"
    )

    child_types = [child["type"] for child in rule["curriculum_rules"]]

    assert rule["type"] == "qualification_distinction"
    assert child_types == [
        "passed_mark_equivalents",
        "passed_mark_equivalents",
        "award_dependency",
    ]
    assert rule["curriculum_rules"][0]["required"] == 10
    assert rule["curriculum_rules"][1]["required"] == 8
    assert rule["curriculum_rules"][2]["minimum_verification_status"] == "verified"


def test_uct_fb1_4_numeric_thresholds_and_verified_law_fb1_2_witness_pass():
    student = _student(["Law"], _law_results() + _first_class_electives())

    distinction = _distinction(student, ["law"])

    assert distinction.qualification_eligible
    assert distinction.status == "verified"
    assert "qualifying subject distinction" in distinction.reason
    assert any(subject.major == "Law" and subject.eligible for subject in distinction.subjects)


def test_uct_fb1_4_subject_witness_can_pass_while_numeric_threshold_fails():
    student = _student(["Law"], _law_results())

    distinction = _distinction(student, ["law"])

    assert not distinction.qualification_eligible
    assert distinction.status == "verified"
    assert any(subject.major == "Law" and subject.eligible for subject in distinction.subjects)
    assert "8 of 10" in distinction.reason


def test_uct_fb1_4_numeric_thresholds_without_subject_distinction_fail():
    student = _student([], _law_results() + _first_class_electives())

    distinction = _distinction(student, [])

    assert not distinction.qualification_eligible
    assert distinction.status == "verified"
    assert "No qualifying subject distinction" in distinction.reason


def test_uct_fb1_4_only_provisional_informatics_does_not_satisfy_verified_dependency():
    results = [
        _passed("INF2011S", 80),
        _passed("INF3011F", 80),
        _passed("INF3014F", 80),
        _passed("INF3003W", 80),
        *_first_class_electives(),
        *_law_results(),
    ]
    student = _student(["Informatics"], results)

    distinction = _distinction(student, ["informatics"])

    assert not distinction.qualification_eligible
    assert distinction.status in {"provisional", "unverified"}
    assert any(subject.major == "Informatics" for subject in distinction.subjects)


def test_uct_fb1_4_verified_witness_not_weakened_by_unrelated_provisional_award():
    results = [
        *_law_results(),
        _passed("INF2011S", 80),
        _passed("INF3011F", 80),
        _passed("INF3014F", 80),
        _passed("INF3003W", 80),
        *_first_class_electives(),
    ]
    student = _student(["Law", "Informatics"], results)

    distinction = _distinction(student, ["law", "informatics"])

    assert distinction.qualification_eligible
    assert distinction.status == "verified"
    assert any(subject.major == "Law" and subject.eligible for subject in distinction.subjects)
    assert any(subject.major == "Informatics" for subject in distinction.subjects)


def test_uct_fb1_4_discretionary_fb1_1_without_selection_does_not_satisfy_dependency():
    student = _student(
        ["Anthropology"],
        _anthropology_results() + _first_class_electives() + _law_results(),
    )

    distinction = _distinction(student, ["anthropology"])

    assert not distinction.qualification_eligible
    assert distinction.status == "discretionary"
    assert any(subject.major == "Anthropology" and subject.status == "discretionary" for subject in distinction.subjects)


def test_uct_fb1_4_verified_selected_set_fb1_1_can_satisfy_dependency():
    selection = _selection(
        "anthropology",
        ["ANS2402S", "ANS3400F", "ANS3401S", "ANS2401F"],
    )
    student = _student(
        ["Anthropology"],
        _anthropology_results() + _first_class_electives() + _law_results(),
    )

    distinction = _distinction(student, ["anthropology"], [selection])

    assert distinction.qualification_eligible
    assert distinction.status == "verified"
    assert any(subject.major == "Anthropology" and subject.eligible for subject in distinction.subjects)


class SyntheticLoadFramework:
    framework_id = "synthetic-load"
    institution_id = "synthetic"

    def __init__(self, values: dict[str, float]) -> None:
        self.values = values

    def load_equivalent(self, item: Any) -> float:
        code = item if isinstance(item, str) else item.code
        return self.values[code]


def _synthetic_catalogue(subject_b_status: str = "provisional") -> Catalogue:
    course_codes = [
        "OPAQUE_A1",
        "OPAQUE_A2",
        "OPAQUE_B1",
        "OPAQUE_B2",
        "OPAQUE_X1",
        "OPAQUE_X2",
    ]
    courses = {
        code: CourseFact(
            code,
            code,
            10,
            7 if code.endswith("2") else 6,
            [],
            [],
            "Synthetic Studies",
            verification_status="verified",
        )
        for code in course_codes
    }
    award_rule = {
        "id": "subject_award",
        "name": "Synthetic subject award",
        "curriculum_rules": [
            {
                "type": "all_courses",
                "id": "all_subject_courses",
                "course_codes": [],
            },
            {
                "type": "weighted_average",
                "id": "subject_average",
                "minimum_average": 75,
                "weighting": {"basis": "equal"},
                "course_codes": [],
            },
        ],
    }
    subject_a_rule = {
        **award_rule,
        "id": "subject_a_award",
        "curriculum_rules": [
            {**award_rule["curriculum_rules"][0], "course_codes": ["OPAQUE_A1", "OPAQUE_A2"]},
            {**award_rule["curriculum_rules"][1], "course_codes": ["OPAQUE_A1", "OPAQUE_A2"]},
        ],
    }
    subject_b_rule = {
        **award_rule,
        "id": "subject_b_award",
        "verification_status": subject_b_status,
        "curriculum_rules": [
            {**award_rule["curriculum_rules"][0], "course_codes": ["OPAQUE_B1", "OPAQUE_B2"]},
            {**award_rule["curriculum_rules"][1], "course_codes": ["OPAQUE_B1", "OPAQUE_B2"]},
        ],
    }
    return Catalogue(
        courses,
        {
            "subject_a": MajorDefinition(
                "subject_a",
                "Subject A",
                "SYNTH",
                ["OPAQUE_A1", "OPAQUE_A2"],
                verification_status="verified",
                award_rules=[subject_a_rule],
            ),
            "subject_b": MajorDefinition(
                "subject_b",
                "Subject B",
                "SYNTH",
                ["OPAQUE_B1", "OPAQUE_B2"],
                verification_status=subject_b_status,
                award_rules=[subject_b_rule],
            ),
        },
        {},
        [],
        faculty_key="synthetic",
        catalogue_version="synthetic-2026",
        award_rules=[
            {
                "id": "synthetic_qualification_distinction",
                "type": "qualification_distinction",
                "verification_status": "verified",
                "curriculum_rules": [
                    {
                        "id": "synthetic_total_first_class_load",
                        "type": "passed_mark_equivalents",
                        "required": 4,
                        "minimum_mark": 75,
                        "filters": {"counts_towards_course_equivalents": True},
                    },
                    {
                        "id": "synthetic_senior_first_class_load",
                        "type": "passed_mark_equivalents",
                        "required": 2,
                        "minimum_mark": 75,
                        "filters": {"senior": True},
                    },
                    {
                        "id": "synthetic_subject_dependency",
                        "type": "award_dependency",
                        "award_scope": "subject_distinction",
                        "minimum_count": 1,
                        "required_outcome": "eligible",
                        "minimum_verification_status": "verified",
                    },
                ],
            }
        ],
    )


def _synthetic_student(mark_a: int = 80, mark_b: int = 80) -> StudentRecord:
    return StudentRecord(
        "SYN7J",
        "Synthetic Dependency Student",
        "Synthetic Programme",
        ["Subject A", "Subject B"],
        [
            _passed("OPAQUE_A1", mark_a),
            _passed("OPAQUE_A2", mark_a),
            _passed("OPAQUE_B1", mark_b),
            _passed("OPAQUE_B2", mark_b),
            _passed("OPAQUE_X1", 80),
            _passed("OPAQUE_X2", 80),
        ],
    )


def _synthetic_distinction(
    major_keys: list[str],
    *,
    catalogue: Catalogue | None = None,
    student: StudentRecord | None = None,
):
    return _compute_distinction(
        student or _synthetic_student(),
        catalogue or _synthetic_catalogue(),
        major_keys,
        course_load_framework=SyntheticLoadFramework(
            {
                "OPAQUE_A1": 1.0,
                "OPAQUE_A2": 1.0,
                "OPAQUE_B1": 1.0,
                "OPAQUE_B2": 1.0,
                "OPAQUE_X1": 1.0,
                "OPAQUE_X2": 1.0,
            }
        ),
    )


def test_synthetic_verified_subject_award_satisfies_dependency():
    distinction = _synthetic_distinction(["subject_a"])

    assert distinction.qualification_eligible
    assert distinction.status == "verified"
    assert "Satisfied by: subject_a" in distinction.reason


def test_synthetic_provisional_subject_award_does_not_verify_dependency():
    distinction = _synthetic_distinction(["subject_b"])

    assert not distinction.qualification_eligible
    assert distinction.status == "provisional"


def test_synthetic_verified_witness_not_weakened_by_unused_provisional_award():
    distinction = _synthetic_distinction(["subject_a", "subject_b"])

    assert distinction.qualification_eligible
    assert distinction.status == "verified"
    assert "Satisfied by: subject_a" in distinction.reason


def test_synthetic_dependency_can_pass_while_numeric_threshold_fails():
    student = _synthetic_student()
    student.results = student.results[:2]

    distinction = _synthetic_distinction(["subject_a"], student=student)

    assert not distinction.qualification_eligible
    assert distinction.status == "verified"
    assert "2 of 4" in distinction.reason


def test_synthetic_numeric_thresholds_can_pass_while_dependency_fails():
    distinction = _synthetic_distinction([])

    assert not distinction.qualification_eligible
    assert distinction.status == "verified"
    assert "No qualifying subject distinction" in distinction.reason


def test_fb1_4_thresholds_and_major_names_are_not_generic_python_policy():
    source = inspect.getsource(_compute_distinction) + "\n" + inspect.getsource(award_policy)

    assert "first_class_sce >= 10" not in source
    assert "first_class_senior_sce >= 8" not in source
    assert "subject_distinction = any(subject.eligible" not in source
