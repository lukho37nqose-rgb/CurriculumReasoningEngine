"""Deterministic package fingerprints, semantic diffs, and rebuild checks.

This module is deliberately independent of institutional reasoning. It compares
governed JSON/data and never overwrites package files.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ReproducibilityError(ValueError):
    """Raised when a governance comparison cannot be performed safely."""


# These fields describe provenance or presentation rather than policy meaning.
_PROVENANCE_KEYS = frozenset({
    "institution_sources", "requirement_source_relationships",
    "source", "source_reference", "source_status", "verification_status",
    "authority", "created_at", "created_by", "notes", "label", "description",
})


@dataclass(frozen=True)
class PackageFingerprints:
    full: str
    semantic: str
    provenance: str


@dataclass(frozen=True)
class SemanticChange:
    path: str
    category: str
    before: Any
    after: Any


@dataclass(frozen=True)
class PackageDiff:
    changes: tuple[SemanticChange, ...]

    @property
    def semantic_changes(self) -> tuple[SemanticChange, ...]:
        return tuple(item for item in self.changes if item.category == "semantic")

    @property
    def governance_changes(self) -> tuple[SemanticChange, ...]:
        return tuple(item for item in self.changes if item.category == "governance")

    @property
    def provenance_changes(self) -> tuple[SemanticChange, ...]:
        return tuple(item for item in self.changes if item.category == "provenance")

    @property
    def metadata_changes(self) -> tuple[SemanticChange, ...]:
        return tuple(item for item in self.changes if item.category == "metadata")


@dataclass(frozen=True)
class RebuildResult:
    status: str
    differences: tuple[str, ...] = ()


@dataclass(frozen=True)
class DeclaredInput:
    identity: str
    role: str
    available: bool
    required_for_rebuild: bool = True
    content_fingerprint: str | None = None
    source_status: str = "unverified"


@dataclass(frozen=True)
class BuildDeclaration:
    institution_id: str
    release_id: str
    package_id: str
    production_mode: str
    output_paths: tuple[str, ...] = ()
    inputs: tuple[DeclaredInput, ...] = ()
    builder_entrypoint: str | None = None
    builder_files: tuple[str, ...] = ()
    schema_version: int = 1
    source_status: str = "unverified"
    mixed_lineage_incomplete: bool = False


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    severity: str = "warning"


@dataclass(frozen=True)
class ReleaseValidationReport:
    institution_id: str
    release_id: str
    package_id: str
    production_mode: str
    fingerprints: PackageFingerprints | None
    input_fingerprints: tuple[tuple[str, str], ...]
    builder_fingerprint: str | None
    rebuild_status: str
    manifest_ok: bool | None
    issues: tuple[ValidationIssue, ...]
    claims: tuple[str, ...]
    correction_status: str = "NOT_APPLICABLE"
    correction_set_fingerprint: str | None = None
    corrections_applied: tuple[str, ...] = ()
    unexplained_drift: bool = False


PRODUCTION_MODES = frozenset({"generated", "manual", "mixed", "unknown"})
REBUILD_STATUSES = frozenset({
    "MATCH", "DRIFT", "UNREPRODUCIBLE", "NOT_APPLICABLE",
    "BUILDER_UNDECLARED", "REQUIRED_INPUTS_UNAVAILABLE", "EXECUTION_FAILURE",
})


def fingerprint_file(path: str | Path) -> str:
    """Fingerprint file content only; paths and timestamps are excluded."""
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError as exc:
        raise ReproducibilityError(f"Could not fingerprint {path}: {exc}") from exc


def fingerprint_builder_files(paths: tuple[str, ...] | list[str]) -> str | None:
    """Fingerprint declared builder files in declared order."""
    if not paths:
        return None
    records = []
    for path in paths:
        records.append({"declared_path": Path(path).as_posix(), "sha256": fingerprint_file(path)})
    return _digest(records)


def _validate_declaration(declaration: BuildDeclaration) -> None:
    if declaration.production_mode not in PRODUCTION_MODES:
        raise ReproducibilityError(f"Unknown production mode: {declaration.production_mode}")
    if declaration.schema_version != 1:
        raise ReproducibilityError(f"Unsupported build declaration schema: {declaration.schema_version}")
    if declaration.production_mode == "generated" and not declaration.builder_entrypoint:
        raise ReproducibilityError("Generated declarations require a builder entrypoint")
    if declaration.production_mode == "mixed" and not declaration.inputs:
        raise ReproducibilityError("Mixed declarations require explicit lineage inputs")


def _input_fingerprints(declaration: BuildDeclaration) -> tuple[tuple[str, str], ...]:
    values = []
    for item in declaration.inputs:
        if item.available and item.content_fingerprint:
            values.append((item.identity, item.content_fingerprint))
    return tuple(values)


def validate_release(
    declaration: BuildDeclaration,
    *,
    package: Any | None = None,
    expected_package: str | Path | None = None,
    regenerated_package: str | Path | None = None,
    manifest_ok: bool | None = None,
    corrections: tuple[Any, ...] = (),
    governed_package: Any | None = None,
) -> ReleaseValidationReport:
    """Build a conservative technical report; never implies institutional approval."""
    _validate_declaration(declaration)
    issues: list[ValidationIssue] = []
    missing = [item.identity for item in declaration.inputs if item.required_for_rebuild and not item.available]
    if missing:
        issues.append(ValidationIssue("INPUT_MISSING", f"Required inputs unavailable: {', '.join(missing)}"))
    if declaration.source_status != "existing_verified_state":
        issues.append(ValidationIssue("SOURCE_STATUS_UNVERIFIED", declaration.source_status))
    if declaration.mixed_lineage_incomplete:
        issues.append(ValidationIssue("MIXED_LINEAGE_UNDECLARED", "Mixed lineage is not complete at field level."))
    builder_fingerprint = fingerprint_builder_files(declaration.builder_files) if declaration.builder_files else None
    if declaration.production_mode == "generated" and not declaration.builder_files:
        issues.append(ValidationIssue("BUILDER_UNDECLARED", "Builder files were not declared."))
    correction_status = "NOT_APPLICABLE"
    correction_set_fingerprint = None
    corrections_applied: tuple[str, ...] = ()
    unexplained_drift = False
    if corrections:
        from .corrections import apply_corrections, correction_fingerprint

        correction_set_fingerprint = correction_fingerprint(corrections)
        correction_status = "DECLARED_CORRECTIONS"
        if package is None:
            issues.append(ValidationIssue("CORRECTION_BASELINE_MISSING", "Corrections require a generated baseline." , "error"))
        else:
            try:
                application = apply_corrections(package, corrections)
                corrections_applied = application.applied_ids
                if governed_package is not None:
                    from .corrections import compare_corrected_candidate

                    correction_status = compare_corrected_candidate(package, governed_package, corrections).status
                    if correction_status == "UNDECLARED_OUTPUT_DRIFT":
                        unexplained_drift = True
                        issues.append(ValidationIssue("UNDECLARED_OUTPUT_DRIFT", "Corrected candidate differs from governed output.", "error"))
            except ValueError as exc:
                correction_status = "CORRECTION_FAILURE"
                issues.append(ValidationIssue("CORRECTION_APPLICATION_FAILED", str(exc), "error"))
    if expected_package and regenerated_package:
        rebuild = verify_rebuild(expected_package, regenerated_package)
        rebuild_status = rebuild.status
        if rebuild_status == "DRIFT":
            issues.append(ValidationIssue("OUTPUT_DRIFT", "Regenerated output differs from governed output.", "error"))
    elif declaration.production_mode == "manual":
        rebuild_status = "NOT_APPLICABLE"
    elif not declaration.builder_entrypoint:
        rebuild_status = "BUILDER_UNDECLARED"
    elif missing:
        rebuild_status = "REQUIRED_INPUTS_UNAVAILABLE"
    else:
        rebuild_status = "UNREPRODUCIBLE"
    package_fingerprints = fingerprints(package) if package is not None else None
    claims = ["technical_validation_only", "institutional_approval_not_assessed"]
    if manifest_ok:
        claims.append("byte_integrity_verified")
    if package_fingerprints:
        claims.append("semantic_fingerprint_computed")
    if rebuild_status == "MATCH":
        claims.append("deterministic_rebuild_verified")
    return ReleaseValidationReport(
        institution_id=declaration.institution_id,
        release_id=declaration.release_id,
        package_id=declaration.package_id,
        production_mode=declaration.production_mode,
        fingerprints=package_fingerprints,
        input_fingerprints=_input_fingerprints(declaration),
        builder_fingerprint=builder_fingerprint,
        rebuild_status=rebuild_status,
        manifest_ok=manifest_ok,
        issues=tuple(issues),
        claims=tuple(claims),
        correction_status=correction_status,
        correction_set_fingerprint=correction_set_fingerprint,
        corrections_applied=corrections_applied,
        unexplained_drift=unexplained_drift,
    )


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _without_provenance(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_provenance(item)
            for key, item in value.items()
            if key not in _PROVENANCE_KEYS
        }
    if isinstance(value, list):
        return [_without_provenance(item) for item in value]
    return value


def _only_provenance(value: Any) -> Any:
    if isinstance(value, dict):
        if "institution_sources" in value or "requirement_source_relationships" in value:
            return {**{key: value[key] for key in ("institution_sources", "requirement_source_relationships") if key in value},
                    "other": _only_provenance({key: item for key, item in value.items() if key not in {"institution_sources", "requirement_source_relationships"}})}
        return {
            key: _only_provenance(item)
            for key, item in value.items()
            if key in _PROVENANCE_KEYS
        }
    if isinstance(value, list):
        return [_only_provenance(item) for item in value]
    return value


def fingerprints(payload: Any) -> PackageFingerprints:
    """Return full, semantic, and provenance fingerprints for JSON-compatible data."""
    return PackageFingerprints(
        full=_digest(payload),
        semantic=_digest(_without_provenance(payload)),
        provenance=_digest(_only_provenance(payload)),
    )


def _category(path: str, before: Any, after: Any) -> str:
    key = path.rsplit(".", 1)[-1].split("[", 1)[0]
    if key in {"verification_status", "authority"}:
        return "governance"
    if key in {"source", "source_reference", "source_status", "created_at", "created_by", "notes"}:
        return "provenance"
    if key in {"label", "description"}:
        return "metadata"
    return "semantic"


def _diff(before: Any, after: Any, path: str, output: list[SemanticChange]) -> None:
    if any(key in path.split(".") for key in ("institution_sources", "requirement_source_relationships")):
        if before != after:
            output.append(SemanticChange(path, "provenance", before, after))
        return
    if type(before) is not type(after):
        output.append(SemanticChange(path or "$", "structural", before, after))
        return
    if isinstance(before, dict):
        for key in sorted(set(before) | set(after)):
            child = f"{path}.{key}" if path else key
            if key not in before or key not in after:
                category = "provenance" if key in {"institution_sources", "requirement_source_relationships"} else "structural"
                output.append(SemanticChange(child, category, before.get(key), after.get(key)))
            else:
                _diff(before[key], after[key], child, output)
        return
    if isinstance(before, list):
        if before != after:
            output.append(SemanticChange(path or "$", "semantic", before, after))
        return
    if before != after:
        output.append(SemanticChange(path or "$", _category(path, before, after), before, after))


def semantic_diff(before: Any, after: Any) -> PackageDiff:
    """Compare JSON while preserving list order and stable object paths."""
    changes: list[SemanticChange] = []
    _diff(before, after, "", changes)
    return PackageDiff(tuple(changes))


def load_json(path: str | Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReproducibilityError(f"Could not read JSON package {path}: {exc}") from exc


def compare_json_files(before: str | Path, after: str | Path) -> PackageDiff:
    return semantic_diff(load_json(before), load_json(after))


def verify_rebuild(expected: str | Path, regenerated: str | Path) -> RebuildResult:
    """Compare a generated package without copying or overwriting either file."""
    expected_path = Path(expected)
    regenerated_path = Path(regenerated)
    if not expected_path.exists() or not regenerated_path.exists():
        return RebuildResult("UNREPRODUCIBLE", ("missing expected or regenerated package",))
    diff = compare_json_files(expected_path, regenerated_path)
    if not diff.changes:
        return RebuildResult("MATCH")
    return RebuildResult("DRIFT", tuple(item.path for item in diff.changes))
