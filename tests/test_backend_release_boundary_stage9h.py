import pytest
from fastapi.testclient import TestClient
from fixtures.northstar import select_release

import app as app_module
from app import app
from curriculum_reasoning_engine.institutions import (
    register_institution_release,
    unregister_institution_release,
)


@pytest.fixture(autouse=True)
def northstar_release():
    release = select_release("northstar", "northstar-fixture-2027")
    register_institution_release(release)
    try:
        yield release
    finally:
        unregister_institution_release(release.institution_id, release.release_id)


def _body(**overrides):
    body = {
        "institution_id": "northstar",
        "release_id": "northstar-fixture-2027",
        "faculty": "systems",
        "programme_key": "systems_inquiry",
        "student_id": "N-9H",
        "name": "Northstar Student",
        "programme": "Systems / Inquiry diploma",
        "declared_majors": [],
        "results": [
            {"code": "FOUND-X7", "nqf_credits": 6, "nqf_level": 1, "mark": 72},
            {"code": "PATH-Z9", "nqf_credits": 9, "nqf_level": 2, "mark": 62},
        ],
        "academic_record_coverage": [
            {
                "course_codes": ["FOUND-X7", "CORE-Q2", "PATH-Z9", "ALT-V8", "CAP-R4", "LAB-T6"],
                "coverage_state": "complete",
                "source_reference": "Synthetic Northstar result snapshot",
                "authority": "Synthetic registry",
                "verification_status": "verified",
            }
        ],
    }
    body.update(overrides)
    return body


def test_explicit_northstar_json_request_uses_selected_release_and_evidence():
    response = TestClient(app).post("/analyse/json", json=_body())
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["programme_key"] == "systems_inquiry"
    assert payload["progression_policy_assessments"]
    assert "NORTHSTAR-2027-FOUNDATION-COMPLETION" in {
        item["policy_id"] for item in payload["progression_policy_assessments"]
    }


def test_backend_recognition_enters_as_completion_evidence_without_local_attempt():
    response = TestClient(app).post(
        "/analyse/json",
        json=_body(
            course_completion_recognition=[
                {
                    "recognition_id": "EXT-77",
                    "target_course_code": "CORE-Q2",
                    "source_learning_identity": "external-learning-77",
                    "authority": "Northstar Recognition Board",
                    "source_reference": "Synthetic Northstar recognition register",
                    "verification_status": "verified",
                }
            ],
            academic_record_coverage=[],
        ),
    )
    assert response.status_code == 200, response.text
    assert "CORE-Q2" not in {
        result["code"] for result in _body()["results"]
    }


def test_explicit_uct_matches_legacy_default_request():
    body = {
        "faculty": "uct_humanities",
        "programme_key": "bsocsc_regular",
        "student_id": "N-9H-UCT",
        "name": "UCT Student",
        "programme": "Bachelor of Social Science",
        "declared_majors": [],
        "results": [],
    }
    legacy = TestClient(app).post("/analyse/json", json=body)
    explicit = TestClient(app).post(
        "/analyse/json", json={**body, "institution_id": "uct", "release_id": "2026"}
    )
    assert legacy.status_code == explicit.status_code == 200
    assert legacy.json() == explicit.json()


@pytest.mark.parametrize(
    "body, message",
    [
        ({"institution_id": "missing", "release_id": "2026"}, "Unknown institution release"),
        ({"institution_id": "northstar", "release_id": "missing"}, "Unknown institution release"),
        ({"institution_id": "northstar"}, "must be supplied together"),
    ],
)
def test_release_selection_errors_are_explicit(body, message):
    request = _body()
    request.update(body)
    if body == {"institution_id": "northstar"}:
        request.pop("release_id")
    response = TestClient(app).post("/analyse/json", json=request)
    assert response.status_code == 422
    assert message in response.json()["detail"]


def test_selected_release_rejects_uct_package_without_fallback():
    response = TestClient(app).post(
        "/analyse/json", json=_body(faculty="uct_humanities", programme_key="bsocsc_regular")
    )
    assert response.status_code == 422


def test_release_selection_does_not_mutate_global_uct_default():
    assert app_module.ACTIVE_INSTITUTION_RELEASE.institution_id == "uct"
    assert app_module.ACTIVE_INSTITUTION_RELEASE.release_id == "2026"
    northstar = TestClient(app).post("/analyse/json", json=_body())
    uct = TestClient(app).post(
        "/analyse/json",
        json={
            "faculty": "uct_humanities",
            "programme_key": "bsocsc_regular",
            "student_id": "N-9H-UCT-2",
            "name": "UCT Student",
            "programme": "Bachelor of Social Science",
            "declared_majors": [],
            "results": [],
        },
    )
    assert northstar.status_code == 200
    assert uct.status_code == 200
    assert app_module.ACTIVE_INSTITUTION_RELEASE.institution_id == "uct"
