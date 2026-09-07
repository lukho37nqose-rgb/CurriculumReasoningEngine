from pathlib import Path

from catalogue_governance.reproducibility import (
    compare_json_files,
    fingerprints,
    verify_rebuild,
)


def test_formatting_and_key_order_do_not_change_semantic_fingerprint():
    first = {"policy": {"threshold": 60, "type": "progression_ratio"}}
    second = {"policy": {"type": "progression_ratio", "threshold": 60}}
    assert fingerprints(first).semantic == fingerprints(second).semantic


def test_ordered_lists_remain_semantically_meaningful():
    first = {"achievement_scale": ["fail", "pass", "distinction"]}
    second = {"achievement_scale": ["fail", "distinction", "pass"]}
    assert fingerprints(first).semantic != fingerprints(second).semantic


def test_semantic_and_governance_changes_are_separated():
    before = {"threshold": 60, "verification_status": "unverified", "source_reference": "p.1"}
    after = {"threshold": 65, "verification_status": "verified", "source_reference": "p.2"}
    diff = compare_json_files(_write_json(before), _write_json(after))
    assert any(item.path == "threshold" and item.category == "semantic" for item in diff.changes)
    assert any(item.path == "verification_status" and item.category == "governance" for item in diff.changes)
    assert any(item.path == "source_reference" and item.category == "provenance" for item in diff.changes)


def test_requirement_operator_change_is_detected():
    before = {"type": "all_of", "conditions": [{"type": "course_completed", "course_code": "A"}]}
    after = {"type": "one_of", "conditions": [{"type": "course_completed", "course_code": "A"}]}
    diff = compare_json_files(_write_json(before), _write_json(after))
    assert any(item.path == "type" and item.before == "all_of" and item.after == "one_of" for item in diff.changes)


def test_rebuild_is_non_destructive_and_reports_match_or_drift(tmp_path: Path):
    expected = tmp_path / "expected.json"
    regenerated = tmp_path / "regenerated.json"
    expected.write_text('{"threshold": 60}\n', encoding="utf-8")
    regenerated.write_text('{"threshold":60}\n', encoding="utf-8")
    assert verify_rebuild(expected, regenerated).status == "MATCH"
    regenerated.write_text('{"threshold":65}\n', encoding="utf-8")
    assert verify_rebuild(expected, regenerated).status == "DRIFT"


def _write_json(value):
    import tempfile
    path = Path(tempfile.mkstemp(suffix=".json")[1])
    path.write_text(__import__("json").dumps(value), encoding="utf-8")
    return path
