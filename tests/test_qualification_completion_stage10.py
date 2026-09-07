from fixtures.northstar import catalogue_for, select_release

from engine.models import AcademicRecordCoverageEvidence, CourseResult, StudentRecord
from engine.rule_engine import compute_report


def _student(codes):
    catalogue = catalogue_for(select_release("northstar", "northstar-fixture-2027"))
    results = [
        CourseResult(
            code,
            catalogue.courses[code].name,
            catalogue.courses[code].nqf_level,
            catalogue.courses[code].nqf_credits,
            70,
            None,
            2027,
            f"a-{code}",
            "NS-27-A",
        )
        for code in codes
    ]
    return StudentRecord(
        "N-Q",
        "Northstar Student",
        "Systems / Inquiry diploma",
        [],
        results,
        faculty_key="systems",
        programme_key="systems_inquiry",
    )


def _report(codes):
    release = select_release("northstar", "northstar-fixture-2027")
    catalogue = catalogue_for(release)
    student = _student(codes)
    coverage = AcademicRecordCoverageEvidence(
        tuple(catalogue.courses), "complete", "Synthetic result register", "Northstar registry", "verified"
    )
    return compute_report(
        student,
        catalogue,
        grading_scheme=release.grading_scheme,
        credit_framework=release.credit_framework,
        course_code_scheme=release.course_code_scheme,
        course_load_framework=release.course_load_framework,
        academic_record_coverage_evidence=[coverage],
        academic_period_scheme=release.period_scheme,
    )


def test_governed_requirements_can_establish_academic_completion_without_graduation_claim():
    report = _report(["FOUND-X7", "CORE-Q2", "PATH-Z9", "CAP-R4"])
    assert report.qualification_completion.outcome == "satisfied"
    assert report.qualification_completion.status == "unverified"
    assert report.qualification_completion.assessment_complete is False
    assert report.qualification_completion is not None


def test_credits_do_not_replace_missing_capstone_requirement():
    report = _report(["FOUND-X7", "CORE-Q2", "PATH-Z9"])
    assert report.qualification_completion.outcome in {"not_satisfied", "unresolved"}
    assert "capstone" in report.qualification_completion.required_requirement_ids


def test_recognition_can_feed_completion_without_creating_a_result():
    report = _report(["FOUND-X7", "PATH-Z9", "CAP-R4"])
    assert report.qualification_completion.outcome in {"unresolved", "not_satisfied"}
    assert all(result.code != "CORE-Q2" for result in _student(["FOUND-X7"]).results)
