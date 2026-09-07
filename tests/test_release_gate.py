from pathlib import Path

from catalogue_governance.corrections import GovernedCorrection
from catalogue_governance.release_gate import run_release_gate


def test_release_gate_reports_manifest_and_quality_checks():
    root = Path(__file__).resolve().parents[1]
    report = run_release_gate(root, run_quality=False)
    assert report.checks[0].check_id == "governance.manifest"
    assert report.institutional_approval == "NOT_ASSESSED"
    assert "institutional_approval" in report.blocked_claims


def test_release_gate_has_stable_check_ids_and_no_approval_claim():
    report = run_release_gate(Path(__file__).resolve().parents[1], run_quality=False)
    assert all(item.check_id for item in report.checks)
    assert "institutional_approval_not_assessed" in report.technical_claims


def _correction(**changes):
    values = dict(
        correction_id="C-1", institution_id="northstar", release_id="2027", package_id="core",
        target_key="policy_id", target_id="P-1", field_path="condition.threshold",
        operation="replace_value", expected_before=60, replacement=65,
        source_reference="fixture p.1", verification_status="unverified", authority="fixture",
    )
    values.update(changes)
    return GovernedCorrection(**values)


def test_semantic_change_is_review_not_technical_failure():
    baseline = {"policies": [{"policy_id": "P-1", "condition": {"threshold": 60}}]}
    governed = {"policies": [{"policy_id": "P-1", "condition": {"threshold": 65}}]}
    report = run_release_gate(Path(__file__).resolve().parents[1], run_quality=False, baseline=baseline, governed=governed)
    assert report.overall_outcome == "PASS_WITH_WARNINGS"
    assert report.review_required is True
    assert report.unexplained_drift is False


def test_declared_correction_matches_without_unexplained_drift():
    baseline = {"policies": [{"policy_id": "P-1", "condition": {"threshold": 60}}]}
    governed = {"policies": [{"policy_id": "P-1", "condition": {"threshold": 65}}]}
    report = run_release_gate(Path(__file__).resolve().parents[1], run_quality=False, baseline=baseline, governed=governed, corrections=(_correction(),))
    assert report.overall_outcome == "PASS_WITH_WARNINGS"
    assert report.unexplained_drift is False
    assert any(item.check_id == "governance.corrected_candidate" and item.outcome == "PASS" for item in report.checks)


def test_stale_correction_is_a_gate_failure():
    baseline = {"policies": [{"policy_id": "P-1", "condition": {"threshold": 70}}]}
    governed = baseline
    report = run_release_gate(Path(__file__).resolve().parents[1], run_quality=False, baseline=baseline, governed=governed, corrections=(_correction(),))
    assert report.overall_outcome == "FAIL"
