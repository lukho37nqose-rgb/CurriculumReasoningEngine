"""Northstar conformance and failure injection for the replay lab."""

import json
from pathlib import Path

from decision_replay.core import create_bundle, fingerprint, replay_bundle


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_bundle_replays_without_the_ui(tmp_path: Path):
    bundle = tmp_path / "bundle"
    create_bundle(bundle)
    report = replay_bundle(bundle)

    assert report["status"] == "EXACT_MATCH"
    artifact = _load(bundle / "decision-artifact.json")
    assert artifact["institution_id"] == "northstar"
    assert artifact["trace"]["nodes"]
    assert "expected" not in json.dumps(_load(bundle / "evidence-bundle.json")).lower()


def test_repeated_creation_is_byte_deterministic(tmp_path: Path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    create_bundle(first)
    create_bundle(second)

    for name in (
        "bundle-manifest.json",
        "evaluation-request.json",
        "evidence-bundle.json",
        "release-reference.json",
        "decision-artifact.json",
        "source-index.json",
        "replay-report.json",
    ):
        assert (first / name).read_bytes() == (second / name).read_bytes(), name


def test_mark_mutation_is_detected_as_input_mismatch(tmp_path: Path):
    bundle = tmp_path / "bundle"
    create_bundle(bundle)
    evidence = _load(bundle / "evidence-bundle.json")
    evidence["modules"][0]["score"] = 71
    (bundle / "evidence-bundle.json").write_text(json.dumps(evidence), encoding="utf-8")

    report = replay_bundle(bundle)

    assert report["status"] == "INPUT_OR_RELEASE_MISMATCH"
    assert report["checks"]["evidence_fingerprint_match"] is False
    assert report["comparison"]["decision_match"] is False


def test_release_rule_mutation_is_detected_before_claiming_replay(tmp_path: Path):
    bundle = tmp_path / "bundle"
    create_bundle(bundle)
    reference = _load(bundle / "release-reference.json")
    reference["package"]["degree_requirements.json"]["programmes"]["systems_inquiry"]["curriculum_rules"][0]["label"] = "Changed rule label"
    (bundle / "release-reference.json").write_text(json.dumps(reference), encoding="utf-8")

    report = replay_bundle(bundle)

    assert report["status"] == "INPUT_OR_RELEASE_MISMATCH"
    assert report["checks"]["release_fingerprint_match"] is False


def test_tampered_artifact_fingerprint_is_reported(tmp_path: Path):
    bundle = tmp_path / "bundle"
    create_bundle(bundle)
    artifact = _load(bundle / "decision-artifact.json")
    artifact["warnings"].append("tampered")
    (bundle / "decision-artifact.json").write_text(json.dumps(artifact), encoding="utf-8")

    report = replay_bundle(bundle)

    assert report["status"] == "INPUT_OR_RELEASE_MISMATCH"
    assert report["checks"]["recorded_artifact_fingerprint_match"] is False


def test_engine_metadata_mismatch_is_visible(tmp_path: Path):
    bundle = tmp_path / "bundle"
    create_bundle(bundle)
    manifest = _load(bundle / "bundle-manifest.json")
    manifest["engine_build"]["implementation"] = "future-engine"
    (bundle / "bundle-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    report = replay_bundle(bundle)

    assert report["status"] == "ENGINE_VERSION_MISMATCH"


def test_fingerprint_is_stable_for_semantically_identical_json():
    assert fingerprint({"b": 2, "a": [1, 2]}) == fingerprint({"a": [1, 2], "b": 2})