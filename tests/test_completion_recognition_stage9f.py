import inspect
from dataclasses import FrozenInstanceError, asdict, fields, replace

import pytest

from app import _to_dict
from engine.completion import (
    CourseCompletionRecognitionEvidence,
    CourseCompletionRecognitionInput,
    CourseCompletionResolver,
    RecognitionEvidenceCoverage,
)
from engine.curriculum import CurriculumEvaluator
from engine.knowledge_graph import KnowledgeGraph
from engine.models import (
    AcademicRecordCoverageEvidence,
    Catalogue,
    CourseFact,
    CourseResult,
    ProgrammeRules,
    StudentRecord,
)
from engine.planner import plan_next_semester
from engine.prerequisites import AcademicConditionEvaluator, PrerequisiteEvaluator, ProjectedCourseCompletions
from engine.reasoner import GraduateGoal
from engine.rule_engine import compute_report


class UniversityTwoGrading:
    institution_id = "university-two"
    scheme_id = "university-two-results"

    def is_passed(self, result):
        return result.grade == "ACHIEVED" or (result.mark is not None and result.mark >= 60)

    def is_pending(self, result):
        return result.mark is None and result.grade != "ACHIEVED"

    def is_failed(self, result):
        return not self.is_passed(result) and not self.is_pending(result)


def setup_case(*results):
    courses = {
        code: CourseFact(
            code,
            code,
            nqf_credits=12,
            nqf_level=5,
            prerequisites=[],
            offered=["Semester 1"],
            department="GEN",
        )
        for code in ("PRE-A", "PRE-B", "ADV")
    }
    courses["ADV"].prerequisite_expression = {
        "type": "course_completed",
        "course_code": "PRE-A",
        "verification_status": "verified",
    }
    policy = {
        "type": "progression_policy",
        "policy_id": "U2-COMPLETION",
        "verification_status": "verified",
        "source_reference": "U2 Regulation",
        "condition": {"type": "required_course_pool_incomplete", "course_codes": ["PRE-A"]},
        "consequence": {"type": "progression_ineligible", "label": "Requirement not met"},
    }
    programme = ProgrammeRules(
        "P",
        "Programme",
        36,
        0,
        0,
        0,
        0,
        0,
        0,
        required_courses=["PRE-A", "ADV"],
        programme_type="structured",
        scope_verified=True,
        progression_rules=[policy],
    )
    catalogue = Catalogue(
        courses,
        {},
        {"P": programme},
        [],
        catalogue_version="R",
        programme_key="P",
        pathway_key="ROUTE",
        scope_status="verified",
    )
    student = StudentRecord(
        "S", "Student", "Programme", [], list(results), programme_key="P", pathway_key="ROUTE"
    )
    evidence = CourseCompletionRecognitionEvidence(
        "DEC-1",
        "S",
        "PRE-A",
        "external-learning:opaque-123",
        "university-two",
        "R",
        "Authorised registry",
        "Decision register entry 1",
        "verified",
        "P",
        "ROUTE",
    )
    return student, catalogue, UniversityTwoGrading(), evidence


def input_for(*decisions, coverage=()):
    return CourseCompletionRecognitionInput(decisions, coverage)


def result(code="PRE-A", mark=70, grade=None):
    return CourseResult(code, code, 5, 12, mark, grade, 2027)


def resolver(*results, decisions=None):
    student, catalogue, scheme, evidence = setup_case(*results)
    return CourseCompletionResolver(student, catalogue, scheme, input_for(*(decisions or [evidence])))


def snapshot(student, catalogue):
    return RecognitionEvidenceCoverage(
        student.student_id,
        "university-two",
        catalogue.catalogue_version,
        tuple(catalogue.courses),
        "Registry",
        "Complete decision snapshot",
        "verified",
    )


def test_evidence_is_immutable_separate_and_has_no_metric_authority():
    _, _, _, evidence = setup_case()
    with pytest.raises(FrozenInstanceError):
        evidence.target_course_code = "PRE-B"
    assert not isinstance(evidence, CourseResult)
    assert not {"mark", "grade", "credits", "nqf_credits", "academic_year", "attempt_id"} & set(
        asdict(evidence)
    )
    assert evidence.source_learning_identity == "external-learning:opaque-123"
    assert resolver().resolve("PRE-A").witness_source == "recognition"


@pytest.mark.parametrize(
    "field,value",
    [
        ("student_id", "OTHER"),
        ("institution_id", "OTHER"),
        ("release_id", "OTHER"),
        ("programme_key", "OTHER"),
        ("pathway_key", "OTHER"),
        ("student_id", ""),
    ],
)
def test_scoped_recognition_never_leaks(field, value):
    student, catalogue, scheme, evidence = setup_case()
    recognition = input_for(replace(evidence, **{field: value}))
    assert (
        CourseCompletionResolver(student, catalogue, scheme, recognition).resolve("PRE-A").outcome
        == "unresolved"
    )


def test_unknown_applicable_target_rejected_but_foreign_decision_ignored():
    student, catalogue, scheme, evidence = setup_case()
    with pytest.raises(ValueError, match="Unknown recognition target"):
        CourseCompletionResolver(
            student, catalogue, scheme, input_for(replace(evidence, target_course_code="UNKNOWN"))
        )
    foreign = replace(evidence, target_course_code="UNKNOWN", student_id="OTHER")
    assert CourseCompletionResolver(student, catalogue, scheme, input_for(foreign)).completed_codes() == set()


@pytest.mark.parametrize("status", ["verified", "provisional", "unverified", "conflict"])
def test_authority_reaches_each_completion_consumer(status):
    student, catalogue, scheme, evidence = setup_case()
    evidence = replace(evidence, verification_status=status)
    recognition = input_for(evidence)
    curriculum = CurriculumEvaluator(student, catalogue, scheme, completion_recognition=recognition)
    course = curriculum.evaluate({"type": "course", "course_codes": ["PRE-A"]})
    prerequisite = PrerequisiteEvaluator(
        student, catalogue, scheme, completion_recognition=recognition
    ).evaluate(
        {
            "type": "course_completed",
            "course_code": "PRE-A",
            "verification_status": "verified",
        }
    )
    report = compute_report(student, catalogue, scheme, completion_recognition=recognition)
    assessment = report.progression_policy_assessments[0]
    assert course.status == prerequisite.status == assessment.effective_status == status
    assert course.complete is (status != "conflict")
    assert prerequisite.outcome == ("conflict" if status == "conflict" else "satisfied")
    assert assessment.condition_outcome == ("conflict" if status == "conflict" else "not_satisfied")
    assert not assessment.consequence_established
    if status != "conflict":
        assert evidence.recognition_id in prerequisite.detail
        assert evidence.source_reference in assessment.detail


def test_duplicate_and_local_plus_recognition_count_once():
    student, catalogue, scheme, evidence = setup_case(result())
    recognition = input_for(evidence, evidence, replace(evidence, recognition_id="DEC-2"))
    evaluator = CurriculumEvaluator(student, catalogue, scheme, completion_recognition=recognition)
    row = evaluator.evaluate({"type": "all_courses", "course_codes": ["PRE-A"]})
    assert row.current == 1
    assert row.used_course_codes == ["PRE-A"]
    assert evaluator.completion.resolve("PRE-A").witness_source == "local_result"


def test_conflict_does_not_get_latest_or_local_override():
    _, _, _, evidence = setup_case()
    conflict = replace(evidence, recognition_id="DEC-conflict", verification_status="conflict")
    assert resolver(result(), decisions=[evidence, conflict]).resolve("PRE-A").outcome == "conflict"
    assert resolver(result(), decisions=[conflict, evidence]).resolve("PRE-A").outcome == "conflict"


def test_completion_has_no_credit_mark_or_attempt_effect():
    student, catalogue, scheme, evidence = setup_case(result(mark=40))
    before = asdict(student)
    recognition = input_for(evidence)
    base = CurriculumEvaluator(student, catalogue, scheme)
    recognised = CurriculumEvaluator(student, catalogue, scheme, completion_recognition=recognition)
    for rule in [
        {"type": "total_credits", "required": 12},
        {"type": "level_credits", "nqf_level": 5, "required": 12},
        {"type": "minimum_mark", "course_codes": ["PRE-A"], "minimum_mark": 65},
    ]:
        assert recognised.evaluate(rule) == base.evaluate(rule)
    assert recognised.pairs == base.pairs == []
    assert recognised.result_by_code == base.result_by_code == {}
    assert student.passed_codes(scheme) == set()
    assert student.credited_results(scheme) == []
    assert asdict(student) == before
    assert recognised.evaluate({"type": "course", "course_codes": ["PRE-A"]}).complete


def test_recognition_does_not_create_global_alias_or_projection():
    student, catalogue, scheme, evidence = setup_case()
    completion = resolver()
    assert completion.resolve("PRE-B").outcome == "unresolved"
    assert completion.resolve(evidence.source_learning_identity).outcome == "unresolved"
    projected = PrerequisiteEvaluator(
        student, catalogue, scheme, projected_course_completions=ProjectedCourseCompletions(("PRE-A",))
    )
    assert projected.evaluate(catalogue.courses["ADV"].prerequisite_expression).status == "provisional"
    assert completion.student.results == []
    assert not hasattr(ProjectedCourseCompletions(), "recognition_id")


def test_transcript_coverage_is_not_recognition_coverage():
    student, catalogue, scheme, _ = setup_case(result(mark=40))
    records = [AcademicRecordCoverageEvidence(("PRE-A",), "complete", verification_status="verified")]
    absent = CourseCompletionResolver(student, catalogue, scheme).resolve("PRE-A", records)
    empty = CourseCompletionResolver(student, catalogue, scheme, input_for()).resolve("PRE-A", records)
    assert absent.outcome == empty.outcome == "unresolved"
    coverage = input_for(coverage=(snapshot(student, catalogue),))
    known = CourseCompletionResolver(student, catalogue, scheme, coverage).resolve("PRE-A", records)
    assert (known.outcome, known.status, known.assessment_complete) == ("not_satisfied", "verified", True)
    report = compute_report(
        student, catalogue, scheme, completion_recognition=coverage, academic_record_coverage_evidence=records
    )
    assessment = report.progression_policy_assessments[0]
    assert assessment.condition_outcome == "satisfied"
    assert assessment.consequence_established


def test_pending_without_witness_stays_unresolved_with_both_coverages():
    student, catalogue, scheme, evidence = setup_case(result(mark=None))
    records = [AcademicRecordCoverageEvidence(("PRE-A",), "complete", verification_status="verified")]
    coverage = snapshot(student, catalogue)
    pending = CourseCompletionResolver(student, catalogue, scheme, input_for(coverage=(coverage,)))
    assert pending.resolve("PRE-A", records).outcome == "unresolved"
    positive = CourseCompletionResolver(student, catalogue, scheme, input_for(evidence))
    assert positive.resolve("PRE-A").outcome == "satisfied"


def test_one_of_uses_positive_witness_without_unused_alternative_coverage():
    student, catalogue, scheme, evidence = setup_case()
    recognition = input_for(
        evidence,
        replace(
            evidence, target_course_code="PRE-B", recognition_id="CONFLICT", verification_status="conflict"
        ),
    )
    expression = {
        "type": "one_of",
        "verification_status": "verified",
        "conditions": [{"type": "course_completed", "course_code": code} for code in ("PRE-A", "PRE-B")],
    }
    evaluated = PrerequisiteEvaluator(
        student, catalogue, scheme, completion_recognition=recognition
    ).evaluate(expression)
    assert evaluated.outcome == "satisfied"
    assert evaluated.status == "verified"
    curriculum = CurriculumEvaluator(student, catalogue, scheme, completion_recognition=recognition)
    assert curriculum.evaluate({"type": "course", "course_codes": ["PRE-A", "PRE-B"]}).status == "verified"
    catalogue.programmes["P"].progression_rules[0]["condition"] = {
        "type": "course_requirement_incomplete",
        "required": 1,
        "course_codes": ["PRE-A", "PRE-B"],
    }
    assessment = compute_report(
        student, catalogue, scheme, completion_recognition=recognition
    ).progression_policy_assessments[0]
    assert assessment.condition_outcome == "not_satisfied"
    assert assessment.effective_status == "verified"


def test_report_planner_reasoner_and_serialization_share_recognition():
    student, catalogue, scheme, evidence = setup_case()
    recognition = input_for(evidence)
    report = compute_report(student, catalogue, scheme, completion_recognition=recognition)
    completed = next(r for r in report.requirements if r.id == "programme_course:PRE-A")
    assert completed.complete
    assert evidence.source_reference in completed.detail
    assert "ADV" in {r.code for r in report.eligible_courses}
    assert "PRE-A" not in {r.code for r in report.eligible_courses}
    planned = plan_next_semester(
        student, catalogue, grading_scheme=scheme, completion_recognition=recognition
    )
    assert "ADV" in {r.code for r in planned}
    assert "PRE-A" not in {r.code for r in planned}
    goal = GraduateGoal(
        student, catalogue, KnowledgeGraph(catalogue), scheme, completion_recognition=recognition
    ).evaluate()
    assert next(r for r in goal.requirements if r.id == completed.id).complete
    assert not any("PRE-A" in step.courses for step in goal.recommended_path)
    data = _to_dict(report)
    assert data["progression_policy_assessments"][0]["condition_outcome"] == "not_satisfied"
    assert data["progression_policy_assessments"][0]["consequence_type"] == "progression_ineligible"
    assert not {"recognition_id", "source_learning_identity"} & {f.name for f in fields(CourseResult)}


def test_shared_owner_has_no_credit_award_or_faculty_policy_logic():
    source = inspect.getsource(CourseCompletionResolver)
    for forbidden in ("nqf_credits", "minimum_mark", "award", "UCT", "MUZ", "HSE1001"):
        assert forbidden not in source
    assert "passed_codes" in source
    assert "CourseCompletionResolver" in inspect.getsource(CurriculumEvaluator.__init__)
    assert ".resolve(" in inspect.getsource(AcademicConditionEvaluator._course_leaf)
    assert "super()._course_leaf" in inspect.getsource(PrerequisiteEvaluator._course_leaf)


def test_local_and_recognised_witnesses_complete_an_all_required_pool():
    student, catalogue, scheme, evidence = setup_case(result("PRE-B"))
    recognition = input_for(evidence)
    row = CurriculumEvaluator(student, catalogue, scheme, completion_recognition=recognition).evaluate(
        {"type": "all_courses", "course_codes": ["PRE-A", "PRE-B"]}
    )
    assert row.complete and row.current == 2
    assert row.status == "verified"
    prerequisite = {
        "type": "all_of",
        "verification_status": "verified",
        "conditions": [{"type": "course_completed", "course_code": code} for code in ("PRE-A", "PRE-B")],
    }
    assert (
        PrerequisiteEvaluator(student, catalogue, scheme, completion_recognition=recognition)
        .evaluate(prerequisite)
        .outcome
        == "satisfied"
    )


@pytest.mark.parametrize(
    "rule",
    [
        {"type": "failed_any", "course_codes": ["PRE-A"]},
        {
            "type": "failed_metric",
            "metric_basis": "course_count",
            "identity": "attempt",
            "temporal_scope": "cumulative",
            "threshold": 1,
        },
        {"type": "pass_rate", "minimum": 0.8},
        {"type": "failed_course_fraction", "threshold": 0.5},
        {"type": "repeat_failure"},
        {"type": "repeat_year_failure"},
    ],
)
def test_attempt_progression_awards_and_credits_do_not_consume_recognition(rule):
    student, catalogue, scheme, evidence = setup_case(result(mark=40), result(mark=35), result("PRE-B"))
    catalogue.programmes["P"].progression_rules = [rule]
    before = compute_report(student, catalogue, scheme)
    after = compute_report(student, catalogue, scheme, completion_recognition=input_for(evidence))
    assert before.exclusion_risk == after.exclusion_risk
    assert before.failed_attempts == after.failed_attempts
    assert before.distinction == after.distinction
    assert before.credits_completed == after.credits_completed
    assert before.level_7_credits == after.level_7_credits
    assert before.semester_course_equivalents == after.semester_course_equivalents


@pytest.mark.parametrize("status", ["provisional", "unverified", "conflict"])
def test_recognition_coverage_authority_and_conflict_are_preserved(status):
    student, catalogue, scheme, _ = setup_case()
    coverage = replace(snapshot(student, catalogue), verification_status=status)
    records = [AcademicRecordCoverageEvidence(("PRE-A",), "complete", verification_status="verified")]
    outcome = CourseCompletionResolver(student, catalogue, scheme, input_for(coverage=(coverage,))).resolve(
        "PRE-A", records
    )
    assert outcome.status == status
    assert not outcome.assessment_complete
    assert outcome.outcome == ("conflict" if status == "conflict" else "not_satisfied")


def test_wrong_release_coverage_and_unused_alternative_are_not_closed():
    student, catalogue, scheme, _ = setup_case()
    records = [AcademicRecordCoverageEvidence(("PRE-A", "PRE-B"), "complete", verification_status="verified")]
    wrong = replace(snapshot(student, catalogue), release_id="OLD")
    assert (
        CourseCompletionResolver(student, catalogue, scheme, input_for(coverage=(wrong,)))
        .resolve("PRE-A", records)
        .outcome
        == "unresolved"
    )
    partial = replace(snapshot(student, catalogue), course_codes=("PRE-A",))
    expression = {
        "type": "one_of",
        "verification_status": "verified",
        "conditions": [{"type": "course_completed", "course_code": code} for code in ("PRE-A", "PRE-B")],
    }
    evaluation = PrerequisiteEvaluator(
        student,
        catalogue,
        scheme,
        academic_record_coverage_evidence=records,
        completion_recognition=input_for(coverage=(partial,)),
    ).evaluate(expression)
    assert evaluation.outcome == "unresolved"


def test_weak_recognition_does_not_become_verified_eligibility_advice():
    student, catalogue, scheme, evidence = setup_case()
    recognition = input_for(replace(evidence, verification_status="unverified"))
    report = compute_report(student, catalogue, scheme, completion_recognition=recognition)
    assert next(r for r in report.eligible_courses if r.code == "ADV").status == "unverified"
    planned = plan_next_semester(
        student, catalogue, grading_scheme=scheme, completion_recognition=recognition
    )
    assert next(r for r in planned if r.code == "ADV").status == "unverified"


def test_legacy_flat_prerequisite_accepts_exact_recognition_but_not_stem_alias():
    student, catalogue, scheme, evidence = setup_case()
    exact = replace(catalogue.courses["ADV"], prerequisite_expression=None, prerequisites=["PRE-A"])
    evaluator = PrerequisiteEvaluator(student, catalogue, scheme, completion_recognition=input_for(evidence))
    assert evaluator.evaluate_for_course(exact).outcome == "satisfied"
    catalogue.courses["ABC1001F"] = replace(catalogue.courses["PRE-A"], code="ABC1001F")
    variant = replace(evidence, target_course_code="ABC1001F")
    evaluator = PrerequisiteEvaluator(student, catalogue, scheme, completion_recognition=input_for(variant))
    stem = replace(exact, prerequisites=["ABC1001"])
    assert evaluator.evaluate_for_course(stem).outcome == "unresolved"


def test_flat_major_report_and_goal_preserve_completion_authority():
    from engine.models import MajorDefinition
    from engine.reasoner import CompleteMajorGoal

    student, catalogue, scheme, evidence = setup_case()
    catalogue.majors["m"] = MajorDefinition("m", "Major", "B", ["PRE-A"], verification_status="verified")
    student.declared_majors = ["m"]
    recognition = input_for(replace(evidence, verification_status="unverified"))
    report = compute_report(student, catalogue, scheme, completion_recognition=recognition)
    assert report.majors[0].complete
    assert report.majors[0].status == "unverified"
    goal = CompleteMajorGoal(
        student, catalogue, KnowledgeGraph(catalogue), "m", scheme, completion_recognition=recognition
    ).evaluate()
    assert goal.complete
    assert goal.metadata["status"] == "unverified"


@pytest.mark.parametrize(
    "changes",
    [
        {"recognition_id": ""},
        {"source_learning_identity": ""},
        {"authority": ""},
        {"source_reference": ""},
        {"verification_status": "approved"},
    ],
)
def test_malformed_applicable_recognition_is_not_treated_as_verified(changes):
    student, catalogue, scheme, evidence = setup_case()
    with pytest.raises(ValueError):
        CourseCompletionResolver(student, catalogue, scheme, input_for(replace(evidence, **changes)))


def test_existing_academic_coverage_normalisation_is_preserved():
    student, catalogue, scheme, _ = setup_case()
    records = [
        AcademicRecordCoverageEvidence(
            (" pre-a ",),
            " COMPLETE ",
            verification_status=" VERIFIED ",
        )
    ]
    completion = CourseCompletionResolver(
        student,
        catalogue,
        scheme,
        input_for(coverage=(snapshot(student, catalogue),)),
    ).resolve("PRE-A", records)
    assert (completion.outcome, completion.status) == ("not_satisfied", "verified")


def test_pending_does_not_hide_explicit_coverage_conflict():
    student, catalogue, scheme, _ = setup_case(result(mark=None))
    records = [
        AcademicRecordCoverageEvidence(
            ("PRE-A",),
            "complete",
            verification_status="conflict",
        )
    ]
    assert (
        CourseCompletionResolver(student, catalogue, scheme).resolve("PRE-A", records).outcome == "conflict"
    )
