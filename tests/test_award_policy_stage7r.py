import inspect

import engine.rule_engine as rule_engine
from engine.catalogue import load_catalogue
from engine.models import Catalogue, CourseFact, CourseResult, ProgrammeRules, StudentRecord
from engine.rule_engine import _compute_distinction, compute_report
from engine.scope import build_programme_scope


def _commerce_scope(programme_key: str):
    full = load_catalogue("uct_commerce")
    return build_programme_scope("uct_commerce", full, programme_key, "")


def _commerce_result(catalogue: Catalogue, code: str, mark: int, year: int = 2026):
    fact = catalogue.courses[code]
    return CourseResult(
        code,
        fact.name,
        fact.nqf_level,
        fact.nqf_credits,
        mark,
        "P" if mark >= 50 else "F",
        year,
    )


def _choose_codes(rule: dict) -> list[str]:
    rule_type = rule.get("type")
    if rule_type == "course":
        return list(rule.get("course_codes", []))[:1]
    if rule_type == "all_courses":
        return list(rule.get("course_codes", []))
    if rule_type == "all_of":
        return [
            code for child in rule.get("children", []) for code in _choose_codes(child)
        ]
    if rule_type == "any_of":
        children = rule.get("children", [])
        return _choose_codes(children[0]) if children else []
    if rule_type == "choose_n":
        return list(rule.get("course_codes", []))[: int(rule.get("required", 1))]
    return []


def _complete_commerce_student(programme_key: str, mark: int = 85):
    catalogue, _ = _commerce_scope(programme_key)
    programme = catalogue.programmes[programme_key]
    codes: list[str] = []
    for rule in programme.curriculum_rules:
        codes.extend(_choose_codes(rule))
    codes = list(dict.fromkeys(code for code in codes if code in catalogue.courses))
    student = StudentRecord(
        "COM7R",
        "Commerce Stage 7R",
        programme.name,
        [],
        [_commerce_result(catalogue, code, mark) for code in codes],
        faculty_key="uct_commerce",
        programme_key=programme_key,
        years_registered=programme.minimum_duration_years,
    )
    return catalogue, student


def _synthetic_course(code: str, level: int, credits: int = 10) -> CourseFact:
    return CourseFact(
        code,
        code,
        credits,
        level,
        [],
        [],
        "Synthetic",
        verification_status="verified",
    )


def _synthetic_result(code: str, mark: int, level: int) -> CourseResult:
    return CourseResult(code, code, level, 10, mark, "P" if mark >= 50 else "F", 2026)


def _synthetic_structured_catalogue() -> Catalogue:
    return Catalogue(
        courses={
            "OPAQUE_ALPHA": _synthetic_course("OPAQUE_ALPHA", 5),
            "OPAQUE_BETA": _synthetic_course("OPAQUE_BETA", 7),
        },
        majors={},
        programmes={
            "opaque_programme": ProgrammeRules(
                key="opaque_programme",
                name="Opaque Structured Programme",
                total_nqf_credits=20,
                level_7_nqf_credits=10,
                semester_course_equivalents=0,
                senior_course_equivalents=0,
                humanities_course_equivalents=0,
                required_majors=0,
                required_humanities_majors=0,
                minimum_duration_years=3,
                programme_type="structured",
                scope_verified=True,
                award_rules=[
                    {
                        "name": "Opaque distinction",
                        "curriculum_rules": [
                            {
                                "type": "first_attempt_weighted_average",
                                "id": "opaque_programme_average",
                                "course_codes": ["OPAQUE_ALPHA", "OPAQUE_BETA"],
                                "minimum_average": 80,
                                "level_weights": {"5": 1, "7": 2},
                            }
                        ],
                        "complete_within_years": 3,
                    },
                    {
                        "name": "Opaque manual award",
                        "id": "opaque_manual_award",
                        "curriculum_rules": [
                            {
                                "type": "manual",
                                "id": "opaque_manual_component",
                                "label": "Manual component",
                                "status": "unverified",
                                "blocking": True,
                                "assumed_complete": True,
                            }
                        ],
                    },
                ],
            )
        },
        forbidden_combinations=[],
        faculty_key="synthetic",
        programme_key="opaque_programme",
        catalogue_version="Synthetic Structured 2026",
    )


def _synthetic_student(*, years_registered: int | None = 3) -> StudentRecord:
    return StudentRecord(
        "SYN7R",
        "Synthetic Structured Student",
        "Opaque Structured Programme",
        [],
        [
            _synthetic_result("OPAQUE_ALPHA", 70, 5),
            _synthetic_result("OPAQUE_BETA", 85, 7),
        ],
        programme_key="opaque_programme",
        years_registered=years_registered,
    )


def test_structured_programme_award_identity_is_deterministic_from_governed_data():
    catalogue, student = _complete_commerce_student("cb001eco02", 90)

    distinction = compute_report(student, catalogue).distinction

    rows = {row.major: row for row in distinction.subjects}
    assert rows["Degree with distinction"].policy_id == (
        "programme:cb001eco02:award:commerce_degree_distinction|bcom_no_failures"
    )
    assert rows["Economics subject distinction"].policy_id == (
        "programme:cb001eco02:award:economics_best3"
    )


def test_multiple_commerce_awards_remain_independent_outputs():
    catalogue, student = _complete_commerce_student("cb001eco02", 90)

    distinction = compute_report(student, catalogue).distinction

    assert {row.major for row in distinction.subjects} == {
        "Degree with distinction",
        "Economics subject distinction",
    }
    assert all(row.policy_id for row in distinction.subjects)


def test_commerce_duration_condition_remains_metadata_driven():
    catalogue, student = _complete_commerce_student("cb001eco02", 90)
    student.years_registered = 4

    distinction = compute_report(student, catalogue).distinction
    degree = next(row for row in distinction.subjects if row.major == "Degree with distinction")

    assert not degree.eligible
    assert degree.status == "verified"
    assert "requires completion within 3" in degree.reason


def test_commerce_missing_duration_evidence_remains_unverified():
    catalogue, student = _complete_commerce_student("cb001eco02", 90)
    student.years_registered = None

    distinction = compute_report(student, catalogue).distinction
    degree = next(row for row in distinction.subjects if row.major == "Degree with distinction")

    assert not degree.eligible
    assert degree.status == "unverified"
    assert "cannot be verified without years registered" in degree.reason


def test_advanced_actuarial_conflict_status_is_unchanged():
    catalogue, student = _complete_commerce_student("cu020bus01", 90)
    elective_rule = next(
        rule
        for rule in catalogue.programmes["cu020bus01"].curriculum_rules
        if rule.get("id") == "CU020BUS01_electives"
    )
    for code in elective_rule["course_codes"][:2]:
        if not any(row.code == code for row in student.results):
            student.results.append(_commerce_result(catalogue, code, 90))

    distinction = compute_report(student, catalogue).distinction

    assert not distinction.qualification_eligible
    assert distinction.status == "conflict"
    assert distinction.subjects[0].status == "conflict"


def test_iop_manual_component_remains_unverified():
    catalogue, student = _complete_commerce_student("cb004bus28", 90)

    distinction = compute_report(student, catalogue).distinction
    iop = next(
        row
        for row in distinction.subjects
        if row.major == "Industrial and Organisational Psychology subject distinction"
    )

    assert not iop.eligible
    assert iop.status == "unverified"
    assert "component" in iop.reason


def test_synthetic_structured_programme_uses_generic_orchestration_without_faculty_identity():
    distinction = _compute_distinction(
        _synthetic_student(),
        _synthetic_structured_catalogue(),
        [],
    )

    rows = {row.major: row for row in distinction.subjects}
    assert rows["Opaque distinction"].eligible
    assert rows["Opaque distinction"].policy_id == (
        "programme:opaque_programme:award:opaque_programme_average"
    )
    assert not rows["Opaque manual award"].eligible
    assert rows["Opaque manual award"].status == "unverified"
    assert distinction.qualification_eligible


def test_synthetic_structured_duration_blocks_without_special_faculty_code():
    distinction = _compute_distinction(
        _synthetic_student(years_registered=4),
        _synthetic_structured_catalogue(),
        [],
    )

    row = next(row for row in distinction.subjects if row.major == "Opaque distinction")
    assert not row.eligible
    assert "requires completion within 3" in row.reason


def test_structured_award_orchestration_does_not_require_commerce_identity():
    source = inspect.getsource(rule_engine._compute_distinction)

    assert "uct_commerce" not in source
    assert "commerce_structured" not in source
    assert "CB001" not in source
    assert "Finance subject distinction" not in source
    assert "Economics subject distinction" not in source


def test_structured_orchestration_does_not_duplicate_status_treatment_policy():
    source = inspect.getsource(rule_engine.CurriculumEvaluator.evaluate)

    assert '{"AB", "DPR", "INC", "EXA"}' not in source
