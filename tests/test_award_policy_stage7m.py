import inspect
from dataclasses import dataclass
from typing import Any

import engine.curriculum as curriculum
import engine.rule_engine as rule_engine
from engine import award_policy
from engine.catalogue import load_catalogue
from engine.curriculum import CurriculumEvaluator
from engine.models import Catalogue, CourseFact, CourseResult, MajorDefinition, StudentRecord
from engine.rule_engine import _compute_distinction, compute_report
from engine.scope import build_programme_scope


@dataclass(frozen=True, slots=True)
class SyntheticCreditFramework:
    credit_by_code: dict[str, int]
    level_by_code: dict[str, str]

    framework_id: str = "synthetic-credits"
    institution_id: str = "synthetic"

    def credit_value(self, item: Any) -> int:
        return self.credit_by_code[item.code]

    def academic_level(self, item: Any) -> str:
        return self.level_by_code[item.code]

    def is_senior_level(self, item: Any) -> bool:
        return self.academic_level(item) == "advanced"

    def is_level(self, item: Any, level: int) -> bool:
        return level == 7 and self.is_senior_level(item)


@dataclass(frozen=True, slots=True)
class SyntheticLoadFramework:
    load_by_code: dict[str, float]

    framework_id: str = "synthetic-load"
    institution_id: str = "synthetic"

    def load_equivalent(self, item: Any) -> float:
        code = item if isinstance(item, str) else item.code
        return self.load_by_code[code]


CREDIT = SyntheticCreditFramework(
    {"ALPHA": 40, "BETA": 60, "GAMMA": 30},
    {"ALPHA": "foundation", "BETA": "advanced", "GAMMA": "advanced"},
)
LOAD = SyntheticLoadFramework({"ALPHA": 0.5, "BETA": 2.0, "GAMMA": 3.0})


def _course(code: str) -> CourseFact:
    return CourseFact(
        code,
        code,
        1,
        0,
        [],
        [],
        "Opaque Studies",
        verification_status="verified",
    )


def _synthetic_catalogue(
    *,
    include_award: bool = True,
    award_status: str = "verified",
) -> Catalogue:
    award_rules = []
    if include_award:
        award_rules = [
            {
                "id": "opaque_subject_award",
                "type": "weighted_average",
                "course_codes": ["ALPHA", "BETA"],
                "minimum_average": 75,
                "weighting": {"basis": "equal"},
                "verification_status": award_status,
            }
        ]
    return Catalogue(
        courses={code: _course(code) for code in ["ALPHA", "BETA", "GAMMA"]},
        majors={
            "opaque_major": MajorDefinition(
                "opaque_major",
                "Opaque Major",
                "SYNTH",
                ["ALPHA", "BETA"],
                verification_status=award_status,
                award_rules=award_rules,
            )
        },
        programmes={},
        forbidden_combinations=[],
        faculty_key="synthetic",
        award_rules=[
            {
                "id": "opaque_direct_qualification",
                "type": "qualification_distinction",
                "verification_status": "verified",
                "curriculum_rules": [
                    {
                        "id": "opaque_total_credits",
                        "type": "passed_mark_credits",
                        "minimum_credits": 100,
                        "minimum_mark": 75,
                        "first_attempt_only": True,
                        "exclude_grade_tokens": ["SUPP"],
                    },
                    {
                        "id": "opaque_senior_credits",
                        "type": "passed_mark_credits",
                        "minimum_credits": 60,
                        "minimum_mark": 75,
                        "first_attempt_only": True,
                        "exclude_grade_tokens": ["SUPP"],
                        "filters": {"senior": True},
                    },
                    {
                        "id": "opaque_subject_dependency",
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


def _synthetic_student(
    *,
    alpha_mark: int = 80,
    beta_mark: int = 78,
    gamma_mark: int = 74,
    beta_grade: str = "P",
    repeated_alpha: bool = False,
) -> StudentRecord:
    results = []
    if repeated_alpha:
        results.append(CourseResult("ALPHA", "ALPHA", 0, 1, 45, "F", 2023))
    results.extend(
        [
            CourseResult("ALPHA", "ALPHA", 0, 1, alpha_mark, "P", 2024),
            CourseResult("BETA", "BETA", 0, 1, beta_mark, beta_grade, 2024),
            CourseResult("GAMMA", "GAMMA", 0, 1, gamma_mark, "P", 2024),
        ]
    )
    return StudentRecord(
        "SYN7M",
        "Synthetic Credit Student",
        "Synthetic Programme",
        ["Opaque Major"],
        results,
    )


def test_passed_mark_credits_uses_academic_credit_not_load_or_count():
    rule = {
        "id": "credit_threshold",
        "type": "passed_mark_credits",
        "minimum_credits": 100,
        "minimum_mark": 75,
    }

    evaluation = CurriculumEvaluator(
        _synthetic_student(),
        _synthetic_catalogue(),
        credit_framework=CREDIT,
        course_load_framework=LOAD,
    ).evaluate(rule)

    assert evaluation.complete
    assert evaluation.current == 100
    assert evaluation.used_course_codes == ["ALPHA", "BETA"]
    assert sum(LOAD.load_equivalent(code) for code in evaluation.used_course_codes) == 2.5


def test_passed_mark_credits_excludes_below_minimum_mark_courses():
    evaluation = CurriculumEvaluator(
        _synthetic_student(gamma_mark=74),
        _synthetic_catalogue(),
        credit_framework=CREDIT,
    ).evaluate(
        {
            "id": "credit_threshold",
            "type": "passed_mark_credits",
            "minimum_credits": 130,
            "minimum_mark": 75,
        }
    )

    assert not evaluation.complete
    assert evaluation.current == 100
    assert "GAMMA" not in evaluation.used_course_codes


def test_passed_mark_credits_senior_filter_uses_credit_framework_levels():
    evaluation = CurriculumEvaluator(
        _synthetic_student(),
        _synthetic_catalogue(),
        credit_framework=CREDIT,
    ).evaluate(
        {
            "id": "senior_credit_threshold",
            "type": "passed_mark_credits",
            "minimum_credits": 60,
            "minimum_mark": 75,
            "filters": {"senior": True},
        }
    )

    assert evaluation.complete
    assert evaluation.current == 60
    assert evaluation.used_course_codes == ["BETA"]


def test_passed_mark_credits_applies_configured_attempt_and_status_treatment():
    repeated = CurriculumEvaluator(
        _synthetic_student(repeated_alpha=True),
        _synthetic_catalogue(),
        credit_framework=CREDIT,
    ).evaluate(
        {
            "id": "first_attempt_credit_threshold",
            "type": "passed_mark_credits",
            "minimum_credits": 100,
            "minimum_mark": 75,
            "first_attempt_only": True,
        }
    )
    supplementary = CurriculumEvaluator(
        _synthetic_student(beta_grade="SUPP"),
        _synthetic_catalogue(),
        credit_framework=CREDIT,
    ).evaluate(
        {
            "id": "status_exclusion_credit_threshold",
            "type": "passed_mark_credits",
            "minimum_credits": 100,
            "minimum_mark": 75,
            "exclude_grade_tokens": ["SUPP"],
        }
    )

    assert not repeated.complete
    assert repeated.current == 60
    assert repeated.used_course_codes == ["BETA"]
    assert not supplementary.complete
    assert supplementary.current == 40
    assert supplementary.used_course_codes == ["ALPHA"]


def test_synthetic_direct_path_can_pass_while_dependency_fails():
    distinction = _compute_distinction(
        _synthetic_student(),
        _synthetic_catalogue(include_award=False),
        ["opaque_major"],
        credit_framework=CREDIT,
        course_load_framework=LOAD,
    )

    assert not distinction.qualification_eligible
    assert distinction.status == "verified"
    assert "No qualifying subject distinction" in distinction.reason


def test_synthetic_dependency_can_pass_while_numeric_threshold_fails():
    distinction = _compute_distinction(
        _synthetic_student(beta_mark=70),
        _synthetic_catalogue(),
        ["opaque_major"],
        credit_framework=CREDIT,
        course_load_framework=LOAD,
    )

    assert not distinction.qualification_eligible
    assert distinction.status == "verified"
    assert "40 of 100 academic credits" in distinction.reason


def test_synthetic_verified_witness_not_weakened_by_unrelated_provisional_award():
    catalogue = _synthetic_catalogue()
    catalogue.majors["provisional_major"] = MajorDefinition(
        "provisional_major",
        "Provisional Major",
        "SYNTH",
        ["GAMMA"],
        verification_status="provisional",
        award_rules=[
            {
                "id": "provisional_award",
                "type": "minimum_mark",
                "course_codes": ["GAMMA"],
                "minimum_mark": 70,
                "verification_status": "provisional",
            }
        ],
    )

    distinction = _compute_distinction(
        _synthetic_student(gamma_mark=80),
        catalogue,
        ["opaque_major", "provisional_major"],
        credit_framework=CREDIT,
        course_load_framework=LOAD,
    )

    assert distinction.qualification_eligible
    assert distinction.status == "verified"
    assert "Satisfied by: opaque_major" in distinction.reason


def _science_catalogue() -> Catalogue:
    full = load_catalogue("uct_science")
    scoped, _ = build_programme_scope(
        "uct_science",
        full,
        "bsc_science",
        "current_2023_plus",
    )
    return scoped


def _science_result(catalogue: Catalogue, code: str, mark: int = 80, grade: str = "P"):
    fact = catalogue.courses[code]
    return CourseResult(code, fact.name, fact.nqf_level, fact.nqf_credits, mark, grade, 2024)


CHEMISTRY_MAJOR_CODES = [
    "CEM1000W",
    "MAM1031F",
    "MAM1032S",
    "PHY1031F",
    "PHY1032S",
    "CEM2005W",
    "CEM3005W",
]


def _direct_science_student(
    *,
    include_major: bool = True,
    extra_codes: list[str] | None = None,
    repeated_code: str = "",
    supplementary_code: str = "",
) -> tuple[Catalogue, StudentRecord]:
    catalogue = _science_catalogue()
    codes = list(CHEMISTRY_MAJOR_CODES if include_major else [])
    if extra_codes is None:
        extra_codes = [
            "AGE2011S",
            "AGE2012F",
            "AGE3006H",
            "AGE3011F",
            "AGE3012S",
            "AGE3013H",
            "AST2002H",
            "AST2003H",
        ]
    for code in extra_codes:
        if code not in codes:
            codes.append(code)
    results = []
    if repeated_code:
        results.append(_science_result(catalogue, repeated_code, 45, "F"))
    for code in codes:
        grade = "SP" if code == supplementary_code else "P"
        results.append(_science_result(catalogue, code, 80, grade))
    student = StudentRecord(
        "SCI7M",
        "Science Direct Student",
        "Bachelor of Science",
        ["Chemistry"] if include_major else [],
        results,
        faculty_key="uct_science",
        programme_key="bsc_science",
        pathway_key="current_2023_plus",
        years_registered=3,
    )
    return catalogue, student


def test_science_direct_fb8_2_policy_is_governed_data():
    catalogue = _science_catalogue()
    rule = next(
        rule
        for rule in catalogue.award_rules
        if rule.get("id") == "science_fb8_2_direct_qualification_distinction"
    )

    assert rule["verification_status"] == "unverified"
    assert [child["type"] for child in rule["curriculum_rules"]] == [
        "passed_mark_credits",
        "passed_mark_credits",
        "award_dependency",
    ]
    assert rule["curriculum_rules"][0]["minimum_credits"] == 264
    assert rule["curriculum_rules"][1]["minimum_credits"] == 192


def test_science_direct_path_computes_but_source_status_bounds_authority():
    catalogue, student = _direct_science_student()

    distinction = compute_report(student, catalogue).distinction

    assert not distinction.qualification_eligible
    assert distinction.status == "unverified"
    assert "264 academic credits" in distinction.reason
    assert "Satisfied by: chemistry" in distinction.reason


def test_science_direct_path_insufficient_total_first_class_credits_fails():
    catalogue, student = _direct_science_student(extra_codes=[])

    distinction = compute_report(student, catalogue).distinction

    assert not distinction.qualification_eligible
    assert "228 of 264 academic credits" in distinction.reason


def test_science_direct_path_insufficient_senior_credits_fails():
    low_senior = [
        "AGE1002S",
        "AGE1005L",
        "AST1000S",
        "BIO1000F",
        "BIO1000H",
        "BIO1004S",
        "CEM1010H",
    ]
    catalogue, student = _direct_science_student(extra_codes=low_senior)

    distinction = compute_report(student, catalogue).distinction

    assert not distinction.qualification_eligible
    assert "120 of 192 academic credits" in distinction.reason


def test_science_direct_path_without_verified_major_distinction_fails_dependency():
    catalogue, student = _direct_science_student(include_major=False)

    distinction = compute_report(student, catalogue).distinction

    assert not distinction.qualification_eligible
    assert "No qualifying subject distinction" in distinction.reason


def test_science_direct_path_excludes_repeated_and_supplementary_results():
    catalogue, repeated = _direct_science_student(repeated_code="CEM3005W")
    repeated_report = compute_report(repeated, catalogue).distinction
    catalogue, supplementary = _direct_science_student(supplementary_code="CEM3005W")
    supplementary_report = compute_report(supplementary, catalogue).distinction

    assert "CEM3005W" in repeated_report.reason
    assert "CEM3005W" in supplementary_report.reason
    assert "Excluded by configured attempt/status treatment" in repeated_report.reason
    assert "Excluded by configured attempt/status treatment" in supplementary_report.reason


def test_science_alternative_path_is_now_governed_and_status_bounded():
    catalogue = _science_catalogue()
    codes = [
        *CHEMISTRY_MAJOR_CODES,
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
    deduped = list(dict.fromkeys(codes))
    student = StudentRecord(
        "SCI7MALT",
        "Science Alternative Student",
        "Bachelor of Science",
        ["Chemistry"],
        [_science_result(catalogue, code, 80) for code in deduped],
        faculty_key="uct_science",
        programme_key="bsc_science",
        pathway_key="current_2023_plus",
        years_registered=3,
    )

    distinction = compute_report(student, catalogue).distinction

    assert not distinction.qualification_eligible
    assert distinction.status == "unverified"
    assert "Science FB8.2 alternative 18/24/36 grouped-average path" in distinction.reason


def test_science_direct_thresholds_no_longer_active_python_policy():
    source = inspect.getsource(rule_engine._compute_distinction) + "\n" + inspect.getsource(award_policy)

    assert "first_credits >= 264" not in source
    assert "senior_first_credits >= 192" not in source
    assert "for credit_value, count in ((18, 6), (24, 6), (36, 4))" not in source


def test_passed_mark_credits_contains_no_uct_or_load_policy():
    source = inspect.getsource(curriculum.CurriculumEvaluator.evaluate)

    assert "science_fb8_2" not in source
    assert "_course_weight" not in source
    assert "load_equivalent" not in source[source.find('if rule_type == "passed_mark_credits"') :]
