"""Governed award structure is checked at loading and direct evaluation boundaries."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from engine.catalogue import _governed_award_declaration_issue, load_catalogue
from engine.models import Catalogue, PathwayDefinition, ProgrammeRules, StudentRecord
from engine.rule_engine import _compute_distinction

INVALID = [
    {}, {"curriculum_rules": []},
    *[{"curriculum_rules": value} for value in (None, "rules", {}, 2, True, ())],
    {"curriculum_rules": [None]},
    {"curriculum_rules": [{"type": "no_failures"}, "bad"]},
    *[{"curriculum_rules": [{"type": kind}]} for kind in ("all_of", "any_of")],
    *[{"curriculum_rules": [{"type": "all_of", "children": value}]}
      for value in ([], None, "rules", {}, 2, True, (), [None])],
    {"curriculum_rules": [{"type": "any_of", "children": []}]},
    {"curriculum_rules": [{"type": "all_of", "children": [
        {"type": "no_failures"}, {"type": "any_of", "children": []}]}]},
    {"curriculum_rules": [{"type": " ALL_OF ", "children": []}]},
    {"complete_within_years": 3},
    None,
]
VALID = [
    {"curriculum_rules": [{"type": "manual"}]},
    {"curriculum_rules": [{"type": "audit_unknown"}]},
    {"curriculum_rules": [{"type": "no_failures"}]},
    {"curriculum_rules": [{"type": "all_of", "children": [
        {"type": "any_of", "children": [{"type": "no_failures"}]}]}]},
    {"curriculum_rules": [{"type": "credits", "required": "malformed"}]},
]


def direct(awards, owner="programme"):
    programme = ProgrammeRules("p", "P", 0, 0, 0, 0, 0, 0, 0,
                               programme_type="structured", scope_verified=True)
    if owner == "programme":
        programme.award_rules = awards
    else:
        programme.pathways = {"path": PathwayDefinition("path", "Path", award_rules=awards)}
    catalogue = Catalogue({}, {}, {"p": programme}, [])
    student = StudentRecord("s", "S", "P", [], programme_key="p", pathway_key="path", years_registered=2)
    return student, catalogue


def loaded(tmp_path, award, owner):
    programme = {"programme_type": "structured", "scope_verified": True}
    if owner == "programme":
        programme["award_rules"] = [award]
    else:
        programme["pathways"] = {"path": {"award_rules": [award]}}
    courses = tmp_path / "courses.json"
    requirements = tmp_path / "requirements.json"
    courses.write_text("[]", encoding="utf-8")
    requirements.write_text(json.dumps({"programmes": {"p": programme}}), encoding="utf-8")
    return load_catalogue("synthetic", courses, requirements)


@pytest.mark.parametrize("award", INVALID)
def test_shared_checker_reports_deterministic_issue(award):
    issue = _governed_award_declaration_issue(award)
    assert isinstance(issue, str) and issue
    assert _governed_award_declaration_issue(award) == issue


@pytest.mark.parametrize("award", VALID)
def test_shared_checker_does_not_validate_criterion_semantics(award):
    assert _governed_award_declaration_issue(award) is None


@pytest.mark.parametrize("award", INVALID)
def test_loader_rejects_invalid_declarations_with_owner_context(tmp_path, award):
    owner = "programme"
    with pytest.raises(ValueError) as error:
        loaded(tmp_path, award, owner)
    message = str(error.value)
    assert "Programme 'p'" in message and "award 1" in message
    assert _governed_award_declaration_issue(award) in message
    if owner == "pathway":
        assert "pathway 'path'" in message


@pytest.mark.parametrize("award", VALID)
def test_loader_accepts_structurally_valid_criteria(tmp_path, award):
    owner = "programme"
    catalogue = loaded(tmp_path, award, owner)
    target = catalogue.programmes["p"]
    if owner == "pathway":
        target = target.pathways["path"]
    assert target.award_rules == [award]


@pytest.mark.parametrize("award", [{}, {"curriculum_rules": [{"type": "all_of", "children": []}]}])
def test_pathway_loader_uses_the_same_validation_and_context(tmp_path, award):
    with pytest.raises(ValueError) as error:
        loaded(tmp_path, award, "pathway")
    assert "Programme 'p', pathway 'path', award 1" in str(error.value)
    assert _governed_award_declaration_issue(award) in str(error.value)


def test_pathway_loader_accepts_manual_criteria(tmp_path):
    award = VALID[0]
    catalogue = loaded(tmp_path, award, "pathway")
    assert catalogue.programmes["p"].pathways["path"].award_rules == [award]


@pytest.mark.parametrize("owner", ["programme", "pathway"])
@pytest.mark.parametrize("award", INVALID)
def test_direct_invalid_award_is_retained_without_evaluator(owner, award):
    student, catalogue = direct([award], owner)
    with patch("engine.rule_engine.CurriculumEvaluator", side_effect=AssertionError("must not evaluate")):
        result = _compute_distinction(student, catalogue, [])
    assert not result.qualification_eligible and result.provisional
    assert result.status == "unverified" and result.confidence == 0.0
    assert len(result.subjects) == 1
    row = result.subjects[0]
    assert not row.eligible and row.status == "unverified"
    assert row.average == 0.0 and row.senior_courses_assessed == 0
    assert row.policy_id.startswith(owner + ":p:")
    assert "Cannot assess" in row.reason and "Cannot assess" in result.reason
    assert "thresholds met" not in result.reason
    assert _governed_award_declaration_issue(award) in row.reason


@pytest.mark.parametrize("kind,status,eligible,average", [
    ("manual", "discretionary", False, 1.0),
    ("audit_unknown", "unverified", False, 0.0),
    ("no_failures", "verified", True, 0.0),
])
def test_valid_zero_course_and_unresolved_criteria_keep_existing_semantics(kind, status, eligible, average):
    student, catalogue = direct([{"curriculum_rules": [{"type": kind}]}])
    result = _compute_distinction(student, catalogue, [])
    row = result.subjects[0]
    assert row.eligible is eligible and result.qualification_eligible is eligible
    assert row.status == status and row.average == average
    assert row.senior_courses_assessed == 0
    assert "declaration is invalid" not in row.reason
    assert result.confidence == (0.95 if eligible else 0.5)
    if kind == "audit_unknown":
        assert "Unsupported curriculum rule type" in row.reason


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("criterion,expected_status,eligible", [
    ({"type": "credits", "required": 10}, "unverified", False),
    ({"type": "no_failures"}, "verified", True),
    ({"type": "manual"}, "unverified", False),
    ({"type": "no_failures", "verification_status": "conflict"}, "conflict", False),
])
def test_invalid_sibling_never_becomes_a_witness(reverse, criterion, expected_status, eligible):
    valid = {"name": "Valid", "curriculum_rules": [criterion]}
    baseline_student, baseline_catalogue = direct([valid])
    baseline = _compute_distinction(baseline_student, baseline_catalogue, []).subjects[0]
    awards = [{"name": "Invalid", "id": "invalid"}, valid]
    if reverse:
        awards.reverse()
    student, catalogue = direct(awards)
    result = _compute_distinction(student, catalogue, [])
    assert [row.major for row in result.subjects] == [award["name"] for award in awards]
    assert next(row for row in result.subjects if row.major == "Valid") == baseline
    assert result.qualification_eligible is eligible
    assert result.status == expected_status and result.provisional
    assert result.confidence == (0.95 if eligible else 0.5)
    invalid = next(row for row in result.subjects if row.major == "Invalid")
    assert not invalid.eligible and invalid.policy_id == "programme:p:invalid"


def test_nonblocking_failure_still_blocks_governed_award():
    student, catalogue = direct([{"curriculum_rules": [{"type": "credits", "required": 1, "blocking": False}]}])
    result = _compute_distinction(student, catalogue, [])
    assert not result.qualification_eligible
    assert result.status == "verified" and result.confidence == 0.8


@pytest.mark.parametrize("years,eligible,status", [(2, True, "verified"), (4, False, "verified"), (None, False, "unverified")])
def test_valid_duration_constraint_is_unchanged(years, eligible, status):
    student, catalogue = direct([{"curriculum_rules": [{"type": "no_failures"}], "complete_within_years": 3}])
    student.years_registered = years
    result = _compute_distinction(student, catalogue, [])
    assert result.qualification_eligible is eligible and result.status == status


def test_invalid_pathway_retains_independent_owner_conflict():
    student, catalogue = direct([{}], "pathway")
    catalogue.programmes["p"].pathways["path"].verification_status = "conflict"
    result = _compute_distinction(student, catalogue, [])
    assert result.status == "conflict" and result.confidence == 0.0
    assert result.subjects[0].status == "unverified"


def test_programme_then_pathway_order_and_structured_early_return():
    student, catalogue = direct([{"name": "Programme"}])
    catalogue.programmes["p"].pathways = {"path": PathwayDefinition(
        "path", "Path", award_rules=[{"name": "Pathway"}])}
    with patch("engine.rule_engine._compute_major_progress", side_effect=AssertionError("must return early")):
        result = _compute_distinction(student, catalogue, ["unused"])
    assert [row.major for row in result.subjects] == ["Programme", "Pathway"]
    assert result.confidence == 0.0


def test_every_packaged_governed_award_satisfies_structure():
    root = Path(__file__).resolve().parents[1]
    paths = sorted((root / "data").glob("*/degree_requirements.json"))
    paths += [root / "northstar/package/degree_requirements.json", root / "tests/fixtures/northstar/degree_requirements.json"]
    count = 0
    for path in paths:
        catalogue = load_catalogue("synthetic", path.with_name("courses.json"), path)
        for programme in catalogue.programmes.values():
            for owner in [programme, *programme.pathways.values()]:
                for award in owner.award_rules:
                    assert _governed_award_declaration_issue(award) is None
                    count += 1
    assert count > 0
    print(f"Validated {count} packaged governed awards")
