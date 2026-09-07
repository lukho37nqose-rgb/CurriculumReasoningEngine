from pathlib import Path

import pytest

from catalogue_governance.reproducibility import (
    BuildDeclaration,
    DeclaredInput,
    ReproducibilityError,
    fingerprint_builder_files,
    fingerprint_file,
    validate_release,
)


def test_declared_input_and_builder_fingerprints_are_content_based(tmp_path: Path):
    source = tmp_path / "source.json"
    builder = tmp_path / "builder.py"
    source.write_text('{"threshold": 60}\n', encoding="utf-8")
    builder.write_text("print('build')\n", encoding="utf-8")
    declaration = BuildDeclaration(
        "northstar", "2027", "core", "generated",
        inputs=(DeclaredInput("source.json", "structured_source_data", True, content_fingerprint=fingerprint_file(source)),),
        builder_entrypoint="builder.py", builder_files=(str(builder),),
    )
    report = validate_release(declaration, package={"threshold": 60})
    assert report.input_fingerprints[0][1] == fingerprint_file(source)
    assert report.builder_fingerprint == fingerprint_builder_files((str(builder),))
    assert "institutional_approval_not_assessed" in report.claims


def test_missing_required_input_prevents_complete_reproducibility():
    declaration = BuildDeclaration(
        "northstar", "2027", "core", "generated",
        inputs=(DeclaredInput("missing.pdf", "authoritative_source_archive", False),),
        builder_entrypoint="builder.py", builder_files=(),
    )
    report = validate_release(declaration)
    assert report.rebuild_status == "REQUIRED_INPUTS_UNAVAILABLE"
    assert any(item.code == "INPUT_MISSING" for item in report.issues)


def test_manual_package_is_not_called_unreproducible():
    declaration = BuildDeclaration("northstar", "2027", "manual", "manual")
    report = validate_release(declaration, package={"rules": []})
    assert report.rebuild_status == "NOT_APPLICABLE"
    assert "semantic_fingerprint_computed" in report.claims


def test_unknown_production_mode_and_unsupported_schema_are_rejected():
    with pytest.raises(ReproducibilityError):
        validate_release(BuildDeclaration("n", "r", "p", "bogus", builder_entrypoint="b"))
    with pytest.raises(ReproducibilityError):
        validate_release(BuildDeclaration("n", "r", "p", "unknown", schema_version=2))


def test_source_status_does_not_become_verified_after_validation():
    declaration = BuildDeclaration(
        "uct", "2026", "law", "unknown",
        source_status="checksum_mismatch_unverified_source_archive",
    )
    report = validate_release(declaration, package={"rules": []}, manifest_ok=True)
    assert any(item.code == "SOURCE_STATUS_UNVERIFIED" for item in report.issues)
    assert "institutional_approval_not_assessed" in report.claims
