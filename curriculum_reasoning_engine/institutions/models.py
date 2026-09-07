"""Immutable institution-release metadata for product compatibility."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .catalogues import CatalogueDescriptor
from .provenance import ReleaseProvenance
from .routing import RouteResolution

if TYPE_CHECKING:
    from curriculum_reasoning_engine.adapters.transcripts import TranscriptAdapter

    from .achievement import ExternalQualificationSystem, NumericAchievementScheme, SymbolicAchievementScheme
    from .catalogues import InstitutionCatalogueResolver
    from .coding import CourseCodeScheme
    from .course_load import CourseLoadFramework
    from .credit_framework import AcademicCreditFramework
    from .grading import GradingScheme
    from .periods import AcademicPeriodScheme
    from .routing import InstitutionRouteResolver


@dataclass(frozen=True, slots=True)
class AcademicUnit:
    """A product-visible academic unit backed by an existing catalogue key."""

    key: str
    name: str
    short_name: str
    description: str
    available: bool
    catalogue_key: str

    def faculty_payload(self) -> dict[str, object]:
        """Return the legacy faculty metadata shape expected by current clients."""
        return {
            "name": self.name,
            "short_name": self.short_name,
            "description": self.description,
            "available": self.available,
        }

    def card_payload(self) -> dict[str, object]:
        """Return the lightweight product bootstrap card shape."""
        return {"key": self.key, **self.faculty_payload()}


@dataclass(frozen=True, slots=True)
class InstitutionRelease:
    """A released institutional implementation of the engine data contract."""

    institution_id: str
    institution_display_name: str
    release_id: str
    academic_year: int
    academic_units: tuple[AcademicUnit, ...]
    route_resolver: InstitutionRouteResolver
    catalogue_resolver: InstitutionCatalogueResolver
    transcript_adapter: TranscriptAdapter
    grading_scheme: GradingScheme
    credit_framework: AcademicCreditFramework
    course_code_scheme: CourseCodeScheme
    course_load_framework: CourseLoadFramework
    academic_period_scheme: AcademicPeriodScheme | None = None
    achievement_scheme: NumericAchievementScheme | SymbolicAchievementScheme | None = None
    external_qualification_systems: tuple[ExternalQualificationSystem, ...] = ()
    provenance: ReleaseProvenance | None = None

    def __post_init__(self):
        if self.provenance and (self.provenance.institution_id, self.provenance.release_id) != (self.institution_id, self.release_id):
            raise ValueError("Release provenance belongs to a different release")

    @property
    def period_scheme(self) -> AcademicPeriodScheme:
        if self.academic_period_scheme is None:
            raise ValueError(
                f"Release {self.institution_id}:{self.release_id} has no academic period scheme."
            )
        return self.academic_period_scheme

    @property
    def academic_unit_keys(self) -> frozenset[str]:
        return frozenset(unit.key for unit in self.academic_units)

    @property
    def enabled_catalogue_keys(self) -> frozenset[str]:
        return frozenset(
            unit.catalogue_key for unit in self.academic_units if unit.available
        )

    def academic_unit(self, key: str) -> AcademicUnit:
        for unit in self.academic_units:
            if unit.key == key:
                return unit
        raise KeyError(
            f"Unknown academic unit {key!r} for "
            f"{self.institution_id}:{self.release_id}."
        )

    def catalogue_key_for_unit(self, key: str) -> str:
        return self.resolve_catalogue(key).catalogue_key

    def faculty_meta_projection(self) -> dict[str, dict[str, object]]:
        """Return the current legacy faculty metadata keyed by product unit key."""
        return {unit.key: unit.faculty_payload() for unit in self.academic_units}

    def infer_academic_unit(self, programme_label: str) -> str:
        return self.route_resolver.infer_academic_unit(programme_label)

    def infer_programme(self, programme_label: str) -> str:
        return self.route_resolver.infer_programme(programme_label)

    def resolve_route(self, programme_label: str) -> RouteResolution:
        return self.route_resolver.resolve(programme_label)

    def resolve_academic_unit(self, unit_key: str) -> str:
        return self.catalogue_resolver.resolve_academic_unit(unit_key)

    def resolve_catalogue(self, unit_key: str) -> CatalogueDescriptor:
        return self.catalogue_resolver.resolve_catalogue(unit_key)

    def available_catalogues(self) -> tuple[CatalogueDescriptor, ...]:
        return self.catalogue_resolver.available_catalogues()
