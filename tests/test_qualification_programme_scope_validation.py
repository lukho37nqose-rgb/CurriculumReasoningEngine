"""Qualification scope validation occurs against the complete catalogue."""

import json

import pytest

from engine.catalogue import load_catalogue


def load(tmp_path, rule):
    courses = tmp_path / "courses.json"
    requirements = tmp_path / "requirements.json"
    courses.write_text("[]", encoding="utf-8")
    requirements.write_text(json.dumps({"programmes": {"p": {}, "q": {}}, "award_rules": [rule]}), encoding="utf-8")
    return load_catalogue("synthetic", courses, requirements)


@pytest.mark.parametrize("targets", [[], "p", None, 4, True, {}, [""], [" "], [" p"], ["p "],
                                     [None], [4], [True], [{}], [["p"]], ["p", "p"], ["absent"], ["P"]])
def test_loader_rejects_malformed_or_unknown_targets(tmp_path, targets):
    with pytest.raises(ValueError, match="Catalogue qualification rule"):
        load(tmp_path, {"type": "qualification_distinction", "applies_to_programmes": targets})


def test_loader_rejects_dual_scope(tmp_path):
    with pytest.raises(ValueError, match="both legacy and explicit"):
        load(tmp_path, {"type": "qualification_distinction", "applies_to_programmes": ["p"], "applies_to": "p"})


def test_loader_accepts_complete_namespace_targets(tmp_path):
    rule = {"type": "qualification_distinction", "applies_to_programmes": ["p", "q"]}
    assert load(tmp_path, rule).award_rules == [rule]


@pytest.mark.parametrize("rule", [{"type": "subject_selected_set_distinction", "applies_to": "sentinel"},
                                  {"type": "other", "applies_to_programmes": None},
                                  {"type": "qualification_distinction"},
                                  {"type": "qualification_distinction", "applies_to": "legacy"}])
def test_loader_does_not_expand_scope_validation_to_other_contracts(tmp_path, rule):
    assert load(tmp_path, rule).award_rules == [rule]
