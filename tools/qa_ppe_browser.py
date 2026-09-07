"""Rendered PPE rehearsal using synthetic backend evidence, never real student data."""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "ppe-browser-qa"
BASE = "http://127.0.0.1:8765"
IDS = ("ppe_year1", "ppe_year2_fixed", "ppe_year2_politics", "ppe_year2_other", "ppe_eco3025", "ppe_phi3", "ppe_pol3")


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    rules = json.loads((ROOT / "data/uct_humanities/degree_requirements.json").read_text(encoding="utf-8"))["programmes"]
    if isinstance(rules, list):
        programme = next(p for p in rules if p["key"] == "bsocsc_ppe")
    else:
        programme = rules["bsocsc_ppe"]
    selected = [r for r in programme["curriculum_rules"] if r["id"] in IDS]
    decision = {"recognition_id": "QA-ONLY", "target_course_code": "POL2039F", "source_learning_identity": "SYNTHETIC-EXT", "authority": "Synthetic registry", "source_reference": "Synthetic QA fixture", "verification_status": "verified"}
    scope = {"course_codes": ["ECO3025S"], "authority": "Synthetic registry", "source_reference": "Synthetic scoped snapshot", "verification_status": "verified"}
    scenarios = {
        "satisfied": {"results": [{"code": "POL2039F", "mark": 70}, {"code": "ECO3025S", "mark": 70}]},
        "unresolved": {},
        "shortfall": {"academic_record_coverage": [{**scope, "coverage_state": "complete"}], "recognition_coverage": [scope]},
        "conflict": {"course_completion_recognition": [{**decision, "verification_status": "conflict"}]},
        "course-recognition": {"course_completion_recognition": [decision]},
        "requirement-recognition": {"requirement_recognition_evidence": [{k: v for k, v in {**decision, "target_requirement_id": "ppe_phi3"}.items() if k != "target_course_code"}]},
    }
    observations = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(BASE + "/faculty/uct_humanities")
            page.add_style_tag(content="html { scroll-behavior: auto !important; }")
            page.locator('#programmeSelect option[value="bsocsc_ppe"]').wait_for(state="attached")
            page.locator("#programmeSelect").select_option("bsocsc_ppe")
            page.wait_for_function("state.programme?.key === 'bsocsc_ppe'")
            page.screenshot(path=str(OUT / "workspace.png"))
            page.locator("#routeContinue").click()
            page.locator("#intentContinue").click()
            page.locator("#transcriptFile").set_input_files({"name": "synthetic-unreadable.pdf", "mimeType": "application/pdf", "buffer": b"not a pdf"})
            page.locator("#analyseButton").click()
            page.locator("#analysisError").wait_for(state="visible")
            observations["input_error"] = page.locator("#analysisError").inner_text()
            assert "enter courses manually" in observations["input_error"]
            page.screenshot(path=str(OUT / "input-error.png"))
            page.locator("#startEmptyToggle").click()
            page.locator("#analyseEmptyBtn").click()
            page.locator("#reportPanel").wait_for(state="visible")
            observations["empty_button"] = "PASS"
            for name, extra in scenarios.items():
                response = page.request.post(BASE + "/api/v1/analyse/json", data={"faculty": "uct_humanities", "programme_key": "bsocsc_ppe", "student_id": "SYNTHETIC-PPE-QA", "name": "Synthetic PPE review", "results": [], **extra})
                assert response.ok, response.text()
                report = response.json()
                page.evaluate("r => {state.report=r; state.reportTab='overview'; renderReport(); document.getElementById('setupPanel').classList.add('hidden'); document.getElementById('reportPanel').classList.remove('hidden');}", report)
                observations[name] = {"outcomes": {c["identity"]: c["outcome"] for c in report["student_reasoning_view"]["conclusions"]}, "views": {}}
                for width in (1440, 390):
                    page.set_viewport_size({"width": width, "height": 1000 if width == 1440 else 844})
                    page.locator(".report-hero").evaluate("e => window.scrollTo(0, e.getBoundingClientRect().top + scrollY - 90)")
                    page.screenshot(path=str(OUT / f"{name}-{width}-top.png"))
                    for rule in selected:
                        card = page.locator(".student-reasoning-view article.notice-row").filter(has=page.get_by_text(rule["label"], exact=True))
                        assert card.count() == 1, rule["id"]
                        card.evaluate("e => window.scrollTo(0, e.getBoundingClientRect().top + scrollY - 100)")
                        if rule["id"] in ("ppe_eco3025", "ppe_year2_other", "ppe_year2_politics", "ppe_year1"):
                            card.screenshot(path=str(OUT / f"{name}-{width}-{rule['id']}.png"))
                    observations[name]["views"][str(width)] = page.evaluate("({width:innerWidth, documentWidth:document.documentElement.scrollWidth, text:document.getElementById('reportContent').innerText})")
                disclosure = page.locator(".student-reasoning-view .human-source > summary").first
                disclosure.focus()
                disclosure.press("Enter")
                assert disclosure.locator("..").get_attribute("open") is not None
                disclosure.locator("..").screenshot(path=str(OUT / f"{name}-source-qualification.png"))
                disclosure.press("Tab")
                assert page.evaluate("document.activeElement.tagName") != "BODY"
                page.locator('[data-report-tab="requirements"]').click()
                for rule in selected:
                    assert page.get_by_text(rule["label"], exact=True).count() >= 1
                page.locator('[data-report-tab="evidence"]').click()
                page.get_by_text("Sources represented in this assessment", exact=True).scroll_into_view_if_needed()
                page.screenshot(path=str(OUT / f"{name}-directory.png"))
                observations[name]["directory"] = page.locator("#reportSectionContent").inner_text()
                for rule in selected:
                    assert rule["label"] in observations[name]["directory"]
            observations["page_errors"] = errors
            (OUT / "observations.json").write_text(json.dumps(observations, indent=2), encoding="utf-8")
            print(json.dumps({"scenarios": list(scenarios), "errors": errors, "output": str(OUT)}))
        finally:
            browser.close()


if __name__ == "__main__":
    run()
