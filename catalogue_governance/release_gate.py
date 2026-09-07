"""Deterministic technical release-verification orchestration."""

from __future__ import annotations

import json
import subprocess  # nosec B404 - fixed local verification commands only
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .corrections import GovernedCorrection, compare_corrected_candidate
from .integrity import load_manifest, verify_manifest
from .reproducibility import semantic_diff


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    category: str
    outcome: str
    severity: str
    summary: str


@dataclass(frozen=True)
class TechnicalReleaseGateReport:
    institution_id: str
    release_id: str
    overall_outcome: str
    checks: tuple[CheckResult, ...]
    technical_claims: tuple[str, ...]
    warnings: tuple[str, ...]
    blocked_claims: tuple[str, ...]
    institutional_approval: str = "NOT_ASSESSED"
    review_required: bool = False
    semantic_changes: tuple[str, ...] = ()
    governance_changes: tuple[str, ...] = ()
    provenance_changes: tuple[str, ...] = ()
    unexplained_drift: bool = False

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["checks"] = [asdict(item) for item in self.checks]
        return payload


def _command_check(root: Path, check_id: str, category: str, command: list[str]) -> CheckResult:
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)  # nosec B603 - command is constructed internally
    if result.returncode == 0:
        return CheckResult(check_id, category, "PASS", "blocking", "completed")
    return CheckResult(check_id, category, "FAIL", "blocking", f"exit code {result.returncode}")


def run_release_gate(
    root: str | Path,
    *,
    institution_id: str = "uct",
    release_id: str = "uct-2026-uploaded-baseline",
    run_quality: bool = True,
    baseline: Any | None = None,
    governed: Any | None = None,
    corrections: tuple[GovernedCorrection, ...] = (),
) -> TechnicalReleaseGateReport:
    """Run the local technical gate without writing packages or manifests."""
    project = Path(root).resolve()
    checks: list[CheckResult] = []
    semantic_changes: list[str] = []
    governance_changes: list[str] = []
    provenance_changes: list[str] = []
    unexplained_drift = False
    review_required = False
    manifest_path = project / "governance" / "releases" / "uct-2026-uploaded-baseline.manifest.json"
    try:
        manifest = load_manifest(manifest_path)
        result = verify_manifest(project / "data", manifest)
        checks.append(CheckResult(
            "governance.manifest", "integrity", "PASS" if result.ok else "FAIL",
            "blocking", "manifest matches" if result.ok else "manifest mismatch",
        ))
        if manifest.get("source_status") != "existing_verified_state":
            checks.append(CheckResult(
                "governance.source_status", "provenance", "INCOMPLETE", "warning",
                str(manifest.get("source_status", "unavailable")),
            ))
    except (OSError, ValueError) as exc:
        checks.append(CheckResult("governance.manifest", "integrity", "FAIL", "blocking", str(exc)))

    from curriculum_reasoning_engine.institutions.provenance import from_package

    packages = [governed] if isinstance(governed, dict) else [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (project / "data").glob("*/degree_requirements.json")
    ]
    for package in packages:
        if "institution_sources" not in package and "requirement_source_relationships" not in package:
            continue
        try:
            # The release key is declared by the source and checked against every relationship.
            source = package["institution_sources"][0]
            from_package(package, source["institution_id"], source["release_id"])
            checks.append(CheckResult("governance.requirement_sources", "provenance", "PASS", "blocking", "source references valid"))
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            checks.append(CheckResult("governance.requirement_sources", "provenance", "FAIL", "blocking", str(exc)))

    if run_quality:
        checks.append(_command_check(project, "tests.full", "repository_quality", [sys.executable, "-m", "pytest", "-q"]))
        checks.append(_command_check(project, "quality.ruff", "repository_quality", [sys.executable, "-m", "ruff", "check", "catalogue_governance"]))
        checks.append(_command_check(project, "security.bandit", "repository_quality", [sys.executable, "-m", "bandit", "-q", "-r", "catalogue_governance"]))

    if baseline is not None and governed is not None:
        diff = semantic_diff(baseline, governed)
        semantic_changes.extend(item.path for item in diff.semantic_changes)
        governance_changes.extend(item.path for item in diff.governance_changes)
        provenance_changes.extend(item.path for item in diff.provenance_changes)
        review_required = bool(diff.changes)
        checks.append(CheckResult(
            "governance.semantic_change", "change_governance",
            "REVIEW_REQUIRED" if review_required else "PASS",
            "review" if review_required else "blocking", f"{len(diff.changes)} classified changes",
        ))
        if corrections:
            try:
                comparison = compare_corrected_candidate(baseline, governed, corrections)
                checks.append(CheckResult(
                    "governance.corrected_candidate", "corrections",
                    "PASS" if comparison.status == "MATCH_AFTER_CORRECTIONS" else "FAIL",
                    "blocking", comparison.status,
                ))
                checks.append(CheckResult(
                    "governance.corrections", "corrections", "PASS", "blocking",
                    f"{len(comparison.application.applied_ids)} applied",
                ))
                unexplained_drift = comparison.status != "MATCH_AFTER_CORRECTIONS"
            except ValueError as exc:
                checks.append(CheckResult("governance.corrections", "corrections", "FAIL", "blocking", str(exc)))
        else:
            checks.append(CheckResult("governance.corrections", "corrections", "NOT_APPLICABLE", "informational", "no declarations"))
            checks.append(CheckResult("governance.corrected_candidate", "corrections", "NOT_APPLICABLE", "informational", "no declarations"))
    else:
        checks.append(CheckResult("governance.provenance", "provenance", "INCOMPLETE", "warning", "declaration not supplied"))
        checks.append(CheckResult("governance.rebuild", "reproducibility", "NOT_APPLICABLE", "informational", "no rebuild declaration"))
        checks.append(CheckResult("governance.corrections", "corrections", "NOT_APPLICABLE", "informational", "no declarations"))
        checks.append(CheckResult("governance.corrected_candidate", "corrections", "NOT_APPLICABLE", "informational", "no declarations"))

    blocking_failure = any(item.outcome == "FAIL" and item.severity == "blocking" for item in checks) or unexplained_drift
    incomplete = any(item.outcome == "INCOMPLETE" for item in checks)
    overall = "FAIL" if blocking_failure else "PASS_WITH_WARNINGS" if incomplete else "PASS"
    return TechnicalReleaseGateReport(
        institution_id=institution_id,
        release_id=release_id,
        overall_outcome=overall,
        checks=tuple(checks),
        technical_claims=("technical_validation_only", "institutional_approval_not_assessed"),
        warnings=tuple(item.summary for item in checks if item.outcome == "INCOMPLETE"),
        blocked_claims=("institutional_approval", "source_fidelity", "institutional_authorisation"),
        review_required=review_required,
        semantic_changes=tuple(semantic_changes),
        governance_changes=tuple(governance_changes),
        provenance_changes=tuple(provenance_changes),
        unexplained_drift=unexplained_drift,
    )


def print_summary(report: TechnicalReleaseGateReport) -> None:
    print(f"CRE Technical Release Verification: {report.institution_id} / {report.release_id}")
    for check in report.checks:
        print(f"{check.check_id}: {check.outcome}")
    print(f"Overall technical gate: {report.overall_outcome}")
    print(f"Institutional review required: {'YES' if report.review_required else 'NO'}")
    print("Institutional approval: NOT ASSESSED")


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Run the non-destructive CRE technical release gate.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--institution", default="uct")
    parser.add_argument("--release", default="uct-2026-uploaded-baseline")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--skip-quality", action="store_true")
    args = parser.parse_args(argv)
    report = run_release_gate(args.root, institution_id=args.institution, release_id=args.release, run_quality=not args.skip_quality)
    if args.json:
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    else:
        print_summary(report)
    return 0 if report.overall_outcome != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
