"""Guards for presentation defects found in the real Chromium rehearsal."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_start_empty_uses_existing_endpoint_and_account_panel():
    source = (ROOT / "static/app.js").read_text(encoding="utf-8")
    block = source.split("async function analyseEmpty()", 1)[1].split("function renderManualCourseList", 1)[0]
    assert '/api/v1/analyse/json' in block
    assert '/api/v1/engine/analyse' not in block
    assert 'setStep("account")' in block
    assert 'reportPanel' in block
    assert 'res.text()' not in block


def test_report_header_does_not_reconstruct_a_failure_from_legacy_fields():
    source = (ROOT / "static/app.js").read_text(encoding="utf-8")
    block = source.split("function renderReport()", 1)[1].split("function copySummary", 1)[0]
    assert 'student_reasoning_view' in block
    assert 'report.graduation_status' not in block
    assert 'row.complete' not in block
    assert 'not yet determined' in block


def test_canonical_visual_states_and_keyboard_focus_are_explicit():
    css = (ROOT / "static/app.css").read_text(encoding="utf-8")
    for state in ("satisfied", "not_satisfied", "unresolved", "unsupported", "conflict"):
        assert f".notice-row.{state}" in css
    assert 'summary:focus-visible' in css
    assert 'white-space:normal' in css
