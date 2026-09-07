from curriculum_reasoning_engine.institutions.grading import ResultState
from engine.completion import CourseCompletionRecognitionInput, RecognitionEvidenceCoverage
from engine.curriculum import CurriculumEvaluator
from engine.models import (
    AcademicRecordCoverageEvidence,
    Catalogue,
    CourseFact,
    CourseResult,
    ProgrammeRules,
    RequirementRecognitionCoverage,
    RequirementRecognitionEvidence,
    StudentRecord,
)


class Grading:
    institution_id = "northstar"

    def classify(self, result):
        if result.mark is None:
            return ResultState.PENDING
        return ResultState.PASSED if result.mark >= 60 else ResultState.FAILED

    def is_passed(self, result): return self.classify(result) == ResultState.PASSED
    def is_failed(self, result): return self.classify(result) == ResultState.FAILED
    def is_pending(self, result): return self.classify(result) == ResultState.PENDING


def _catalogue():
    programme = ProgrammeRules(
        key="p", name="Programme", total_nqf_credits=30, level_7_nqf_credits=0,
        semester_course_equivalents=0, senior_course_equivalents=0,
        humanities_course_equivalents=0, required_majors=0,
        required_humanities_majors=0,
        curriculum_rules=[{
            "id": "foundation_block", "type": "all_courses",
            "course_codes": ["CORE-Q2", "PATH-Z9"],
            "recognition_allowed": True,
            "verification_status": "verified",
        }],
    )
    return Catalogue(
        courses={
            code: CourseFact(code, code, 6, 1, [], [], "core")
            for code in ("CORE-Q2", "PATH-Z9")
        },
        majors={}, programmes={"p": programme}, forbidden_combinations=[],
        programme_key="p", catalogue_version="northstar-1",
    )


def _student(results=()):
    return StudentRecord("S", "Student", "route", [], list(results), programme_key="p")


def _recognition(status="verified", target="foundation_block", student="S"):
    return RequirementRecognitionEvidence(
        "RR-1", student, "northstar", "northstar-1", "p", target,
        "EXT-PACKAGE", "registrar", "Synthetic decision register", status,
    )


def test_requirement_recognition_satisfies_target_without_child_course_truth():
    evaluator = CurriculumEvaluator(
        _student(), _catalogue(), Grading(),
        requirement_recognition_evidence=[_recognition()],
        institution_id="northstar",
    )
    result = evaluator.evaluate_many(_catalogue().programmes["p"].curriculum_rules)[0]
    assert result.outcome == "satisfied"
    assert result.recognition_witness == "RR-1"
    assert evaluator.completion.resolve("CORE-Q2").outcome != "satisfied"


def test_missing_requirement_recognition_is_unresolved_without_coverage():
    evaluator = CurriculumEvaluator(_student(), _catalogue(), Grading(), institution_id="northstar")
    assert evaluator.evaluate_many(_catalogue().programmes["p"].curriculum_rules)[0].outcome == "unresolved"


def test_complete_recognition_coverage_allows_definitive_negative():
    evaluator = CurriculumEvaluator(
        _student(), _catalogue(), Grading(), institution_id="northstar",
        requirement_recognition_coverage=[RequirementRecognitionCoverage(
            "S", "northstar", "northstar-1", "p", ("foundation_block",), "complete",
        )],
        academic_record_coverage_evidence=[AcademicRecordCoverageEvidence(
            ("CORE-Q2", "PATH-Z9"), "complete",
        )],
        completion_recognition=CourseCompletionRecognitionInput(coverage=(RecognitionEvidenceCoverage(
            "S", "northstar", "northstar-1", ("CORE-Q2", "PATH-Z9"),
            "Registry", "Synthetic registry", "verified", "p",
        ),)),
    )
    assert evaluator.evaluate_many([{
        "id": "foundation_block", "type": "course", "course_codes": ["CORE-Q2"],
        "recognition_allowed": True, "verification_status": "verified",
    }])[0].outcome == "not_satisfied"


def test_direct_satisfaction_witness_is_not_weakened_by_unknown_recognition():
    results = [
        CourseResult("CORE-Q2", "CORE-Q2", 1, 6, 70, None),
        CourseResult("PATH-Z9", "PATH-Z9", 1, 6, 70, None),
    ]
    evaluator = CurriculumEvaluator(_student(results), _catalogue(), Grading(), institution_id="northstar")
    assert evaluator.evaluate_many(_catalogue().programmes["p"].curriculum_rules)[0].outcome == "satisfied"
