"""Chromium service-failure and keyboard checks against the real adapter boundary."""

import socket
import threading
import time

import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from playwright.sync_api import expect, sync_playwright

import app as backend
from northstar.package import ROOT
from northstar.records import StudentRecords
from northstar.web import install


@pytest.fixture
def unavailable_domain_server():
    class Records(StudentRecords):
        def fetch(self, institution_id, subject_reference):
            record = super().fetch(institution_id, subject_reference)
            record['domains']['recognition'] = None
            return record

    app = FastAPI()
    app.mount('/static', StaticFiles(directory=ROOT.parent / 'static'))
    install(app, backend.analyse_json, records=Records())
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='error', ws='none'))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and time.monotonic() < deadline:
            time.sleep(.02)
        assert server.started
        yield f'http://127.0.0.1:{port}'
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        assert not thread.is_alive()


@pytest.mark.parametrize('width', [1440, 390])
def test_real_domain_failure_and_safe_service_errors(unavailable_domain_server, width):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={'width': width, 'height': 900})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(unavailable_domain_server + '/northstar')
        page.locator('#ns-subject option').nth(14).wait_for(state='attached')
        page.select_option('#ns-subject', 'NS-005')
        page.get_by_role('button', name='Log in and retrieve my record').click()
        expect(page.locator('#ns-workspace')).to_be_visible()
        expect(page.locator('#ns-domain-warning')).to_contain_text('Some evidence could not be retrieved')
        page.locator('#ns-nav button[data-view="curriculum"]').click()
        core = page.locator('article').filter(has=page.get_by_text('Foundation and core completion', exact=True))
        expect(core).to_have_class('notice-row unresolved human-card')
        page.locator('#ns-nav button[data-view="evidence"]').click()
        expect(page.locator('#ns-results')).to_contain_text('service problem is not an academic failure')
        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
        summary = page.locator('.ns-debug > summary')
        summary.focus()
        page.keyboard.press('Enter')
        expect(page.locator('.ns-debug')).to_have_attribute('open', '')
        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
        page.locator('#ns-nav button[data-view="help"]').click()
        expect(page.locator('#ns-content')).to_be_focused()
        expect(page.locator('#ns-results')).to_contain_text('Entry eligibility is not admission')
        for status, message in [(401, 'could not be confirmed'), (422, 'release or supplied evidence'),
                                (503, 'record or reasoning service'), (500, 'Reasoning is unavailable')]:
            # Transport failure only: no mocked academic assessment or evidence result.
            page.route('**/api/northstar/analyse', lambda route, _request, status=status: route.fulfill(status=status, body='private diagnostic'))
            page.locator('#ns-refresh').click()
            expect(page.locator('#ns-message')).to_contain_text(message)
            expect(page.locator('#ns-message')).to_contain_text('previous assessment remains displayed')
            assert 'private diagnostic' not in page.locator('body').inner_text()
            page.unroute('**/api/northstar/analyse')
        page.locator('#ns-switch').click()
        expect(page.locator('#ns-login')).to_be_visible()
        page.fill('#ns-code', 'wrong')
        page.get_by_role('button', name='Log in and retrieve my record').click()
        expect(page.locator('#ns-message')).to_contain_text('could not be confirmed')
        assert not errors
        browser.close()
