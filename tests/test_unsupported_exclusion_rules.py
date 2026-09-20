"""Applicable unknown policy must not become a verified exclusion assessment."""

import pytest

from engine.models import Catalogue, PathwayDefinition, ProgrammeRules, StudentRecord
from engine.rule_engine import _compute_exclusion_risk

MISSING = (
    "An applicable progression/exclusion rule has no supported rule type; "
    "institutional review is required."
)


def unsupported(name):
    return f"Unsupported progression/exclusion rule type {name!r}; institutional review is required."


def assess(rules, *, pathway_rules=(), years=2, assessments=None, pathway="track"):
    programme = ProgrammeRules("P", "Audit", 0, 0, 0, 0, 0, 0, 0, progression_rules=rules)
    programme.pathways["track"] = PathwayDefinition(
        "track", "Track", progression_rules=list(pathway_rules)
    )
    catalogue = Catalogue(courses={}, majors={}, programmes={"P": programme}, forbidden_combinations=[])
    student = StudentRecord("S", "Student", "Audit", [], [], years_registered=years, pathway_key=pathway)
    return _compute_exclusion_risk(
        student, catalogue, "P", progression_policy_assessments=assessments
    )


@pytest.mark.parametrize("rule,message", [
    ({"type": "audit_unknown_rule"}, unsupported("audit_unknown_rule")),
    ({}, MISSING),
    ({"type": ""}, MISSING),
    ({"type": "  "}, MISSING),
    ({"type": None}, MISSING),
])
def test_unknown_only_is_unresolved_without_risk_or_policy_assessment(rule, message):
    assessments = []
    risk = assess([rule], assessments=assessments)
    assert risk.at_risk is False
    assert risk.reasons == []
    assert risk.assessed is False
    assert risk.status == "unverified"
    assert risk.confidence == 0.35
    assert risk.basis.count(message) == 1
    assert assessments == []


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("maximum", [1, 3])
def test_known_risk_or_note_survives_unknown_rule(maximum, reverse):
    known = {"type": "maximum_years", "maximum": maximum, "label": "Registration"}
    baseline = assess([known])
    rules = [known, {"type": "extension"}]
    risk = assess(list(reversed(rules)) if reverse else rules)
    assert risk.at_risk == baseline.at_risk
    assert risk.reasons == baseline.reasons
    assert baseline.basis in risk.basis
    assert not risk.assessed
    assert risk.status == "unverified"
    assert risk.basis.count(unsupported("extension")) == 1


@pytest.mark.parametrize("kind", [
    "accumulated_metric", "annual_credits", "annual_course_equivalents",
    "cumulative_credits", "science_cumulative_credits", "senior_cumulative_credits",
    "course_equivalents_cumulative", "senior_course_equivalents_cumulative",
])
def test_accumulated_fall_through_is_not_unknown(kind):
    risk = assess([{"type": kind, "minimum": 1, "label": "Accumulated"}])
    assert "Unsupported progression/exclusion" not in risk.basis
    assert MISSING not in risk.basis
    if kind in {"annual_credits", "annual_course_equivalents"}:
        assert not risk.assessed  # Existing missing academic-year evidence.
    else:
        assert risk.assessed
        assert risk.at_risk
        assert risk.status == "verified"


@pytest.mark.parametrize("rule", [{"type": "extension"}, {}, {"type": None}])
def test_year_filtered_unknown_remains_skipped(rule):
    risk = assess([{**rule, "year": 1}])
    assert risk.assessed
    assert risk.status == "verified"
    assert risk.confidence == 0.95
    assert not risk.at_risk
    assert "Unresolved:" not in risk.basis


def test_missing_registration_year_keeps_existing_applicability_message():
    risk = assess([{"type": "extension", "year": 1, "label": "Timing"}], years=None)
    assert not risk.assessed
    assert "Timing: years registered are required." in risk.basis
    assert "Unsupported progression/exclusion" not in risk.basis


def test_programme_then_selected_pathway_message_order():
    risk = assess([{"type": "p_first"}, {"type": "p_second"}],
                  pathway_rules=[{"type": "t_first"}, {"type": "t_second"}])
    expected = " ".join(unsupported(name) for name in ("p_first", "p_second", "t_first", "t_second"))
    assert risk.basis.endswith("Unresolved: " + expected)
    other = assess([], pathway_rules=[{"type": "unselected"}], pathway="other")
    assert "unselected" not in other.basis


@pytest.mark.parametrize("reverse", [False, True])
def test_conflict_and_governed_assessment_survive_unknown(reverse):
    policy = {
        "type": "progression_policy", "policy_id": "CONFLICT", "verification_status": "conflict",
        "consequence": {"type": "advisory_risk"},
        "condition": {"type": "failed_metric", "threshold": 1},
    }
    before_assessments = []
    before = assess([policy], assessments=before_assessments)
    rules = [policy, {"type": "extension"}]
    after_assessments = []
    after = assess(list(reversed(rules)) if reverse else rules, assessments=after_assessments)
    assert before.status == after.status == "conflict"
    assert not after.assessed
    assert after.at_risk == before.at_risk
    assert after.reasons == before.reasons
    assert after_assessments == before_assessments
    assert len(after_assessments) == 1
    assert after.basis.count(unsupported("extension")) == 1


@pytest.mark.parametrize("rule,error", [
    ({"type": "maximum_years", "maximum": "invalid"}, "invalid literal"),
    ({"type": "failed_metric"}, "requires threshold or minimum"),
])
def test_malformed_supported_rules_keep_validation_errors(rule, error):
    with pytest.raises(ValueError, match=error):
        assess([rule])
