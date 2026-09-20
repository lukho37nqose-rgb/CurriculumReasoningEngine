"""Distinction must use the supplied grading scheme for major completion."""

import pytest

from curriculum_reasoning_engine.institutions.uct_grading import UCTGradingScheme
from engine.models import Catalogue, CourseFact, CourseResult, MajorDefinition, StudentRecord
from engine.rule_engine import _compute_distinction, _compute_major_progress


def case(mark, curriculum_rules, selected_set=False):
    courses = {
        code: CourseFact(code, code, 10, 7, [], [], "Synthetic", verification_status="verified")
        for code in ("OPAQUE_A", "OPAQUE_B")
    }
    major = MajorDefinition(
        "major", "Synthetic major", "SYN", list(courses),
        verification_status="verified",
        curriculum_rules=[{"type": "all_courses", "course_codes": list(courses)}] if curriculum_rules else [],
        award_rules=[] if selected_set else [{
            "id": "subject_award", "type": "weighted_average",
            "course_codes": ["OPAQUE_B"], "minimum_average": 75,
            "weighting": {"basis": "equal"},
        }],
    )
    catalogue = Catalogue(courses, {major.key: major}, {}, [])
    if selected_set:
        # Keep the failed prerequisite outside the senior award set so only
        # major completion, not missing selected marks, determines eligibility.
        courses["OPAQUE_A"].nqf_level = 5
        catalogue.award_rules = [{
            "id": "selected_set", "type": "subject_selected_set_distinction",
            "applies_to": "standard_faculty_owned_major_without_award_rules",
            "minimum_average": 0, "weighting": {"basis": "equal"},
            "selection_boundary": {"maximum": 100},
        }]
    student = StudentRecord("S", "Student", "Synthetic", [major.key], [
        CourseResult("OPAQUE_A", "A", 7, 10, mark, None),
        CourseResult("OPAQUE_B", "B", 7, 10, 80, None),
    ])
    return student, catalogue, major


@pytest.mark.parametrize("curriculum_rules", [False, True], ids=["legacy-major", "curriculum-major"])
@pytest.mark.parametrize("threshold,mark,expected", [(60, 55, False), (None, 55, True), (40, 45, True)],
                         ids=["higher-threshold", "default-grading", "lower-threshold"])
def test_subject_award_uses_major_grading_environment(curriculum_rules, threshold, mark, expected):
    student, catalogue, major = case(mark, curriculum_rules)
    grading = None if threshold is None else UCTGradingScheme(pass_mark=threshold)
    progress = _compute_major_progress(major, student, catalogue=catalogue, grading_scheme=grading)
    assert progress.complete is expected
    # Direct callers that omit grading retain the legacy threshold.
    assert _compute_major_progress(major, student, catalogue=catalogue).complete is (mark >= 50)
    row = _compute_distinction(student, catalogue, [major.key], grading_scheme=grading).subjects[0]
    assert row.eligible is expected
    assert row.average == 80
    assert row.status == "verified"
    assert row.policy_id == "subject_award"


@pytest.mark.parametrize("curriculum_rules", [False, True], ids=["legacy-major", "curriculum-major"])
def test_selected_set_receives_corrected_major_completion(curriculum_rules):
    student, catalogue, major = case(55, curriculum_rules, selected_set=True)
    default = _compute_distinction(student, catalogue, [major.key]).subjects[0]
    assert default.eligible
    grading = UCTGradingScheme(pass_mark=60)
    assert not _compute_major_progress(major, student, catalogue=catalogue, grading_scheme=grading).complete
    row = _compute_distinction(student, catalogue, [major.key], grading_scheme=grading).subjects[0]
    assert not row.eligible
    assert row.policy_id == default.policy_id == "selected_set"
    assert row.status == default.status == "verified"
    assert row.reason == default.reason
    assert row.average == default.average == 80
    assert row.senior_courses_assessed == default.senior_courses_assessed == 1
