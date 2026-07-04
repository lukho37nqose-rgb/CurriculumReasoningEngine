from __future__ import annotations

from pathlib import Path

import pytest

from catalogue_governance.integrity import (
    ManifestError,
    build_manifest,
    compare_manifests,
    verify_manifest,
    write_manifest,
)


def _make_data(root: Path) -> Path:
    data = root / "data"
    (data / "uct_humanities").mkdir(parents=True)
    (data / "uct_humanities" / "courses.json").write_text(
        '{"A": 1}\n', encoding="utf-8"
    )
    (data / "uct_humanities" / "degree_requirements.json").write_text(
        '{"B": 2}\n', encoding="utf-8"
    )
    return data


def test_manifest_is_deterministic_except_timestamp(tmp_path: Path) -> None:
    data = _make_data(tmp_path)
    first = build_manifest(
        data,
        release_id="baseline",
        academic_year=2026,
        created_by="tester",
    )
    second = build_manifest(
        data,
        release_id="baseline",
        academic_year=2026,
        created_by="tester",
    )
    assert first["files"] == second["files"]
    assert first["content_sha256"] == second["content_sha256"]


def test_verify_detects_changed_missing_and_unexpected(tmp_path: Path) -> None:
    data = _make_data(tmp_path)
    manifest = build_manifest(
        data,
        release_id="baseline",
        academic_year=2026,
        created_by="tester",
    )
    (data / "uct_humanities" / "courses.json").write_text(
        '{"A": 99}\n', encoding="utf-8"
    )
    (data / "uct_humanities" / "degree_requirements.json").unlink()
    (data / "uct_humanities" / "new_file.json").write_text("{}\n", encoding="utf-8")

    result = verify_manifest(data, manifest)

    assert not result.ok
    assert result.changed == ("uct_humanities/courses.json",)
    assert result.missing == ("uct_humanities/degree_requirements.json",)
    assert result.unexpected == ("uct_humanities/new_file.json",)


def test_manifest_writer_refuses_silent_overwrite(tmp_path: Path) -> None:
    data = _make_data(tmp_path)
    manifest = build_manifest(
        data,
        release_id="baseline",
        academic_year=2026,
        created_by="tester",
    )
    destination = tmp_path / "manifest.json"
    write_manifest(manifest, destination)
    with pytest.raises(ManifestError):
        write_manifest(manifest, destination)


def test_manifest_diff_is_explicit(tmp_path: Path) -> None:
    data = _make_data(tmp_path)
    old = build_manifest(
        data,
        release_id="old",
        academic_year=2026,
        created_by="tester",
    )
    (data / "uct_humanities" / "courses.json").write_text(
        '{"A": 3}\n', encoding="utf-8"
    )
    (data / "uct_humanities" / "added.json").write_text("{}\n", encoding="utf-8")
    new = build_manifest(
        data,
        release_id="new",
        academic_year=2027,
        created_by="tester",
    )

    diff = compare_manifests(old, new)

    assert diff.changed == ("uct_humanities/courses.json",)
    assert diff.added == ("uct_humanities/added.json",)
    assert diff.removed == ()
    assert diff.unchanged_count == 1


def test_verify_rejects_unexpected_file_even_when_baseline_files_match(
    tmp_path: Path,
) -> None:
    data = _make_data(tmp_path)
    manifest = build_manifest(
        data,
        release_id="baseline",
        academic_year=2026,
        created_by="tester",
    )
    (data / "uct_humanities" / "unreviewed.json").write_text("{}\n", encoding="utf-8")

    result = verify_manifest(data, manifest)

    assert not result.ok
    assert result.missing == ()
    assert result.changed == ()
    assert result.unexpected == ("uct_humanities/unreviewed.json",)
