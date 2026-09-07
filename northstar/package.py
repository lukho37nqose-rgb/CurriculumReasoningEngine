"""Northstar-owned frameworks and explicit demonstrator release selection."""

import json
from dataclasses import dataclass
from pathlib import Path

from curriculum_reasoning_engine.institutions.achievement import (
    ExternalQualificationSystem,
    NumericAchievementScheme,
)
from curriculum_reasoning_engine.institutions.catalogues import CatalogueDescriptor
from curriculum_reasoning_engine.institutions.grading import ResultState
from curriculum_reasoning_engine.institutions.models import AcademicUnit, InstitutionRelease
from curriculum_reasoning_engine.institutions.periods import ExplicitAcademicPeriodScheme
from curriculum_reasoning_engine.institutions.provenance import from_package
from curriculum_reasoning_engine.institutions.routing import RouteResolution

ROOT = Path(__file__).parent
INSTITUTION = "northstar"
RELEASE = "northstar-v1"
PROGRAMME = "systems_inquiry"
CODES = ("FOUND-X7", "CORE-Q2", "PATH-Z9", "ALT-V8", "CAP-R4", "LAB-T6")


def read_package(name):
    return json.loads((ROOT / "package" / name).read_text(encoding="utf-8"))


@dataclass(frozen=True)
class Grading:
    institution_id: str = INSTITUTION
    scheme_id: str = "northstar-pass-60"

    def classify(self, result):
        if result.mark is None:
            return ResultState.PENDING
        return ResultState.PASSED if result.mark >= 60 else ResultState.FAILED

    def is_passed(self, result):
        return self.classify(result) == ResultState.PASSED

    def is_failed(self, result):
        return self.classify(result) == ResultState.FAILED

    def is_pending(self, result):
        return self.classify(result) == ResultState.PENDING


@dataclass(frozen=True)
class Credits:
    institution_id: str = INSTITUTION
    framework_id: str = "northstar-module-credit"

    def credit_value(self, item):
        return item.nqf_credits

    def academic_level(self, item):
        return item.nqf_level

    def is_senior_level(self, item):
        return self.academic_level(item) == 3

    def is_level(self, item, level):
        return self.academic_level(item) == level


@dataclass(frozen=True)
class Codes:
    institution_id: str = INSTITUTION
    scheme_id: str = "northstar-opaque"

    def infer_academic_level(self, code):
        return 0

    def infer_year_level(self, code):
        return 0

    def infer_department(self, code):
        return ""


@dataclass(frozen=True)
class Load:
    institution_id: str = INSTITUTION
    framework_id: str = "northstar-independent-load"

    def load_equivalent(self, item):
        return dict(zip(CODES, (0.8, 0.3, 0.5, 0.9, 0.4, 0.7), strict=True))[item.code]


@dataclass(frozen=True)
class Routes:
    def resolve(self, programme_label):
        if programme_label != "Diploma in Systems Inquiry":
            raise ValueError("Unknown Northstar route")
        return RouteResolution(programme_label, "systems", "systems", PROGRAMME)

    def infer_academic_unit(self, programme_label):
        return self.resolve(programme_label).academic_unit_key

    def infer_programme(self, programme_label):
        return self.resolve(programme_label).programme_key


@dataclass(frozen=True)
class Catalogues:
    descriptor: CatalogueDescriptor

    def resolve_academic_unit(self, unit_key):
        if unit_key != "systems":
            raise KeyError(unit_key)
        return unit_key

    def resolve_catalogue(self, unit_key):
        self.resolve_academic_unit(unit_key)
        return self.descriptor

    def available_catalogues(self):
        return (self.descriptor,)


class RecordsOnlyAdapter:
    adapter_id = "northstar-records-v1"
    institution_id = INSTITUTION
    supported_formats = ()

    def parse_text(self, text):
        raise ValueError("Use the authenticated synthetic records service")

    def parse_pdf(self, value):
        raise ValueError("Northstar v1 does not ingest transcripts")


def release():
    descriptor = CatalogueDescriptor(INSTITUTION, RELEASE, "systems", "systems",
                                     ROOT / "package/courses.json", ROOT / "package/degree_requirements.json",
                                     catalogue_version=RELEASE)
    return InstitutionRelease(
        INSTITUTION, "Northstar University (synthetic)", RELEASE, 2027,
        (AcademicUnit("systems", "School of Systems", "Systems", "Synthetic academic unit", True, "systems"),),
        Routes(), Catalogues(descriptor), RecordsOnlyAdapter(), Grading(), Credits(), Codes(), Load(),
        ExplicitAcademicPeriodScheme((("P-Z", "CYCLE-Q", 10), ("P-A", "CYCLE-Q", 20),
                                     ("P-M", "CYCLE-Q", 30), ("P-B", "CYCLE-R", 40),
                                     ("P-X", "CYCLE-S", 50)), scheme_id="northstar-v1-periods"),
        NumericAchievementScheme(0, 20, "northstar-achievement-20", INSTITUTION),
        (ExternalQualificationSystem("ORION-CERT", "Orion Certificate",
                                     NumericAchievementScheme(0, 10, "orion-10", "orion"),
                                     frozenset({"OR-MATH"}), "unverified", "Synthetic Orion register",
                                     frozenset({"ORA-K7"})),),
        provenance=from_package(read_package("degree_requirements.json"), INSTITUTION, RELEASE),
    )
