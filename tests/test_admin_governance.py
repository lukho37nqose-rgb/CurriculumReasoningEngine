from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app as app_module

client = TestClient(app_module.app)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _payload(**overrides):
    payload = {
        "actor_name": "Faculty Steward",
        "actor_email": "steward@example.edu",
        "actor_role": "faculty_data_steward",
        "faculty_key": "uct_humanities",
        "course_code": "PHI1024F",
        "field": "course_name",
        "new_value": "Introduction to Philosophy (Governance Test)",
        "reason": "Correcting display metadata from the faculty handbook.",
        "owner_unit": "Humanities Faculty Office",
        "source_page_or_section": "p. 14",
    }
    payload.update(overrides)
    return payload


@pytest.fixture(autouse=True)
def isolated_admin_audit(monkeypatch, tmp_path):
    monkeypatch.delenv("ADMIN_WRITES_ENABLED", raising=False)
    monkeypatch.delenv("ADMIN_WRITE_TOKEN", raising=False)
    monkeypatch.setenv("ADMIN_AUDIT_DIR", str(tmp_path / "admin"))
    app_module._clear_catalogue_caches()
    yield tmp_path / "admin" / "quick_edits.jsonl"
    app_module._clear_catalogue_caches()


def test_admin_permissions_expose_role_matrix_without_enabling_publication():
    response = client.get("/api/v1/admin/permissions")

    assert response.status_code == 200
    data = response.json()
    assert data["writes_enabled"] is False
    assert data["publication_enabled"] is False
    assert "department" in data["quick_edit"]["blocked_tier_1_fields"]
    assert "prerequisites" in data["quick_edit"]["blocked_tier_1_fields"]
    assert "faculty_data_steward" in {role["role"] for role in data["roles"]}


def test_quick_edit_is_disabled_by_default(isolated_admin_audit):
    response = client.post(
        "/api/v1/admin/quick-edit",
        headers={"X-Admin-Token": "test-token"},
        json=_payload(),
    )

    assert response.status_code == 403
    assert not isolated_admin_audit.exists()


def test_quick_edit_applies_runtime_overlay_and_preserves_catalogue_json(
    monkeypatch, isolated_admin_audit
):
    monkeypatch.setenv("ADMIN_WRITES_ENABLED", "1")
    monkeypatch.setenv("ADMIN_WRITE_TOKEN", "test-token")
    data_file = Path("data/uct_humanities/courses.json")
    before_hash = _sha256(data_file)

    response = client.post(
        "/api/v1/admin/quick-edit",
        headers={"X-Admin-Token": "test-token"},
        json=_payload(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "applied"
    assert body["publication_effect"] == "runtime_overlay_only"
    assert _sha256(data_file) == before_hash

    events = [
        json.loads(line)
        for line in isolated_admin_audit.read_text(encoding="utf-8").splitlines()
    ]
    assert len(events) == 1
    assert events[0]["course_code"] == "PHI1024F"
    assert events[0]["old_value"] != events[0]["new_value"]
    assert len(events[0]["event_hash"]) == 64

    catalogue = app_module.get_catalogue("uct_humanities")
    assert (
        catalogue.courses["PHI1024F"].name
        == "Introduction to Philosophy (Governance Test)"
    )

    audit_response = client.get(
        "/api/v1/admin/quick-edits",
        headers={"X-Admin-Token": "test-token"},
    )
    assert audit_response.status_code == 200
    assert audit_response.json()["edits"][0]["change_id"] == body["change_id"]


def test_quick_edit_rejects_fields_that_affect_reasoning(
    monkeypatch, isolated_admin_audit
):
    monkeypatch.setenv("ADMIN_WRITES_ENABLED", "1")
    monkeypatch.setenv("ADMIN_WRITE_TOKEN", "test-token")

    response = client.post(
        "/api/v1/admin/quick-edit",
        headers={"X-Admin-Token": "test-token"},
        json=_payload(field="department", new_value="Philosophy"),
    )

    assert response.status_code == 400
    assert not isolated_admin_audit.exists()


def test_read_only_roles_cannot_submit_quick_edits(monkeypatch, isolated_admin_audit):
    monkeypatch.setenv("ADMIN_WRITES_ENABLED", "1")
    monkeypatch.setenv("ADMIN_WRITE_TOKEN", "test-token")

    response = client.post(
        "/api/v1/admin/quick-edit",
        headers={"X-Admin-Token": "test-token"},
        json=_payload(actor_role="read_only_auditor"),
    )

    assert response.status_code == 403
    assert not isolated_admin_audit.exists()
