import copy
import json
import os
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from catalogue_governance.corrections import (
    CorrectionError,
    GovernedCorrection,
    apply_corrections,
    compare_corrected_candidate,
)
from catalogue_governance.reproducibility import fingerprints, semantic_diff
from curriculum_advisor.presentation import (
    PresentationContext,
    advisor_reasoning_view,
    student_reasoning_view,
)
from curriculum_reasoning_engine.institutions.provenance import from_package
from curriculum_reasoning_engine.institutions.uct import UCT_2026_RELEASE
from tools.humanities_provenance import PPE_IDS, SOURCE_ID, build_provenance

ROOT = Path(__file__).resolve().parents[1]


def package():
    return json.loads((ROOT / "data/uct_humanities/degree_requirements.json").read_text(encoding="utf-8"))


def report(ids=PPE_IDS, programme="bsocsc_ppe"):
    return SimpleNamespace(programme_key=programme, requirements=[SimpleNamespace(
        id="curriculum:" + key, label=key, complete=False, status="unresolved", detail="", explanation=""
    ) for key in ids])


@pytest.mark.parametrize("key", PPE_IDS)
def test_each_governed_relationship_survives_projection(key):
    raw = package()
    rule = next(item for item in raw["programmes"]["bsocsc_ppe"]["curriculum_rules"] if item["id"] == key)
    context = PresentationContext({}, {}, UCT_2026_RELEASE.provenance)
    view = student_reasoning_view(report(), context=context)
    link = next(item for item in view["source_relationships"] if item["conclusion_id"] == "curriculum:" + key)
    assert link["source_id"] == SOURCE_ID
    assert link["relationship"] == "DIRECT_RULE_SOURCE"
    assert link["locator"] == {k: v for k, v in rule["source"].items() if k != "document"}
    assert link["release_id"] == "2026"
    assert link["source_status"] == "checksum_mismatch_unverified_source_archive"
    assert link["relationship_status"] == "unverified"
    assert link["rule_status"] == rule["verification_status"]
    assert len(view["source_directory"]) == 1
    assert len(view["source_directory"][0]["conclusion_links"]) == 7
    assert advisor_reasoning_view(report(), context=context)["source_relationships"] == view["source_relationships"]


@pytest.mark.parametrize("key,programme", [("credits", "ba_regular"), ("ppe_eco3", "bsocsc_ppe"), ("child", "bsocsc_ppe"), ("ppe_year1", "ba_regular")])
def test_no_source_leakage(key, programme):
    view = student_reasoning_view(report([key], programme), context=PresentationContext({}, {}, UCT_2026_RELEASE.provenance))
    assert view["source_directory"] == []
    assert view["conclusions"][0]["source_missing"]


def test_deterministic_builder_parity():
    raw = package()
    assert build_provenance(raw["programmes"]) == {k: raw[k] for k in ("institution_sources", "requirement_source_relationships")}
    assert len(raw["requirement_source_relationships"]) == 7
    assert build_provenance(raw["programmes"]) == build_provenance(raw["programmes"])
    baseline = {key: value for key, value in raw.items() if key not in {"institution_sources", "requirement_source_relationships"}}
    assert fingerprints(baseline).semantic == fingerprints(raw).semantic
    assert len(semantic_diff(baseline, raw).provenance_changes) == 2


def hostile():
    raw = build_provenance(package()["programmes"])
    source = raw["institution_sources"][0]
    source.update(institution_id="northstar", release_id="2027", source_id="northstar:2027:registry:RX-OMEGA", source_kind="registry")
    source["title"] = "Opaque register"
    for item in raw["requirement_source_relationships"]:
        item.update(institution_id="northstar", release_id="2027", source_id=source["source_id"], locator={"record_id": "QZ-441", "clause": item["requirement_id"], "future": {"opaque": [1, 2]}})
    raw["programmes"] = package()["programmes"]
    return raw


def test_hostile_registry_immutable_many_locators_and_release_isolation():
    raw = hostile()
    index = from_package(raw, "northstar", "2027")
    assert len(index.for_source(index.sources[0].source_id)) == 7
    with pytest.raises(TypeError):
        index.relationships[0].locator["future"]["opaque"] = ()
    with pytest.raises(ValueError):
        replace(UCT_2026_RELEASE, provenance=index)
    raw["requirement_source_relationships"][1]["relationship_type"] = "PACKAGE_SOURCE"
    view = student_reasoning_view(report(), context=PresentationContext({}, {}, from_package(raw, "northstar", "2027")))
    assert len(view["source_relationships"]) == 6


@pytest.mark.parametrize("change", ["source", "requirement", "release", "duplicate"])
def test_invalid_reference_fails(change):
    raw = hostile()
    relation = raw["requirement_source_relationships"][0]
    if change == "source":
        relation["source_id"] = "missing"
    elif change == "requirement":
        relation["requirement_id"] = "missing"
    elif change == "release":
        relation["release_id"] = "2028"
    else:
        raw["requirement_source_relationships"].append(copy.deepcopy(relation))
    with pytest.raises(ValueError):
        from_package(raw, "northstar", "2027")


def test_fingerprints_and_corrections():
    raw = hostile()
    changed = copy.deepcopy(raw)
    changed["requirement_source_relationships"][0]["locator"]["clause"] = "KAPPA"
    assert fingerprints(raw).semantic == fingerprints(changed).semantic
    assert fingerprints(raw).provenance != fingerprints(changed).provenance
    assert semantic_diff(raw, changed).provenance_changes
    relation = raw["requirement_source_relationships"][0]
    correction = GovernedCorrection("fix", "northstar", "2027", "fixture", "relationship_id", relation["relationship_id"], "locator.clause", "replace_value", relation["locator"]["clause"], "KAPPA", "register", "unverified", "fixture author")
    assert apply_corrections(raw, (correction,)).candidate == changed
    assert compare_corrected_candidate(raw, changed, ()).status == "UNDECLARED_OUTPUT_DRIFT"
    assert compare_corrected_candidate(raw, changed, (correction,)).status == "MATCH_AFTER_CORRECTIONS"
    with pytest.raises(CorrectionError):
        apply_corrections(changed, (correction,))
    changed["programmes"]["bsocsc_ppe"]["curriculum_rules"][2]["required"] = 2
    assert fingerprints(raw).semantic != fingerprints(changed).semantic


def test_real_backend_projection_and_reasoning_independence(monkeypatch):
    from fastapi.testclient import TestClient

    import app as backend

    body = {"faculty": "uct_humanities", "programme_key": "bsocsc_ppe",
            "student_id": "PPE-PROVENANCE", "results": []}
    client = TestClient(backend.app)
    response = client.post("/analyse/json", json=body)
    assert response.status_code == 200, response.text
    indexed = response.json()
    links = indexed["student_reasoning_view"]["source_relationships"]
    assert {item["conclusion_id"] for item in links if item.get("source_id") == SOURCE_ID} == {"curriculum:" + key for key in PPE_IDS}
    monkeypatch.setattr(backend, "ACTIVE_INSTITUTION_RELEASE", replace(UCT_2026_RELEASE, provenance=None))
    plain_report = client.post("/analyse/json", json=body).json()
    indexed.pop("student_reasoning_view")
    plain_report.pop("student_reasoning_view")
    indexed.pop("advisor_reasoning_view")
    plain_report.pop("advisor_reasoning_view")
    assert indexed == plain_report


def test_isolated_full_builder(tmp_path):
    target = tmp_path / "tools"
    target.mkdir()
    for name in ("build_structured_humanities.py", "humanities_provenance.py"):
        shutil.copyfile(ROOT / "tools" / name, target / name)
    shutil.copytree(ROOT / "data/uct_humanities", tmp_path / "data/uct_humanities")
    result = subprocess.run([sys.executable, str(target / "build_structured_humanities.py")],
                            cwd=tmp_path, env={**os.environ, "PYTHONUTF8": "1"},
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    rebuilt = json.loads((tmp_path / "data/uct_humanities/degree_requirements.json").read_text(encoding="utf-8"))
    original = package()
    for key in ("institution_sources", "requirement_source_relationships"):
        assert rebuilt[key] == original[key]
    original_rules = {rule["id"]: rule for rule in original["programmes"]["bsocsc_ppe"]["curriculum_rules"]}
    rebuilt_rules = {rule["id"]: rule for rule in rebuilt["programmes"]["bsocsc_ppe"]["curriculum_rules"]}
    for key in PPE_IDS:
        assert rebuilt_rules[key] == original_rules[key]


def test_release_gate_rejects_invalid_reference_and_reviews_locator_change():
    from catalogue_governance.release_gate import run_release_gate

    raw = hostile()
    changed = copy.deepcopy(raw)
    changed["requirement_source_relationships"][0]["locator"]["clause"] = "KAPPA"
    result = run_release_gate(ROOT, run_quality=False, baseline=raw, governed=changed)
    assert result.review_required and result.provenance_changes
    assert not result.semantic_changes
    changed["requirement_source_relationships"][0]["source_id"] = "unknown"
    assert run_release_gate(ROOT, run_quality=False, governed=changed).overall_outcome == "FAIL"
