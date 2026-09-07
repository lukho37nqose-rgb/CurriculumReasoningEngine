"""Institution-owned catalogue resolution contracts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class CatalogueDescriptor:
    """A resolved catalogue package for one academic unit in a release."""

    institution_id: str
    release_id: str
    academic_unit_key: str
    catalogue_key: str
    courses_path: Path
    requirements_path: Path
    enabled: bool = True
    catalogue_version: str = ""


class InstitutionCatalogueResolver(Protocol):
    """Institution-specific mapping from academic units to catalogue packages."""

    def resolve_academic_unit(self, unit_key: str) -> str:
        """Return the canonical product academic-unit key for a key or alias."""

    def resolve_catalogue(self, unit_key: str) -> CatalogueDescriptor:
        """Resolve an academic unit key or alias to a catalogue descriptor."""

    def available_catalogues(self) -> tuple[CatalogueDescriptor, ...]:
        """Return descriptors for enabled catalogues in this release."""

