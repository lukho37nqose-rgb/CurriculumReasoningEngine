"""Bounded second-institution onboarding gate, using production evaluators."""

import json
from dataclasses import asdict, replace
from pathlib import Path

import pytest
from fixtures.northstar import (
    ROOT,
    analyse,
    catalogue_for,
    frameworks,
    read_json,
    select_release,
)

from engine.completion import CourseCompletionResolver
from engine.curriculum import CurriculumEvaluator
from engine.knowledge_graph import KnowledgeGraph
from engine.planner import plan_next_semester
from engine.prerequisites import PrerequisiteEvaluator, ProjectedCourseCompletions
from engine.reasoner import GraduateGoal
from engine.rule_engine import compute_report


def run(name):
    return analyse(read_json("scenarios.json")[name])


def prerequisites(release, catalogue, inputs, projected=None):
    return PrerequisiteEvaluator(
        inputs.student,
        catalogue,
        **frameworks(release),
        academic_record_coverage_evidence=inputs.result_coverage,
        completion_recognition=inputs.recognition,
        projected_course_completions=projected,
    )


def curriculum(release, catalogue, inputs):
    return CurriculumEvaluator(
        inputs.student,
        catalogue,
        **frameworks(release),
        completion_recognition=inputs.recognition,
    )


def test_explicit_release_and_catalogue_selection():
    release = select_release("northstar", "northstar-fixture-2027")
    assert release.institution_id == "northstar"
    assert release.release_id == "northstar-fixture-2027"
    assert release.resolve_route("Systems / Inquiry diploma").programme_key == "systems_inquiry"
    descriptor = release.resolve_catalogue("systems")
    assert descriptor.courses_path == ROOT / "courses.json"
    catalogue = catalogue_for(release)
    assert not catalogue.data_issues
    assert catalogue.catalogue_version == release.release_id
    for identity in [("uct", release.release_id), ("northstar", "wrong-release")]:
        with pytest.raises(KeyError):
            select_release(*identity)
    with pytest.raises(ValueError):
        release.resolve_route("Unknown route")


def test_grading_boundary_58_fails_62_passes():
    release, _, inputs, report, _ = run("grading")
    first, second = inputs.student.results
    assert release.grading_scheme.is_failed(first)
    assert release.grading_scheme.is_passed(second)
    assert inputs.student.passed_codes(release.grading_scheme) == {"CORE-Q2"}
    assert report.credits_completed == 9
    ratio = report.progression_policy_assessments[0]
    assert ratio.condition_outcome == "satisfied"  # 9 / 15 = 0.60, below 0.65


@pytest.mark.parametrize("code", read_json("release.json")["load_equivalents"])
def test_codes_do_not_imply_department_level_or_period(code):
    release, catalogue, _, _, _ = run("clean")
    assert release.course_code_scheme.infer_academic_level(code) == 0
    assert release.course_code_scheme.infer_department(code) == ""
    assert release.course_code_scheme.infer_year_level(code) == 0
    assert catalogue.courses[code].nqf_level in {1, 2, 3}
    assert catalogue.courses[code].offered == ["Cycle-A"]


def test_credits_and_load_are_independent():
    release, catalogue, _, report, _ = run("clean")
    assert report.credits_completed == 30
    assert report.semester_course_equivalents == 2.5  # 1.75 + .25 + .5
    a, b = (catalogue.courses[code] for code in ("FOUND-X7", "ALT-V8"))
    assert release.credit_framework.credit_value(a) == release.credit_framework.credit_value(b) == 6
    assert release.course_load_framework.load_equivalent(a) != release.course_load_framework.load_equivalent(
        b
    )


def test_academic_unit_is_not_uct_faculty_structure():
    release, _, _, _, data = run("clean")
    assert release.academic_unit("systems").name == "School of Systems"
    assert release.academic_unit_keys == {"systems"}
    assert data["faculty_key"] == "systems"  # Compatibility key, not faculty semantics.


@pytest.mark.parametrize(
    "rule_id,complete,current",
    [
        ("foundation", True, 1),
        ("core", True, 2),
        ("studio", True, 1),
        ("studio_credit", True, 15),
    ],
)
def test_curriculum_shapes(rule_id, complete, current):
    release, catalogue, inputs, _, _ = run("clean")
    rows = curriculum(release, catalogue, inputs).evaluate_many(
        catalogue.programmes["systems_inquiry"].curriculum_rules
    )
    row = next(row for row in rows if row.id == rule_id)
    assert row.complete is complete
    assert row.current == current


@pytest.mark.parametrize(
    "code,shape",
    [
        ("PATH-Z9", "course_completed"),
        ("ALT-V8", "all_of"),
        ("CAP-R4", "one_of"),
        ("LAB-T6", "all_of"),
    ],
)
def test_prerequisite_shapes(code, shape):
    release, catalogue, inputs, _, _ = run("clean")
    course = catalogue.courses[code]
    assert course.prerequisites == []
    assert course.prerequisite_expression["type"] == shape
    outcome = prerequisites(release, catalogue, inputs).evaluate_for_course(course)
    assert outcome.outcome == "satisfied"
    assert outcome.status == "verified"


def test_student_clean_progress_and_award_below_threshold():
    _, _, _, report, _ = run("clean")
    assert all(not p.consequence_established for p in report.progression_policy_assessments)
    assert "71.80" in report.distinction.reason  # (6*72+9*68+15*74)/30
    assert not report.distinction.qualification_eligible
    assert report.distinction.status == "unverified"


def test_partial_result_record_remains_unresolved():
    release, catalogue, inputs, report, _ = run("partial")
    outcome = prerequisites(release, catalogue, inputs).evaluate_for_course(catalogue.courses["ALT-V8"])
    assert outcome.outcome == "unresolved"
    assert not outcome.assessment_complete
    assert report.progression_policy_assessments[1].condition_outcome == "unresolved"
    assert not inputs.result_coverage and not inputs.recognition.coverage


def test_both_coverage_domains_establish_negative():
    release, catalogue, inputs, report, _ = run("negative")
    outcome = prerequisites(release, catalogue, inputs).evaluate_for_course(catalogue.courses["ALT-V8"])
    assert outcome.outcome == "not_satisfied"
    assert outcome.assessment_complete
    assert report.progression_policy_assessments[1].condition_outcome == "satisfied"
    assert report.progression_policy_assessments[1].consequence_established
    assert report.progression_policy_assessments[1].effective_status == "unverified"


@pytest.mark.parametrize("absent_domain", ["complete_results", "complete_recognition"])
def test_one_coverage_domain_is_not_enough(absent_domain):
    raw = read_json("scenarios.json")["negative"]
    raw.pop(absent_domain)
    _, _, _, report, _ = analyse(raw)
    assert report.progression_policy_assessments[1].condition_outcome == "unresolved"


def test_recognition_ingestion_and_completion_without_local_attempt():
    release, catalogue, inputs, report, _ = run("recognition")
    decision = inputs.recognition.decisions[0]
    assert decision.source_learning_identity == "EXT-77"
    assert decision.target_course_code == "CORE-Q2"
    assert decision.student_id == inputs.student.student_id
    assert decision.institution_id == release.institution_id
    assert decision.release_id == release.release_id
    assert all(row.code != "CORE-Q2" for row in inputs.student.results)
    assert (
        prerequisites(release, catalogue, inputs).evaluate_for_course(catalogue.courses["ALT-V8"]).outcome
        == "satisfied"
    )
    assert report.progression_policy_assessments[1].condition_outcome == "not_satisfied"
    assert report.credits_completed == 21
    assert not hasattr(decision, "mark")


def test_recognition_cannot_change_attempt_metrics_credits_or_awards():
    raw = read_json("scenarios.json")["recognition"]
    _, _, inputs, recognised, _ = analyse(raw)
    raw.pop("recognitions")
    _, _, without_inputs, without, _ = analyse(raw)
    assert inputs.student == without_inputs.student
    assert recognised.credits_completed == without.credits_completed == 21
    assert recognised.semester_course_equivalents == without.semester_course_equivalents
    assert recognised.progression_policy_assessments[0] == without.progression_policy_assessments[0]
    assert recognised.failed_attempts == without.failed_attempts
    assert recognised.distinction == without.distinction
    assert without.progression_policy_assessments[1].condition_outcome == "unresolved"


def test_weak_recognition_bounds_effective_authority():
    raw = read_json("scenarios.json")["recognition"]
    raw["recognitions"][0]["status"] = "unverified"
    release, catalogue, inputs, report, _ = analyse(raw)
    outcome = prerequisites(release, catalogue, inputs).evaluate_for_course(catalogue.courses["ALT-V8"])
    assert outcome.outcome == "satisfied"
    assert outcome.status == "unverified"
    assert report.progression_policy_assessments[1].effective_status == "unverified"


def test_pending_possible_witness_remains_unresolved():
    raw = read_json("scenarios.json")["negative"]
    raw["modules"].append({"module": "CORE-Q2", "score": None, "period": "Cycle-A"})
    _, _, _, report, _ = analyse(raw)
    assert report.progression_policy_assessments[1].condition_outcome == "unresolved"


def test_planning_projection_chain_is_not_current_evidence():
    release, catalogue, inputs, report, _ = run("planning")
    before = asdict(inputs.student)
    current = prerequisites(release, catalogue, inputs)
    assert current.evaluate_for_course(catalogue.courses["PATH-Z9"]).outcome == "satisfied"
    assert current.evaluate_for_course(catalogue.courses["CAP-R4"]).outcome == "unresolved"
    future = prerequisites(release, catalogue, inputs, ProjectedCourseCompletions(("PATH-Z9",)))
    for code in ("CAP-R4", "LAB-T6"):
        assessment = future.evaluate_for_course(catalogue.courses[code])
        assert assessment.outcome == "satisfied"
        assert assessment.status == "provisional"
    assert asdict(inputs.student) == before
    assert "CAP-R4" not in {course.code for course in report.eligible_courses}
    recommendations = plan_next_semester(
        inputs.student,
        catalogue,
        semester="Cycle-A",
        **frameworks(release),
        completion_recognition=inputs.recognition,
        projected_course_completions=ProjectedCourseCompletions(("PATH-Z9",)),
    )
    assert "CAP-R4" in {course.code for course in recommendations}


def test_reasoner_consumes_selected_frameworks():
    release, catalogue, inputs, report, _ = run("recognition")
    goal = GraduateGoal(
        inputs.student,
        catalogue,
        KnowledgeGraph(catalogue),
        **frameworks(release),
        completion_recognition=inputs.recognition,
    ).evaluate()
    requirement_id = "programme_course:CORE-Q2"
    assert next(r for r in goal.requirements if r.id == requirement_id).complete
    assert next(r for r in report.requirements if r.id == requirement_id).complete


def test_award_threshold_is_governed_and_computed_without_authority_upgrade():
    release, catalogue, inputs, report, _ = run("award")
    rows = curriculum(release, catalogue, inputs).evaluate_many(catalogue.award_rules[0]["curriculum_rules"])
    average = next(row for row in rows if row.id == "award_average")
    assert average.current == pytest.approx(86.2)
    assert average.required == 82
    assert all(row.complete for row in rows)
    assert all(row.status == "verified" for row in rows)
    assert all("unsupported" not in row.detail.lower() for row in rows)
    assert report.distinction.status == "unverified"
    assert not report.distinction.qualification_eligible
    catalogue.award_rules[0]["curriculum_rules"][0]["minimum_average"] = 91
    stricter = compute_report(inputs.student, catalogue, **frameworks(release))
    assert "91" in stricter.distinction.reason


def test_adapter_text_contract_and_unsupported_input():
    release = select_release("northstar", "northstar-fixture-2027")
    raw = read_json("scenarios.json")["clean"]
    assert (
        release.transcript_adapter.parse_text(json.dumps(raw))
        == release.transcript_adapter.ingest(raw).student
    )
    raw["modules"][0]["period"] = "UNKNOWN"
    with pytest.raises(KeyError):
        release.transcript_adapter.ingest(raw)
    with pytest.raises(NotImplementedError):
        release.transcript_adapter.parse_pdf(None)


@pytest.mark.parametrize("scenario", read_json("scenarios.json"))
def test_public_serialization_preserves_identity_and_sources(scenario):
    _, _, _, report, data = run(scenario)
    assert json.loads(json.dumps(data)) == data
    assert data["programme_key"] == "systems_inquiry"
    assert all(p["policy_id"].startswith("NORTHSTAR-") for p in data["progression_policy_assessments"])
    assert all(
        p["source_reference"].startswith("Synthetic Northstar")
        for p in data["progression_policy_assessments"]
    )
    assert not any(token in json.dumps(data).lower() for token in ("uct-", "uct_", "uct 2026"))
    assert all(p.policy_status == "unverified" for p in report.progression_policy_assessments)


def test_recognition_does_not_create_global_equivalence():
    release, catalogue, inputs, _, _ = run("recognition")
    assert "EXT-77" not in catalogue.courses
    other_student = replace(inputs.student, student_id="OTHER")
    completion = CourseCompletionResolver(
        other_student, catalogue, release.grading_scheme, inputs.recognition
    )
    assert completion.resolve("CORE-Q2").outcome == "unresolved"


def test_no_institution_specific_branch_in_generic_runtime():
    root = Path(__file__).parents[1]
    tokens = [
        "northstar",
        "university_two",
        "school of systems",
        "college of inquiry",
        *[row["code"].lower() for row in read_json("courses.json")],
        "ext-77",
    ]
    for path in (root / "engine").glob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        assert not any(token in text for token in tokens), path


def test_explicit_frameworks_never_call_uct_fallbacks(monkeypatch):
    from curriculum_reasoning_engine.institutions import (
        UCTCourseCodeScheme,
        UCTCourseLoadFramework,
        UCTCreditFramework,
        UCTGradingScheme,
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("UCT framework fallback used by Northstar")

    for cls, names in [
        (UCTGradingScheme, ("is_passed", "is_failed", "is_pending")),
        (UCTCourseCodeScheme, ("infer_academic_level", "infer_year_level", "infer_department")),
        (UCTCourseLoadFramework, ("load_equivalent",)),
        (UCTCreditFramework, ("credit_value", "academic_level", "is_senior_level", "is_level")),
    ]:
        for name in names:
            monkeypatch.setattr(cls, name, forbidden)
    for name in read_json("scenarios.json"):
        run(name)


def test_award_verified_test_authority_can_establish_a_positive_conclusion():
    release, catalogue, inputs, _, _ = run("award")
    # Authority control only; the committed synthetic policy remains unverified.
    catalogue.award_rules[0]["verification_status"] = "verified"
    report = compute_report(inputs.student, catalogue, **frameworks(release))
    assert report.distinction.qualification_eligible
    assert report.distinction.status == "verified"
    assert read_json("degree_requirements.json")["award_rules"][0]["verification_status"] == "unverified"


def test_either_studio_satisfies_the_same_requirement():
    raw = read_json("scenarios.json")["clean"]
    raw["modules"][-1]["module"] = "ALT-V8"
    release, catalogue, inputs, _, _ = analyse(raw)
    evaluator = curriculum(release, catalogue, inputs)
    row = evaluator.evaluate(catalogue.programmes["systems_inquiry"].curriculum_rules[2])
    assert row.complete and row.used_course_codes == ["ALT-V8"]
    assert (
        prerequisites(release, catalogue, inputs).evaluate_for_course(catalogue.courses["CAP-R4"]).outcome
        == "satisfied"
    )


def test_adapter_does_not_infer_local_credit_or_mark_from_recognition_metadata():
    raw = read_json("scenarios.json")["recognition"]
    raw["recognitions"][0].update({"external_score": 99, "credits": 900})
    _, _, inputs, report, _ = analyse(raw)
    assert report.credits_completed == 21
    assert len(inputs.student.results) == 2
    assert not hasattr(inputs.recognition.decisions[0], "external_score")


def test_load_change_does_not_change_credit_ratio_or_award_average():
    release, catalogue, inputs, before, _ = run("clean")
    changed_load = replace(
        release.course_load_framework,
        values=tuple((code, load * 3) for code, load in release.course_load_framework.values),
    )
    after = compute_report(
        inputs.student, catalogue, **frameworks(replace(release, course_load_framework=changed_load))
    )
    assert after.semester_course_equivalents == before.semester_course_equivalents * 3
    assert after.credits_completed == before.credits_completed
    assert after.progression_policy_assessments[0] == before.progression_policy_assessments[0]
    assert after.distinction == before.distinction


def test_all_committed_scenarios_avoid_unsupported_conditions():
    for name in read_json("scenarios.json"):
        release, catalogue, inputs, report, _ = run(name)
        assert all(row.condition_outcome != "unsupported" for row in report.progression_policy_assessments)
        assert "unsupported" not in report.distinction.reason.lower()
        rows = curriculum(release, catalogue, inputs).evaluate_many(
            catalogue.programmes["systems_inquiry"].curriculum_rules
        )
        assert all("unsupported" not in row.detail.lower() for row in rows)
