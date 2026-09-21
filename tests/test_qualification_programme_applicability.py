"""Qualification scope: exact targets, route selection and bounded uncertainty."""

from copy import deepcopy
from dataclasses import replace

import pytest

from engine.models import (
    Catalogue,
    CourseFact,
    CourseResult,
    PathwayDefinition,
    ProgrammeRules,
    StudentRecord,
)
from engine.rule_engine import _compute_distinction, _resolve_qualification_award_applicability


def resolve(rule, key="p", compatibility=False):
    return _resolve_qualification_award_applicability(
        rule, selected_programme_key=key, allow_programme_less_compatibility=compatibility,
    )


@pytest.mark.parametrize("key,state", [("p", "applicable"), ("q", "inapplicable"), ("P", "inapplicable"),
                                       (" p ", "inapplicable"), (None, "unresolved")])
def test_exact_programme_key(key, state):
    assert resolve({"applies_to_programmes": ["p"]}, key)[0] == state


MALFORMED = [[], "p", None, 4, True, {}, ("p",), {"p"}, [""], [" "], [" p"], ["p "],
             [None], [4], [True], [{}], [["p"]], ["p", "p"]]


@pytest.mark.parametrize("targets", MALFORMED)
def test_malformed_direct_scope_is_unresolved(targets):
    state, reason = resolve({"applies_to_programmes": targets})
    assert state == "unresolved"
    assert "Malformed" in reason


@pytest.mark.parametrize("value", ["general_humanities_degree", "structured", "future_unknown_scope", "", None, ["p"]])
def test_legacy_scope_is_never_interpreted(value):
    assert resolve({"applies_to": value})[0] == "unresolved"


def test_dual_declaration_is_unresolved():
    assert resolve({"applies_to": "p", "applies_to_programmes": ["p"]})[0] == "unresolved"


def test_only_programme_less_missing_scope_compatibility():
    assert resolve({}, None, True)[0] == "applicable"
    assert resolve({}, None, False)[0] == "unresolved"
    assert resolve({}, "p", True)[0] == "unresolved"
    assert resolve({"applies_to": ""}, None, True)[0] == "unresolved"
    assert resolve({"applies_to_programmes": None}, None, True)[0] == "unresolved"


def qualification(name="Relevant", targets=None, status="verified", required=1):
    return {
        "id": name, "name": name, "type": "qualification_distinction",
        "applies_to_programmes": ["p"] if targets is None else targets,
        "verification_status": status,
        "curriculum_rules": [{"type": "course_count", "course_codes": ["A"], "required": required}],
    }


def environment(rules, structured=False, fallback_status="verified"):
    programme = ProgrammeRules("p", "Programme", 0, 0, 0, 0, 0, 0, 0,
        programme_type="structured" if structured else "general_degree", scope_verified=True)
    if structured:
        programme.award_rules = [{"name": "Programme award", "verification_status": fallback_status,
            "curriculum_rules": [{"type": "course_count", "course_codes": ["A"], "required": 1}]}]
        programme.pathways = {"path": PathwayDefinition("path", "Path", award_rules=[{
            "name": "Path award", "verification_status": fallback_status,
            "curriculum_rules": [{"type": "course_count", "course_codes": ["A"], "required": 1}],
        }])}
    catalogue = Catalogue({"A": CourseFact("A", "A", 10, 7, [], [], "Synthetic", verification_status="verified")},
        {}, {"p": programme, "q": replace(programme, key="q")}, [], award_rules=rules)
    student = StudentRecord("S", "Student", "Programme", [], [CourseResult("A", "A", 7, 10, 80, None)],
        programme_key="p", pathway_key="path")
    return student, catalogue


def evaluate(rules, *, structured=False, majors=None, fallback_status="verified"):
    student, catalogue = environment(rules, structured, fallback_status)
    return _compute_distinction(student, catalogue, majors or [])


@pytest.mark.parametrize("status", ["verified", "unverified", "conflict"])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("required", [1, 2])
def test_inapplicable_rules_cannot_contaminate_result(status, reverse, required):
    relevant = qualification(required=required)
    irrelevant = qualification("Irrelevant", ["q"], status, required=2)
    rules = [relevant, irrelevant]
    if reverse:
        rules.reverse()
    assert evaluate(rules) == evaluate([relevant])


def test_inapplicable_criteria_never_execute():
    # CurriculumEvaluator would raise converting this required value to a number.
    irrelevant = qualification("Never execute", ["q"], required=None)
    assert evaluate([irrelevant, qualification()]) == evaluate([qualification()])


def test_no_applicable_rule_preserves_absence_result():
    assert evaluate([qualification("Irrelevant", ["q"])]) == evaluate([])


@pytest.mark.parametrize("reverse", [False, True])
def test_successful_witness_retains_applicable_order(reverse):
    rules = [qualification("First"), qualification("Second")]
    if reverse:
        rules.reverse()
    result = evaluate(rules)
    assert result.qualification_eligible
    assert result.reason.startswith(rules[0]["name"] + ":")
    assert rules[1]["name"] not in result.reason


def unresolved_rule(name="Unknown"):
    rule = qualification(name, required=None)
    rule.pop("applies_to_programmes")
    rule["applies_to"] = "unsupported_scope"
    return rule


def test_applicable_success_with_unresolved_sibling_keeps_evidence_but_not_eligibility():
    result = evaluate([qualification(), unresolved_rule()])
    assert not result.qualification_eligible
    assert result.provisional and result.status == "unverified" and result.confidence == 0.65
    assert "Relevant: 1 of 1" in result.reason
    assert "Cannot establish whether qualification policy 'Unknown'" in result.reason


def test_unresolved_explanations_keep_catalogue_order():
    result = evaluate([unresolved_rule("Unknown B"), qualification(), unresolved_rule("Unknown A")])
    assert result.reason.index("Unknown B") < result.reason.index("Unknown A")


def test_known_inapplicable_rules_allow_programme_and_pathway_fallback():
    assert evaluate([qualification("Irrelevant", ["q"], required=None)], structured=True) == evaluate([], structured=True)


@pytest.mark.parametrize("status", ["verified", "conflict"])
def test_unresolved_scope_preserves_fallback_rows_and_conflict(status):
    baseline = evaluate([], structured=True, fallback_status=status)
    result = evaluate([unresolved_rule()], structured=True, fallback_status=status)
    assert result.subjects == baseline.subjects
    assert [row.major for row in result.subjects] == ["Programme award", "Path award"]
    assert not result.qualification_eligible and result.provisional
    assert result.status == ("conflict" if status == "conflict" else "unverified")
    assert result.confidence == min(baseline.confidence, 0.65)
    assert result.reason.startswith(baseline.reason)


def test_unresolved_scope_without_fallback_preserves_zero_confidence():
    student, catalogue = environment([unresolved_rule()], structured=True)
    catalogue.programmes["p"].award_rules = []
    catalogue.programmes["p"].pathways = {}
    result = _compute_distinction(student, catalogue, [])
    assert result.confidence == 0 and result.status == "unverified"
    assert "Unknown" in result.reason


@pytest.mark.parametrize("majors", [[], ["missing_major"]])
def test_missing_scope_with_programme_does_not_depend_on_major_keys(majors):
    rule = qualification(required=None)
    rule.pop("applies_to_programmes")
    result = evaluate([rule], majors=majors)
    assert not result.qualification_eligible and result.status == "unverified"
    assert "scope is missing" in result.reason


def test_programme_less_compatibility_and_unresolved_selected_identity():
    rule = qualification()
    rule.pop("applies_to_programmes")
    student, catalogue = environment([rule])
    catalogue.programmes = {}
    student.programme_key = ""
    assert _compute_distinction(student, catalogue, []).qualification_eligible
    student.programme_key = "unknown"
    assert not _compute_distinction(student, catalogue, []).qualification_eligible
    catalogue.award_rules = [qualification()]
    result = _compute_distinction(student, catalogue, [])
    assert "selected programme identity is unresolved" in result.reason


def test_catalogue_selected_identity_is_used():
    student, catalogue = environment([qualification()])
    student.programme_key = ""
    catalogue.programme_key = "p"
    assert _compute_distinction(student, catalogue, []).qualification_eligible


def test_applicability_does_not_modify_inputs():
    student, catalogue = environment([qualification(), unresolved_rule()])
    before = deepcopy((student, catalogue))
    _compute_distinction(student, catalogue, [])
    assert (student, catalogue) == before


@pytest.mark.parametrize("targets", [None, "p", [" p "], ["p", "p"]])
def test_malformed_scope_does_not_execute_criteria_or_award(targets):
    rule = qualification(required=None)
    rule["applies_to_programmes"] = targets
    result = evaluate([rule])
    assert not result.qualification_eligible and result.status == "unverified"
    assert "Malformed programme scope" in result.reason


def test_poison_criterion_would_raise_if_applicable():
    with pytest.raises(TypeError):
        evaluate([qualification(required=None)])


def test_resolver_is_institution_neutral_and_independent_of_criteria():
    import inspect

    from engine import rule_engine

    source = inspect.getsource(rule_engine._resolve_qualification_award_applicability)
    assert list(inspect.signature(rule_engine._resolve_qualification_award_applicability).parameters) == [
        "rule", "selected_programme_key", "allow_programme_less_compatibility",
    ]
    for token in ("faculty_key", "programme_type", "major_keys", "CurriculumEvaluator", "Report", "grading_scheme"):
        assert token not in source
    orchestration = inspect.getsource(rule_engine._compute_distinction)
    assert "has_applicable_catalogue_qualification_awards" not in orchestration
    assert "programme_type in applies_to" not in orchestration
    assert 'str(rule.get("applies_to"' not in orchestration
