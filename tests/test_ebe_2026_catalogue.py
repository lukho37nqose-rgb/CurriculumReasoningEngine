import pytest
from fastapi.testclient import TestClient

from app import app
from engine.catalogue import load_catalogue
from engine.curriculum import CurriculumEvaluator
from engine.models import CourseResult, StudentRecord
from engine.recognition import provisional_open_credit_allocations
from engine.rule_engine import compute_report
from engine.scope import build_programme_scope


client = TestClient(app)


def _pass(scoped, code: str, mark: int = 65, academic_year: int | None = None) -> CourseResult:
    fact = scoped.courses[code]
    return CourseResult(
        code=code,
        name=fact.name,
        nqf_level=fact.nqf_level,
        nqf_credits=fact.nqf_credits,
        mark=mark,
        grade=None,
        academic_year=academic_year,
    )


def _unknown(code: str, credits: int, level: int, mark: int = 65, academic_year: int | None = None) -> CourseResult:
    return CourseResult(
        code=code,
        name="Transcript-only approved elective",
        nqf_level=level,
        nqf_credits=credits,
        mark=mark,
        grade=None,
        academic_year=academic_year,
    )


def _rule(programme, rule_id: str):
    return next(rule for rule in programme.curriculum_rules if rule.get("id") == rule_id)


def test_ebe_inventory_and_version():
    catalogue = load_catalogue("uct_ebe")
    assert len(catalogue.programmes) == 28
    assert len(catalogue.courses) == 354
    assert catalogue.catalogue_version == "2026.1-ebe"
    assert not catalogue.data_issues


def test_every_ebe_programme_and_pathway_scope_builds_without_missing_course_references():
    catalogue = load_catalogue("uct_ebe")
    combinations = 0
    for key, programme in catalogue.programmes.items():
        pathways = list(programme.pathways) or [""]
        for pathway_key in pathways:
            scoped, scope = build_programme_scope("uct_ebe", catalogue, key, pathway_key)
            combinations += 1
            assert scoped.programme_key == key
            assert scoped.pathway_key == pathway_key
            assert not any(
                "missing course definitions" in issue.lower()
                for issue in scoped.data_issues
            )
            if programme.availability != "restricted":
                assert scope.course_codes
    assert combinations == 40


def test_current_and_legacy_engineering_cohorts_are_not_merged():
    catalogue = load_catalogue("uct_ebe")
    current, current_scope = build_programme_scope(
        "uct_ebe", catalogue, "civil_engineering_4", "current_560"
    )
    legacy, legacy_scope = build_programme_scope(
        "uct_ebe", catalogue, "civil_engineering_4", "legacy_576"
    )
    assert current_scope.status == "verified"
    assert legacy_scope.status == "unverified"
    assert current.programmes["civil_engineering_4"].total_nqf_credits == 560
    assert any(
        rule.get("id") == "legacy_credits" and rule.get("required") == 576
        for rule in legacy.programmes["civil_engineering_4"].pathways["legacy_576"].curriculum_rules
    )


def test_corrected_chemical_level_8_elective_credit_values():
    catalogue = load_catalogue("uct_ebe")
    assert catalogue.courses["CHE4057F"].nqf_credits == 8
    assert catalogue.courses["CHE4058Z"].nqf_credits == 8
    assert catalogue.courses["CHE4068F"].nqf_credits == 16


def test_chemical_humanities_pool_matches_published_categories_and_exclusions():
    catalogue = load_catalogue("uct_ebe")
    scoped, _ = build_programme_scope("uct_ebe", catalogue, "chemical_engineering_4")
    assert "AGE1002S" in scoped.courses
    assert "ANS1401S" in scoped.courses
    assert "AFS1100S" in scoped.courses
    assert "ASL2202F" in scoped.courses
    assert "POL1004F" in scoped.courses
    assert "SLL1054F" in scoped.courses
    assert "ECO1010F" not in scoped.courses
    assert "FAM1000S" not in scoped.courses
    assert "SLL1002F" not in scoped.courses


def test_transcript_only_free_elective_is_counted_provisionally_not_silently_verified():
    catalogue = load_catalogue("uct_ebe")
    scoped, _ = build_programme_scope("uct_ebe", catalogue, "chemical_engineering_4")
    student = StudentRecord(
        "CHE001",
        "Chemical Student",
        "BSc Engineering Chemical Engineering",
        [],
        [_unknown("ECO1010F", 15, 5, 70)],
        faculty_key="uct_ebe",
        programme_key="chemical_engineering_4",
        years_registered=1,
    )
    evaluator = CurriculumEvaluator(student, scoped)
    free_rule = _rule(scoped.programmes["chemical_engineering_4"], "free_elective")
    free = evaluator.evaluate(free_rule)
    assert free.complete
    assert free.current == 15
    assert free.status == "unverified"
    assert free.used_course_codes == ["ECO1010F"]

    report = compute_report(student, scoped)
    assert report.credits_completed == 15
    credit_requirement = next(req for req in report.requirements if req.id == "credits")
    assert credit_requirement.status == "unverified"
    assert "ECO1010F" in credit_requirement.detail
    assert report.graduation_status == "not_eligible"
    assert any("provisionally includes" in warning.lower() for warning in report.warnings)


def test_unknown_course_is_not_counted_without_a_published_open_or_approved_pool():
    catalogue = load_catalogue("uct_humanities")
    scoped, _ = build_programme_scope("uct_humanities", catalogue, "bsocsc_regular")
    student = StudentRecord(
        "HUM-X",
        "Humanities Student",
        "Bachelor of Social Science",
        [],
        [_unknown("ZZZ1000F", 18, 5, 70)],
        faculty_key="uct_humanities",
        programme_key="bsocsc_regular",
    )
    report = compute_report(student, scoped)
    assert report.credits_completed == 0
    assert any("not counted automatically" in warning.lower() for warning in report.warnings)


def test_ece_complementary_pool_does_not_consume_an_approved_csc_final_elective():
    catalogue = load_catalogue("uct_ebe")
    scoped, _ = build_programme_scope(
        "uct_ebe", catalogue, "electrical_computer_engineering_4", "current_560"
    )
    results = [
        _pass(scoped, "EEE4114F"),
        _pass(scoped, "EEE4118F"),
        _unknown("CSC3007S", 16, 7),
        _unknown("ECO1010F", 18, 5),
    ]
    student = StudentRecord(
        "ECE001",
        "ECE Student",
        "BSc Engineering Electrical and Computer Engineering",
        [],
        results,
        faculty_key="uct_ebe",
        programme_key="electrical_computer_engineering_4",
        pathway_key="current_560",
    )
    allocations = {a.rule_id: a for a in provisional_open_credit_allocations(student, scoped)}
    assert [r.code for r in allocations["complementary"].results] == ["ECO1010F"]
    assert [r.code for r in allocations["final_total"].results] == ["CSC3007S"]

    evaluator = CurriculumEvaluator(student, scoped)
    programme = scoped.programmes["electrical_computer_engineering_4"]
    complementary = evaluator.evaluate(_rule(programme, "complementary"))
    final_total = evaluator.evaluate(_rule(programme, "final_total"))
    assert complementary.complete and complementary.current == 18
    assert final_total.complete and final_total.current == 48
    assert final_total.status == "unverified"


def test_first_year_chemical_progression_uses_academic_year_credit_evidence():
    catalogue = load_catalogue("uct_ebe")
    scoped, _ = build_programme_scope("uct_ebe", catalogue, "chemical_engineering_4")
    results = []
    credits = 0
    for code in scoped.programmes["chemical_engineering_4"].required_courses:
        result = _pass(scoped, code, academic_year=2026)
        results.append(result)
        credits += result.nqf_credits
        if credits >= 102:
            break
    student = StudentRecord(
        "CHE-PROG",
        "Chemical Student",
        "BSc Engineering Chemical Engineering",
        [],
        results,
        faculty_key="uct_ebe",
        programme_key="chemical_engineering_4",
        years_registered=1,
    )
    report = compute_report(student, scoped)
    assert report.exclusion_risk.assessed
    assert report.exclusion_risk.status == "verified"
    assert not report.exclusion_risk.at_risk
    assert "102-credit threshold" in report.exclusion_risk.basis


def test_published_credit_conflicts_block_definitive_positive_outcomes():
    catalogue = load_catalogue("uct_ebe")
    for key in ("bas", "construction_studies", "property_studies"):
        scoped, _ = build_programme_scope("uct_ebe", catalogue, key)
        results = [_pass(scoped, code, 80) for code in scoped.courses]
        student = StudentRecord(
            f"{key}-student",
            "EBE Student",
            scoped.programmes[key].name,
            [],
            results,
            faculty_key="uct_ebe",
            programme_key=key,
            years_registered=scoped.programmes[key].minimum_duration_years,
        )
        report = compute_report(student, scoped)
        assert report.graduation_status != "eligible"
        assert any(req.status == "conflict" for req in report.requirements)


def test_restricted_transfer_routes_are_visible_but_not_self_certifying():
    catalogue = load_catalogue("uct_ebe")
    restricted = [p for p in catalogue.programmes.values() if p.availability == "restricted"]
    assert len(restricted) == 5
    for programme in restricted:
        assert not programme.scope_verified
        assert any(rule.get("type") == "manual" for rule in programme.curriculum_rules)


def test_ebe_faculty_endpoint_exposes_routes_and_pathways():
    response = client.get("/faculties/uct_ebe")
    assert response.status_code == 200
    body = response.json()
    assert len(body["programmes"]) == 28
    civil = next(p for p in body["programmes"] if p["key"] == "civil_engineering_4")
    assert {path["key"] for path in civil["pathways"]} == {"current_560", "legacy_576"}
    assert next(p for p in body["programmes"] if p["key"] == "geomatics_geoinformatics_egs_4")["availability"] == "continuing_only"
