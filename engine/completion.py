"""Course completion witnesses, independent of credit and attempt accounting."""

from dataclasses import dataclass

from curriculum_reasoning_engine.institutions.grading import GradingScheme, legacy_default_grading_scheme

from .models import AcademicRecordCoverageEvidence, Catalogue, StudentRecord


@dataclass(frozen=True)
class CourseCompletionRecognitionEvidence:
    recognition_id: str
    student_id: str
    target_course_code: str
    source_learning_identity: str
    institution_id: str
    release_id: str
    authority: str
    source_reference: str
    verification_status: str = "unverified"
    programme_key: str = ""
    pathway_key: str = ""


@dataclass(frozen=True)
class RecognitionEvidenceCoverage:
    """An explicit complete decision snapshot for the named course targets."""

    student_id: str
    institution_id: str
    release_id: str
    course_codes: tuple[str, ...]
    authority: str
    source_reference: str
    verification_status: str = "unverified"
    programme_key: str = ""
    pathway_key: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "course_codes", tuple(self.course_codes))


@dataclass(frozen=True)
class CourseCompletionRecognitionInput:
    decisions: tuple[CourseCompletionRecognitionEvidence, ...] = ()
    coverage: tuple[RecognitionEvidenceCoverage, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "decisions", tuple(self.decisions))
        object.__setattr__(self, "coverage", tuple(self.coverage))


@dataclass(frozen=True)
class CourseCompletionAssessment:
    outcome: str
    status: str
    detail: str
    witness_source: str = ""
    recognition_ids: tuple[str, ...] = ()

    @property
    def assessment_complete(self) -> bool:
        return self.outcome in {"satisfied", "not_satisfied"} and self.status == "verified"


def weaker_status(*statuses: str) -> str:
    rank = {"verified": 0, "provisional": 1, "unverified": 2, "conflict": 3}
    return max(statuses or ("unverified",), key=lambda s: rank.get(s, 2))


class CourseCompletionResolver:
    def __init__(
        self,
        student: StudentRecord,
        catalogue: Catalogue,
        grading_scheme: GradingScheme | None = None,
        recognition: CourseCompletionRecognitionInput | None = None,
    ) -> None:
        self.student = student
        self.catalogue = catalogue
        self.scheme = grading_scheme or legacy_default_grading_scheme()
        self.recognition = recognition or CourseCompletionRecognitionInput()
        self.local_codes = student.passed_codes(self.scheme) & set(catalogue.courses)
        self.decisions = tuple(d for d in self.recognition.decisions if self._applies(d))
        self.coverage = tuple(d for d in self.recognition.coverage if self._applies(d))
        for decision in self.decisions:
            if decision.target_course_code not in catalogue.courses:
                raise ValueError(f"Unknown recognition target {decision.target_course_code!r}.")
            if not all(
                isinstance(value, str) and value.strip()
                for value in (
                    decision.recognition_id,
                    decision.source_learning_identity,
                    decision.authority,
                    decision.source_reference,
                )
            ):
                raise ValueError(
                    "Recognition requires identity, source learning, authority and source reference."
                )
            if decision.verification_status not in {"verified", "provisional", "unverified", "conflict"}:
                raise ValueError("Unsupported recognition verification status.")
        for coverage in self.coverage:
            if not coverage.authority or not coverage.source_reference:
                raise ValueError("Recognition coverage requires authority and source reference.")
            if coverage.verification_status not in {"verified", "provisional", "unverified", "conflict"}:
                raise ValueError("Unsupported recognition coverage status.")
            if not coverage.course_codes or set(coverage.course_codes) - set(catalogue.courses):
                raise ValueError("Recognition coverage requires known exact course targets.")

    def _applies(self, evidence: CourseCompletionRecognitionEvidence | RecognitionEvidenceCoverage) -> bool:
        return (
            bool(evidence.student_id and evidence.institution_id and evidence.release_id)
            and evidence.student_id == self.student.student_id
            and evidence.institution_id == self.scheme.institution_id
            and evidence.release_id == self.catalogue.recognition_release_id
            and (
                not evidence.programme_key
                or evidence.programme_key == (self.catalogue.programme_key or self.student.programme_key)
            )
            and (
                not evidence.pathway_key
                or evidence.pathway_key == (self.catalogue.pathway_key or self.student.pathway_key)
            )
        )

    def resolve(
        self, code: str, result_coverage: list[AcademicRecordCoverageEvidence] | None = None
    ) -> CourseCompletionAssessment:
        decisions = [d for d in self.decisions if d.target_course_code == code]
        if any(d.verification_status == "conflict" for d in decisions):
            return CourseCompletionAssessment(
                "conflict", "conflict", f"Recognition evidence conflicts for {code}."
            )
        if code in self.local_codes:
            return CourseCompletionAssessment(
                "satisfied", "verified", f"{code} is completed by a local result.", "local_result"
            )
        if decisions:
            chosen = min(
                decisions,
                key=lambda d: (
                    {"verified": 0, "provisional": 1, "unverified": 2}[d.verification_status],
                    d.recognition_id,
                    d.source_learning_identity,
                    d.authority,
                    d.source_reference,
                ),
            )
            return CourseCompletionAssessment(
                "satisfied",
                chosen.verification_status,
                f"{code} completion recognised by {chosen.authority}; recognition {chosen.recognition_id}: {chosen.source_reference}.",
                "recognition",
                tuple(sorted({d.recognition_id for d in decisions})),
            )
        records = [
            e
            for e in result_coverage or ()
            if code in {str(value).strip().upper() for value in e.course_codes}
        ]
        recognition = [e for e in self.coverage if code in e.course_codes]
        if any(
            str(e.verification_status).strip().lower() == "conflict" for e in [*records, *recognition]
        ) or any(str(e.coverage_state).strip().lower() == "conflict" for e in records):
            return CourseCompletionAssessment(
                "conflict", "conflict", f"Coverage evidence conflicts for {code}."
            )
        if any(r.code == code and self.scheme.is_pending(r) for r in self.student.results):
            return CourseCompletionAssessment("unresolved", "unverified", f"{code} has a pending result.")
        complete = [e for e in records if str(e.coverage_state).strip().lower() == "complete"]
        if complete and recognition:
            status = weaker_status(
                *(
                    str(e.verification_status or "unverified").strip().lower()
                    for e in [*complete, *recognition]
                )
            )
            return CourseCompletionAssessment(
                "not_satisfied",
                status,
                f"No completion witness for {code} exists in the covered result and recognition records.",
            )
        return CourseCompletionAssessment(
            "unresolved",
            "unverified",
            f"Completion of {code} is not established without complete academic-record coverage and recognition decision coverage.",
        )

    def completed_codes(self) -> set[str]:
        return {code for code in self.catalogue.courses if self.resolve(code).outcome == "satisfied"}
