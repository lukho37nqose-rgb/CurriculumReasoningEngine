from __future__ import annotations

import inspect
import json

import pytest
from recognition_fixtures import empty_recognition_snapshot

from engine.catalogue import load_catalogue
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
from engine.prerequisites import (
    PrerequisiteEvaluator,
    ProjectedCourseCompletions,
    legacy_prereqs_met,
)
from engine.reasoner import GraduateGoal
from engine.rule_engine import _compute_eligible_courses
from engine.scope import build_programme_scope


def _course(
    code: str,
    expression: dict | None = None,
    prerequisites: list[str] | None = None,
) -> CourseFact:
    return CourseFact(
        code=code,
        name=code,
        nqf_credits=12,
        nqf_level=5,
        prerequisites=list(prerequisites or []),
        offered=["Semester 1"],
        department="GEN",
        prerequisite_expression=expression,
    )


def _programme(required: list[str]) -> ProgrammeRules:
    return ProgrammeRules(
        key="u2-programme",
        name="University Two Programme",
        total_nqf_credits=36,
        level_7_nqf_credits=0,
        semester_course_equivalents=0,
        senior_course_equivalents=0,
        humanities_course_equivalents=0,
        required_majors=0,
        required_humanities_majors=0,
        required_courses=required,
        programme_type="structured",
        scope_verified=True,
    )


def _catalogue(*courses: CourseFact, required: list[str] | None = None) -> Catalogue:
    programme = _programme(required or [course.code for course in courses])
    return Catalogue(
        courses={course.code: course for course in courses},
        majors={},
        programmes={programme.key: programme},
        forbidden_combinations=[],
        faculty_key="university_two",
        catalogue_version="test-release",
        programme_key=programme.key,
        scope_status="verified",
        elective_course_codes=set(),
    )


def _student(*results: CourseResult) -> StudentRecord:
    return StudentRecord(
        student_id="U2-1",
        name="Student",
        programme="University Two Programme",
        declared_majors=[],
        results=list(results),
        faculty_key="university_two",
        programme_key="u2-programme",
    )


def _result(code: str, mark: int | None) -> CourseResult:
    return CourseResult(code, code, 5, 12, mark, None, 2027)


def _coverage(*codes: str, status: str = "verified") -> AcademicRecordCoverageEvidence:
    return AcademicRecordCoverageEvidence(tuple(codes), "complete", verification_status=status)


def _leaf(code: str) -> dict:
    return {"type": "course_completed", "course_code": code}


def _expression(node_type: str, *conditions: dict, status: str = "verified") -> dict:
    return {
        "type": node_type,
        "conditions": list(conditions),
        "verification_status": status,
    }


def _evaluate(
    expression: dict,
    results: list[CourseResult] | None = None,
    coverage: list[AcademicRecordCoverageEvidence] | None = None,
    projected: ProjectedCourseCompletions | None = None,
):
    codes = {"TGT", "PRE-A", "PRE-B", "PRE-C", "PRE-D", "PRE1001", "PRE1001F"}
    catalogue = _catalogue(*[_course(code) for code in sorted(codes)])
    return PrerequisiteEvaluator(
        _student(*(results or [])),
        catalogue,
        academic_record_coverage_evidence=coverage,
        completion_recognition=empty_recognition_snapshot(_student(*(results or [])), catalogue),
        projected_course_completions=projected,
    ).evaluate(expression)


def test_course_leaf_positive_history_and_pending_semantics():
    expression = {**_leaf("PRE-A"), "verification_status": "verified"}
    assert _evaluate(expression, [_result("PRE-A", 60)]).outcome == "satisfied"
    assert _evaluate(expression, [_result("PRE-A", 30), _result("PRE-A", 60)]).outcome == "satisfied"
    assert _evaluate(expression, [_result("PRE-A", 60), _result("PRE-A", 30)]).outcome == "satisfied"
    pending = _evaluate(expression, [_result("PRE-A", None)], [_coverage("PRE-A")])
    assert (pending.outcome, pending.assessment_complete) == ("unresolved", False)


@pytest.mark.parametrize("results", [[], [_result("PRE-A", 30)]])
def test_course_leaf_needs_coverage_for_negative_inference(results):
    expression = {**_leaf("PRE-A"), "verification_status": "verified"}
    unresolved = _evaluate(expression, results)
    negative = _evaluate(expression, results, [_coverage("PRE-A")])
    assert unresolved.outcome == "unresolved"
    assert (negative.outcome, negative.assessment_complete, negative.status) == (
        "not_satisfied",
        True,
        "verified",
    )


def test_unverified_coverage_bounds_negative_authority():
    result = _evaluate(
        {**_leaf("PRE-A"), "verification_status": "verified"},
        coverage=[_coverage("PRE-A", status="unverified")],
    )
    assert (result.outcome, result.assessment_complete, result.status) == (
        "not_satisfied",
        False,
        "unverified",
    )


def test_all_of_preserves_truth_completeness_and_decisive_authority():
    expression = _expression("all_of", _leaf("PRE-A"), _leaf("PRE-B"))
    complete = _evaluate(expression, [_result("PRE-A", 60), _result("PRE-B", 60)])
    unresolved = _evaluate(expression, [_result("PRE-A", 60)])
    decisive_false = _evaluate(expression, coverage=[_coverage("PRE-A")])
    assert (complete.outcome, complete.assessment_complete) == ("satisfied", True)
    assert (unresolved.outcome, unresolved.assessment_complete) == (
        "unresolved",
        False,
    )
    assert (decisive_false.outcome, decisive_false.assessment_complete) == (
        "not_satisfied",
        False,
    )
    assert decisive_false.status == "verified"


def test_one_of_uses_successful_witness_authority_without_hiding_incompleteness():
    expression = _expression("one_of", _leaf("PRE-A"), _leaf("PRE-B"))
    result = _evaluate(expression, [_result("PRE-A", 60)])
    assert (result.outcome, result.assessment_complete, result.status) == (
        "satisfied",
        False,
        "verified",
    )
    assert result.witness_course_codes == ("PRE-A",)


def test_one_of_negative_requires_coverage_for_every_alternative():
    expression = _expression("one_of", _leaf("PRE-A"), _leaf("PRE-B"))
    partial = _evaluate(expression, [_result("PRE-A", 30)], [_coverage("PRE-A")])
    complete = _evaluate(
        expression,
        [_result("PRE-A", 30)],
        [_coverage("PRE-A", "PRE-B")],
    )
    assert partial.outcome == "unresolved"
    assert (complete.outcome, complete.assessment_complete) == (
        "not_satisfied",
        True,
    )


def test_nested_and_of_or_and_paired_alternatives():
    and_of_or = _expression(
        "all_of",
        {"type": "one_of", "conditions": [_leaf("PRE-A"), _leaf("PRE-B")]},
        _leaf("PRE-C"),
    )
    paired = _expression(
        "one_of",
        {"type": "all_of", "conditions": [_leaf("PRE-A"), _leaf("PRE-B")]},
        {"type": "all_of", "conditions": [_leaf("PRE-C"), _leaf("PRE-D")]},
    )
    first = _evaluate(and_of_or, [_result("PRE-A", 60), _result("PRE-C", 60)])
    second = _evaluate(paired, [_result("PRE-A", 60), _result("PRE-B", 60)])
    assert (first.outcome, first.assessment_complete) == ("satisfied", False)
    assert (second.outcome, second.status) == ("satisfied", "verified")
    assert second.witness_course_codes == ("PRE-A", "PRE-B")


def test_malformed_empty_deep_conflict_and_unsupported_results():
    empty = _evaluate({"type": "all_of", "conditions": [], "verification_status": "verified"})
    unknown = _evaluate({"type": "minimum_mark", "minimum": 60})
    deep = _evaluate(
        _expression(
            "all_of",
            {
                "type": "one_of",
                "conditions": [
                    {
                        "type": "all_of",
                        "conditions": [_leaf("PRE-A"), _leaf("PRE-B")],
                    }
                ],
            },
        )
    )
    conflict = _evaluate(
        _expression("all_of", _leaf("PRE-A"), _leaf("PRE-B")),
        coverage=[AcademicRecordCoverageEvidence(("PRE-A",), "conflict", verification_status="conflict")],
    )
    assert empty.outcome == unknown.outcome == deep.outcome == "unsupported"
    assert conflict.outcome == "conflict"


def test_canonical_exact_code_does_not_use_legacy_stem_matching():
    canonical = _evaluate(
        {**_leaf("PRE1001"), "verification_status": "verified"},
        [_result("PRE1001F", 60)],
        [_coverage("PRE1001")],
    )
    legacy = _course("TGT", prerequisites=["PRE1001"])
    assert canonical.outcome == "not_satisfied"
    assert legacy_prereqs_met(legacy, {"PRE1001F"})


def test_canonical_expression_takes_precedence_over_legacy_list():
    course = _course(
        "TGT",
        {**_leaf("PRE-B"), "verification_status": "verified"},
        ["PRE-A"],
    )
    catalogue = _catalogue(_course("PRE-A"), _course("PRE-B"), course)
    result = PrerequisiteEvaluator(_student(_result("PRE-A", 60)), catalogue).evaluate_for_course(course)
    assert result.outcome == "unresolved"


def test_projected_completion_is_provisional_and_does_not_mutate_record():
    expression = {**_leaf("PRE-A"), "verification_status": "verified"}
    student = _student()
    catalogue = _catalogue(_course("PRE-A"), _course("TGT"))
    actual = PrerequisiteEvaluator(student, catalogue).evaluate(expression)
    projected = PrerequisiteEvaluator(
        student,
        catalogue,
        projected_course_completions=ProjectedCourseCompletions(("PRE-A",)),
    ).evaluate(expression)
    assert actual.outcome == "unresolved"
    assert (projected.outcome, projected.status) == ("satisfied", "provisional")
    assert student.results == []
    assert not isinstance(ProjectedCourseCompletions(("PRE-A",)), CourseResult)


def test_eligibility_and_planner_use_structured_evaluator():
    target = _course("TGT", {**_leaf("PRE-A"), "verification_status": "verified"})
    catalogue = _catalogue(_course("PRE-A"), target, required=["TGT"])
    student = _student()
    assert _compute_eligible_courses(student, catalogue) == []
    assert plan_next_semester(student, catalogue) == []
    projected = plan_next_semester(
        student,
        catalogue,
        projected_course_completions=ProjectedCourseCompletions(("PRE-A",)),
    )
    assert [item.code for item in projected] == ["TGT"]


def test_reasoner_chains_projected_completions_through_same_evaluator():
    a = _course("PRE-A")
    b = _course("PRE-B", {**_leaf("PRE-A"), "verification_status": "verified"})
    c = _course("PRE-C", {**_leaf("PRE-B"), "verification_status": "verified"})
    catalogue = _catalogue(a, b, c, required=["PRE-A", "PRE-B", "PRE-C"])
    goal = GraduateGoal(_student(), catalogue, KnowledgeGraph(catalogue))
    path = goal._compute_graduation_path([], catalogue.programmes["u2-programme"])
    assert [step.courses for step in path] == [["PRE-A"], ["PRE-B"], ["PRE-C"]]


def test_knowledge_graph_does_not_flatten_canonical_or():
    target = _course(
        "TGT",
        _expression("one_of", _leaf("PRE-A"), _leaf("PRE-B")),
    )
    graph = KnowledgeGraph(_catalogue(_course("PRE-A"), _course("PRE-B"), target))
    assert graph.get_prerequisites("TGT") == set()


def test_flattened_ebe_rows_are_not_auto_canonicalised():
    catalogue = load_catalogue("uct_ebe")
    for code in ("APG2040F", "EEE2046F", "ECO1008F", "CSC2001F"):
        assert catalogue.courses[code].prerequisite_expression is None


def test_catalogue_loads_canonical_expression_additively(tmp_path):
    expression = _expression("one_of", _leaf("PRE-A"), _leaf("PRE-B"))
    courses_path = tmp_path / "courses.json"
    requirements_path = tmp_path / "requirements.json"
    courses_path.write_text(
        json.dumps(
            [
                {
                    "code": "TGT",
                    "name": "Target",
                    "credits": 12,
                    "nqf_level": 5,
                    "prerequisites": ["LEGACY"],
                    "prerequisites_verified": True,
                    "prerequisite_expression": expression,
                    "offered": ["Semester 1"],
                    "department": "GEN",
                }
            ]
        ),
        encoding="utf-8",
    )
    requirements_path.write_text(
        json.dumps(
            {
                "programmes": {
                    "u2-programme": {
                        "name": "University Two Programme",
                        "programme_type": "structured",
                        "required_courses": ["TGT"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    catalogue = load_catalogue("university_two", courses_path, requirements_path)
    assert catalogue.courses["TGT"].prerequisite_expression == expression


def test_programme_expression_override_replaces_without_merging():
    catalogue_expression = {**_leaf("PRE-A"), "verification_status": "verified"}
    override = {**_leaf("PRE-B"), "verification_status": "unverified"}
    target = _course("TGT", catalogue_expression, ["LEGACY"])
    catalogue = _catalogue(_course("PRE-A"), _course("PRE-B"), target, required=["TGT"])
    catalogue.programmes["u2-programme"].prerequisite_expression_overrides = {"TGT": override}
    scoped, _ = build_programme_scope("university_two", catalogue, "u2-programme")
    assert scoped.courses["TGT"].prerequisite_expression == override
    assert scoped.courses["TGT"].prerequisites == ["LEGACY"]


def test_consumers_do_not_implement_structured_boolean_logic():
    import engine.planner as planner
    import engine.reasoner as reasoner
    import engine.rule_engine as rule_engine

    for module in (planner, reasoner, rule_engine):
        source = inspect.getsource(module)
        assert 'node_type == "all_of"' not in source
        assert 'node_type == "one_of"' not in source
