import pytest

from catalogue_governance.corrections import (
    CorrectionError,
    GovernedCorrection,
    apply_corrections,
    compare_corrected_candidate,
    correction_fingerprint,
)
from catalogue_governance.reproducibility import BuildDeclaration, validate_release


def _correction(**kwargs):
    values = dict(
        correction_id="C-1", institution_id="northstar", release_id="2027",
        package_id="core", target_key="policy_id", target_id="P-1",
        field_path="condition.threshold", operation="replace_value",
        expected_before=60, replacement=65, source_reference="fixture p.1",
        verification_status="unverified", authority="fixture authority",
    )
    values.update(kwargs)
    return GovernedCorrection(**values)


def test_correction_applies_to_copy_and_preserves_baseline():
    baseline = {"policies": [{"policy_id": "P-1", "condition": {"threshold": 60}}]}
    result = apply_corrections(baseline, (_correction(),))
    assert baseline["policies"][0]["condition"]["threshold"] == 60
    assert result.candidate["policies"][0]["condition"]["threshold"] == 65
    assert result.applied_ids == ("C-1",)


def test_stale_target_fails_closed():
    baseline = {"policies": [{"policy_id": "P-1", "condition": {"threshold": 70}}]}
    with pytest.raises(CorrectionError, match="PRECONDITION"):
        apply_corrections(baseline, (_correction(),))


def test_missing_and_conflicting_targets_fail_closed():
    baseline = {"policies": [{"policy_id": "P-1", "condition": {"threshold": 60}}]}
    with pytest.raises(CorrectionError, match="MISSING_OR_AMBIGUOUS"):
        apply_corrections(baseline, (_correction(target_id="P-9"),))
    with pytest.raises(CorrectionError, match="CONFLICT"):
        apply_corrections(baseline, (_correction(), _correction(correction_id="C-2", replacement=70)))


def test_correction_fingerprint_is_deterministic_and_provenance_sensitive():
    first = correction_fingerprint((_correction(),))
    second = correction_fingerprint((_correction(),))
    changed = correction_fingerprint((_correction(source_reference="fixture p.2"),))
    assert first == second
    assert first != changed


def test_validation_report_attaches_correction_status():
    declaration = BuildDeclaration("northstar", "2027", "core", "generated", builder_entrypoint="build")
    report = validate_release(
        declaration,
        package={"policies": [{"policy_id": "P-1", "condition": {"threshold": 60}}]},
        corrections=(_correction(),),
    )
    assert report.correction_status == "DECLARED_CORRECTIONS"
    assert report.corrections_applied == ("C-1",)
    assert report.correction_set_fingerprint


def test_corrected_candidate_explains_expected_governed_output():
    baseline = {"policies": [{"policy_id": "P-1", "condition": {"threshold": 60}}]}
    governed = {"policies": [{"policy_id": "P-1", "condition": {"threshold": 65}}]}
    comparison = compare_corrected_candidate(baseline, governed, (_correction(),))
    assert comparison.status == "MATCH_AFTER_CORRECTIONS"
