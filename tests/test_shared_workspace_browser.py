"""Real Chromium journeys through both shells and the same workspace renderer."""
import os
import re
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from playwright.sync_api import expect, sync_playwright

import app as backend


@pytest.fixture(scope='module')
def workspace_server():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(backend.app, host='127.0.0.1', port=port, log_level='error', ws='none'))
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


def capture(page, name):
    # Opt-in review artifacts, never required as test inputs.
    if directory := os.environ.get('CRE_WORKSPACE_SCREENSHOTS'):
        destination = Path(directory)
        destination.mkdir(parents=True, exist_ok=True)
        page.evaluate('window.scrollTo(0, 0)')
        page.screenshot(path=str(destination / f'{name}.png'), full_page=True)


def no_overflow(page):
    assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')


def shared_script_contract(page, shell):
    scripts = page.evaluate('[...document.scripts].map(script => new URL(script.src).pathname)')
    assert scripts == [f'/static/{name}.js' for name in
                       ['student-shared', 'student-language', 'student-portal', 'student-workspace', shell]]
    resources = page.evaluate('performance.getEntriesByType("resource").map(item => new URL(item.name).pathname)')
    assert ('/static/app.js' in resources) == (shell == 'app')
    assert page.evaluate('typeof studentConclusionCard') == 'function'
    assert page.evaluate('typeof esc') == 'function'
    assert page.evaluate('typeof asArray') == 'function'
    assert page.evaluate('typeof titleCase') == 'function'


def export_checks(page, root):
    page.context.grant_permissions(['clipboard-read', 'clipboard-write'])
    root.locator('[data-copy]').click()
    expect(root.locator('[data-workspace-message]')).to_contain_text('Reasoning summary copied')
    copied = page.evaluate('navigator.clipboard.readText()')
    assert 'not an official academic record' in copied
    assert 'Entry eligibility is not admission' in copied
    assert 'not fully verified' in copied
    page.emulate_media(media='print')
    assert 'not an official academic record' in root.evaluate('el => getComputedStyle(el, "::before").content')
    expect(root.locator('.cre-tools')).to_be_hidden()
    page.emulate_media(media='screen')


def sections(page, root, nav, registry):
    expect(root.locator('.cre-questions h2')).to_have_text(['Where am I?', 'What needs attention?', 'What can I do next?'])
    for section in ['curriculum', 'evidence', 'sources', 'explore', 'help', 'overview']:
        nav.locator(f'[data-view="{section}"]').click()
        expect(root.locator('.cre-section')).to_have_attribute('data-section', section)
        expect(nav.locator(f'[data-view="{section}"]')).to_have_attribute('aria-current', 'page')
        no_overflow(page)
        if section == 'sources':
            root.locator('.portal-source summary').first.click()
            expect(root.locator('.cre-section')).to_contain_text('Record RX-441' if registry else 'Page')
            expect(root.locator('.cre-section')).to_contain_text('interpretation')
            root.locator('[data-conclusion-target]').first.click()
            expect(root.locator('.cre-section')).to_have_attribute('data-section', 'curriculum')
            expect(root.locator('[data-conclusion-id]:focus')).to_have_count(1)
        if section == 'explore':
            expect(root.locator('.cre-section')).to_contain_text('not live registration promises')
            root.locator('[data-course-query]').fill('nonexistent-course')
            expect(root.locator('[data-course-search]:visible')).to_have_count(0)
    page.go_back()
    expect(root.locator('.cre-section')).to_have_attribute('data-section', 'help')
    page.go_forward()
    expect(root.locator('.cre-section')).to_have_attribute('data-section', 'overview')


@pytest.mark.parametrize('width', [1440, 390])
def test_northstar_shared_workspace_journeys(workspace_server, width):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={'width': width, 'height': 960})
        errors, retrievals = [], []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: retrievals.append(request.url) if request.url.endswith('/api/northstar/analyse') else None)
        page.goto(workspace_server + '/northstar')
        page.locator('#ns-subject option').nth(14).wait_for(state='attached')
        for index, subject in enumerate(['NS-001', 'NS-003', 'NS-006', 'NS-007', 'NS-008', 'NS-011', 'NS-012', 'NS-013', 'NS-014', 'NS-015']):
            page.select_option('#ns-subject', subject)
            page.get_by_role('button', name='Log in and retrieve my record').click()
            root, nav = page.locator('#ns-results'), page.locator('#ns-nav')
            expect(root.locator('.cre-account')).to_be_visible()
            assert len(retrievals) == index + 1
            expect(root.locator('[data-copy]')).to_have_count(1)
            if subject == 'NS-001':
                capture(page, f'northstar-overview-{width}')
                sections(page, root, nav, registry=True)
                export_checks(page, root)
            nav.locator('[data-view="curriculum"]').click()
            expect(root.locator('.human-card')).not_to_have_count(0)
            # Retain the old rehearsal's expanded-evidence and token checks.
            normal = root.locator('.cre-section').inner_text()
            assert not any(token in normal for token in [
                'assessment_complete', 'choose_n', 'DIRECT_RULE_SOURCE', 'unverified',
                'curriculum:', 'NS-V1-', 'REC-NS'])
            root.locator('.human-why summary').first.click()
            expect(root.locator('.cre-section')).to_contain_text('Ways of Inquiry')
            root.locator('.human-why summary').first.click()
            if subject in ['NS-003', 'NS-006']:
                state = 'unresolved' if subject == 'NS-003' else 'conflict'
                expect(root.locator(f'article.{state}').first).to_be_visible()
            if subject == 'NS-007':
                expect(root.locator('.cre-section')).not_to_contain_text('choose_n')
                capture(page, f'northstar-curriculum-{width}')
            if subject == 'NS-011':
                expect(root.locator('.cre-section')).to_contain_text('not an admission decision')
                expect(root.locator('.cre-section')).not_to_contain_text('You are admitted')
            if subject in ['NS-013', 'NS-014', 'NS-015']:
                expect(root.locator('.cre-section')).to_contain_text('Graduation eligibility is not formal approval')
                assert root.get_by_text('Award evidence supplied', exact=True).is_visible() == (subject == 'NS-015')
            nav.locator('[data-view="evidence"]').click()
            expect(root.locator('.cre-section')).to_contain_text('Northstar supplied this demonstration record')
            if subject == 'NS-008':
                root.get_by_text('Achievement values supplied', exact=True).click()
                expect(root.locator('.cre-section')).to_contain_text('Northstar achievement points (0 to 20)')
                expect(root.locator('.cre-section')).to_contain_text('15')
                expect(root.locator('.cre-section')).not_to_contain_text('15%')
            if subject == 'NS-012':
                root.get_by_text('What your registration history shows', exact=True).click()
                expect(root.locator('.cre-section')).to_contain_text('2 active academic cycles')
                expect(root.locator('.cre-section')).to_contain_text('not a current enrolment decision')
            no_overflow(page)
            nav.locator('[data-view="sources"]').click()
            root.locator('.portal-source summary').first.click()
            expect(root.locator('.cre-section')).to_contain_text('Record RX-')
            expect(root.locator('.cre-section')).not_to_contain_text('Page ')
            no_overflow(page)
            nav.locator('[data-view="help"]').click()
            expect(root.locator('.cre-section')).to_contain_text('What does CRE do?')
            page.locator('.ns-debug > summary').click()
            expect(page.locator('#ns-debug')).to_contain_text(subject)
            expect(page.locator('#ns-debug')).to_contain_text('NS-REGISTRY')
            page.locator('#ns-switch').click()
            expect(page.locator('#ns-login')).to_be_visible()
            expect(root).to_be_empty()
        shared_script_contract(page, 'northstar')
        assert not errors
        browser.close()


@pytest.mark.parametrize('width', [1440, 390])
@pytest.mark.parametrize('manual', [False, True])
def test_uct_entry_and_shared_workspace(workspace_server, width, manual):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={'width': width, 'height': 960})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(workspace_server)
        page.get_by_role('button', name=re.compile('04 Humanities')).click()
        page.get_by_role('combobox').select_option(label='Bachelor of Social Science in Philosophy, Politics and Economics')
        page.get_by_role('button', name='Next: Your plan').click()
        page.get_by_role('button', name='Next: Build your profile').click()
        if manual:
            page.get_by_text('Add courses manually', exact=True).click()
            page.locator('#manualCourseSearch').fill('ECO3025S')
            page.locator('#manualAddBtn').click()
            expect(page.locator('.manual-mark-input')).to_have_count(1)
            page.locator('.manual-mark-input').fill('70')
            page.locator('.manual-mark-input').press('Tab')
            page.locator('#analyseManualBtn').click()
        else:
            page.get_by_text('Start empty', exact=True).click()
            page.get_by_role('button', name='Explore options', exact=True).click()
        root = page.locator('#reportContent')
        expect(root.locator('.cre-account')).to_be_visible()
        expect(page.get_by_role('button', name='Copy summary', exact=True)).to_have_count(1)
        expect(page.get_by_role('button', name='Print', exact=True)).to_have_count(1)
        if not manual:
            capture(page, f'uct-overview-{width}')
        sections(page, root, root.locator('.cre-nav'), registry=False)
        export_checks(page, root)
        root.locator('.cre-nav [data-view="curriculum"]').click()
        capstone = root.locator('.human-card').filter(has=page.get_by_text('Compulsory third-year Economics course', exact=True))
        expected_state = 'satisfied' if manual else 'unresolved'
        expect(capstone).to_have_class(re.compile(rf'\b{expected_state}\b'))
        expect(root.locator('.cre-section')).not_to_contain_text('UCT supplied')
        if manual:
            capture(page, f'uct-curriculum-{width}')
        root.locator('.cre-nav [data-view="evidence"]').click()
        expect(root.locator('.cre-section')).to_contain_text('You supplied this information')
        no_overflow(page)
        shared_script_contract(page, 'app')
        assert not errors
        browser.close()
