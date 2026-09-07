import pytest
from fixtures.northstar import select_release

from curriculum_reasoning_engine.institutions.achievement import (
    ExternalQualificationSystem,
    SymbolicAchievementScheme,
)
from engine.models import Catalogue, CourseFact, CourseResult, StudentRecord
from engine.prerequisites import PrerequisiteEvaluator


class Grading:
    def is_pending(self, result):
        return result.mark is None and result.achievement_value is None

    def is_passed(self, result):
        return not self.is_pending(result)

    def is_failed(self, result):
        return False


def test_explicit_symbolic_value_is_not_lost_to_numeric_pending_state():
    scheme = SymbolicAchievementScheme(("LOW", "HIGH"), "s", "symbolic-u")
    student = StudentRecord("S", "Student", "route", [], [
        CourseResult("FOUND-X7", "Foundation", 1, 6, None, None, achievement_value="HIGH")
    ])
    result = PrerequisiteEvaluator(
        student, _catalogue(), type("NumericGrading", (), {
            "is_pending": lambda self, item: item.mark is None,
            "is_passed": lambda self, item: False,
            "is_failed": lambda self, item: False,
        })(), achievement_scheme=scheme,
    ).evaluate({"type": "course_achievement", "course_code": "FOUND-X7",
                "comparator": "gte", "threshold": "HIGH",
                "attempt_selection": "any_qualifying_attempt"})
    assert result.outcome == "satisfied"


def _catalogue():
    return Catalogue(
        courses={"FOUND-X7": CourseFact("FOUND-X7", "Foundation", 6, 1, [], [], "Systems")},
        majors={}, programmes={}, forbidden_combinations=[],
    )


def _evaluate(value, expression=None, coverage=None, evidence=()):
    scheme = SymbolicAchievementScheme(("ZETA_LOW", "ALPHA_MID", "BETA_HIGH"), "letters", "symbolic-u")
    student = StudentRecord("S", "Student", "route", [], [
        CourseResult("FOUND-X7", "Foundation", 1, 6, None, None, achievement_value=value)
    ])
    system = ExternalQualificationSystem("VEGA-CERT", "Vega", scheme, frozenset({"VG-MATH"}), "verified")
    return PrerequisiteEvaluator(
        student, _catalogue(), Grading(), external_qualification_systems=(system,),
        achievement_scheme=scheme, course_attempt_coverage_evidence=coverage,
        external_subject_achievement_evidence=list(evidence),
    ).evaluate(expression or {"type": "course_achievement", "course_code": "FOUND-X7",
                              "comparator": "gte", "threshold": "ALPHA_MID",
                              "attempt_selection": "any_qualifying_attempt"})


def test_symbolic_scheme_is_explicit_and_not_lexical():
    scheme = SymbolicAchievementScheme(("ZETA_LOW", "ALPHA_MID", "BETA_HIGH"), "s", "i")
    assert scheme.meets("BETA_HIGH", "gte", "ALPHA_MID")
    assert not scheme.meets("ZETA_LOW", "gte", "ALPHA_MID")
    assert scheme.compare("ZETA_LOW", "ALPHA_MID") == -1


def test_symbolic_scheme_rejects_empty_and_duplicate_values():
    with pytest.raises(ValueError):
        SymbolicAchievementScheme((), "s", "i")
    with pytest.raises(ValueError):
        SymbolicAchievementScheme(("A", "A"), "s", "i")


def test_local_symbolic_achievement_and_exact_values():
    assert _evaluate("BETA_HIGH").outcome == "satisfied"
    assert _evaluate("ALPHA_MID").outcome == "satisfied"
    assert _evaluate("ZETA_LOW", coverage=[type("Coverage", (), {
        "course_codes": ("FOUND-X7",), "coverage_state": "complete", "verification_status": "verified"
    })()]).outcome == "not_satisfied"
    assert _evaluate("alpha_mid").outcome == "unresolved"


def test_unknown_symbol_and_numeric_cross_domain_are_not_converted():
    assert _evaluate("SUPERIOR").outcome == "unresolved"
    assert _evaluate(15).outcome == "unresolved"
    assert _evaluate("BETA_HIGH", expression={"type": "course_achievement", "course_code": "FOUND-X7",
        "comparator": "gte", "threshold": 20, "attempt_selection": "any_qualifying_attempt"}).outcome == "unsupported"


def test_symbolic_external_subject_achievement():
    evidence = (type("Evidence", (), {
        "student_id": "S", "qualification_system_id": "VEGA-CERT", "subject_id": "VG-MATH",
        "achievement_value": "BETA_HIGH", "verification_status": "verified"
    })(),)
    expression = {"type": "external_subject_achievement", "qualification_system_id": "VEGA-CERT",
                  "subject_id": "VG-MATH", "comparator": "gte", "threshold": "ALPHA_MID"}
    assert _evaluate(None, expression=expression, evidence=evidence).outcome == "satisfied"


def test_external_low_symbol_requires_external_coverage_for_negative():
    evidence = (type("Evidence", (), {
        "student_id": "S", "qualification_system_id": "VEGA-CERT", "subject_id": "VG-MATH",
        "achievement_value": "ZETA_LOW", "verification_status": "verified"
    })(),)
    expression = {"type": "external_subject_achievement", "qualification_system_id": "VEGA-CERT",
                  "subject_id": "VG-MATH", "comparator": "gte", "threshold": "ALPHA_MID"}
    result = _evaluate(None, expression=expression, evidence=evidence)
    assert result.outcome == "unresolved"


def test_conflicting_symbolic_external_values_do_not_choose_highest():
    evidence = tuple(type("Evidence", (), {
        "student_id": "S", "qualification_system_id": "VEGA-CERT", "subject_id": "VG-MATH",
        "achievement_value": value, "verification_status": "verified"
    })() for value in ("ZETA_LOW", "BETA_HIGH"))
    expression = {"type": "external_subject_achievement", "qualification_system_id": "VEGA-CERT",
                  "subject_id": "VG-MATH", "comparator": "gte", "threshold": "ALPHA_MID"}
    assert _evaluate(None, expression=expression, evidence=evidence).outcome == "conflict"


def test_numeric_northstar_scheme_is_unchanged():
    release = select_release("northstar", "northstar-fixture-2027")
    assert release.achievement_scheme.meets(16, "gte", 15)
    assert not release.achievement_scheme.meets("BETA_HIGH", "gte", 15)


def test_composition_keeps_symbolic_and_numeric_domains_separate():
    expression = {"type": "one_of", "conditions": [
        {"type": "course_achievement", "course_code": "FOUND-X7", "comparator": "gte",
         "threshold": "BETA_HIGH", "attempt_selection": "any_qualifying_attempt"},
        {"type": "course_completed", "course_code": "FOUND-X7"},
    ]}
    assert _evaluate("BETA_HIGH", expression=expression).outcome == "satisfied"
