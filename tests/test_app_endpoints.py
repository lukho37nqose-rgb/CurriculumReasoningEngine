import pytest
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)


def _valid_student():
    return {
        "student_id": "TST001",
        "name": "Test Student",
        "programme": "Bachelor of Social Science",
        "declared_majors": [],
        "results": [
            {
                "code": "PHI1024F",
                "name": "Introduction To Philosophy",
                "nqf_level": 5,
                "nqf_credits": 18,
                "mark": 65,
                "grade": "2-",
            }
        ],
    }


def test_simulate_fail_valid():
    payload = {
        "student": _valid_student(),
        "course_code": "PHI1024F",
        "faculty": "uct_humanities",
        "programme_key": "bsocsc_regular",
    }
    response = client.post("/simulate/fail", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "report" in data
    assert "blocked_courses" in data


def test_simulate_fail_invalid_student():
    payload = {
        "student": {
            "results": [
                {
                    # missing "code" which is a required key in the try block
                    "name": "Missing Code Course"
                }
            ]
        },
        "course_code": "PHI1024F",
        "faculty": "uct_humanities",
        "programme_key": "bsocsc_regular",
    }
    response = client.post("/simulate/fail", json=payload)
    assert response.status_code == 422


def test_simulate_pass_valid():
    payload = {
        "student": _valid_student(),
        "course_code": "POL1004F",
        "mark": 75,
        "faculty": "uct_humanities",
        "programme_key": "bsocsc_regular",
    }
    response = client.post("/simulate/pass", json=payload)
    assert response.status_code == 200
    data = response.json()
    # It returns a report
    assert isinstance(data, dict)
    assert "requirements" in data


def test_simulate_pass_invalid_student():
    payload = {
        "student": {"results": [{"name": "Missing code"}]},
        "course_code": "POL1004F",
        "faculty": "uct_humanities",
        "programme_key": "bsocsc_regular",
    }
    response = client.post("/simulate/pass", json=payload)
    assert response.status_code == 422


def test_simulate_switch_valid():
    payload = {
        "student": _valid_student(),
        "new_majors": ["Test Major"],
        "faculty": "uct_humanities",
        "programme_key": "bsocsc_regular",
    }
    response = client.post("/simulate/switch", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert "requirements" in data


def test_simulate_switch_invalid_student():
    payload = {
        "student": {"results": [{"name": "Missing code"}]},
        "new_majors": ["Test Major"],
        "faculty": "uct_humanities",
        "programme_key": "bsocsc_regular",
    }
    response = client.post("/simulate/switch", json=payload)
    assert response.status_code == 422


def test_simulate_semester_valid():
    payload = {
        "student": _valid_student(),
        "courses": [["POL1004F", 75], ["SOC1001F", 70]],
        "faculty": "uct_humanities",
        "programme_key": "bsocsc_regular",
    }
    response = client.post("/simulate/semester", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert "requirements" in data


def test_simulate_semester_invalid_student():
    payload = {
        "student": {"results": [{"name": "Missing code"}]},
        "courses": [["POL1004F", 75]],
        "faculty": "uct_humanities",
        "programme_key": "bsocsc_regular",
    }
    response = client.post("/simulate/semester", json=payload)
    assert response.status_code == 422


def test_evaluate_goals_valid():
    payload = {
        "student": _valid_student(),
        "faculty": "uct_humanities",
        "programme_key": "bsocsc_regular",
    }
    response = client.post("/goals", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "graduation_goal" in data
    assert "honours_goals" in data


def test_evaluate_goals_invalid_student():
    payload = {
        "student": {"results": [{"name": "Missing code"}]},
        "faculty": "uct_humanities",
        "programme_key": "bsocsc_regular",
    }
    response = client.post("/goals", json=payload)
    assert response.status_code == 422
