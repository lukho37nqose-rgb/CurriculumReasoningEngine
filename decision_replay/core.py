"""Laboratory implementation of a replayable CRE decision bundle.

This module deliberately targets the test Northstar fixture first. It does not
change curriculum semantics; it captures the inputs and projects the existing
Report into a small canonical artifact.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "northstar"
SCHEMA_VERSION = "decision-replay-bundle-v0"
ARTIFACT_SCHEMA_VERSION = "decision-artifact-v0"
SERIALIZATION = "JSON UTF-8, sorted keys, compact separators, newline terminated"


def _plain(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {key: _plain(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted((_plain(item) for item in value), key=lambda item: json.dumps(item, sort_keys=True))
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, float):
        return round(value, 10)
    return value


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(_plain(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _engine_build() -> dict[str, Any]:
    files = ["engine/rule_engine.py", "engine/curriculum.py", "engine/models.py", "engine/reasoning.py"]
    file_hashes = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in files}
    return {
        "implementation": "cre-laboratory-existing-engine",
        "git_commit": _git_commit(),
        "python": platform.python_version(),
        "engine_files": file_hashes,
        "artifact_schema": ARTIFACT_SCHEMA_VERSION,
    }


def _load_fixture():
    tests_root = str(ROOT / "tests")
    if tests_root not in sys.path:
        sys.path.insert(0, tests_root)
    from fixtures import northstar

    return northstar


@contextmanager
def _fixture_root(root: Path) -> Iterator[Any]:
    fixture = _load_fixture()
    previous = fixture.ROOT
    fixture.ROOT = root
    try:
        yield fixture
    finally:
        fixture.ROOT = previous


def _package_files(root: Path) -> dict[str, Any]:
    names = ("release.json", "courses.json", "degree_requirements.json")
    return {name: json.loads((root / name).read_text(encoding="utf-8")) for name in names}


def _source_index(package: dict[str, Any]) -> list[dict[str, Any]]:
    requirements = package["degree_requirements.json"]
    sources = [{
        "source_id": "NORTHSTAR-PACKAGE",
        "kind": "synthetic_release_package",
        "reference": package["release.json"].get("source", ""),
        "status": "unverified",
    }]
    programme = requirements.get("programmes", {}).get("systems_inquiry", {})
    for rule in programme.get("curriculum_rules", []):
        sources.append({
            "source_id": f"rule:{rule['id']}",
            "kind": "synthetic_rule",
            "reference": requirements.get("source", ""),
            "rule_id": rule["id"],
            "status": requirements.get("verification_status", "unverified"),
        })
    return sources


def _evidence_bundle(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "person": raw["person"],
        "subject_reference": raw["person"],
        "institution_id": "northstar",
        "release_id": "northstar-fixture-2027",
        "route": raw["route"],
        "domains": raw.get("domains", {}),
        "modules": raw.get("modules", []),
    }


def _evidence_index(inputs: Any) -> list[dict[str, Any]]:
    rows = []
    for result in inputs.student.results:
        rows.append({"evidence_id": f"result:{result.attempt_id}", "kind": "course_result", "code": result.code})
    for coverage in inputs.result_coverage:
        rows.append({"evidence_id": "coverage:academic_record", "kind": "coverage", "scope": list(coverage.course_codes)})
    for decision in inputs.recognition.decisions:
        rows.append({"evidence_id": f"recognition:{decision.recognition_id}", "kind": "recognition", "target": decision.target_course_code})
    return rows


def _outcome(item: Any) -> str:
    value = getattr(item, "outcome", None)
    if value:
        return value
    if getattr(item, "status", "") == "conflict":
        return "conflict"
    status = getattr(item, "status", "unverified")
    assessment_complete = getattr(item, "assessment_complete", None)
    if status not in {"verified", "discretionary"}:
        return "unresolved"
    if assessment_complete is False:
        return "unresolved"
    if getattr(item, "complete", False):
        return "satisfied"
    return "not_satisfied"


def _conclusion(item: Any, identity: str, kind: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    raw = _plain(item)
    used = list(getattr(item, "used_course_codes", ()) or ())
    evidence_ids = [row["evidence_id"] for row in evidence if row.get("code") in used]
    source_reference = getattr(item, "source_reference", "") or raw.get("source", {}).get("reference", "")
    return {
        "id": identity,
        "kind": kind,
        "outcome": _outcome(item),
        "assessment_complete": (
            getattr(item, "assessment_complete", None)
            if getattr(item, "assessment_complete", None) is not None
            else _outcome(item) not in {"unresolved", "conflict", "unsupported"}
        ),
        "status": getattr(item, "status", "unverified"),
        "confidence": getattr(item, "confidence", None),
        "current": getattr(item, "current", None),
        "required": getattr(item, "required", None),
        "applied_rule_ids": list(getattr(item, "applied_rules", ()) or ()),
        "depends_on": list(getattr(item, "depends_on", ()) or ()),
        "evidence_ids": evidence_ids,
        "used_course_codes": used,
        "missing_evidence": list(getattr(item, "unresolved_requirement_ids", ()) or ()),
        "assumptions": list(getattr(item, "assumptions", ()) or ()),
        "source_references": ([{"reference": source_reference}] if source_reference else []),
        "detail": getattr(item, "detail", ""),
    }


def _decision_artifact(release: Any, inputs: Any, report: Any, request: dict[str, Any], release_fp: str, evidence_fp: str) -> dict[str, Any]:
    evidence = _evidence_index(inputs)
    conclusions = [_conclusion(item, f"curriculum:{item.id}", "curriculum", evidence) for item in report.requirements]
    for attr, kind, identity in (
        ("qualification_completion", "completion", "qualification:systems_inquiry"),
        ("graduation_eligibility_assessment", "graduation", "graduation:systems_inquiry"),
        ("qualification_award_assessment", "award", "award:systems_inquiry"),
        ("distinction", "distinction", "distinction:systems_inquiry"),
    ):
        item = getattr(report, attr, None)
        if item is not None:
            conclusions.append(_conclusion(item, identity, kind, evidence))
    for item in report.progression_policy_assessments:
        conclusions.append(_conclusion(item, f"progression:{item.policy_id}", "progression", evidence))
    trace = {
        "nodes": [{"id": item["id"], "outcome": item["outcome"], "status": item["status"]} for item in conclusions],
        "edges": [{"from": dependency, "to": item["id"]} for item in conclusions for dependency in item["depends_on"]],
        "trace_origin": "Report fields and explicit dependency fields; no native complete graph was available",
    }
    artifact = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "evaluation_event_id": "pending",
        "institution_id": release.institution_id,
        "release_id": release.release_id,
        "release_fingerprint": release_fp,
        "engine_build": _engine_build(),
        "evaluation_request_fingerprint": fingerprint(request),
        "evidence_fingerprint": evidence_fp,
        "evidence_index": evidence,
        "conclusions": conclusions,
        "trace": trace,
        "warnings": list(report.warnings),
        "compatibility": {"report_scalar_fields": {"credits_completed": report.credits_completed, "graduation_status": report.graduation_status}},
    }
    artifact["evaluation_event_id"] = f"decision:{fingerprint(artifact)[:24]}"
    return artifact


def _write_json(path: Path, value: Any) -> None:
    path.write_bytes(canonical_bytes(value))


def create_bundle(output: str | Path, scenario: str = "clean") -> dict[str, Any]:
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)
    package = _package_files(FIXTURE_ROOT)
    raw = json.loads((FIXTURE_ROOT / "scenarios.json").read_text(encoding="utf-8"))[scenario]
    request = {"institution_id": "northstar", "release_id": package["release.json"]["release_id"], "subject_reference": raw["person"], "route": raw["route"], "scope": "full_fixture_report", "clock_policy": "not_semantic"}
    evidence = _evidence_bundle(raw)
    release_fp = fingerprint(package)
    evidence_fp = fingerprint(evidence)
    with _fixture_root(FIXTURE_ROOT) as fixture:
        release, _, inputs, report, _ = fixture.analyse(raw)
    artifact = _decision_artifact(release, inputs, report, request, release_fp, evidence_fp)
    _write_json(output_path / "evaluation-request.json", request)
    _write_json(output_path / "evidence-bundle.json", evidence)
    _write_json(output_path / "release-reference.json", {"mode": "embedded", "package": package, "fingerprint": release_fp})
    _write_json(output_path / "source-index.json", _source_index(package))
    _write_json(output_path / "decision-artifact.json", artifact)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "institution_id": request["institution_id"], "release_id": request["release_id"],
        "release_fingerprint": release_fp, "engine_build": artifact["engine_build"],
        "evaluator_schema_version": ARTIFACT_SCHEMA_VERSION, "evidence_fingerprint": evidence_fp,
        "evaluation_request_fingerprint": fingerprint(request), "decision_artifact_fingerprint": fingerprint(artifact),
        "created_at": "not-recorded-in-semantic-identity", "deterministic_fields": ["all fields except created_at"],
        "serialization": SERIALIZATION,
    }
    _write_json(output_path / "bundle-manifest.json", manifest)
    replay_report = replay_bundle(output_path)
    _write_json(output_path / "replay-report.json", replay_report)
    return manifest


def _compare(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    expected_copy = dict(expected)
    actual_copy = dict(actual)
    expected_copy.pop("engine_build", None)
    actual_copy.pop("engine_build", None)
    return {"decision_match": expected_copy == actual_copy, "trace_match": expected.get("trace") == actual.get("trace"), "semantic_fingerprint_expected": fingerprint(expected), "semantic_fingerprint_actual": fingerprint(actual)}


def replay_bundle(bundle: str | Path) -> dict[str, Any]:
    root = Path(bundle)
    try:
        manifest = json.loads((root / "bundle-manifest.json").read_text(encoding="utf-8"))
        request = json.loads((root / "evaluation-request.json").read_text(encoding="utf-8"))
        evidence = json.loads((root / "evidence-bundle.json").read_text(encoding="utf-8"))
        release_ref = json.loads((root / "release-reference.json").read_text(encoding="utf-8"))
        recorded = json.loads((root / "decision-artifact.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        return {"status": "INVALID_BUNDLE", "error": str(exc)}
    package = release_ref.get("package")
    if not isinstance(package, dict):
        return {"status": "UNSUPPORTED_REPLAY", "reason": "Only embedded release packages are supported in v0."}
    checks = {"evidence_fingerprint_match": fingerprint(evidence) == manifest.get("evidence_fingerprint"), "request_fingerprint_match": fingerprint(request) == manifest.get("evaluation_request_fingerprint"), "release_fingerprint_match": fingerprint(package) == manifest.get("release_fingerprint") == release_ref.get("fingerprint"), "recorded_artifact_fingerprint_match": fingerprint(recorded) == manifest.get("decision_artifact_fingerprint"), "engine_metadata_match": manifest.get("engine_build") == recorded.get("engine_build")}
    with tempfile.TemporaryDirectory(prefix="cre-replay-") as temp:
        package_root = Path(temp)
        for name, value in package.items():
            _write_json(package_root / name, value)
        try:
            with _fixture_root(package_root) as fixture:
                release, _, inputs, report, _ = fixture.analyse(evidence)
            actual = _decision_artifact(release, inputs, report, request, fingerprint(package), fingerprint(evidence))
        except (KeyError, TypeError, ValueError, OSError) as exc:
            return {"status": "UNSUPPORTED_REPLAY", "checks": checks, "error": str(exc)}
    comparison = _compare(recorded, actual)
    manifest_engine_match = manifest.get("engine_build") == recorded.get("engine_build")
    engine_match = recorded.get("engine_build") == actual.get("engine_build")
    if not all(checks.values()):
        status = "ENGINE_VERSION_MISMATCH" if not manifest_engine_match else "INPUT_OR_RELEASE_MISMATCH"
    elif not engine_match:
        status = "ENGINE_VERSION_MISMATCH" if comparison["decision_match"] else "DECISION_DIFFERS"
    elif not comparison["decision_match"]:
        status = "DECISION_DIFFERS"
    elif not comparison["trace_match"]:
        status = "TRACE_DIFFERS"
    else:
        status = "EXACT_MATCH"
    return {"status": status, "checks": checks, "engine_version_match": engine_match, "comparison": comparison, "recorded_event_id": recorded.get("evaluation_event_id"), "replayed_event_id": actual.get("evaluation_event_id")}