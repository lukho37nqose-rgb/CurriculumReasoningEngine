import pytest
from fixtures.northstar import select_release

from curriculum_reasoning_engine.institutions import (
    ExplicitAcademicPeriodScheme,
    LegacyAcademicYearPeriodScheme,
    get_institution_release,
)
from engine.models import CourseResult, ResultContextEvidence, StudentRecord
from engine.rule_engine import compute_report


def test_period_scheme_orders_opaque_keys_from_release_data_only():
    scheme = ExplicitAcademicPeriodScheme(
        (("Q-2", "AY-27", 20), ("Q-1", "AY-27", 10), ("Q-3", "AY-27", 30)),
        scheme_id="hostile",
    )
    assert scheme.order("Q-1") < scheme.order("Q-2") < scheme.order("Q-3")
    assert scheme.latest_period(["Q-2", "Q-1", "Q-3"]) == "Q-3"
    assert scheme.latest_cycle(["Q-1", "Q-2"]) == "AY-27"


def test_cycle_can_cross_calendar_labels_without_year_parsing():
    scheme = ExplicitAcademicPeriodScheme(
        (("CAL-2026-Q3", "AY27", 10), ("CAL-2026-Q4", "AY27", 20), ("CAL-2027-Q1", "AY27", 30)),
        scheme_id="cross-calendar",
    )
    assert scheme.latest_cycle(["CAL-2026-Q3", "CAL-2027-Q1"]) == "AY27"


def test_unknown_period_is_rejected_instead_of_lexically_sorted():
    scheme = ExplicitAcademicPeriodScheme((("A", "C", 1),), scheme_id="hostile")
    with pytest.raises(ValueError, match="Unknown academic period"):
        scheme.order("B")


def test_uct_year_only_records_keep_legacy_compatibility():
    scheme = LegacyAcademicYearPeriodScheme()
    assert scheme.period_key_for_year(2026) == "2026"
    assert scheme.order("2026") < scheme.order("2027")
    release = get_institution_release("uct", "2026")
    assert release.period_scheme.scheme_id == "legacy-academic-year"


def test_northstar_release_owns_opaque_period_scheme():
    release = select_release("northstar", "northstar-fixture-2027")
    assert release.period_scheme.scheme_id == "northstar-fixture-periods"
    assert release.period_scheme.cycle_key("NS-27-C") == "AY27"
    assert release.period_scheme.order("NS-27-C") < release.period_scheme.order("NS-28-A")


def test_course_code_and_period_schemes_are_independent():
    release = select_release("northstar", "northstar-fixture-2027")
    assert release.course_code_scheme is not release.period_scheme
    assert release.course_code_scheme.infer_academic_level("FOUND-X7") == 0


def test_report_validates_explicit_period_keys_under_selected_release():
    release = select_release("northstar", "northstar-fixture-2027")
    student = StudentRecord(
        "PERIOD-1", "Student", "Systems / Inquiry diploma", [],
        [CourseResult("FOUND-X7", "Foundation", 1, 6, 72, None, 2027, "a1", "NS-27-A")],
        faculty_key="systems", programme_key="systems_inquiry",
    )
    report = compute_report(
        student,
        __import__("fixtures.northstar", fromlist=["catalogue_for"]).catalogue_for(release),
        grading_scheme=release.grading_scheme,
        credit_framework=release.credit_framework,
        course_code_scheme=release.course_code_scheme,
        course_load_framework=release.course_load_framework,
        academic_period_scheme=release.period_scheme,
    )
    assert report.programme_key == "systems_inquiry"


def test_report_rejects_unknown_selected_period():
    release = select_release("northstar", "northstar-fixture-2027")
    student = StudentRecord(
        "PERIOD-2", "Student", "Systems / Inquiry diploma", [],
        [CourseResult("FOUND-X7", "Foundation", 1, 6, 72, None, 2027, "a1", "NOT-KNOWN")],
        faculty_key="systems", programme_key="systems_inquiry",
    )
    from fixtures.northstar import catalogue_for
    with pytest.raises(ValueError, match="Unknown academic period"):
        compute_report(
            student, catalogue_for(release),
            grading_scheme=release.grading_scheme,
            credit_framework=release.credit_framework,
            course_code_scheme=release.course_code_scheme,
            course_load_framework=release.course_load_framework,
            academic_period_scheme=release.period_scheme,
        )


def test_explicit_context_period_is_validated_without_inferencing_history():
    release = select_release("northstar", "northstar-fixture-2027")
    student = StudentRecord("PERIOD-3", "Student", "Systems / Inquiry diploma", [], [], programme_key="systems_inquiry")
    from fixtures.northstar import catalogue_for
    with pytest.raises(ValueError, match="Unknown academic period"):
        compute_report(
            student,
            catalogue_for(release),
            grading_scheme=release.grading_scheme,
            credit_framework=release.credit_framework,
            course_code_scheme=release.course_code_scheme,
            course_load_framework=release.course_load_framework,
            result_context_evidence=[
                ResultContextEvidence("a1", "systems_inquiry", "stage-1", "NOT-KNOWN")
            ],
            academic_period_scheme=release.period_scheme,
        )
