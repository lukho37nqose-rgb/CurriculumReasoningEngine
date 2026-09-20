import inspect
from dataclasses import dataclass
from typing import Any

from engine import award_policy, rule_engine
from engine.catalogue import load_catalogue
from engine.curriculum import CurriculumEvaluator
from engine.models import Catalogue, CourseFact, CourseResult, StudentRecord
from engine.rule_engine import compute_report
from engine.scope import build_programme_scope


@dataclass(frozen=True, slots=True)
class SyntheticCreditFramework:
    credits: dict[str, int]
    framework_id: str = "synthetic-award-credit"
    institution_id: str = "test"

    def credit_value(self, item: Any) -> int:
        return self.credits[item.code]

    def academic_level(self, item: Any) -> int:
        return 1

    def is_senior_level(self, item: Any) -> bool:
        return True

    def is_level(self, item: Any, level: int) -> bool:
        return level == 1


@dataclass(frozen=True, slots=True)
class SyntheticLoadFramework:
    loads: dict[str, float]
    framework_id: str = "synthetic-award-load"
    institution_id: str = "test"

    def load_equivalent(self, item: Any) -> float:
        return self.loads[item.code]


BASE_CREDIT = SyntheticCreditFramework({"ALPHA": 10, "BETA": 30})
ALT_CREDIT = SyntheticCreditFramework({"ALPHA": 30, "BETA": 10})
ALPHA_HEAVY_LOAD = SyntheticLoadFramework({"ALPHA": 2.0, "BETA": 0.5})
BETA_HEAVY_LOAD = SyntheticLoadFramework({"ALPHA": 0.5, "BETA": 2.0})


def _opaque_catalogue() -> Catalogue:
    courses = {
        code: CourseFact(
            code=code,
            name=code,
            nqf_credits=1,
            nqf_level=1,
            prerequisites=[],
            offered=[],
            department="Opaque",
        )
        for code in ("ALPHA", "BETA")
    }
    return Catalogue(
        courses=courses,
        majors={},
        programmes={},
        forbidden_combinations=[],
        faculty_key="synthetic",
        scope_status="verified",
    )


def _opaque_student() -> StudentRecord:
    return StudentRecord(
        "AW1",
        "Synthetic Award Student",
        "Opaque Award",
        [],
        [
            CourseResult("ALPHA", "ALPHA", 1, 1, 100, None),
            CourseResult("BETA", "BETA", 1, 1, 55, None),
        ],
        faculty_key="synthetic",
    )


def _average_rule(basis: str) -> dict[str, Any]:
    return {
        "type": "weighted_average",
        "id": f"{basis}_average",
        "label": f"{basis} average",
        "course_codes": ["ALPHA", "BETA"],
        "minimum_average": 75,
        "weighting": {"basis": basis},
    }


def test_weighted_average_uses_rule_owned_credit_value_basis():
    result = CurriculumEvaluator(
        _opaque_student(),
        _opaque_catalogue(),
        credit_framework=BASE_CREDIT,
        course_load_framework=BETA_HEAVY_LOAD,
    ).evaluate(_average_rule("credit_value"))

    assert result.current == 66.25
    assert not result.complete


def test_weighted_average_uses_rule_owned_equal_basis():
    result = CurriculumEvaluator(
        _opaque_student(),
        _opaque_catalogue(),
        credit_framework=BASE_CREDIT,
        course_load_framework=BETA_HEAVY_LOAD,
    ).evaluate(_average_rule("equal"))

    assert result.current == 77.5
    assert result.complete


def test_weighted_average_uses_rule_owned_course_load_basis():
    high_alpha = CurriculumEvaluator(
        _opaque_student(),
        _opaque_catalogue(),
        credit_framework=BASE_CREDIT,
        course_load_framework=ALPHA_HEAVY_LOAD,
    ).evaluate(_average_rule("course_load_equivalent"))
    high_beta = CurriculumEvaluator(
        _opaque_student(),
        _opaque_catalogue(),
        credit_framework=BASE_CREDIT,
        course_load_framework=BETA_HEAVY_LOAD,
    ).evaluate(_average_rule("course_load_equivalent"))

    assert high_alpha.current == 91
    assert high_alpha.complete
    assert high_beta.current == 64
    assert not high_beta.complete


def test_average_weighting_boundaries_are_independent():
    credit_before = CurriculumEvaluator(
        _opaque_student(),
        _opaque_catalogue(),
        credit_framework=BASE_CREDIT,
        course_load_framework=ALPHA_HEAVY_LOAD,
    ).evaluate(_average_rule("credit_value"))
    credit_after_load_change = CurriculumEvaluator(
        _opaque_student(),
        _opaque_catalogue(),
        credit_framework=BASE_CREDIT,
        course_load_framework=BETA_HEAVY_LOAD,
    ).evaluate(_average_rule("credit_value"))
    equal_after_credit_change = CurriculumEvaluator(
        _opaque_student(),
        _opaque_catalogue(),
        credit_framework=ALT_CREDIT,
        course_load_framework=BETA_HEAVY_LOAD,
    ).evaluate(_average_rule("equal"))

    assert credit_before.current == credit_after_load_change.current == 66.25
    assert equal_after_credit_change.current == 77.5
    assert equal_after_credit_change.complete


def _law_student(marks: dict[str, int]) -> StudentRecord:
    return StudentRecord(
        "LAW1",
        "Law Major Student",
        "Bachelor of Social Science",
        ["Law"],
        [
            CourseResult(code, code, 0, 0, mark, None, 2024)
            for code, mark in marks.items()
        ],
        faculty_key="uct_humanities",
        programme_key="bsocsc_regular",
        years_registered=3,
    )


def test_humanities_law_fb1_2_is_governed_award_rule_data():
    catalogue = load_catalogue("uct_humanities")
    law = catalogue.majors["law"]

    assert law.award_rules
    rule = law.award_rules[0]["curriculum_rules"][1]
    assert rule["type"] == "weighted_average"
    assert rule["weighting"] == {"basis": "credit_value"}
    assert set(rule["course_codes"]) == set(law.required_courses)


def test_migrated_humanities_law_fb1_2_distinction_regression():
    full = load_catalogue("uct_humanities")
    scoped, _ = build_programme_scope("uct_humanities", full, "bsocsc_regular")
    high_marks = {code: 75 for code in scoped.majors["law"].required_courses}
    low_marks = {code: 74 for code in scoped.majors["law"].required_courses}

    eligible = compute_report(_law_student(high_marks), scoped).distinction.subjects[0]
    ineligible = compute_report(_law_student(low_marks), scoped).distinction.subjects[0]

    assert eligible.major == "Law"
    assert eligible.status == "verified"
    assert eligible.eligible
    assert eligible.average == 75
    assert not ineligible.eligible
    assert ineligible.average == 74


def test_law_award_policy_is_not_hard_coded_in_compute_distinction():
    source = inspect.getsource(rule_engine._compute_distinction) + "\n" + inspect.getsource(award_policy)

    assert 'key == "law"' not in source
    assert "PBL, PVL, CML" not in source
    assert "PBL\", \"PVL\", \"CML" not in source
    assert "credit-weighted average of at least 75% across all six Law" not in source
