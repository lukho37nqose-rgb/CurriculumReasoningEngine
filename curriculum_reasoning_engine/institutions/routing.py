"""Institution-owned route resolution contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RouteResolution:
    """A best-effort mapping from an external programme label to stable keys."""

    source_label: str
    academic_unit_key: str
    catalogue_key: str
    programme_key: str
    pathway_key: str = ""
    status: str = "resolved"
    confidence: float = 1.0


class InstitutionRouteResolver(Protocol):
    """Institution-specific interpretation of programme and transcript labels."""

    def infer_academic_unit(self, programme_label: str) -> str:
        """Return the academic-unit key for a programme label, or an unknown key."""

    def infer_programme(self, programme_label: str) -> str:
        """Return the programme key for a programme label, or an unknown key."""

    def resolve(self, programme_label: str) -> RouteResolution:
        """Resolve every route identifier currently inferable from a label."""

