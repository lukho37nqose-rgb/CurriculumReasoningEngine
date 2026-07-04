#!/usr/bin/env python3
"""CLI for CurriculumAdvisor catalogue integrity and operational-data checks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from catalogue_governance.integrity import (  # noqa: E402
    ManifestError,
    build_manifest,
    compare_manifests,
    load_manifest,
    verify_manifest,
    write_manifest,
)
from catalogue_governance.operational import (  # noqa: E402
    OperationalDataError,
    validate_offerings_payload,
)


def _snapshot(args: argparse.Namespace) -> int:
    manifest = build_manifest(
        args.data_root,
        release_id=args.release_id,
        academic_year=args.academic_year,
        created_by=args.created_by,
        source_status=args.source_status,
    )
    destination = write_manifest(manifest, args.output, overwrite=args.force)
    print(f"Wrote baseline manifest: {destination}")
    print(f"Files recorded: {manifest['file_count']}")
    print(f"Content SHA-256: {manifest['content_sha256']}")
    return 0


def _verify(args: argparse.Namespace) -> int:
    manifest = load_manifest(args.manifest)
    result = verify_manifest(args.data_root, manifest)
    print(
        json.dumps(
            {
                "ok": result.ok,
                "content_hash_matches": result.content_hash_matches,
                "missing": list(result.missing),
                "changed": list(result.changed),
                "unexpected": list(result.unexpected),
            },
            indent=2,
        )
    )
    return 0 if result.ok else 2


def _diff(args: argparse.Namespace) -> int:
    old = load_manifest(args.old_manifest)
    new = load_manifest(args.new_manifest)
    result = compare_manifests(old, new)
    print(
        json.dumps(
            {
                "has_changes": result.has_changes,
                "added": list(result.added),
                "removed": list(result.removed),
                "changed": list(result.changed),
                "unchanged_count": result.unchanged_count,
            },
            indent=2,
        )
    )
    return 0


def _validate_offerings(args: argparse.Namespace) -> int:
    payload = json.loads(Path(args.path).read_text(encoding="utf-8"))
    warnings = validate_offerings_payload(payload)
    print(json.dumps({"valid": True, "warnings": warnings}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Non-destructive integrity and timetable validation for CurriculumAdvisor."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    snapshot = subparsers.add_parser(
        "snapshot", help="Record checksums for the existing data directory"
    )
    snapshot.add_argument("--data-root", default="data")
    snapshot.add_argument("--output", required=True)
    snapshot.add_argument("--release-id", required=True)
    snapshot.add_argument("--academic-year", required=True, type=int)
    snapshot.add_argument("--created-by", required=True)
    snapshot.add_argument("--source-status", default="existing_verified_state")
    snapshot.add_argument(
        "--force",
        action="store_true",
        help="Explicitly replace the destination manifest",
    )
    snapshot.set_defaults(func=_snapshot)

    verify = subparsers.add_parser(
        "verify", help="Verify current data against a recorded manifest"
    )
    verify.add_argument("--data-root", default="data")
    verify.add_argument("--manifest", required=True)
    verify.set_defaults(func=_verify)

    diff = subparsers.add_parser("diff", help="Compare two manifests")
    diff.add_argument("--old-manifest", required=True)
    diff.add_argument("--new-manifest", required=True)
    diff.set_defaults(func=_diff)

    offerings = subparsers.add_parser(
        "validate-offerings",
        help="Validate term-specific offering/timetable data without touching curriculum rules",
    )
    offerings.add_argument("path")
    offerings.set_defaults(func=_validate_offerings)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except (ManifestError, OperationalDataError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
