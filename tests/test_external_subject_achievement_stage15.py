from curriculum_reasoning_engine.institutions.achievement import (
    ExternalQualificationSystem,
    NumericAchievementScheme,
)
from curriculum_reasoning_engine.institutions.grading import ResultState
from engine.models import (
    Catalogue,
    CourseFact,
    ExternalSubjectAchievementCoverage,
    ExternalSubjectAchievementEvidence,
    StudentRecord,
)
from engine.prerequisites import PrerequisiteEvaluator


class Grading:
    institution_id = "northstar"

    def classify(self, result): return ResultState.PASSED
    def is_passed(self, result): return True
    def is_failed(self, result): return False
    def is_pending(self, result): return False


def _evaluate(evidence=(), coverage=(), expression=None):
    system = ExternalQualificationSystem(
        "ORION-CERT", "Orion", NumericAchievementScheme(0, 10, "orion-0-10", "orion-cert"),
        frozenset({"OR-MATH", "OR-SCI"}),
    )
    student = StudentRecord("S", "Student", "route", [])
    catalogue = Catalogue(
        courses={"FOUND-X7": CourseFact("FOUND-X7", "Foundation", 6, 1, [], [], "core")},
        majors={}, programmes={}, forbidden_combinations=[], programme_key="p", catalogue_version="northstar-1",
    )
    return PrerequisiteEvaluator(
        student, catalogue, Grading(), external_qualification_systems=(system,),
        external_subject_achievement_evidence=list(evidence),
        external_subject_achievement_coverage=list(coverage),
    ).evaluate(expression or {
        "type": "external_subject_achievement", "qualification_system_id": "ORION-CERT",
        "subject_id": "OR-MATH", "comparator": "gte", "threshold": 7,
    })


def _evidence(value, subject="OR-MATH", status="verified"):
    return ExternalSubjectAchievementEvidence("E1", "S", "ORION-CERT", subject, value, "Orion registrar", "Synthetic result", status)


def _coverage(*subjects):
    return ExternalSubjectAchievementCoverage("S", "ORION-CERT", subjects, "complete", "Orion registrar", "Synthetic result set")


def test_external_numeric_subject_threshold_uses_opaque_non_percentage_scale():
    assert _evaluate((_evidence(8),)).outcome == "satisfied"
    assert _evaluate((_evidence(5),), (_coverage("OR-MATH"),)).outcome == "not_satisfied"
    assert _evaluate((_evidence(5),)).outcome == "unresolved"


def test_external_absence_requires_complete_subject_coverage():
    assert _evaluate().outcome == "unresolved"
    assert _evaluate(coverage=(_coverage("OR-MATH"),)).outcome == "not_satisfied"


def test_external_gt_and_multi_subject_and():
    assert _evaluate((_evidence(6),), expression={
        "type": "external_subject_achievement", "qualification_system_id": "ORION-CERT",
        "subject_id": "OR-MATH", "comparator": "gt", "threshold": 5,
    }).outcome == "satisfied"
    result = _evaluate((_evidence(8), _evidence(6, "OR-SCI")), expression={
        "type": "all_of", "conditions": [
            {"type": "external_subject_achievement", "qualification_system_id": "ORION-CERT", "subject_id": "OR-MATH", "comparator": "gte", "threshold": 7},
            {"type": "external_subject_achievement", "qualification_system_id": "ORION-CERT", "subject_id": "OR-SCI", "comparator": "gt", "threshold": 5},
        ],
    })
    assert result.outcome == "satisfied"


def test_external_result_does_not_create_local_course_or_attempt():
    result = _evaluate((_evidence(8),))
    assert result.outcome == "satisfied"
    assert result.witness_course_codes == ("OR-MATH",)
