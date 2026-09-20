import inspect

import engine.rule_engine as rule_engine
from engine import award_policy
from engine.models import Catalogue, CourseFact, CourseResult, MajorDefinition, StudentRecord
from engine.rule_engine import _compute_distinction


def _course(code: str) -> CourseFact:
    return CourseFact(
        code,
        code,
        10,
        7,
        [],
        [],
        "Synthetic",
        verification_status="verified",
    )


def _passed(code: str, mark: int = 80) -> CourseResult:
    return CourseResult(code, code, 7, 10, mark, "P", 2024)


def _catalogue(
    *,
    path_a_status: str = "verified",
    path_b_status: str = "provisional",
    path_a_required: int = 2,
    path_b_required: int = 2,
) -> Catalogue:
    return Catalogue(
        courses={code: _course(code) for code in ["OPAQUE_A", "OPAQUE_B", "OPAQUE_C"]},
        majors={
            "opaque_major": MajorDefinition(
                "opaque_major",
                "Opaque Major",
                "SYN",
                ["OPAQUE_A", "OPAQUE_B"],
                verification_status="verified",
                award_rules=[
                    {
                        "id": "opaque_major_award",
                        "type": "weighted_average",
                        "course_codes": ["OPAQUE_A", "OPAQUE_B"],
                        "minimum_average": 75,
                        "weighting": {"basis": "equal"},
                    }
                ],
            )
        },
        programmes={},
        forbidden_combinations=[],
        faculty_key="synthetic",
        award_rules=[
            {
                "id": "opaque_path_a",
                "name": "Opaque verified path A",
                "type": "qualification_distinction",
                "verification_status": path_a_status,
                "curriculum_rules": [
                    {
                        "id": "path_a_count",
                        "type": "course_count",
                        "required": path_a_required,
                        "course_codes": ["OPAQUE_A", "OPAQUE_B"],
                    },
                    {
                        "id": "path_a_dependency",
                        "type": "award_dependency",
                        "award_scope": "subject_distinction",
                        "minimum_count": 1,
                        "required_outcome": "eligible",
                        "minimum_verification_status": "verified",
                    },
                ],
            },
            {
                "id": "opaque_path_b",
                "name": "Opaque provisional path B",
                "type": "qualification_distinction",
                "verification_status": path_b_status,
                "curriculum_rules": [
                    {
                        "id": "path_b_count",
                        "type": "course_count",
                        "required": path_b_required,
                        "course_codes": ["OPAQUE_A", "OPAQUE_C"],
                    },
                    {
                        "id": "path_b_dependency",
                        "type": "award_dependency",
                        "award_scope": "subject_distinction",
                        "minimum_count": 1,
                        "required_outcome": "eligible",
                        "minimum_verification_status": "verified",
                    },
                ],
            },
        ],
    )


def _student(*, include_c: bool = True, mark: int = 80) -> StudentRecord:
    results = [_passed("OPAQUE_A", mark), _passed("OPAQUE_B", mark)]
    if include_c:
        results.append(_passed("OPAQUE_C", mark))
    return StudentRecord(
        "SYN7P",
        "Synthetic Award Student",
        "Synthetic Programme",
        ["Opaque Major"],
        results,
    )


def test_generic_governed_award_orchestration_uses_verified_path_witness():
    distinction = _compute_distinction(_student(), _catalogue(), ["opaque_major"])

    assert distinction.qualification_eligible
    assert distinction.status == "verified"
    assert "Opaque verified path A" in distinction.reason
    assert "Opaque provisional path B" not in distinction.reason
    assert "Satisfied by: opaque_major" in distinction.reason


def test_generic_governed_award_orchestration_can_use_second_verified_path():
    distinction = _compute_distinction(
        _student(),
        _catalogue(path_a_required=99, path_b_status="verified"),
        ["opaque_major"],
    )

    assert distinction.qualification_eligible
    assert distinction.status == "verified"
    assert "Opaque provisional path B" in distinction.reason


def test_only_unverified_successful_paths_do_not_produce_verified_award():
    distinction = _compute_distinction(
        _student(),
        _catalogue(path_a_status="unverified", path_b_status="provisional"),
        ["opaque_major"],
    )

    assert not distinction.qualification_eligible
    assert distinction.status == "unverified"
    assert "Opaque verified path A" in distinction.reason
    assert "Opaque provisional path B" in distinction.reason


def test_all_governed_qualification_paths_can_fail_without_institution_branch():
    distinction = _compute_distinction(
        _student(include_c=False),
        _catalogue(path_a_required=99, path_b_required=99),
        ["opaque_major"],
    )

    assert not distinction.qualification_eligible
    assert distinction.status == "provisional"


def test_compute_distinction_no_longer_contains_science_award_branch():
    source = inspect.getsource(rule_engine._compute_distinction) + "\n" + inspect.getsource(award_policy)

    assert "uct_science" not in source
    assert "science_degree" not in source
    assert "science_fb8_2" not in source
    assert "first_credits" not in source
    assert "senior_first_credits" not in source
