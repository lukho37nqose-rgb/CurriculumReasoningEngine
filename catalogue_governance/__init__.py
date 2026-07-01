"""Non-destructive catalogue governance utilities for CurriculumAdvisor.

This package is intentionally independent of the reasoning engine. It can be
added to the repository without changing catalogue loading or student outcomes.
"""

from .integrity import (
    ManifestDiff,
    VerificationResult,
    build_manifest,
    compare_manifests,
    load_manifest,
    verify_manifest,
    write_manifest,
)
from .operational import OperationalDataError, validate_offerings_payload

__all__ = [
    "ManifestDiff",
    "OperationalDataError",
    "VerificationResult",
    "build_manifest",
    "compare_manifests",
    "load_manifest",
    "validate_offerings_payload",
    "verify_manifest",
    "write_manifest",
]
