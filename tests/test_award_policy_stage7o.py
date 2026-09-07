import inspect
from dataclasses import dataclass
from typing import Any

import engine.curriculum as curriculum
import engine.rule_engine as rule_engine
from engine.catalogue import load_catalogue
from engine.curriculum import CurriculumEvaluator
from engine.models import Catalogue, CourseFact, CourseResult, StudentRecord
from engine.rule_engine import compute_report
from engine.scope import build_programme_scope


@dataclass(frozen=True, slots=True)
class SyntheticCreditFramework:
    credit_by_code: dict[str, int]

    framework_id: str = "synthetic-credit-values"
    institution_id: str = "synthetic"

    def credit_value(self, item: Any) -> int:
        return self.credit_by_code[item.code]

    def academic_level(self, item: Any) -> str:
        return "advanced"

    def is_senior_level(self, item: Any) -> bool:
        return True

    def is_level(self, item: Any, level: int) -> bool:
        return level == 7


@dataclass(frozen=True, slots=True)
class SyntheticLoadFramework:
    load_by_code: dict[str, float]

    framework_id: str = "synthetic-load-values"
    institution_id: str = "synthetic"

    def load_equivalent(self, item: Any) -> float:
        code = item if isinstance(item, str) else item.code
        return self.load_by_code[code]


def _opaque_fact(code: str) -> CourseFact:
    return CourseFact(
        code,
        code,
        1,
        0,
        [],
        [],
        "Opaque Studies",
        counts_as_science=True,
        verification_status="verified",
    )


def _opaque_catalogue(codes: list[str]) -> Catalogue:
    return Catalogue(
        {code: _opaque_fact(code) for code in codes},
        {},
        {},
        [],
        faculty_key="synthetic",
    )


def _opaque_student(
    codes: list[str],
    *,
    marks: dict[str, int | None] | None = None,
    grades: dict[str, str] | None = None,
    repeated_code: str = "",
) -> StudentRecord:
    marks = marks or {}
    grades = grades or {}
    results = []
    if repeated_code:
        results.append(CourseResult(repeated_code, repeated_code, 0, 1, 45, "F", 2023))
    results.extend(
        CourseResult(
            code,
            code,
            0,
            1,
            marks.get(code, 80),
            grades.get(code, "P"),
            2024,
        )
        for code in codes
    )
    return StudentRecord(
        "SYN7O",
        "Opaque Best-N Student",
        "Synthetic Programme",
        [],
        results,
    )


def _best_n_rule(credit_value: int, required: int = 2) -> dict[str, Any]:
    return {
        "id": "opaque_best_n",
        "type": "best_n_average",
        "required": required,
        "minimum_average": 75,
        "weighting": {"basis": "equal"},
        "filters": {"credit_values": [credit_value]},
        "first_attempt_only": True,
        "exclude_grade_tokens": ["ALT"],
    }


def test_best_n_average_filters_by_academic_credit_framework_not_load():
    codes = ["OPAQUE_A", "OPAQUE_B", "OPAQUE_C", "OPAQUE_D"]
    credit = SyntheticCreditFramework(
        {
            "OPAQUE_A": 5,
            "OPAQUE_B": 5,
            "OPAQUE_C": 8,
            "OPAQUE_D": 5,
        }
    )
    load = SyntheticLoadFramework(
        {
            "OPAQUE_A": 9.0,
            "OPAQUE_B": 0.25,
            "OPAQUE_C": 0.25,
            "OPAQUE_D": 4.0,
        }
    )

    evaluation = CurriculumEvaluator(
        _opaque_student(codes, marks={"OPAQUE_A": 90, "OPAQUE_B": 70, "OPAQUE_D": 80}),
        _opaque_catalogue(codes),
        credit_framework=credit,
        course_load_framework=load,
    ).evaluate(_best_n_rule(5))

    assert evaluation.complete
    assert evaluation.used_course_codes == ["OPAQUE_A", "OPAQUE_D"]
    assert evaluation.current == 85


def test_best_n_average_uses_configured_status_and_attempt_exclusions():
    codes = ["OPAQUE_A", "OPAQUE_B", "OPAQUE_C"]
    credit = SyntheticCreditFramework({code: 5 for code in codes})
    evaluation = CurriculumEvaluator(
        _opaque_student(
            codes,
            grades={"OPAQUE_B": "ALT"},
            repeated_code="OPAQUE_C",
        ),
        _opaque_catalogue(codes),
        credit_framework=credit,
    ).evaluate(_best_n_rule(5))

    assert not evaluation.complete
    assert evaluation.used_course_codes == ["OPAQUE_A"]
    assert "OPAQUE_B" in evaluation.detail
    assert "OPAQUE_C" in evaluation.detail


def test_best_n_average_missing_numeric_mark_cannot_qualify():
    codes = ["OPAQUE_A", "OPAQUE_B", "OPAQUE_C"]
    credit = SyntheticCreditFramework({code: 5 for code in codes})
    evaluation = CurriculumEvaluator(
        _opaque_student(codes, marks={"OPAQUE_A": 80, "OPAQUE_B": None}),
        _opaque_catalogue(codes),
        credit_framework=credit,
    ).evaluate(_best_n_rule(5, required=3))

    assert not evaluation.complete
    assert evaluation.status == "unverified"
    assert "Numeric marks are missing" in " ".join(evaluation.assumptions)


def _science_catalogue() -> Catalogue:
    full = load_catalogue("uct_science")
    scoped, _ = build_programme_scope(
        "uct_science",
        full,
        "bsc_science",
        "current_2023_plus",
    )
    return scoped


def _science_result(
    catalogue: Catalogue,
    code: str,
    mark: int | None = 80,
    grade: str = "P",
) -> CourseResult:
    fact = catalogue.courses[code]
    return CourseResult(code, fact.name, fact.nqf_level, fact.nqf_credits, mark, grade, 2024)


SCIENCE_18_24_36_CODES = [
    "CEM1000W",
    "MAM1031F",
    "MAM1032S",
    "PHY1031F",
    "PHY1032S",
    "CEM2005W",
    "CEM3005W",
    "AGE1002S",
    "AGE1005L",
    "AST1000S",
    "BIO1000F",
    "BIO1000H",
    "BIO1004S",
    "AGE2011S",
    "AGE2012F",
    "AST2002H",
    "AST2003H",
    "BIO2014F",
    "BIO2015F",
    "AGE3006H",
    "AGE3011F",
    "AGE3012S",
    "AGE3013H",
]


def _science_alternative_student(
    *,
    omit: str = "",
    marks: dict[str, int | None] | None = None,
    grades: dict[str, str] | None = None,
    repeated_code: str = "",
    years_registered: int | None = 3,
    include_major: bool = True,
) -> tuple[Catalogue, StudentRecord]:
    catalogue = _science_catalogue()
    codes = [code for code in SCIENCE_18_24_36_CODES if code != omit]
    results = []
    if repeated_code:
        results.append(_science_result(catalogue, repeated_code, 45, "F"))
    marks = marks or {}
    grades = grades or {}
    results.extend(
        _science_result(
            catalogue,
            code,
            marks.get(code, 80),
            grades.get(code, "P"),
        )
        for code in codes
    )
    student = StudentRecord(
        "SCI7O",
        "Science Alternative Student",
        "Bachelor of Science",
        ["Chemistry"] if include_major else [],
        results,
        faculty_key="uct_science",
        programme_key="bsc_science",
        pathway_key="current_2023_plus",
        years_registered=years_registered,
    )
    return catalogue, student


def test_science_alternative_fb8_2_policy_is_governed_data():
    catalogue = _science_catalogue()
    rule = next(
        rule
        for rule in catalogue.award_rules
        if rule.get("id")
        == "science_fb8_2_alternative_18_24_36_qualification_distinction"
    )

    assert rule["verification_status"] == "unverified"
    assert rule["complete_within_years"] == "programme_minimum_duration"
    assert [child["type"] for child in rule["curriculum_rules"]] == [
        "best_n_average",
        "best_n_average",
        "best_n_average",
        "award_dependency",
    ]
    assert [child["filters"]["credit_values"][0] for child in rule["curriculum_rules"][:3]] == [
        18,
        24,
        36,
    ]
    assert [child["required"] for child in rule["curriculum_rules"][:3]] == [6, 6, 4]
    assert all(child["exclude_grade_tokens"] == ["SP"] for child in rule["curriculum_rules"][:3])


def test_science_alternative_path_computes_but_unverified_policy_bounds_authority():
    catalogue, student = _science_alternative_student()

    distinction = compute_report(student, catalogue).distinction

    assert not distinction.qualification_eligible
    assert distinction.status == "unverified"
    assert "Science FB8.2" in distinction.reason
    assert "Satisfied by: chemistry" in distinction.reason


def test_science_alternative_missing_credit_group_candidate_fails():
    catalogue, student = _science_alternative_student(omit="AGE2011S")

    distinction = compute_report(student, catalogue).distinction

    assert not distinction.qualification_eligible
    assert "Best 5 of 6 eligible results average" in distinction.reason


def test_science_alternative_group_average_preserves_best_n_compatibility():
    catalogue, student = _science_alternative_student(
        marks={"AGE1002S": 40, "AGE1005L": 80}
    )

    distinction = compute_report(student, catalogue).distinction

    assert not distinction.qualification_eligible
    assert "Best 6 of 6 eligible results average 80.00%" in distinction.reason


def test_science_alternative_excludes_repeat_sp_and_missing_mark():
    catalogue, repeated = _science_alternative_student(repeated_code="AGE2011S")
    repeated_report = compute_report(repeated, catalogue).distinction
    catalogue, supplementary = _science_alternative_student(grades={"AGE2011S": "SP"})
    supplementary_report = compute_report(supplementary, catalogue).distinction
    catalogue, missing = _science_alternative_student(marks={"AGE2011S": None})
    missing_report = compute_report(missing, catalogue).distinction

    assert "AGE2011S" in repeated_report.reason
    assert "AGE2011S" in supplementary_report.reason
    assert "Best 5 of 6 eligible results average" in missing_report.reason


def test_science_alternative_duration_and_dependency_are_governed_path_conditions():
    catalogue, too_long = _science_alternative_student(years_registered=4)
    too_long_report = compute_report(too_long, catalogue).distinction
    catalogue, missing_duration = _science_alternative_student(years_registered=None)
    missing_duration_report = compute_report(missing_duration, catalogue).distinction
    catalogue, no_major = _science_alternative_student(include_major=False)
    no_major_report = compute_report(no_major, catalogue).distinction

    assert "requires completion within 3" in too_long_report.reason
    assert "cannot be verified without years registered" in missing_duration_report.reason
    assert "No qualifying subject distinction" in no_major_report.reason


def test_science_alternative_policy_removed_from_generic_python():
    distinction_source = inspect.getsource(rule_engine._compute_distinction)
    evaluator_source = inspect.getsource(curriculum.CurriculumEvaluator.evaluate)

    assert "for credit_value, count in ((18, 6), (24, 6), (36, 4))" not in distinction_source
    assert "grade != \"SP\"" not in distinction_source
    assert "science_fb8_2_alternative" not in evaluator_source
    best_n_source = evaluator_source[evaluator_source.find('if rule_type == "best_n_average"') :]
    assert "\"SP\"" not in best_n_source
