"""Read-only governance status for the public and draft administration views."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from catalogue_governance.integrity import load_manifest, verify_manifest


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def governance_status(project_root: Path) -> dict[str, Any]:
    data_root = project_root / "data"
    releases_root = project_root / "governance" / "releases"
    manifests = sorted(releases_root.glob("*.manifest.json"))
    if not manifests:
        return {
            "integrity": "unavailable",
            "message": "No catalogue baseline manifest is installed.",
            "release": None,
        }

    manifest_path = manifests[-1]
    manifest = load_manifest(manifest_path)
    verification = verify_manifest(data_root, manifest)
    source_verification_path = releases_root / "source_archive_verification.json"
    source_verification = (
        _read_json(source_verification_path) if source_verification_path.exists() else None
    )
    return {
        "integrity": "verified" if verification.ok else "attention_required",
        "message": (
            "Every catalogue file matches the recorded baseline."
            if verification.ok
            else "The catalogue directory differs from its recorded baseline."
        ),
        "release": {
            "release_id": manifest.get("release_id"),
            "academic_year": manifest.get("academic_year"),
            "state": manifest.get("state"),
            "created_at": manifest.get("created_at"),
            "created_by": manifest.get("created_by"),
            "file_count": manifest.get("file_count"),
            "content_sha256": manifest.get("content_sha256"),
        },
        "verification": {
            "missing": list(verification.missing),
            "changed": list(verification.changed),
            "unexpected": list(verification.unexpected),
            "content_hash_matches": verification.content_hash_matches,
        },
        "source_archive": source_verification,
        "workflow": [
            "draft",
            "submitted_for_review",
            "validated",
            "approved",
            "published",
            "superseded",
        ],
        "publication_enabled": False,
        "publication_note": (
            "This redesign intentionally exposes a read-only governance desk. "
            "Authentication and institutional authority must exist before publication controls are enabled."
        ),
    }
