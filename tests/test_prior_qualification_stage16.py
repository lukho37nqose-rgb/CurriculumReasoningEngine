from curriculum_reasoning_engine.institutions.achievement import (
    ExternalQualificationSystem,
    NumericAchievementScheme,
)
from curriculum_reasoning_engine.institutions.grading import ResultState
from engine.models import (
    Catalogue,
    CourseFact,
    PriorQualificationCoverage,
    PriorQualificationEvidence,
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
        "ORION-AWARDS", "Orion Awards", NumericAchievementScheme(0, 10, "orion-0-10", "orion"),
        qualification_ids=frozenset({"ORA-K7", "ORA-T2"}),
    )
    return PrerequisiteEvaluator(
        StudentRecord("S", "Student", "route", []),
        Catalogue(courses={"LOCAL-A": CourseFact("LOCAL-A", "Local", 6, 1, [], [], "core")}, majors={}, programmes={}, forbidden_combinations=[], programme_key="p", catalogue_version="northstar-1"),
        Grading(), external_qualification_systems=(system,),
        prior_qualification_evidence=list(evidence), prior_qualification_coverage=list(coverage),
    ).evaluate(expression or {"type": "qualification_held", "qualification_system_id": "ORION-AWARDS", "qualification_id": "ORA-K7"})


def _evidence(qualification="ORA-K7", status="verified", student="S"):
    return PriorQualificationEvidence("Q1", student, "ORION-AWARDS", qualification, "Orion registrar", "Synthetic award register", status)


def _coverage(*qualifications):
    return PriorQualificationCoverage("S", "ORION-AWARDS", qualifications, "complete", "Orion registrar", "Synthetic qualification snapshot")


def test_prior_qualification_positive_and_opaque_identity():
    assert _evaluate((_evidence(),)).outcome == "satisfied"
    assert _evaluate((_evidence("ORA-T2"),), expression={"type": "one_of", "conditions": [
        {"type": "qualification_held", "qualification_system_id": "ORION-AWARDS", "qualification_id": "ORA-K7"},
        {"type": "qualification_held", "qualification_system_id": "ORION-AWARDS", "qualification_id": "ORA-T2"},
    ]}).outcome == "satisfied"


def test_missing_prior_qualification_requires_complete_coverage_for_negative():
    assert _evaluate().outcome == "unresolved"
    assert _evaluate(coverage=(_coverage("ORA-K7"),)).outcome == "not_satisfied"


def test_wrong_student_and_unknown_qualification_do_not_satisfy():
    assert _evaluate((_evidence(student="OTHER"),)).outcome == "unresolved"
    assert _evaluate(expression={"type": "qualification_held", "qualification_system_id": "ORION-AWARDS", "qualification_id": "UNKNOWN"}).outcome == "unsupported"


def test_prior_qualification_does_not_create_local_academic_facts():
    result = _evaluate((_evidence(),))
    assert result.outcome == "satisfied"
    assert result.witness_course_codes == ()
