import inspect
from typing import Any

import engine.rule_engine as rule_engine
from engine import award_policy
from engine.catalogue import load_catalogue
from engine.models import Catalogue, CourseFact, CourseResult, MajorDefinition, StudentRecord
from engine.rule_engine import _compute_distinction, compute_report
from engine.scope import build_programme_scope


def _science_catalogue() -> Catalogue:
    full = load_catalogue("uct_science")
    scoped, _ = build_programme_scope(
        "uct_science", full, "bsc_science", "current_2023_plus"
    )
    return scoped


def _result(catalogue: Catalogue, code: str, mark: int = 80) -> CourseResult:
    fact = catalogue.courses[code]
    return CourseResult(code, fact.name, fact.nqf_level, fact.nqf_credits, mark, "P", 2024)


def _chemistry_student(mark: int = 80) -> tuple[Catalogue, StudentRecord]:
    catalogue = _science_catalogue()
    codes = [
        "CEM1000W",
        "MAM1031F",
        "MAM1032S",
        "PHY1031F",
        "PHY1032S",
        "CEM2005W",
        "CEM3005W",
    ]
    return catalogue, StudentRecord(
        "SCI7L",
        "Science Identity Student",
        "Bachelor of Science",
        ["Chemistry"],
        [_result(catalogue, code, mark) for code in codes],
        faculty_key="uct_science",
        programme_key="bsc_science",
        pathway_key="current_2023_plus",
        years_registered=3,
    )


def test_science_fb8_1_award_row_carries_generic_identity():
    catalogue, student = _chemistry_student()

    row = compute_report(student, catalogue).distinction.subjects[0]

    assert row.major == "Chemistry"
    assert row.major_key == "chemistry"
    assert row.policy_id == "chem_dist"
    assert row.eligible
    assert row.status == "verified"


def test_all_current_science_majors_have_governed_award_rules():
    catalogue = load_catalogue("uct_science")

    assert len(catalogue.majors) == 22
    assert all(major.award_rules for major in catalogue.majors.values())


def test_science_provisional_award_rule_cannot_produce_verified_row():
    catalogue, student = _chemistry_student()
    catalogue.majors["chemistry"].award_rules[0]["verification_status"] = "provisional"

    row = _compute_distinction(student, catalogue, ["chemistry"]).subjects[0]

    assert not row.eligible
    assert row.status == "unverified"
    assert row.major_key == "chemistry"
    assert row.policy_id == "chem_dist"


def test_science_failed_rule_remains_failed_with_stable_identity():
    catalogue, student = _chemistry_student(mark=74)

    row = compute_report(student, catalogue).distinction.subjects[0]

    assert not row.eligible
    assert row.status == "verified"
    assert row.major_key == "chemistry"
    assert row.policy_id == "chem_dist"


def test_science_missing_rule_fallback_retains_unverified_identity():
    catalogue, student = _chemistry_student()
    catalogue.majors["chemistry"].award_rules = []

    row = _compute_distinction(student, catalogue, ["chemistry"]).subjects[0]

    assert not row.eligible
    assert row.status == "unverified"
    assert row.major_key == "chemistry"
    assert row.policy_id == "chemistry:award_rules"


class SyntheticLoadFramework:
    framework_id = "synthetic-load"
    institution_id = "synthetic"

    def load_equivalent(self, item: Any) -> float:
        return 1.0


def _synthetic_catalogue(*, status: str = "verified") -> Catalogue:
    courses = {
        code: CourseFact(
            code,
            code,
            10,
            7,
            [],
            [],
            "Opaque Studies",
            verification_status="verified",
        )
        for code in ["OPAQUE_A", "OPAQUE_B", "OPAQUE_C", "OPAQUE_D"]
    }
    return Catalogue(
        courses,
        {
            "opaque_major": MajorDefinition(
                "opaque_major",
                "Opaque Major",
                "SYNTH",
                ["OPAQUE_A", "OPAQUE_B"],
                verification_status=status,
                award_rules=[
                    {
                        "id": "opaque_major_award",
                        "type": "weighted_average",
                        "course_codes": ["OPAQUE_A", "OPAQUE_B"],
                        "minimum_average": 75,
                        "weighting": {"basis": "equal"},
                        "verification_status": status,
                    }
                ],
            )
            ,
            "provisional_major": MajorDefinition(
                "provisional_major",
                "Provisional Major",
                "SYNTH",
                ["OPAQUE_C", "OPAQUE_D"],
                verification_status="provisional",
                award_rules=[
                    {
                        "id": "provisional_major_award",
                        "type": "weighted_average",
                        "course_codes": ["OPAQUE_C", "OPAQUE_D"],
                        "minimum_average": 75,
                        "weighting": {"basis": "equal"},
                        "verification_status": "provisional",
                    }
                ],
            ),
        },
        {},
        [],
        faculty_key="synthetic",
        award_rules=[
            {
                "id": "synthetic_dependency_ready_qualification",
                "type": "qualification_distinction",
                "curriculum_rules": [
                    {
                        "id": "synthetic_subject_award_dependency",
                        "type": "award_dependency",
                        "award_scope": "subject_distinction",
                        "minimum_count": 1,
                        "required_outcome": "eligible",
                        "minimum_verification_status": "verified",
                    }
                ],
            }
        ],
    )


def _synthetic_student(mark: int = 80) -> StudentRecord:
    return StudentRecord(
        "SYN7L",
        "Opaque Student",
        "Synthetic Programme",
        ["Opaque Major"],
        [
            CourseResult("OPAQUE_A", "OPAQUE_A", 7, 10, mark, "P", 2024),
            CourseResult("OPAQUE_B", "OPAQUE_B", 7, 10, mark, "P", 2024),
            CourseResult("OPAQUE_C", "OPAQUE_C", 7, 10, mark, "P", 2024),
            CourseResult("OPAQUE_D", "OPAQUE_D", 7, 10, mark, "P", 2024),
        ],
    )


def test_synthetic_governed_major_award_identity_without_institution_branch():
    row = _compute_distinction(
        _synthetic_student(),
        _synthetic_catalogue(),
        ["opaque_major"],
        course_load_framework=SyntheticLoadFramework(),
    ).subjects[0]

    assert row.eligible
    assert row.status == "verified"
    assert row.major_key == "opaque_major"
    assert row.policy_id == "opaque_major_award"


def test_synthetic_provisional_governed_major_award_is_not_verified():
    row = _compute_distinction(
        _synthetic_student(),
        _synthetic_catalogue(status="provisional"),
        ["opaque_major"],
        course_load_framework=SyntheticLoadFramework(),
    ).subjects[0]

    assert not row.eligible
    assert row.status == "provisional"
    assert row.major_key == "opaque_major"
    assert row.policy_id == "opaque_major_award"


def test_synthetic_award_dependency_can_use_governed_major_identity():
    distinction = _compute_distinction(
        _synthetic_student(),
        _synthetic_catalogue(),
        ["opaque_major", "provisional_major"],
        course_load_framework=SyntheticLoadFramework(),
    )

    assert distinction.qualification_eligible
    assert distinction.status == "verified"
    assert "Satisfied by: opaque_major" in distinction.reason
    assert any(
        subject.major_key == "provisional_major"
        and subject.policy_id == "provisional_major_award"
        for subject in distinction.subjects
    )


def test_science_fb8_1_has_no_named_major_policy_in_generic_python():
    source = inspect.getsource(rule_engine._compute_distinction) + "\n" + inspect.getsource(award_policy)

    assert "chemistry" not in source
    assert "computer_science" not in source
    assert "first_class_group" not in source


def test_science_legacy_alternative_fb8_2_thresholds_are_no_longer_python_policy():
    source = inspect.getsource(rule_engine._compute_distinction) + "\n" + inspect.getsource(award_policy)

    assert "for credit_value, count in ((18, 6), (24, 6), (36, 4))" not in source
