"""Checksum manifests for non-destructive curriculum-data releases.

The module never edits catalogue files. It only reads them, creates manifests,
and compares later states with a recorded baseline.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

MANIFEST_SCHEMA_VERSION = 1
DEFAULT_EXCLUDED_PARTS = frozenset(
    {".git", "__pycache__", ".pytest_cache", ".ruff_cache"}
)


class ManifestError(ValueError):
    """Raised when a manifest is malformed or cannot be written safely."""


@dataclass(frozen=True)
class FileRecord:
    path: str
    size: int
    sha256: str


@dataclass(frozen=True)
class VerificationResult:
    missing: tuple[str, ...]
    changed: tuple[str, ...]
    unexpected: tuple[str, ...]
    content_hash_matches: bool

    @property
    def ok(self) -> bool:
        return (
            not self.missing
            and not self.changed
            and not self.unexpected
            and self.content_hash_matches
        )


@dataclass(frozen=True)
class ManifestDiff:
    added: tuple[str, ...]
    removed: tuple[str, ...]
    changed: tuple[str, ...]
    unchanged_count: int

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed or self.changed)


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _normalise_relative_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _should_include(path: Path, root: Path, excluded_parts: frozenset[str]) -> bool:
    relative = path.relative_to(root)
    return path.is_file() and not any(part in excluded_parts for part in relative.parts)


def iter_files(
    root: Path,
    *,
    excluded_parts: frozenset[str] = DEFAULT_EXCLUDED_PARTS,
) -> Iterable[Path]:
    """Yield files in deterministic relative-path order."""
    root = root.resolve()
    if not root.exists() or not root.is_dir():
        raise ManifestError(f"Catalogue root is not a directory: {root}")
    files = [
        path for path in root.rglob("*") if _should_include(path, root, excluded_parts)
    ]
    yield from sorted(files, key=lambda item: _normalise_relative_path(item, root))


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _content_hash(records: list[dict[str, Any]]) -> str:
    canonical = json.dumps(
        records, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_manifest(
    root: str | Path,
    *,
    release_id: str,
    academic_year: int,
    created_by: str,
    source_status: str = "existing_verified_state",
) -> dict[str, Any]:
    """Create an in-memory immutable-content manifest for a catalogue directory."""
    catalogue_root = Path(root).resolve()
    if not release_id.strip():
        raise ManifestError("release_id is required")
    if academic_year < 2000 or academic_year > 2200:
        raise ManifestError("academic_year must be between 2000 and 2200")
    if not created_by.strip():
        raise ManifestError("created_by is required")

    files: list[dict[str, Any]] = []
    for path in iter_files(catalogue_root):
        files.append(
            {
                "path": _normalise_relative_path(path, catalogue_root),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )

    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "release_id": release_id,
        "academic_year": academic_year,
        "state": "baseline",
        "created_at": _utc_now(),
        "created_by": created_by,
        "source_status": source_status,
        "catalogue_root_name": catalogue_root.name,
        "file_count": len(files),
        "content_sha256": _content_hash(files),
        "files": files,
        "notes": [
            "This manifest records existing files without changing them.",
            "A matching manifest does not itself establish institutional authority.",
        ],
    }


def write_manifest(
    manifest: dict[str, Any],
    destination: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Atomically write a manifest, refusing replacement unless explicitly allowed."""
    destination_path = Path(destination).resolve()
    if destination_path.exists() and not overwrite:
        raise ManifestError(
            f"Refusing to overwrite existing manifest: {destination_path}. "
            "Use an explicit force/overwrite option only after review."
        )
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=destination_path.parent,
        prefix=f".{destination_path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(payload)
        temporary = Path(handle.name)
    temporary.replace(destination_path)
    return destination_path


def load_manifest(path: str | Path) -> dict[str, Any]:
    manifest_path = Path(path)
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"Could not read manifest {manifest_path}: {exc}") from exc
    _validate_manifest_structure(payload)
    return payload


def _validate_manifest_structure(manifest: dict[str, Any]) -> None:
    required = {
        "schema_version",
        "release_id",
        "academic_year",
        "content_sha256",
        "file_count",
        "files",
    }
    missing = sorted(required - manifest.keys())
    if missing:
        raise ManifestError(f"Manifest is missing required keys: {', '.join(missing)}")
    if manifest["schema_version"] != MANIFEST_SCHEMA_VERSION:
        raise ManifestError(
            f"Unsupported manifest schema version: {manifest['schema_version']}"
        )
    if not isinstance(manifest["files"], list):
        raise ManifestError("Manifest files must be a list")
    seen: set[str] = set()
    for index, record in enumerate(manifest["files"]):
        if not isinstance(record, dict):
            raise ManifestError(f"File record {index} is not an object")
        if set(record) != {"path", "size", "sha256"}:
            raise ManifestError(f"File record {index} has an invalid shape")
        path = record["path"]
        if not isinstance(path, str) or not path or path.startswith(("/", "../")):
            raise ManifestError(f"File record {index} has an unsafe path")
        if path in seen:
            raise ManifestError(f"Duplicate manifest path: {path}")
        seen.add(path)
        if not isinstance(record["size"], int) or record["size"] < 0:
            raise ManifestError(f"Invalid size for {path}")
        digest = record["sha256"]
        if not isinstance(digest, str) or len(digest) != 64:
            raise ManifestError(f"Invalid SHA-256 digest for {path}")
    if manifest["file_count"] != len(manifest["files"]):
        raise ManifestError("Manifest file_count does not match files list")
    if manifest["content_sha256"] != _content_hash(manifest["files"]):
        raise ManifestError("Manifest content_sha256 does not match its file records")


def verify_manifest(root: str | Path, manifest: dict[str, Any]) -> VerificationResult:
    """Compare current files with a baseline without changing either side."""
    _validate_manifest_structure(manifest)
    catalogue_root = Path(root).resolve()
    expected = {record["path"]: record for record in manifest["files"]}
    current: dict[str, dict[str, Any]] = {}
    for path in iter_files(catalogue_root):
        relative = _normalise_relative_path(path, catalogue_root)
        current[relative] = {
            "path": relative,
            "size": path.stat().st_size,
            "sha256": sha256_file(path),
        }

    expected_paths = set(expected)
    current_paths = set(current)
    missing = tuple(sorted(expected_paths - current_paths))
    unexpected = tuple(sorted(current_paths - expected_paths))
    changed = tuple(
        sorted(
            path
            for path in expected_paths & current_paths
            if expected[path]["size"] != current[path]["size"]
            or expected[path]["sha256"] != current[path]["sha256"]
        )
    )
    expected_records_in_current_order = [
        current[path] for path in sorted(expected_paths & current_paths)
    ]
    content_hash_matches = (
        not missing
        and not changed
        and len(expected_records_in_current_order) == len(expected)
        and _content_hash(expected_records_in_current_order)
        == manifest["content_sha256"]
    )
    return VerificationResult(
        missing=missing,
        changed=changed,
        unexpected=unexpected,
        content_hash_matches=content_hash_matches,
    )


def compare_manifests(old: dict[str, Any], new: dict[str, Any]) -> ManifestDiff:
    _validate_manifest_structure(old)
    _validate_manifest_structure(new)
    old_records = {record["path"]: record for record in old["files"]}
    new_records = {record["path"]: record for record in new["files"]}
    old_paths = set(old_records)
    new_paths = set(new_records)
    changed = tuple(
        sorted(
            path
            for path in old_paths & new_paths
            if old_records[path]["sha256"] != new_records[path]["sha256"]
            or old_records[path]["size"] != new_records[path]["size"]
        )
    )
    unchanged_count = len(old_paths & new_paths) - len(changed)
    return ManifestDiff(
        added=tuple(sorted(new_paths - old_paths)),
        removed=tuple(sorted(old_paths - new_paths)),
        changed=changed,
        unchanged_count=unchanged_count,
    )
