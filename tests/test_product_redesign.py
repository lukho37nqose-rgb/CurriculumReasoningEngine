from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import app
from engine.models import CourseResult, StudentRecord

client = TestClient(app)


def test_bootstrap_exposes_decision_model_and_lightweight_faculties():
    response = client.get("/api/v1/bootstrap")
    assert response.status_code == 200
    data = response.json()
    assert data["product"]["name"] == "CurriculumAdvisor"
    assert [lens["key"] for lens in data["decision_lenses"]] == ["position", "blockers", "next"]
    assert len(data["faculties"]) == 6
    assert all("programmes" not in faculty for faculty in data["faculties"])
    assert data["capabilities"]["live_timetable"] is False


def test_ready_loads_every_enabled_faculty_catalogue():
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert set(data["faculties"]) == {
        "uct_commerce", "uct_ebe", "uct_health", "uct_humanities", "uct_law", "uct_science"
    }
    assert not data["failures"]


def test_governance_status_verifies_catalogue_baseline_without_writes():
    response = client.get("/api/v1/governance/status")
    assert response.status_code == 200
    data = response.json()
    assert data["integrity"] == "verified"
    assert data["verification"]["changed"] == []
    assert data["verification"]["missing"] == []
    assert data["publication_enabled"] is False


def test_student_and_admin_frontends_use_external_assets():
    student = client.get("/")
    admin = client.get("/admin")
    assert student.status_code == 200
    assert admin.status_code == 200
    assert '/static/app.css' in student.text
    assert '/static/app.js' in student.text
    assert 'http://127.0.0.1:8000' not in Path("static/app.js").read_text(encoding="utf-8")
    assert 'Publication controls remain deliberately disabled' in admin.text


def test_pdf_endpoint_returns_programme_scoped_report():
    parsed = StudentRecord(
        student_id="TST-PDF-001",
        name="Transcript Student",
        programme="Bachelor of Social Science",
        declared_majors=[],
        results=[CourseResult("PHI1024F", "Introduction to Philosophy", 5, 18, 65, "2-", 2024)],
    )
    with patch("app.parse_transcript_pdf", return_value=parsed):
        response = client.post(
            "/api/v1/analyse",
            params={
                "faculty": "uct_humanities",
                "programme": "bsocsc_regular",
                "majors": "philosophy",
                "years_registered": 2,
            },
            files={"file": ("transcript.pdf", b"%PDF-1.7\nsynthetic", "application/pdf")},
        )
    assert response.status_code == 200
    report = response.json()
    assert report["faculty_key"] == "uct_humanities"
    assert report["programme_key"] == "bsocsc_regular"
    assert report["programme_name"]
    assert report["student_name"] == "Transcript Student"
    assert isinstance(report["requirements"], list)
    assert isinstance(report["eligible_courses"], list)
