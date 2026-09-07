"""Actual synthetic login -> records -> report browser rehearsal."""

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def run(base_url, destination):
    destination.mkdir(parents=True, exist_ok=True)
    observations = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for width, height, label in [(1440, 1000, "desktop"), (390, 844, "mobile")]:
            context = browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=1)
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error, errors=errors: errors.append(str(error)))
            page.goto(base_url + "/northstar")
            page.locator("#ns-subject option").nth(14).wait_for(state="attached")
            page.screenshot(path=str(destination / f"{label}-login.png"), full_page=True)
            for subject in ["NS-001", "NS-003", "NS-006", "NS-007", "NS-008", "NS-011", "NS-012", "NS-013", "NS-014", "NS-015"]:
                page.select_option("#ns-subject", subject)
                with page.expect_response(lambda response: response.url.endswith("/api/northstar/analyse")) as received:
                    page.get_by_role("button", name="Log in and retrieve my record").click()
                response = received.value
                assert response.status == 200
                page.locator("#ns-workspace").wait_for(state="visible")
                assert page.locator("#ns-title").inner_text() == "Dashboard"
                page.add_style_tag(content="html {scroll-behavior:auto!important}")
                page.screenshot(path=str(destination / f"{label}-{subject}.png"), full_page=True)
                overflow = page.evaluate("document.documentElement.scrollWidth > innerWidth")
                assert not overflow, (label, subject)
                report = response.json()["report"]
                page.locator('#ns-nav button[data-view="curriculum"]').click()
                for item in report["student_reasoning_view"]["conclusions"]:
                    if not item.get("legacy_compatibility") and item.get("kind") == "curriculum":
                        assert page.locator("#ns-results").get_by_text(item["title"], exact=True).count() >= 1
                if subject == "NS-006":
                    assert page.locator("#ns-results").get_by_text("Conflicting information", exact=True).count() > 0
                if subject == "NS-011":
                    assert "This is not an admission decision" in page.locator("#ns-results").inner_text()
                if subject == "NS-015":
                    assert page.locator("#ns-results").get_by_text("Award evidence supplied", exact=True).count() == 1
                    award = page.locator("article").filter(has=page.get_by_text("Formal award", exact=True))
                    award.scroll_into_view_if_needed()
                    page.screenshot(path=str(destination / f"{label}-award-boundary.png"))
                assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
                if subject in {"NS-006", "NS-007", "NS-014", "NS-015"}:
                    page.screenshot(path=str(destination / f"{label}-{subject}-curriculum.png"), full_page=True)
                normal = page.locator('#ns-results').inner_text()
                assert not any(token in normal for token in ['assessment_complete', 'choose_n', 'DIRECT_RULE_SOURCE', 'unverified', 'curriculum:', 'NS-V1-', 'REC-NS'])
                page.locator('#ns-results .human-why summary').first.click()
                assert 'Ways of Inquiry' in page.locator('#ns-results').inner_text()
                assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
                page.locator('#ns-nav button[data-view="sources"]').click()
                page.locator('#ns-sources details').first.locator('summary').click()
                assert "Record RX-" in page.locator('#ns-sources').inner_text()
                assert "Page " not in page.locator('#ns-sources').inner_text()
                page.screenshot(path=str(destination / f"{label}-{subject}-sources.png"), full_page=True)
                page.locator('#ns-nav button[data-view="evidence"]').click()
                assert "not every item is used by every conclusion" in page.locator('#ns-results').inner_text()
                if subject == "NS-008":
                    page.get_by_text('Achievement values supplied', exact=True).click()
                    assert "FOUND-X7 - Ways of Inquiry: 15" in page.locator('#ns-results').inner_text()
                    assert "0 to 20" in page.locator('#ns-results').inner_text()
                if subject == "NS-012":
                    page.get_by_text('What your registration history shows', exact=True).click()
                    assert "not a current enrolment decision" in page.locator('#ns-results').inner_text()
                assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
                page.screenshot(path=str(destination / f"{label}-{subject}-evidence.png"), full_page=True)
                page.locator('#ns-nav button[data-view="help"]').click()
                assert 'What does CRE do?' in page.locator('#ns-results').inner_text()
                page.locator(".ns-debug > summary").click()
                assert subject in page.locator("#ns-debug").inner_text()
                assert "NS-REGISTRY" in json.dumps(report["student_reasoning_view"]["sources"])
                observations.append(dict(viewport=label, subject=subject, overflow=overflow, errors=list(errors),
                    qualification=report["qualification_completion"]["outcome"],
                    graduation=report["graduation_eligibility_assessment"]["outcome"],
                    award=report["qualification_award_assessment"]["outcome"],
                    entry=report["programme_entry_eligibility_assessment"]["outcome"]))
                page.get_by_role("button", name="Switch demo student").click()
                page.locator("#ns-login").wait_for(state="visible")
                assert page.locator("#ns-results").inner_text() == ""
            assert not errors, errors
            context.close()
        browser.close()
    (destination / "observations.json").write_text(json.dumps(observations, indent=2) + "\n", encoding="utf-8")
    print(f"{len(observations)} desktop/mobile login-to-report cases passed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8770")
    parser.add_argument("--output", type=Path, default=Path("artifacts/northstar-student-interface"))
    args = parser.parse_args()
    run(args.url, args.output)
