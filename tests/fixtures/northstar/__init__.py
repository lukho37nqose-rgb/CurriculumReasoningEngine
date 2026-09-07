"""Executable synthetic institution package; no production registration."""

from __future__ import annotations

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
from curriculum_reasoning_engine.institutions.routing import RouteResolution
from engine.catalogue import load_catalogue
from engine.completion import (
    CourseCompletionRecognitionEvidence,
    CourseCompletionRecognitionInput,
    RecognitionEvidenceCoverage,
)
from engine.models import AcademicRecordCoverageEvidence, CourseResult, StudentRecord
from engine.rule_engine import compute_report

ROOT = Path(__file__).parent


def read_json(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


@dataclass(frozen=True)
class NorthstarGrading:
    pass_mark: int
    institution_id: str = "northstar"
    scheme_id: str = "northstar-numeric"

    def classify(self, result):
        if result.mark is None:
            return ResultState.PENDING
        return ResultState.PASSED if result.mark >= self.pass_mark else ResultState.FAILED

    def is_passed(self, result):
        return self.classify(result) == ResultState.PASSED

    def is_failed(self, result):
        return self.classify(result) == ResultState.FAILED

    def is_pending(self, result):
        return self.classify(result) == ResultState.PENDING


@dataclass(frozen=True)
class NorthstarCredits:
    institution_id: str = "northstar"
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
class NorthstarCodes:
    institution_id: str = "northstar"
    scheme_id: str = "northstar-opaque"

    def infer_academic_level(self, code):
        return 0

    def infer_year_level(self, code):
        return 0

    def infer_department(self, code):
        return ""


@dataclass(frozen=True)
class NorthstarLoad:
    values: tuple[tuple[str, float], ...]
    institution_id: str = "northstar"
    framework_id: str = "northstar-independent-load"

    def load_equivalent(self, item):
        return dict(self.values)[item.code]


@dataclass(frozen=True)
class NorthstarRoutes:
    label: str
    programme: str
    unit: str

    def resolve(self, programme_label):
        if programme_label != self.label:
            raise ValueError("Unknown Northstar programme label")
        return RouteResolution(programme_label, self.unit, self.unit, self.programme)

    def infer_academic_unit(self, programme_label):
        return self.resolve(programme_label).academic_unit_key

    def infer_programme(self, programme_label):
        return self.resolve(programme_label).programme_key


@dataclass(frozen=True)
class NorthstarCatalogues:
    descriptor: CatalogueDescriptor

    def resolve_academic_unit(self, unit_key):
        if unit_key != self.descriptor.academic_unit_key:
            raise KeyError(unit_key)
        return unit_key

    def resolve_catalogue(self, unit_key):
        self.resolve_academic_unit(unit_key)
        return self.descriptor

    def available_catalogues(self):
        return (self.descriptor,)


@dataclass(frozen=True)
class AdaptedInput:
    student: StudentRecord
    result_coverage: tuple[AcademicRecordCoverageEvidence, ...]
    recognition: CourseCompletionRecognitionInput


class NorthstarAdapter:
    adapter_id = "northstar-json"
    institution_id = "northstar"
    supported_formats = ("json",)

    def __init__(self, config):
        self.config = config

    def parse_text(self, text):
        return self.ingest(json.loads(text)).student

    def parse_pdf(self, pdf_path_or_file):
        raise NotImplementedError("The bounded Northstar fixture accepts JSON, not PDF")

    def ingest(self, raw):
        config = self.config
        if raw["route"] != config["route_label"]:
            raise ValueError("Unknown Northstar route")
        facts = {row["code"]: row for row in read_json("courses.json")}
        results = []
        for position, row in enumerate(raw.get("modules", [])):
            fact = facts[row["module"]]
            score = row.get("score")
            if score is not None and (
                isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= 100
            ):
                raise ValueError("Northstar scores must be numeric transcript values")
            results.append(
                CourseResult(
                    fact["code"],
                    fact["name"],
                    fact["nqf_level"],
                    fact["credits"],
                    score,
                    None,
                    config["cycle_years"][row["period"]],
                    row.get("attempt", f"{raw['person']}:result:{position}"),
                    f"NS-{config['cycle_years'][row['period']] % 100:02d}-{row['period'][-1]}",
                )
            )
        student = StudentRecord(
            raw["person"],
            raw.get("name", raw["person"]),
            config["route_label"],
            [],
            results,
            faculty_key=config["unit_id"],
            programme_key=config["programme_id"],
        )
        decisions = tuple(
            CourseCompletionRecognitionEvidence(
                row["decision"],
                student.student_id,
                row["target"],
                row["learning"],
                config["institution_id"],
                config["release_id"],
                row["authority"],
                row["source"],
                row.get("status", "unverified"),
                config["programme_id"],
            )
            for row in raw.get("recognitions", [])
        )
        coverage = ()
        if raw.get("complete_recognition"):
            coverage = (
                RecognitionEvidenceCoverage(
                    student.student_id,
                    config["institution_id"],
                    config["release_id"],
                    tuple(raw["complete_recognition"]),
                    "Synthetic registry",
                    "Synthetic Northstar complete decision snapshot",
                    raw.get("coverage_status", "verified"),
                    config["programme_id"],
                ),
            )
        result_coverage = ()
        if raw.get("complete_results"):
            result_coverage = (
                AcademicRecordCoverageEvidence(
                    tuple(raw["complete_results"]),
                    "complete",
                    source_reference="Synthetic Northstar result snapshot",
                    authority="Synthetic registry",
                    verification_status=raw.get("coverage_status", "verified"),
                ),
            )
        return AdaptedInput(student, result_coverage, CourseCompletionRecognitionInput(decisions, coverage))


def select_release(institution_id, release_id):
    """Explicit test-harness selection; never changes the app's active release."""
    config = read_json("release.json")
    if (institution_id, release_id) != (config["institution_id"], config["release_id"]):
        raise KeyError((institution_id, release_id))
    descriptor = CatalogueDescriptor(
        institution_id,
        release_id,
        config["unit_id"],
        config["unit_id"],
        ROOT / "courses.json",
        ROOT / "degree_requirements.json",
        catalogue_version=release_id,
    )
    return InstitutionRelease(
        institution_id,
        config["institution_display_name"],
        release_id,
        config["academic_year"],
        (
            AcademicUnit(
                config["unit_id"],
                config["unit_name"],
                "Systems",
                "Synthetic integration academic unit",
                True,
                config["unit_id"],
            ),
        ),
        NorthstarRoutes(config["route_label"], config["programme_id"], config["unit_id"]),
        NorthstarCatalogues(descriptor),
        NorthstarAdapter(config),
        NorthstarGrading(config["pass_mark"]),
        NorthstarCredits(),
        NorthstarCodes(),
        NorthstarLoad(tuple(config["load_equivalents"].items())),
        ExplicitAcademicPeriodScheme(
            (
                ("NS-27-A", "AY27", 10),
                ("NS-27-B", "AY27", 20),
                ("NS-27-C", "AY27", 30),
                ("NS-28-A", "AY28", 40),
                ("NS-28-B", "AY28", 50),
                ("NS-28-C", "AY28", 60),
                ("NS-29-A", "AY29", 70),
            ),
            scheme_id="northstar-fixture-periods",
        ),
        NumericAchievementScheme(0, 20, "northstar-2027-0-20", "northstar"),
        (ExternalQualificationSystem(
            "ORION-CERT", "Orion School Certificate",
            NumericAchievementScheme(0, 10, "orion-0-10", "orion-cert"),
            frozenset({"OR-MATH", "OR-SCI"}), "unverified", "Synthetic Northstar external-system fixture",
            frozenset({"ORA-K7", "ORA-T2"}),
        ),),
    )


def catalogue_for(release):
    descriptor = release.resolve_catalogue("systems")
    catalogue = load_catalogue(
        descriptor.catalogue_key,
        descriptor.courses_path,
        descriptor.requirements_path,
        release.course_code_scheme,
    )
    catalogue.programme_key = release.infer_programme(read_json("release.json")["route_label"])
    catalogue.scope_status = "verified"
    return catalogue


def frameworks(release):
    return {
        "grading_scheme": release.grading_scheme,
        "credit_framework": release.credit_framework,
        "course_code_scheme": release.course_code_scheme,
        "course_load_framework": release.course_load_framework,
    }


def analyse(raw, institution_id="northstar", release_id="northstar-fixture-2027"):
    """Institution adapter -> unchanged generic report -> actual app serializer."""
    from app import _to_dict

    release = select_release(institution_id, release_id)
    catalogue = catalogue_for(release)
    inputs = release.transcript_adapter.ingest(raw)
    report = compute_report(
        inputs.student,
        catalogue,
        **frameworks(release),
        academic_record_coverage_evidence=inputs.result_coverage,
        completion_recognition=inputs.recognition,
        academic_period_scheme=release.period_scheme,
    )
    return release, catalogue, inputs, report, _to_dict(report)
