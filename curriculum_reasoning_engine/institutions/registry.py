"""Institution release registry."""

from __future__ import annotations

from .models import InstitutionRelease
from .uct import UCT_2026_RELEASE

_RELEASES = {
    (UCT_2026_RELEASE.institution_id, UCT_2026_RELEASE.release_id): UCT_2026_RELEASE,
}


def register_institution_release(release: InstitutionRelease) -> None:
    """Register an explicit release for an application or integration fixture."""
    if not release.institution_id or not release.release_id:
        raise ValueError("An institution release requires institution_id and release_id.")
    _RELEASES[(release.institution_id, release.release_id)] = release


def unregister_institution_release(institution_id: str, release_id: str) -> None:
    """Remove an injected release, primarily for isolated integration tests."""
    _RELEASES.pop((institution_id, release_id), None)


def get_institution_release(
    institution_id: str = "uct", release_id: str = "2026"
) -> InstitutionRelease:
    """Resolve an institution release or fail safely with a lookup error."""
    key = (institution_id, release_id)
    try:
        return _RELEASES[key]
    except KeyError as exc:
        known = ", ".join(f"{inst}:{rel}" for inst, rel in sorted(_RELEASES))
        raise KeyError(
            f"Unknown institution release {institution_id}:{release_id}. "
            f"Known releases: {known}."
        ) from exc
