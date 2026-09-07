"""Fail-closed, deterministic governed corrections for JSON package baselines."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from .reproducibility import _digest, fingerprints


class CorrectionError(ValueError):
    """Raised when a declared correction cannot be safely applied."""


@dataclass(frozen=True)
class GovernedCorrection:
    correction_id: str
    institution_id: str
    release_id: str
    package_id: str
    target_key: str
    target_id: str
    field_path: str
    operation: str
    expected_before: Any
    replacement: Any
    source_reference: str
    verification_status: str
    authority: str
    rationale: str = ""
    schema_version: int = 1


@dataclass(frozen=True)
class CorrectionApplication:
    candidate: Any
    applied_ids: tuple[str, ...]
    fingerprint: str


@dataclass(frozen=True)
class CorrectionComparison:
    status: str
    application: CorrectionApplication


def correction_fingerprint(corrections: tuple[GovernedCorrection, ...]) -> str:
    payload = [
        {
            "correction_id": item.correction_id,
            "institution_id": item.institution_id,
            "release_id": item.release_id,
            "package_id": item.package_id,
            "target_key": item.target_key,
            "target_id": item.target_id,
            "field_path": item.field_path,
            "operation": item.operation,
            "expected_before": item.expected_before,
            "replacement": item.replacement,
            "source_reference": item.source_reference,
            "verification_status": item.verification_status,
            "authority": item.authority,
        }
        for item in corrections
    ]
    return _digest(payload)


def _find_targets(node: Any, key: str, value: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(node, dict):
        if node.get(key) == value:
            found.append(node)
        for child in node.values():
            found.extend(_find_targets(child, key, value))
    elif isinstance(node, list):
        for child in node:
            found.extend(_find_targets(child, key, value))
    return found


def _walk_parent(target: dict[str, Any], parts: list[str]) -> tuple[dict[str, Any], str]:
    if not parts:
        raise CorrectionError("Correction field_path must identify a field")
    parent: Any = target
    for part in parts[:-1]:
        if not isinstance(parent, dict) or part not in parent:
            raise CorrectionError(f"Correction path is missing: {'.'.join(parts)}")
        parent = parent[part]
    if not isinstance(parent, dict):
        raise CorrectionError("Correction path parent is not an object")
    return parent, parts[-1]


def apply_corrections(
    baseline: Any,
    corrections: tuple[GovernedCorrection, ...],
) -> CorrectionApplication:
    """Apply corrections to a deep copy; baseline is never mutated."""
    candidate = copy.deepcopy(baseline)
    seen_ids: set[str] = set()
    seen_targets: dict[tuple[str, str], GovernedCorrection] = {}
    applied: list[str] = []
    for correction in corrections:
        if correction.schema_version != 1:
            raise CorrectionError(f"Unsupported correction schema: {correction.schema_version}")
        if not correction.source_reference or not correction.authority:
            raise CorrectionError(f"Correction {correction.correction_id} lacks provenance")
        if correction.correction_id in seen_ids:
            raise CorrectionError(f"Duplicate correction ID: {correction.correction_id}")
        seen_ids.add(correction.correction_id)
        target_identity = (correction.target_key, correction.target_id)
        prior = seen_targets.get(target_identity)
        if prior and prior.field_path == correction.field_path:
            raise CorrectionError(f"CORRECTION_CONFLICT: {correction.correction_id}")
        seen_targets[target_identity] = correction
        targets = _find_targets(candidate, correction.target_key, correction.target_id)
        if len(targets) != 1:
            raise CorrectionError(f"CORRECTION_TARGET_MISSING_OR_AMBIGUOUS: {correction.correction_id}")
        target = targets[0]
        parts = correction.field_path.split(".")
        parent, field = _walk_parent(target, parts)
        present = field in parent
        before = parent.get(field)
        if correction.operation == "replace_value":
            if not present or before != correction.expected_before:
                raise CorrectionError(f"CORRECTION_PRECONDITION_FAILED: {correction.correction_id}")
            parent[field] = copy.deepcopy(correction.replacement)
        elif correction.operation == "add_field":
            if present or correction.expected_before is not None:
                raise CorrectionError(f"CORRECTION_PRECONDITION_FAILED: {correction.correction_id}")
            parent[field] = copy.deepcopy(correction.replacement)
        elif correction.operation == "remove_field":
            if not present or before != correction.expected_before:
                raise CorrectionError(f"CORRECTION_PRECONDITION_FAILED: {correction.correction_id}")
            del parent[field]
        else:
            raise CorrectionError(f"Unsupported correction operation: {correction.operation}")
        applied.append(correction.correction_id)
    return CorrectionApplication(candidate, tuple(applied), correction_fingerprint(corrections))


def compare_corrected_candidate(
    baseline: Any,
    governed: Any,
    corrections: tuple[GovernedCorrection, ...],
) -> CorrectionComparison:
    application = apply_corrections(baseline, corrections)
    status = "MATCH_AFTER_CORRECTIONS" if fingerprints(application.candidate).semantic == fingerprints(governed).semantic else "UNDECLARED_OUTPUT_DRIFT"
    # Governed relationship drift must not disappear behind semantic equivalence.
    if isinstance(governed, dict) and isinstance(application.candidate, dict):
        for key in ("institution_sources", "requirement_source_relationships"):
            if application.candidate.get(key) != governed.get(key):
                status = "UNDECLARED_OUTPUT_DRIFT"
    return CorrectionComparison(status, application)
