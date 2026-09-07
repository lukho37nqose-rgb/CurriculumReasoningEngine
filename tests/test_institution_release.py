import pytest
from fastapi.testclient import TestClient

import app as app_module
from app import ACTIVE_INSTITUTION_RELEASE, app, get_catalogue
from curriculum_reasoning_engine.adapters.transcripts import TranscriptAdapter
from curriculum_reasoning_engine.adapters.transcripts.uct import UCTTranscriptAdapter
from curriculum_reasoning_engine.institutions import get_institution_release
from curriculum_reasoning_engine.institutions.catalogues import CatalogueDescriptor
from curriculum_reasoning_engine.institutions.routing import RouteResolution
from curriculum_reasoning_engine.institutions.uct import UCTCatalogueResolver, UCTRouteResolver
from engine.catalogue import load_catalogue
from engine.models import CourseResult, StudentRecord
from engine.rule_engine import compute_report
from engine.scope import build_programme_scope
from engine.utils import _infer_faculty_key, _infer_programme_key

client = TestClient(app)


EXPECTED_UCT_UNITS = {
    "uct_commerce",
    "uct_ebe",
    "uct_health",
    "uct_humanities",
    "uct_law",
    "uct_science",
}

EXPECTED_STABLE_TO_LEGACY_CATALOGUES = {
    "commerce": "uct_commerce",
    "ebe": "uct_ebe",
    "health": "uct_health",
    "humanities": "uct_humanities",
    "law": "uct_law",
    "science": "uct_science",
}


def test_uct_2026_release_resolves_through_registry():
    release = get_institution_release("uct", "2026")
    assert release.institution_id == "uct"
    assert release.institution_display_name == "University of Cape Town"
    assert release.release_id == "2026"
    assert release.academic_year == 2026


def test_uct_2026_release_exposes_exactly_current_enabled_units():
    release = get_institution_release("uct", "2026")
    assert {unit.key for unit in release.academic_units} == EXPECTED_UCT_UNITS
    assert {unit.catalogue_key for unit in release.academic_units} == EXPECTED_UCT_UNITS
    assert release.enabled_catalogue_keys == frozenset(EXPECTED_UCT_UNITS)
    assert all(unit.available for unit in release.academic_units)


def test_release_catalogue_keys_still_resolve_with_existing_loader():
    release = get_institution_release("uct", "2026")
    for unit in release.academic_units:
        catalogue = load_catalogue(unit.catalogue_key)
        assert catalogue.faculty_key == unit.catalogue_key
        assert catalogue.programmes
        assert catalogue.courses


def test_uct_2026_release_exposes_catalogue_resolution():
    release = get_institution_release("uct", "2026")
    assert isinstance(release.catalogue_resolver, UCTCatalogueResolver)
    descriptors = release.available_catalogues()
    assert all(isinstance(item, CatalogueDescriptor) for item in descriptors)
    assert {item.catalogue_key for item in descriptors} == EXPECTED_UCT_UNITS


@pytest.mark.parametrize(
    ("stable_key", "legacy_key"),
    sorted(EXPECTED_STABLE_TO_LEGACY_CATALOGUES.items()),
)
def test_stable_academic_unit_resolves_to_existing_uct_catalogue_package(
    stable_key, legacy_key
):
    release = get_institution_release("uct", "2026")
    descriptor = release.resolve_catalogue(stable_key)
    assert descriptor.institution_id == "uct"
    assert descriptor.release_id == "2026"
    assert descriptor.academic_unit_key == stable_key
    assert descriptor.catalogue_key == legacy_key
    assert descriptor.courses_path.name == "courses.json"
    assert descriptor.requirements_path.name == "degree_requirements.json"

    legacy_descriptor = release.resolve_catalogue(legacy_key)
    assert legacy_descriptor == descriptor


def test_every_release_resolved_catalogue_still_loads_through_existing_loader():
    release = get_institution_release("uct", "2026")
    for descriptor in release.available_catalogues():
        catalogue = load_catalogue(descriptor.catalogue_key)
        assert catalogue.faculty_key == descriptor.catalogue_key
        assert catalogue.courses
        assert catalogue.programmes


def test_unknown_catalogue_resolution_fails_safely():
    release = get_institution_release("uct", "2026")
    with pytest.raises(KeyError, match="Unknown academic unit"):
        release.resolve_catalogue("not_a_unit")

    with pytest.raises(ValueError, match="Unknown faculty catalogue"):
        get_catalogue("not_a_unit")


def test_app_catalogue_access_uses_active_release_resolution():
    app_module._clear_catalogue_caches()
    catalogue = get_catalogue("humanities")
    assert catalogue.faculty_key == "uct_humanities"
    assert set(app_module._catalogues) == {"uct_humanities"}


def test_legacy_load_catalogue_compatibility_still_works():
    catalogue = load_catalogue("uct_humanities")
    assert catalogue.faculty_key == "uct_humanities"
    assert "bsocsc_regular" in catalogue.programmes


def test_catalogue_cache_is_isolated_by_resolved_academic_unit():
    app_module._clear_catalogue_caches()
    humanities = get_catalogue("humanities")
    science = get_catalogue("science")

    assert humanities is not science
    assert humanities.faculty_key == "uct_humanities"
    assert science.faculty_key == "uct_science"
    assert set(app_module._catalogues) == {"uct_humanities", "uct_science"}


def test_application_bootstrap_derives_faculty_metadata_from_active_release():
    response = client.get("/api/v1/bootstrap")
    assert response.status_code == 200
    bootstrap_faculties = response.json()["faculties"]
    release_cards = [
        unit.card_payload() for unit in ACTIVE_INSTITUTION_RELEASE.academic_units
    ]
    assert bootstrap_faculties == release_cards


def test_unknown_institution_release_and_unit_fail_safely():
    with pytest.raises(KeyError, match="Unknown institution release"):
        get_institution_release("unknown", "2026")

    release = get_institution_release("uct", "2026")
    with pytest.raises(KeyError, match="Unknown academic unit"):
        release.academic_unit("not_a_unit")


def test_unknown_application_unit_returns_existing_404_behaviour():
    response = client.get("/faculties/not_a_unit")
    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown faculty."


@pytest.mark.parametrize(
    ("label", "faculty_key", "programme_key"),
    [
        ("Bachelor of Social Science", "uct_humanities", "bsocsc_regular"),
        ("Bachelor of Social Science Extended", "uct_humanities", "bsocsc_extended"),
        ("Bachelor of Arts", "uct_humanities", "ba_regular"),
        ("Bachelor of Commerce CB25ACC01", "uct_commerce", "cb025acc01"),
        ("Bachelor of Science in Engineering", "uct_ebe", "unknown_programme"),
        ("Bachelor of Laws 3-year Graduate Stream", "uct_law", "llb_three_year_graduate"),
        ("Bachelor of Science Extended SB016", "uct_science", "bsc_science_edp"),
        ("Bachelor of Medicine and Bachelor of Surgery", "uct_health", "unknown_programme"),
        ("Unknown Credential", "unknown_faculty", "unknown_programme"),
    ],
)
def test_uct_route_resolver_preserves_legacy_representative_inference(
    label, faculty_key, programme_key
):
    release = get_institution_release("uct", "2026")
    resolution = release.resolve_route(label)
    assert isinstance(resolution, RouteResolution)
    assert resolution.academic_unit_key == faculty_key
    assert resolution.catalogue_key == faculty_key
    assert resolution.programme_key == programme_key
    assert resolution.pathway_key == ""
    assert release.infer_academic_unit(label) == _infer_faculty_key(label)
    assert release.infer_programme(label) == _infer_programme_key(label)


def test_uct_2026_release_exposes_route_resolver():
    release = get_institution_release("uct", "2026")
    assert isinstance(release.route_resolver, UCTRouteResolver)
    assert release.resolve_route("Unknown Programme").status == "unknown"


def test_uct_2026_release_exposes_transcript_adapter():
    release = get_institution_release("uct", "2026")
    assert isinstance(release.transcript_adapter, TranscriptAdapter)
    assert isinstance(release.transcript_adapter, UCTTranscriptAdapter)
    assert release.transcript_adapter.supported_formats == ("text", "pdf")


def test_app_transcript_mismatch_behaviour_remains_unchanged():
    response = client.post(
        "/analyse/json",
        json={
            "faculty": "uct_humanities",
            "programme_key": "bsocsc_regular",
            "student_id": "T-STAGE2-MISMATCH",
            "name": "Student",
            "programme": "Bachelor of Commerce",
            "declared_majors": [],
            "results": [],
        },
    )
    assert response.status_code == 422
    assert "appears to belong to uct_commerce" in response.json()["detail"]


def test_incomplete_transcript_label_can_still_bind_to_explicit_route():
    response = client.post(
        "/analyse/json",
        json={
            "faculty": "uct_humanities",
            "programme_key": "bsocsc_extended",
            "student_id": "T-STAGE2-ROUTE",
            "name": "Student",
            "programme": "Bachelor of Social Science",
            "declared_majors": [],
            "results": [],
        },
    )
    assert response.status_code == 200
    assert response.json()["programme_key"] == "bsocsc_extended"


def test_representative_academic_report_is_unchanged_by_resolver_boundary():
    full = load_catalogue("uct_humanities")
    scoped, _ = build_programme_scope("uct_humanities", full, "bsocsc_regular")
    student = StudentRecord(
        "T-STAGE2-REPORT",
        "Student",
        "Bachelor of Social Science",
        ["philosophy"],
        [CourseResult("PHI1024F", "Introduction to Philosophy", 5, 18, 65, "2-")],
        faculty_key="uct_humanities",
        programme_key="bsocsc_regular",
    )

    report = compute_report(student, scoped)

    assert report.faculty_key == "uct_humanities"
    assert report.programme_key == "bsocsc_regular"
    assert report.graduation_status == "not_eligible"
    assert report.graduation_eligible is False


def test_generic_routing_contracts_do_not_own_uct_policy_mappings():
    import inspect

    import curriculum_reasoning_engine.institutions.catalogues as catalogues
    import curriculum_reasoning_engine.institutions.models as models
    import curriculum_reasoning_engine.institutions.routing as routing
    import engine.utils as utils

    generic_source = (
        inspect.getsource(routing)
        + inspect.getsource(catalogues)
        + inspect.getsource(models)
    )
    assert "uct_" not in generic_source.lower()
    assert "bachelor of social science" not in generic_source.lower()
    assert "llb" not in generic_source.lower()

    utils_source = inspect.getsource(utils)
    assert "get_institution_release" in utils_source
    assert "Bachelor of Science" not in utils_source
    assert "bachelor of science" not in utils_source


def test_uct_catalogue_mapping_is_owned_by_uct_institution_implementation():
    resolver = UCTCatalogueResolver()
    assert resolver.resolve_catalogue("humanities").catalogue_key == "uct_humanities"
    assert resolver.resolve_catalogue("uct_humanities").academic_unit_key == "humanities"


def test_app_uses_active_transcript_adapter_boundary():
    import inspect

    import app as app_module

    source = inspect.getsource(app_module)
    assert "TRANSCRIPT_ADAPTER" in source
    assert "from engine.parser" not in source
