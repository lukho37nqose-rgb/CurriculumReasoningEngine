from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import app
from engine.catalogue import load_catalogue
from engine.curriculum import CurriculumEvaluator
from engine.models import CourseResult, StudentRecord
from engine.rule_engine import compute_report
from engine.scope import build_programme_scope

client = TestClient(app)


def _passed_from_scope(scoped, code: str, mark: int = 65) -> CourseResult:
    fact = scoped.courses[code]
    return CourseResult(
        code=code,
        name=fact.name,
        nqf_level=fact.nqf_level,
        nqf_credits=fact.nqf_credits,
        mark=mark,
        grade=None,
    )


def test_complete_humanities_route_inventory_is_present():
    catalogue = load_catalogue("uct_humanities")
    assert len(catalogue.programmes) == 24
    assert len(catalogue.courses) == 888
    assert len(catalogue.majors) == 42
    assert catalogue.catalogue_version == "2026.2-humanities-complete"


@pytest.mark.parametrize(
    "programme_key",
    [
        "advanced_certificate_senior_phase",
        "advanced_diploma_school_leadership",
        "bachelor_social_work",
        "diploma_music_performance_regular",
        "diploma_music_performance_extended",
        "bachelor_music_regular",
        "bachelor_music_extended",
        "diploma_theatre_performance",
        "ba_theatre_performance",
    ],
)
def test_pathway_required_routes_reject_an_unscoped_analysis(programme_key):
    catalogue = load_catalogue("uct_humanities")
    with pytest.raises(
        ValueError, match="requires a pathway|requires a pathway or stream"
    ):
        build_programme_scope("uct_humanities", catalogue, programme_key)


def test_every_programme_and_pathway_builds_a_nonempty_consistent_scope():
    catalogue = load_catalogue("uct_humanities")
    for key, programme in catalogue.programmes.items():
        pathway_keys = list(programme.pathways) or [""]
        for pathway_key in pathway_keys:
            scoped, scope = build_programme_scope(
                "uct_humanities", catalogue, key, pathway_key
            )
            assert scoped.programme_key == key
            assert scoped.pathway_key == pathway_key
            assert scope.course_codes
            assert not any(
                "missing course definitions" in issue.lower()
                for issue in scoped.data_issues
            )


def test_higher_certificate_acet_can_reach_verified_eligibility():
    full = load_catalogue("uct_humanities")
    scoped, _ = build_programme_scope("uct_humanities", full, "higher_certificate_acet")
    codes = ["EDN1031FS", "EDN1030FS", "EDN1032FS"]
    student = StudentRecord(
        "HC001",
        "Certificate Student",
        "Higher Certificate in Adult and Community Education and Training",
        [],
        [_passed_from_scope(scoped, code) for code in codes],
        faculty_key="uct_humanities",
        programme_key="higher_certificate_acet",
        years_registered=1,
    )
    report = compute_report(student, scoped)
    assert report.graduation_status == "eligible"
    assert report.credits_completed == 120
    assert report.scope_status == "verified"


def test_higher_certificate_acet_missing_final_module_is_not_eligible():
    full = load_catalogue("uct_humanities")
    scoped, _ = build_programme_scope("uct_humanities", full, "higher_certificate_acet")
    student = StudentRecord(
        "HC002",
        "Certificate Student",
        "Higher Certificate in Adult and Community Education and Training",
        [],
        [
            _passed_from_scope(scoped, "EDN1031FS"),
            _passed_from_scope(scoped, "EDN1030FS"),
        ],
        faculty_key="uct_humanities",
        programme_key="higher_certificate_acet",
        years_registered=1,
    )
    report = compute_report(student, scoped)
    assert report.graduation_status == "not_eligible"
    core = next(
        req for req in report.requirements if req.id == "curriculum:hc_acet_core"
    )
    assert not core.complete


def test_social_work_pathways_do_not_leak_into_each_other():
    full = load_catalogue("uct_humanities")
    psychology, _ = build_programme_scope(
        "uct_humanities", full, "bachelor_social_work", "psychology"
    )
    sociology, _ = build_programme_scope(
        "uct_humanities", full, "bachelor_social_work", "sociology"
    )
    assert "PSY3005F" in psychology.courses
    assert "SOC3029S" not in psychology.courses
    assert "SOC3029S" in sociology.courses
    assert "PSY3005F" not in sociology.courses


def test_theatre_concentrations_are_kept_coherent():
    full = load_catalogue("uct_humanities")
    acting, _ = build_programme_scope(
        "uct_humanities", full, "ba_theatre_performance", "acting"
    )
    dance, _ = build_programme_scope(
        "uct_humanities", full, "ba_theatre_performance", "dance_performance"
    )
    assert {"TDP3042W", "TDP4040W"} <= set(acting.courses)
    assert "TDP3046W" not in acting.courses
    assert {"TDP3046W", "TDP4045W"} <= set(dance.courses)
    assert "TDP3042W" not in dance.courses


def test_music_streams_remain_explicitly_unverified_instead_of_false_positive():
    full = load_catalogue("uct_humanities")
    scoped, scope = build_programme_scope(
        "uct_humanities", full, "diploma_music_performance_regular", "classical"
    )
    assert scope.status == "unverified"
    student = StudentRecord(
        "MUS001",
        "Music Student",
        "Diploma in Music Performance",
        [],
        [_passed_from_scope(scoped, code, 75) for code in scoped.courses],
        faculty_key="uct_humanities",
        programme_key="diploma_music_performance_regular",
        pathway_key="classical",
        years_registered=3,
    )
    report = compute_report(student, scoped)
    assert report.graduation_status != "eligible"
    assert any(
        req.status in {"unverified", "discretionary", "provisional"}
        for req in report.requirements
        if req.blocking
    )


def test_structured_programmes_do_not_use_general_degree_distinction_formula():
    full = load_catalogue("uct_humanities")
    scoped, _ = build_programme_scope("uct_humanities", full, "higher_certificate_acet")
    student = StudentRecord(
        "HC003",
        "Certificate Student",
        "Higher Certificate in Adult and Community Education and Training",
        [],
        [
            _passed_from_scope(scoped, "EDN1031FS", 80),
            _passed_from_scope(scoped, "EDN1030FS", 80),
            _passed_from_scope(scoped, "EDN1032FS", 80),
        ],
        faculty_key="uct_humanities",
        programme_key="higher_certificate_acet",
        years_registered=1,
    )
    report = compute_report(student, scoped)
    assert report.distinction.status == "unverified"
    assert not report.distinction.qualification_eligible
    assert "structured qualification" in report.distinction.reason.lower()


def test_route_availability_is_not_hidden():
    catalogue = load_catalogue("uct_humanities")
    assert catalogue.programmes["advanced_diploma_opera"].availability == "not_offered"
    assert (
        catalogue.programmes["advanced_diploma_theatre"].availability == "not_offered"
    )
    assert (
        catalogue.programmes["ba_fine_art_extended"].availability == "continuing_only"
    )
    assert (
        catalogue.programmes["bachelor_music_extended"].availability
        == "continuing_only"
    )


def test_non_tdp_elective_count_excludes_tdp_courses():
    full = load_catalogue("uct_humanities")
    scoped, _ = build_programme_scope(
        "uct_humanities", full, "ba_theatre_performance", "acting"
    )
    student = StudentRecord(
        "TDP001",
        "Theatre Student",
        "Bachelor of Arts in Theatre and Performance",
        [],
        [
            _passed_from_scope(scoped, "TDP1017H"),
            _passed_from_scope(scoped, "TDP1027F"),
        ],
        faculty_key="uct_humanities",
        programme_key="ba_theatre_performance",
        pathway_key="acting",
    )
    evaluator = CurriculumEvaluator(student, scoped)
    rule = next(
        item
        for item in scoped.programmes["ba_theatre_performance"].curriculum_rules
        if item["id"] == "batp_y1_electives"
    )
    evaluation = evaluator.evaluate(rule)
    assert evaluation.current == 0
    assert not evaluation.complete


def test_faculty_and_programme_endpoints_expose_complete_route_metadata():
    faculty = client.get("/faculties/uct_humanities")
    assert faculty.status_code == 200
    body = faculty.json()
    assert len(body["programmes"]) == 24
    bsw = next(p for p in body["programmes"] if p["key"] == "bachelor_social_work")
    assert {path["key"] for path in bsw["pathways"]} == {"psychology", "sociology"}

    missing = client.get(
        "/programme",
        params={
            "faculty_key": "uct_humanities",
            "programme_key": "bachelor_social_work",
        },
    )
    assert missing.status_code == 422

    selected = client.get(
        "/programme",
        params={
            "faculty_key": "uct_humanities",
            "programme_key": "bachelor_social_work",
            "pathway_key": "psychology",
        },
    )
    assert selected.status_code == 200
    assert selected.json()["scope"]["pathway_key"] == "psychology"


def test_frontend_contains_pathway_routing_and_scoped_analysis_parameters():
    html = Path("static/index.html").read_text(encoding="utf-8")
    javascript = Path("static/app.js").read_text(encoding="utf-8")
    assert 'id="pathwaySelect"' in html
    assert 'id="majorOneField"' in html
    assert 'params.set("pathway", pathway.key)' in javascript
    assert 'params.set("pathway_key", pathway.key)' in javascript
    assert "api(`/api/v1/analyse?${params}`" in javascript


def test_theatre_first_year_studiowork_progression_mark_is_machine_checked():
    full = load_catalogue("uct_humanities")
    scoped, _ = build_programme_scope(
        "uct_humanities", full, "diploma_theatre_performance", "acting"
    )
    programme = scoped.programmes["diploma_theatre_performance"]
    mark_rule = next(
        rule
        for rule in programme.curriculum_rules
        if rule["id"] == "dtp_studiowork_mark"
    )

    below = StudentRecord(
        "TDP002",
        "Theatre Student",
        "Diploma in Theatre and Performance",
        [],
        [_passed_from_scope(scoped, "TDP1046W", 55)],
        faculty_key="uct_humanities",
        programme_key="diploma_theatre_performance",
        pathway_key="acting",
    )
    assert not CurriculumEvaluator(below, scoped).evaluate(mark_rule).complete

    threshold = StudentRecord(
        "TDP003",
        "Theatre Student",
        "Diploma in Theatre and Performance",
        [],
        [_passed_from_scope(scoped, "TDP1046W", 60)],
        faculty_key="uct_humanities",
        programme_key="diploma_theatre_performance",
        pathway_key="acting",
    )
    assert CurriculumEvaluator(threshold, scoped).evaluate(mark_rule).complete
