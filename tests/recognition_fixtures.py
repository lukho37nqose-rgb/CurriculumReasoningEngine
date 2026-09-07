"""Explicit empty recognition snapshots for closed-record regression scenarios."""

from curriculum_reasoning_engine.institutions.grading import legacy_default_grading_scheme
from engine.completion import CourseCompletionRecognitionInput, RecognitionEvidenceCoverage


def empty_recognition_snapshot(student, catalogue, scheme=None):
    return CourseCompletionRecognitionInput(
        coverage=(
            RecognitionEvidenceCoverage(
                student.student_id,
                (scheme or legacy_default_grading_scheme()).institution_id,
                catalogue.catalogue_version,
                tuple(catalogue.courses),
                "Test registry",
                "Explicit complete recognition decision snapshot (no decisions)",
                "verified",
            ),
        )
    )
