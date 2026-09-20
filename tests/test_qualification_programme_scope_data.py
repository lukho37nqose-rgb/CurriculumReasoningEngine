"""Explicit qualification programme targets in the owning catalogue data."""

import json
from pathlib import Path

import pytest

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
    assert rule["applies_to_programmes"] == targets
    assert set(targets) <= data["programmes"].keys()


def test_science_alternatives_keep_their_order():
    data = json.loads(Path("data/uct_science/degree_requirements.json").read_text(encoding="utf-8"))
    rules = [r for r in data["award_rules"] if r["type"] == "qualification_distinction"]
    assert [r["id"] for r in rules] == [TARGETS[1][1], TARGETS[2][1]]
    assert rules[0]["curriculum_rules"] != rules[1]["curriculum_rules"]
