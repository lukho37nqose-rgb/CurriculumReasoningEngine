"""Explicit qualification programme targets in the owning catalogue data."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from engine.catalogue import load_catalogue
from engine.models import StudentRecord
from engine.rule_engine import _compute_distinction, _resolve_qualification_award_applicability
from engine.scope import build_programme_scope

TARGETS = [
    ("data/uct_humanities/degree_requirements.json", "humanities_fb1_4_qualification_distinction",
     ["ba_regular", "bsocsc_regular", "ba_extended", "bsocsc_extended"]),
    ("data/uct_science/degree_requirements.json", "science_fb8_2_direct_qualification_distinction",
     ["bsc_science", "bsc_science_edp"]),
    ("data/uct_science/degree_requirements.json", "science_fb8_2_alternative_18_24_36_qualification_distinction",
     ["bsc_science", "bsc_science_edp"]),
    ("northstar/package/degree_requirements.json", "NS-V1-DISTINCTION", ["systems_inquiry"]),
    ("tests/fixtures/northstar/degree_requirements.json", "NORTHSTAR-2027-ACHIEVEMENT", ["systems_inquiry"]),
]


@pytest.mark.parametrize("path,policy_id,targets", TARGETS)
def test_exact_targets_exist_in_complete_catalogue(path, policy_id, targets):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rule = next(r for r in data["award_rules"] if r["id"] == policy_id)
    assert "applies_to" not in rule
    assert rule["applies_to_programmes"] == targets
    assert set(targets) <= data["programmes"].keys()


def test_science_alternatives_keep_their_order():
    data = json.loads(Path("data/uct_science/degree_requirements.json").read_text(encoding="utf-8"))
    rules = [r for r in data["award_rules"] if r["type"] == "qualification_distinction"]
    assert [r["id"] for r in rules] == [TARGETS[1][1], TARGETS[2][1]]
    assert rules[0]["curriculum_rules"] != rules[1]["curriculum_rules"]


@pytest.mark.parametrize("path,policy_id,key", [(path, policy_id, key) for path, policy_id, keys in TARGETS for key in keys])
def test_every_packaged_target_resolves_and_reaches_qualification_route(path, policy_id, key):
    directory = Path(path).parent
    catalogue = load_catalogue(directory.name, directory / "courses.json", Path(path))
    programme = catalogue.programmes[key]
    scoped, _ = build_programme_scope(directory.name, catalogue, key, next(iter(programme.pathways), ""))
    rule = next(r for r in scoped.award_rules if r["id"] == policy_id)
    assert _resolve_qualification_award_applicability(
        rule, selected_programme_key=key, allow_programme_less_compatibility=False,
    )[0] == "applicable"
    # Sibling targets remain valid after the programme namespace is reduced.
    assert list(scoped.programmes) == [key]
    assert rule["applies_to_programmes"] == next(keys for p, i, keys in TARGETS if p == path and i == policy_id)
    result = _compute_distinction(StudentRecord("S", "Student", programme.name, [], programme_key=key), scoped, [])
    assert rule["name"] in result.reason


@pytest.mark.parametrize("path", [TARGETS[3][0], TARGETS[4][0]])
def test_second_structured_programme_does_not_inherit_northstar_award(path):
    directory = Path(path).parent
    catalogue = load_catalogue(directory.name, directory / "courses.json", Path(path))
    second = replace(catalogue.programmes["systems_inquiry"], key="second", name="Second")
    assert second.programme_type == "structured"
    catalogue.programmes["second"] = second
    result = _compute_distinction(StudentRecord("S", "Student", "Second", [], programme_key="second"), catalogue, [])
    assert not result.qualification_eligible
    assert "Systems Inquiry Achievement" not in result.reason


def test_subject_scope_sentinel_is_unchanged():
    data = json.loads(Path(TARGETS[0][0]).read_text(encoding="utf-8"))
    subject = next(r for r in data["award_rules"] if r["type"] == "subject_selected_set_distinction")
    assert subject["applies_to"] == "standard_faculty_owned_major_without_award_rules"
    assert "applies_to_programmes" not in subject
