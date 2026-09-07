"""UCT 2026 institution release compatibility wrapper."""

from __future__ import annotations

import json
import re
from pathlib import Path

from curriculum_reasoning_engine.adapters.transcripts import UCTTranscriptAdapter

from .achievement import NumericAchievementScheme
from .catalogues import CatalogueDescriptor
from .models import AcademicUnit, InstitutionRelease
from .periods import LegacyAcademicYearPeriodScheme
from .provenance import from_package
from .routing import RouteResolution
from .uct_coding import UCTCourseCodeScheme
from .uct_course_load import UCTCourseLoadFramework
from .uct_credit_framework import UCTCreditFramework
from .uct_grading import UCTGradingScheme

_REPO_ROOT = Path(__file__).resolve().parents[2]


class UCTCatalogueResolver:
    """UCT 2026 academic-unit to legacy catalogue package mapping."""

    _UNIT_TO_CATALOGUE = {
        "commerce": "uct_commerce",
        "ebe": "uct_ebe",
        "health": "uct_health",
        "humanities": "uct_humanities",
        "law": "uct_law",
        "science": "uct_science",
    }
    _LEGACY_TO_UNIT = {value: key for key, value in _UNIT_TO_CATALOGUE.items()}

    def __init__(self, institution_id: str = "uct", release_id: str = "2026"):
        self.institution_id = institution_id
        self.release_id = release_id

    def resolve_academic_unit(self, unit_key: str) -> str:
        if unit_key in self._UNIT_TO_CATALOGUE:
            return unit_key
        if unit_key in self._LEGACY_TO_UNIT:
            return self._LEGACY_TO_UNIT[unit_key]
        raise KeyError(
            f"Unknown academic unit {unit_key!r} for "
            f"{self.institution_id}:{self.release_id}."
        )

    def resolve_catalogue(self, unit_key: str) -> CatalogueDescriptor:
        academic_unit_key = self.resolve_academic_unit(unit_key)
        catalogue_key = self._UNIT_TO_CATALOGUE[academic_unit_key]
        data_dir = _REPO_ROOT / "data" / catalogue_key
        return CatalogueDescriptor(
            institution_id=self.institution_id,
            release_id=self.release_id,
            academic_unit_key=academic_unit_key,
            catalogue_key=catalogue_key,
            courses_path=data_dir / "courses.json",
            requirements_path=data_dir / "degree_requirements.json",
            enabled=True,
        )

    def available_catalogues(self) -> tuple[CatalogueDescriptor, ...]:
        return tuple(
            self.resolve_catalogue(unit_key)
            for unit_key in sorted(self._UNIT_TO_CATALOGUE)
        )


class UCTRouteResolver:
    """UCT 2026 programme-label routing.

    This preserves the legacy matching behaviour from `engine.utils`. Ambiguous
    or incomplete labels still return the same `unknown_*` sentinels as before.
    """

    def infer_academic_unit(self, programme_label: str) -> str:
        name = programme_label.lower()
        if (
            "commerce" in name
            or "bcom" in name
            or "business science" in name
            or "actuarial science" in name
        ):
            return "uct_commerce"
        if (
            "engineering" in name
            or "bsc(eng)" in name
            or "bsc (eng)" in name
            or "architectural studies" in name
            or "architecture" in name
            or "geomatics" in name
            or "construction studies" in name
            or "property studies" in name
            or "city and regional planning" in name
        ):
            return "uct_ebe"
        if (
            "medicine" in name
            or "surgery" in name
            or "mbchb" in name
            or "health science" in name
            or "occupational therapy" in name
            or "physiotherapy" in name
            or "audiology" in name
            or "speech-language pathology" in name
        ):
            return "uct_health"
        if (
            "bachelor of laws" in name
            or re.search(r"\bllb\b", name)
            or "law faculty" in name
        ):
            return "uct_law"
        if (
            "social science" in name
            or "social work" in name
            or "bachelor of arts" in name
            or "bachelor of social" in name
            or "music" in name
            or "fine art" in name
            or "theatre" in name
            or "performance" in name
            or "adult and community education" in name
            or "foundation phase" in name
            or "intermediate phase" in name
        ):
            return "uct_humanities"
        if "science" in name or "bsc" in name:
            return "uct_science"
        if "law" in name or "llb" in name:
            return "uct_law"
        return "unknown_faculty"

    def infer_programme(self, programme_label: str) -> str:
        name = programme_label.lower().strip()
        commerce_code = re.search(r"\b(c[bu]\d{2,3}[a-z]{3}\d{2})\b", name, re.I)
        if commerce_code:
            key = commerce_code.group(1).lower()
            prefix = re.match(r"(c[bu])(\d{2,3})([a-z]{3}\d{2})", key, re.I)
            if prefix and len(prefix.group(2)) == 2:
                key = (
                    prefix.group(1).lower()
                    + "0"
                    + prefix.group(2)
                    + prefix.group(3).lower()
                )
            return key
        if (
            ("bachelor of science" in name or re.search(r"\bbsc\b", name))
            and "engineering" not in name
            and "bsc(eng)" not in name
            and "bsc (eng)" not in name
        ):
            return (
                "bsc_science_edp"
                if ("extended" in name or "sb016" in name)
                else "bsc_science"
            )
        if "bachelor of laws" in name or re.search(r"\bllb\b", name):
            if "five" in name or "5-year" in name or "lb003" in name:
                return "llb_five_year_continuing"
            if "two-year" in name or "2-year" in name or "combined" in name:
                return "llb_two_year_combined"
            if "three-year" in name or "3-year" in name or "graduate" in name:
                return "llb_three_year_graduate"
            return "llb_four_year_undergraduate"
        extended = "extended" in name
        if "philosophy, politics and economics" in name or "ppe" in name:
            return "bsocsc_ppe"
        if "social work" in name or "bsw" in name:
            return "bsw"
        if "screen production" in name:
            return "ba_screen_production"
        if "fine art" in name:
            return "ba_fine_art"
        if "music" in name or "bmus" in name:
            return "diploma_music_performance" if "diploma" in name else "bmus"
        if "theatre" in name or "performance" in name:
            return (
                "diploma_theatre_performance"
                if "diploma" in name
                else "ba_theatre_performance"
            )
        if "bachelor of social science" in name or "bsocsc" in name:
            return "bsocsc_extended" if extended else "bsocsc_regular"
        if "bachelor of arts" in name or re.search(r"\bba\b", name):
            return "ba_extended" if extended else "ba_regular"
        if "extended" in name:
            return "bsocsc_extended"
        return "unknown_programme"

    def resolve(self, programme_label: str) -> RouteResolution:
        academic_unit_key = self.infer_academic_unit(programme_label)
        programme_key = self.infer_programme(programme_label)
        return RouteResolution(
            source_label=programme_label,
            academic_unit_key=academic_unit_key,
            catalogue_key=academic_unit_key,
            programme_key=programme_key,
            status=(
                "unknown"
                if academic_unit_key == "unknown_faculty"
                and programme_key == "unknown_programme"
                else "resolved"
            ),
            confidence=(
                0.0
                if academic_unit_key == "unknown_faculty"
                and programme_key == "unknown_programme"
                else 1.0
            ),
        )

UCT_2026_RELEASE = InstitutionRelease(
    institution_id="uct",
    institution_display_name="University of Cape Town",
    release_id="2026",
    provenance=from_package(json.loads((_REPO_ROOT / "data/uct_humanities/degree_requirements.json").read_text(encoding="utf-8")), "uct", "2026"),
    academic_year=2026,
    route_resolver=UCTRouteResolver(),
    catalogue_resolver=UCTCatalogueResolver(),
    transcript_adapter=UCTTranscriptAdapter(),
    grading_scheme=UCTGradingScheme(),
    credit_framework=UCTCreditFramework(),
    course_code_scheme=UCTCourseCodeScheme(),
    course_load_framework=UCTCourseLoadFramework(),
    academic_period_scheme=LegacyAcademicYearPeriodScheme(),
    achievement_scheme=NumericAchievementScheme(0, 100, "uct-2026-percentage", "uct"),
    academic_units=(
        AcademicUnit(
            key="uct_commerce",
            name="Commerce",
            short_name="Commerce",
            description="Business Science, Commerce, Economics, Finance, Accounting and related programmes.",
            available=True,
            catalogue_key="uct_commerce",
        ),
        AcademicUnit(
            key="uct_ebe",
            name="Engineering & the Built Environment",
            short_name="EBE",
            description="Engineering, architecture, construction, property and geomatics programmes.",
            available=True,
            catalogue_key="uct_ebe",
        ),
        AcademicUnit(
            key="uct_health",
            name="Health Sciences",
            short_name="Health Sciences",
            description="Medicine, rehabilitation sciences, clinical training and other undergraduate health programmes.",
            available=True,
            catalogue_key="uct_health",
        ),
        AcademicUnit(
            key="uct_humanities",
            name="Humanities",
            short_name="Humanities",
            description="Arts, social sciences, performance, education and related programmes.",
            available=True,
            catalogue_key="uct_humanities",
        ),
        AcademicUnit(
            key="uct_law",
            name="Law",
            short_name="Law",
            description="Four-year, graduate-entry, combined and continuing-student LLB pathways.",
            available=True,
            catalogue_key="uct_law",
        ),
        AcademicUnit(
            key="uct_science",
            name="Science",
            short_name="Science",
            description="Regular and extended BSc routes across mathematical, computational, physical, earth and life sciences.",
            available=True,
            catalogue_key="uct_science",
        ),
    ),
)
