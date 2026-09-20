"""Report-local recognition caching and unchanged compatibility boundaries."""

import inspect
from dataclasses import FrozenInstanceError, asdict, fields
from unittest.mock import Mock

import pytest
from fixtures.northstar import catalogue_for, frameworks, read_json, select_release

from engine import evaluation_context as context_module
from engine import rule_engine
from engine.completion import CourseCompletionResolver
from engine.curriculum import CurriculumEvaluator
from engine.evaluation_context import EvaluationContext
from engine.models import Catalogue, CourseFact, CourseResult, ProgrammeRules, StudentRecord
from engine.recognition import provisional_open_credit_results, recognised_credited_pairs


def sample():
    programme = ProgrammeRules("p", "P", 30, 0, 0, 0, 0, 0, 0)
    courses = {
        code: CourseFact(code, code, credits, 5, [], [], "A", verification_status="verified")
        for code, credits in [("AAA1001F", 10), ("ZERO1001F", 0)]
    }
    courses["ZERO1001F"].credit_bearing = False
    catalogue = Catalogue(courses, {}, {"p": programme}, [], programme_key="p")
    student = StudentRecord("S", "S", "P", [], [
        CourseResult(code, code, 5, credits, 70, None)
        for code, credits in [("AAA1001F", 10), ("ZERO1001F", 0), ("EXT1001F", 10), ("EXT1002F", 20)]
    ], programme_key="p")
    return student, catalogue


def context(student, catalogue):
    return EvaluationContext(student, catalogue, None, None, None, None)


def test_explicit_fields_and_shallow_freeze():
    student, catalogue = sample()
    ctx = context(student, catalogue)
    assert [f.name for f in fields(ctx)] == [
        "student", "catalogue", "grading_scheme", "credit_framework", "course_code_scheme", "course_load_framework"
    ]
    with pytest.raises(TypeError):
        EvaluationContext(student, catalogue)
    with pytest.raises(FrozenInstanceError):
        ctx.student = student
    assert ctx != context(student, catalogue)
    assert ctx.student is student and ctx.catalogue is catalogue
    assert all(getattr(ctx, name) is None for name in (
        "grading_scheme", "credit_framework", "course_code_scheme", "course_load_framework"
    ))


@pytest.mark.parametrize("explicit", [False, True])
def test_lazy_once_per_context_and_exact_forwarding(monkeypatch, explicit):
    student, catalogue = sample()
    release = select_release("northstar", "northstar-fixture-2027")
    values = tuple(frameworks(release).values()) if explicit else (None,) * 4
    pair = (student.results[0], catalogue.courses["AAA1001F"])
    exclusion = object()
    recognition = Mock(return_value=([pair], [exclusion]))
    provisional = Mock(return_value=[student.results[-1], student.results[-2]])
    monkeypatch.setattr(context_module, "recognised_credited_pairs", recognition)
    monkeypatch.setattr(context_module, "provisional_open_credit_results", provisional)
    ctx = EvaluationContext(student, catalogue, *values)
    other = EvaluationContext(student, catalogue, *values)
    recognition.assert_not_called()
    provisional.assert_not_called()
    first = ctx.recognition
    assert ctx.recognition is first
    recognition.assert_called_once_with(student, catalogue, values[0], values[2])
    provisional.assert_not_called()
    results = ctx.provisional_results
    assert ctx.provisional_results is results
    provisional.assert_called_once_with(student, catalogue, values[0], values[1], values[2])
    assert first == ((pair,), (exclusion,))
    assert first[0][0][0] is student.results[0]
    assert first[0][0][1] is catalogue.courses["AAA1001F"]
    assert results == (student.results[-1], student.results[-2])
    assert results[0] is student.results[-1]
    assert other.recognition is not first
    assert other.provisional_results is not results
    assert recognition.call_count == provisional.call_count == 2


def test_music_cap_retains_transcript_order_and_exclusion_order():
    from test_course_code_scheme import MusicLimitCodeScheme

    student, catalogue = sample()
    codes = [f"MUZOPAQUE{i}" for i in [5, 2, 4, 0, 3, 1]]
    catalogue.courses = {
        code: CourseFact(code, code, 10, 5, [], [], "Music") for code in codes
    }
    student.results = [CourseResult(code, code, 5, 10, 70, None) for code in codes]
    ctx = EvaluationContext(student, catalogue, None, None, MusicLimitCodeScheme(), None)
    pairs, exclusions = ctx.recognition
    assert [r.code for r, _ in pairs] == codes[:4]
    assert [e.code for e in exclusions] == codes[4:]
    expected = recognised_credited_pairs(student, catalogue, None, ctx.course_code_scheme)
    assert (list(pairs), list(exclusions)) == expected


def add_pools(catalogue):
    catalogue.programmes["p"].curriculum_rules = [
        {"id": name, "type": "approved_credit_pool", "required": 10,
         "transcript_only": True, "allow_unlisted_transcript_courses": True}
        for name in ("first", "second")
    ]


def test_open_pool_order_unknown_zero_credit_and_provisional_semantics():
    student, catalogue = sample()
    before = context(student, catalogue)
    assert before.provisional_results == ()
    assert rule_engine._compute_credits_with_context(before) == (10, 0, [])
    assert "EXT1001F, EXT1002F" in " ".join(rule_engine._compute_warnings_with_context(before, []))
    assert "ZERO1001F" in CourseCompletionResolver(student, catalogue).completed_codes()
    assert "ZERO1001F" not in {r.code for r, _ in before.recognition[0]}
    add_pools(catalogue)
    ctx = context(student, catalogue)
    assert [r.code for r in ctx.provisional_results] == ["EXT1001F", "EXT1002F"]
    assert list(ctx.provisional_results) == provisional_open_credit_results(student, catalogue)
    evaluator = CurriculumEvaluator(student, catalogue)
    assert [a.results[0].code for a in evaluator.open_credit_allocations] == ["EXT1001F", "EXT1002F"]
    assert all(row.status == "unverified" for row in evaluator.evaluate_many(catalogue.programmes["p"].curriculum_rules))
    assert rule_engine._compute_credits_with_context(ctx)[:2] == (40, 0)
    assert not any("outside the selected" in w for w in rule_engine._compute_warnings_with_context(ctx, []))


def test_legacy_signatures_equivalence_and_fresh_lists(monkeypatch):
    student, catalogue = sample()
    add_pools(catalogue)
    ctx = context(student, catalogue)
    assert rule_engine._compute_credits(student, catalogue) == rule_engine._compute_credits_with_context(ctx)
    assert rule_engine._compute_course_equivalents(student, catalogue) == rule_engine._compute_course_equivalents_with_context(ctx)
    assert rule_engine._compute_warnings(student, catalogue, []) == rule_engine._compute_warnings_with_context(ctx, [])
    assert rule_engine._compute_credits(student=student, catalogue=catalogue, grading_scheme=None,
                                      credit_framework=None, course_code_scheme=None) == (40, 0, list(ctx.provisional_results))
    # Exercise the legacy wrapper against a known context to verify ownership.
    monkeypatch.setattr(rule_engine, "EvaluationContext", lambda *args: ctx)
    returned = rule_engine._compute_credits(student, catalogue)[2]
    returned.clear()
    assert len(ctx.provisional_results) == 2
    assert len(rule_engine._compute_credits_with_context(ctx)[2]) == 2


@pytest.mark.parametrize("scenario", list(read_json("scenarios.json")))
def test_northstar_full_report_cached_matches_uncached(monkeypatch, scenario):
    release = select_release("northstar", "northstar-fixture-2027")
    catalogue = catalogue_for(release)
    inputs = release.transcript_adapter.ingest(read_json("scenarios.json")[scenario])
    kwargs = dict(frameworks(release), completion_recognition=inputs.recognition,
                  academic_record_coverage_evidence=inputs.result_coverage,
                  academic_period_scheme=release.period_scheme)
    created = []
    recognition = Mock(wraps=context_module.recognised_credited_pairs)
    provisional = Mock(wraps=context_module.provisional_open_credit_results)
    monkeypatch.setattr(context_module, "recognised_credited_pairs", recognition)
    monkeypatch.setattr(context_module, "provisional_open_credit_results", provisional)

    def record(*args):
        ctx = EvaluationContext(*args)
        created.append(ctx)
        return ctx

    monkeypatch.setattr(rule_engine, "EvaluationContext", record)
    actual = asdict(rule_engine.compute_report(inputs.student, catalogue, **kwargs))
    assert len(created) == 1
    assert recognition.call_count == provisional.call_count == 1
    assert "recognition" in created[0].__dict__ and "provisional_results" in created[0].__dict__

    class Uncached(EvaluationContext):
        recognition = property(EvaluationContext.recognition.func)
        provisional_results = property(EvaluationContext.provisional_results.func)

    monkeypatch.setattr(rule_engine, "EvaluationContext", Uncached)
    assert asdict(rule_engine.compute_report(inputs.student, catalogue, **kwargs)) == actual


def test_new_owner_retains_course_load_boundary():
    assert "_course_weight" not in inspect.getsource(rule_engine._compute_course_equivalents_with_context)
    assert "rule_engine" not in inspect.getsource(context_module)


@pytest.mark.parametrize("faculty,programme,pathway", [
    ("uct_humanities", "bsocsc_ppe", ""),
    ("uct_law", "llb_four_year_undergraduate", "numeracy_test_passed"),
])
def test_uct_full_report_cached_matches_uncached(monkeypatch, faculty, programme, pathway):
    from engine.catalogue import load_catalogue

    catalogue = load_catalogue(faculty)
    assert programme in catalogue.programmes
    from engine.scope import build_programme_scope

    catalogue, _ = build_programme_scope(faculty, catalogue, programme, pathway)
    student = StudentRecord("UCT", "UCT", catalogue.programmes[programme].name, [],
                            programme_key=programme, years_registered=2)
    expected = asdict(rule_engine.compute_report(student, catalogue))

    class Uncached(EvaluationContext):
        recognition = property(EvaluationContext.recognition.func)
        provisional_results = property(EvaluationContext.provisional_results.func)

    monkeypatch.setattr(rule_engine, "EvaluationContext", Uncached)
    assert asdict(rule_engine.compute_report(student, catalogue)) == expected


def test_northstar_legacy_wrappers_accept_explicit_frameworks():
    release = select_release("northstar", "northstar-fixture-2027")
    catalogue = catalogue_for(release)
    inputs = release.transcript_adapter.ingest(read_json("scenarios.json")["clean"])
    values = frameworks(release)
    ctx = EvaluationContext(inputs.student, catalogue, **values)
    assert rule_engine._compute_course_equivalents(inputs.student, catalogue, **values) == (
        rule_engine._compute_course_equivalents_with_context(ctx)
    )
    credit_values = {key: value for key, value in values.items() if key != "course_load_framework"}
    assert rule_engine._compute_credits(inputs.student, catalogue, **credit_values) == (
        rule_engine._compute_credits_with_context(ctx)
    )
    assert rule_engine._compute_warnings(inputs.student, catalogue, [], **credit_values) == (
        rule_engine._compute_warnings_with_context(ctx, [])
    )
