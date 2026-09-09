"""Useful checks migrated from retired browser scripts; no capture files required."""
import re

import pytest
from playwright.sync_api import expect, sync_playwright
from test_shared_workspace_browser import no_overflow
from test_shared_workspace_browser import workspace_server as workspace_server


@pytest.mark.parametrize('width', [1440, 390])
def test_ppe_rehearsal_scenarios(workspace_server, width):
    decision = {'recognition_id': 'QA-ONLY', 'target_course_code': 'POL2039F',
                'source_learning_identity': 'SYNTHETIC-EXT', 'authority': 'Synthetic registry',
                'source_reference': 'Synthetic QA fixture', 'verification_status': 'verified'}
    scope = {'course_codes': ['ECO3025S'], 'authority': 'Synthetic registry',
             'source_reference': 'Synthetic scoped snapshot', 'verification_status': 'verified'}
    scenarios = {
        'satisfied': {'results': [{'code': 'POL2039F', 'mark': 70}, {'code': 'ECO3025S', 'mark': 70}]},
        'unresolved': {},
        'shortfall': {'academic_record_coverage': [{**scope, 'coverage_state': 'complete'}],
                      'recognition_coverage': [scope]},
        'conflict': {'course_completion_recognition': [{**decision, 'verification_status': 'conflict'}]},
        'course-recognition': {'course_completion_recognition': [decision]},
        'requirement-recognition': {'requirement_recognition_evidence': [
            {k: v for k, v in {**decision, 'target_requirement_id': 'ppe_phi3'}.items()
             if k != 'target_course_code'}]},
    }
    ids = ['ppe_year1', 'ppe_year2_fixed', 'ppe_year2_politics', 'ppe_year2_other',
           'ppe_eco3025', 'ppe_phi3', 'ppe_pol3']
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={'width': width, 'height': 960})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(workspace_server + '/faculty/uct_humanities')
        page.locator('#programmeSelect option[value="bsocsc_ppe"]').wait_for(state='attached')
        page.select_option('#programmeSelect', 'bsocsc_ppe')
        page.wait_for_function("state.programme?.key === 'bsocsc_ppe'")
        page.locator('#routeContinue').click()
        page.locator('#intentContinue').click()
        page.locator('#transcriptFile').set_input_files({
            'name': 'synthetic-unreadable.pdf', 'mimeType': 'application/pdf', 'buffer': b'not a pdf'})
        page.locator('#analyseButton').click()
        expect(page.locator('#analysisError')).to_contain_text('enter courses manually')
        expect(page.locator('#reportPanel')).to_be_hidden()
        page.locator('#startEmptyToggle').click()
        page.locator('#analyseEmptyBtn').click()
        root = page.locator('#reportContent')
        expect(root.locator('.cre-account')).to_be_visible()
        for name, extra in scenarios.items():
            response = page.request.post(workspace_server + '/api/v1/analyse/json', data={
                'faculty': 'uct_humanities', 'programme_key': 'bsocsc_ppe',
                'student_id': 'SYNTHETIC-PPE-QA', 'name': 'Synthetic PPE review', 'results': [], **extra})
            assert response.ok, (name, response.text())
            report = response.json()
            page.evaluate("r => {state.report=r; state.reportTab='overview'; renderReport();}", report)
            root.locator('.cre-nav [data-view="curriculum"]').click()
            conclusions = {row['identity']: row for row in report['student_reasoning_view']['conclusions']}
            for identity in ids:
                item = conclusions['curriculum:' + identity]
                card = root.locator(f'[data-conclusion-id="curriculum:{identity}"]')
                expect(card).to_have_count(1)
                expect(card).to_have_class(re.compile(rf"\b{item['outcome']}\b"))
                expect(card).to_contain_text(item['title'])
            disclosure = root.locator('.human-source > summary').first
            disclosure.focus()
            disclosure.press('Enter')
            expect(disclosure.locator('..')).to_have_attribute('open', '')
            expect(disclosure.locator('..')).to_contain_text('does not mean the institution has formally confirmed')
            disclosure.press('Tab')
            assert page.evaluate('document.activeElement.tagName') != 'BODY'
            no_overflow(page)
            root.locator('.cre-nav [data-view="sources"]').click()
            for identity in ids:
                expect(root.locator('.cre-section')).to_contain_text(conclusions['curriculum:' + identity]['title'])
            root.locator('.portal-source summary').first.click()
            expect(root.locator('.cre-section')).to_contain_text('Page')
            expect(root.locator('.cre-section')).not_to_contain_text('Record RX-')
            no_overflow(page)
            root.locator('.cre-nav [data-view="evidence"]').click()
            expect(root.locator('.cre-section')).to_contain_text('Not every item is used for every answer')
            no_overflow(page)
        assert not errors
        browser.close()
