import inspect
import json
from pathlib import Path

import engine.curriculum as curriculum
import engine.rule_engine as rule_engine
from engine.catalogue import load_catalogue
from engine.curriculum import CurriculumEvaluator
from engine.models import Catalogue, CourseFact, CourseResult, ProgrammeRules, StudentRecord
from engine.rule_engine import compute_report
from engine.scope import build_programme_scope


def _course(code: str, level: int, credits: int = 10) -> CourseFact:
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


def _result(
    code: str,
    mark: int | None,
    grade: str | None,
    *,
    level: int = 5,
    credits: int = 10,
    year: int = 2026,
) -> CourseResult:
    return CourseResult(code, code, level, credits, mark, grade, year)


def _synthetic_catalogue() -> Catalogue:
    return Catalogue(
        courses={
            "OPAQUE_LOW": _course("OPAQUE_LOW", 5, 10),
            "OPAQUE_HIGH": _course("OPAQUE_HIGH", 7, 10),
        },
        majors={},
        programmes={
            "opaque_programme": ProgrammeRules(
                key="opaque_programme",
                name="Opaque Programme",
                total_nqf_credits=20,
                level_7_nqf_credits=10,
                semester_course_equivalents=0,
                senior_course_equivalents=0,
                humanities_course_equivalents=0,
                required_majors=0,
                required_humanities_majors=0,
                programme_type="structured",
                scope_verified=True,
            )
        },
        forbidden_combinations=[],
        faculty_key="synthetic",
        programme_key="opaque_programme",
    )


def _synthetic_student(*results: CourseResult) -> StudentRecord:
    return StudentRecord(
        "SYN7S",
        "Synthetic Stage 7S",
        "Opaque Programme",
        [],
        list(results),
        programme_key="opaque_programme",
        years_registered=3,
    )


def _first_attempt_rule(action: str | None, *, threshold: int = 75) -> dict:
    rule = {
        "id": "synthetic_first_attempt_average",
        "type": "first_attempt_weighted_average",
        "course_codes": ["OPAQUE_LOW", "OPAQUE_HIGH"],
        "minimum_average": threshold,
        "level_weights": {"5": 1, "7": 2},
    }
    if action is not None:
        rule["status_treatment"] = {"VOID": action}
    return rule


def _evaluate_synthetic(rule: dict, student: StudentRecord | None = None):
    student = student or _synthetic_student(
        _result("OPAQUE_LOW", None, "VOID", level=5),
        _result("OPAQUE_HIGH", 90, "P", level=7),
    )
    return CurriculumEvaluator(student, _synthetic_catalogue()).evaluate(rule)


def _commerce_scope(programme_key: str):
    full = load_catalogue("uct_commerce")
    return build_programme_scope("uct_commerce", full, programme_key, "")


def _commerce_result(
    catalogue: Catalogue,
    code: str,
    mark: int | None,
    grade: str | None,
    *,
    year: int = 2026,
) -> CourseResult:
    fact = catalogue.courses[code]
    return CourseResult(
        code,
        fact.name,
        fact.nqf_level,
        fact.nqf_credits,
        mark,
        grade,
        year,
    )


def _commerce_award_rule(programme_key: str = "cb001eco02"):
    catalogue, _ = _commerce_scope(programme_key)
    rule = catalogue.programmes[programme_key].award_rules[0]["curriculum_rules"][0]
    return catalogue, rule


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
        "COM7SREG",
        "Commerce Stage 7S Regression",
        programme.name,
        [],
        [_commerce_result(catalogue, code, mark, "P") for code in codes],
        faculty_key="uct_commerce",
        programme_key=programme_key,
        years_registered=programme.minimum_duration_years,
    )
    return catalogue, student


def _commerce_token_evaluation(token: str):
    catalogue, rule = _commerce_award_rule()
    student = StudentRecord(
        "COM7S",
        "Commerce Stage 7S",
        "BCom Economics and Finance",
        [],
        [
            _commerce_result(catalogue, "ACC1021F", None, token),
            _commerce_result(catalogue, "ACC1022Z", 90, "P"),
        ],
        faculty_key="uct_commerce",
        programme_key="cb001eco02",
        years_registered=3,
    )
    return CurriculumEvaluator(student, catalogue).evaluate(rule)


def test_status_treatment_zero_is_rule_owned_and_preserves_level_weights():
    evaluation = _evaluate_synthetic(_first_attempt_rule("zero"))

    assert not evaluation.complete
    assert evaluation.current == 60
    assert evaluation.used_course_codes == ["OPAQUE_HIGH", "OPAQUE_LOW"]
    assert "counted OPAQUE_LOW as zero" in evaluation.detail


def test_status_treatment_exclude_removes_attempt_from_numerator_and_denominator():
    evaluation = _evaluate_synthetic(_first_attempt_rule("exclude"))

    assert evaluation.complete
    assert evaluation.current == 90
    assert evaluation.used_course_codes == ["OPAQUE_HIGH"]
    assert "excluded OPAQUE_LOW" in evaluation.detail


def test_status_treatment_requires_verification_does_not_create_verified_positive():
    evaluation = _evaluate_synthetic(_first_attempt_rule("requires_verification"))

    assert evaluation.complete
    assert evaluation.current == 90
    assert evaluation.status == "unverified"
    assert evaluation.confidence == 0.0
    assert "requires verification for OPAQUE_LOW" in evaluation.detail


def test_same_raw_token_can_have_different_rule_owned_treatments():
    zero = _evaluate_synthetic(_first_attempt_rule("zero"))
    exclude = _evaluate_synthetic(_first_attempt_rule("exclude"))
    requires = _evaluate_synthetic(_first_attempt_rule("requires_verification"))

    assert zero.current == 60
    assert exclude.current == 90
    assert requires.current == 90
    assert not zero.complete
    assert exclude.complete
    assert requires.status == "unverified"


def test_later_pass_does_not_replace_configured_zero_first_attempt():
    student = _synthetic_student(
        _result("OPAQUE_LOW", None, "VOID", level=5, year=2025),
        _result("OPAQUE_LOW", 100, "P", level=5, year=2026),
        _result("OPAQUE_HIGH", 90, "P", level=7, year=2026),
    )

    evaluation = _evaluate_synthetic(_first_attempt_rule("zero"), student)

    assert evaluation.current == 60
    assert evaluation.used_course_codes == ["OPAQUE_HIGH", "OPAQUE_LOW"]


def test_numeric_failed_first_attempt_uses_numeric_mark_not_status_treatment():
    student = _synthetic_student(
        _result("OPAQUE_LOW", 42, "F", level=5),
        _result("OPAQUE_HIGH", 90, "P", level=7),
    )

    evaluation = _evaluate_synthetic(_first_attempt_rule("zero"), student)

    assert evaluation.current == 74
    assert "counted OPAQUE_LOW as zero" not in evaluation.detail


def test_unconfigured_status_without_mark_is_unverified_not_implicit_zero():
    student = _synthetic_student(_result("OPAQUE_LOW", None, "VOID", level=5))
    evaluation = _evaluate_synthetic(_first_attempt_rule(None), student)

    assert not evaluation.complete
    assert evaluation.current == 0
    assert evaluation.status == "unverified"
    assert "No first-attempt numeric results are available" in evaluation.detail


def test_commerce_rules_encode_explicit_uct_status_treatment():
    data = json.loads(Path("data/uct_commerce/degree_requirements.json").read_text())
    first_attempt_rules: list[dict] = []

    def visit(value):
        if isinstance(value, dict):
            if value.get("type") == "first_attempt_weighted_average":
                first_attempt_rules.append(value)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(data)

    assert len(first_attempt_rules) == 68
    assert all(
        rule.get("status_treatment")
        == {"AB": "zero", "DPR": "zero", "INC": "zero", "EXA": "zero"}
        for rule in first_attempt_rules
    )


def test_commerce_configured_status_tokens_preserve_zero_treatment():
    for token in ("AB", "DPR", "INC", "EXA"):
        evaluation = _commerce_token_evaluation(token)

        assert evaluation.current < 90
        assert "counted ACC1021F as zero" in evaluation.detail


def test_commerce_configured_zero_first_attempt_ignores_later_pass():
    catalogue, rule = _commerce_award_rule()
    student = StudentRecord(
        "COM7S2",
        "Commerce Stage 7S",
        "BCom Economics and Finance",
        [],
        [
            _commerce_result(catalogue, "ACC1021F", None, "AB", year=2025),
            _commerce_result(catalogue, "ACC1021F", 100, "P", year=2026),
            _commerce_result(catalogue, "ACC1022Z", 90, "P", year=2026),
        ],
        faculty_key="uct_commerce",
        programme_key="cb001eco02",
        years_registered=3,
    )

    evaluation = CurriculumEvaluator(student, catalogue).evaluate(rule)

    assert evaluation.current < 90
    assert "counted ACC1021F as zero" in evaluation.detail


def test_commerce_numeric_failed_first_attempt_is_not_replaced_or_zeroed():
    catalogue, rule = _commerce_award_rule()
    student = StudentRecord(
        "COM7S3",
        "Commerce Stage 7S",
        "BCom Economics and Finance",
        [],
        [
            _commerce_result(catalogue, "ACC1021F", 42, "F", year=2025),
            _commerce_result(catalogue, "ACC1021F", 100, "P", year=2026),
            _commerce_result(catalogue, "ACC1022Z", 90, "P", year=2026),
        ],
        faculty_key="uct_commerce",
        programme_key="cb001eco02",
        years_registered=3,
    )

    evaluation = CurriculumEvaluator(student, catalogue).evaluate(rule)

    assert 42 < evaluation.current < 90
    assert "counted ACC1021F as zero" not in evaluation.detail


def test_commerce_failed_no_mark_fallback_remains_separate_from_status_treatment():
    catalogue, rule = _commerce_award_rule()
    student = StudentRecord(
        "COM7S4",
        "Commerce Stage 7S",
        "BCom Economics and Finance",
        [],
        [
            _commerce_result(catalogue, "ACC1021F", None, "F"),
            _commerce_result(catalogue, "ACC1022Z", 90, "P"),
        ],
        faculty_key="uct_commerce",
        programme_key="cb001eco02",
        years_registered=3,
    )

    evaluation = CurriculumEvaluator(student, catalogue).evaluate(rule)

    assert evaluation.current < 90
    assert "counted ACC1021F as zero" not in evaluation.detail


def test_commerce_degree_distinction_regression_remains_unchanged():
    catalogue, student = _complete_commerce_student("cb001eco02", 90)

    distinction = compute_report(student, catalogue).distinction
    degree = next(row for row in distinction.subjects if row.major == "Degree with distinction")

    assert degree.eligible
    assert degree.status == "verified"
    assert distinction.qualification_eligible


def test_commerce_no_failures_duration_conflict_and_manual_regressions_unchanged():
    catalogue, student = _complete_commerce_student("cb001eco02", 90)
    student.results.append(_commerce_result(catalogue, "ACC1021F", 45, "F", year=2025))
    no_failures = compute_report(student, catalogue).distinction
    degree = next(row for row in no_failures.subjects if row.major == "Degree with distinction")
    assert not degree.eligible
    assert "Failed attempt" in degree.reason

    catalogue, student = _complete_commerce_student("cb001eco02", 90)
    student.years_registered = 4
    duration = compute_report(student, catalogue).distinction
    degree = next(row for row in duration.subjects if row.major == "Degree with distinction")
    assert not degree.eligible
    assert "requires completion within 3" in degree.reason

    actuarial_catalogue, actuarial = _complete_commerce_student("cu020bus01", 90)
    conflict = compute_report(actuarial, actuarial_catalogue).distinction
    assert conflict.status == "conflict"

    iop_catalogue, iop_student = _complete_commerce_student("cb004bus28", 90)
    iop = compute_report(iop_student, iop_catalogue).distinction
    row = next(
        item
        for item in iop.subjects
        if item.major == "Industrial and Organisational Psychology subject distinction"
    )
    assert row.status == "unverified"


def test_first_attempt_weighted_average_contains_no_hard_coded_uct_tokens():
    source = inspect.getsource(CurriculumEvaluator.evaluate)

    assert "status_treatment" in source
    for token in ("AB", "DPR", "INC", "EXA"):
        assert token not in source


def test_status_treatment_is_not_owned_by_grading_or_commerce_identity():
    evaluator_source = inspect.getsource(CurriculumEvaluator.evaluate)
    distinction_source = inspect.getsource(rule_engine._compute_distinction)
    grading_source = inspect.getsource(curriculum.GradingScheme)

    assert "uct_commerce" not in evaluator_source
    assert "status_treatment" not in grading_source
    assert "status_treatment" not in distinction_source
