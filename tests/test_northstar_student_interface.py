"""Shared product rendering over real request-local institutional projections."""

import copy
import json
import re
import subprocess

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app as backend
from northstar.package import ROOT
from northstar.records import StudentRecords
from northstar.web import install

REPO = ROOT.parent


def request(client, subject):
    assert client.post('/api/northstar/login', json={'subject': subject, 'access_code': 'northstar-demo'}).status_code == 200
    response = client.post('/api/northstar/analyse')
    assert response.status_code == 200
    return response.json()


@pytest.fixture(scope='module')
def cases():
    app = FastAPI()
    install(app, backend.analyse_json)
    with TestClient(app) as client:
        return {f'NS-{i:03}': request(client, f'NS-{i:03}') for i in range(1, 16)}


def render(payload, config=None):
    script = r'''
const fs = require('fs'), vm = require('vm');
const data = JSON.parse(fs.readFileSync(0, 'utf8'));
const src = fs.readFileSync('static/app.js', 'utf8');
const context = {data, asArray: x => Array.isArray(x) ? x : [],
 esc: x => String(x ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('"', '&quot;'),
 titleCase: x => x, statusKey: x => x, sourceLocator: x => JSON.stringify(x)};
vm.createContext(context);
vm.runInContext(fs.readFileSync('static/student-language.js', 'utf8'), context);
const start = src.indexOf('function studentConclusionCard(');
vm.runInContext(src.slice(start, src.indexOf('\nfunction ', start + 1)), context);
vm.runInContext(fs.readFileSync('static/student-portal.js', 'utf8'), context);
const before = JSON.stringify(data);
const output = vm.runInContext(`({
 counts: StudentPortal.counts(data.payload.report.student_reasoning_view),
 dashboard: StudentPortal.dashboard(data.payload.report.student_reasoning_view, data.config),
 curriculum: StudentPortal.curriculum(data.payload.report.student_reasoning_view, data.config),
 evidence: StudentPortal.evidence(data.payload.report.student_reasoning_view, data.config, data.payload.retrieval || [], data.payload.registration_duration),
 sources: StudentPortal.sources(data.payload.report.student_reasoning_view),
 help: StudentPortal.help(data.config)})`, context);
output.unchanged = before === JSON.stringify(data);
process.stdout.write(JSON.stringify(output));
'''
    if config is None:
        with TestClient(backend.app) as client:
            config = client.get('/api/northstar/presentation').json()['config']
    output = subprocess.run(['node', '-e', script], input=json.dumps(dict(payload=payload, config=config)),
                            capture_output=True, text=True, encoding='utf-8', cwd=REPO, check=True)
    return json.loads(output.stdout)


@pytest.mark.parametrize('subject', [f'NS-{i:03}' for i in range(1, 16)])
def test_every_case_uses_canonical_cards_without_mutation(cases, subject):
    payload = cases[subject]
    rendered = render(payload)
    assert rendered['unchanged']
    assert sum(rendered['counts'].values()) == 6
    for item in payload['report']['student_reasoning_view']['conclusions']:
        if not item.get('legacy_compatibility'):
            if item['kind'] == 'curriculum':
                assert item['title'] in rendered['curriculum']
                assert {'satisfied': 'Met', 'not_satisfied': 'Needs attention', 'unresolved': 'Not enough information yet',
                        'conflict': 'Conflicting information', 'unsupported': 'Not assessed by CRE'}[item['outcome']] in rendered['curriculum']
    assert 'choose_n' not in rendered['curriculum']
    assert 'one_of' not in rendered['curriculum']
    assert 'not a percentage' in rendered['dashboard']


@pytest.mark.parametrize('subject,state', [('NS-002', 'not_satisfied'), ('NS-003', 'unresolved'), ('NS-006', 'conflict')])
def test_distinct_states(cases, subject, state):
    rendered = render(cases[subject])
    assert rendered['counts'][state] > 0
    assert f'notice-row {state}' in rendered['curriculum']


def test_sources_and_evidence_are_separate_and_registry_has_no_page(cases):
    rendered = render(cases['NS-015'])
    assert 'Record RX-' in rendered['sources'] and 'Clause KAPPA' in rendered['sources']
    assert 'Page ' not in rendered['sources']
    assert 'Student-evidence source' not in rendered['sources']
    assert 'Where this information came from' in rendered['evidence']
    assert 'not every item is used by every conclusion' in rendered['evidence']


def test_nonpercentage_achievement_is_explicit_not_converted(cases):
    rendered = render(cases['NS-008'])
    assert 'FOUND-X7 - Ways of Inquiry: <strong>15</strong>' in rendered['evidence']
    assert '0 to 20' in rendered['evidence']
    assert '15%' not in rendered['evidence']
    assert 'Supporting identifiers: FOUND-X7' in rendered['curriculum']
    assert 'badge policy_clear' in rendered['curriculum']


def test_alternative_witness_does_not_render_unused_failures(cases):
    view = cases['NS-007']['report']['student_reasoning_view']
    studio = next(item for item in view['conclusions'] if item['identity'].endswith('studio'))
    assert studio['outcome'] == 'satisfied'
    assert 'PATH-Z9' in render(cases['NS-007'])['curriculum']
    assert not any(item['title'] == 'ALT-V8' and item['outcome'] == 'not_satisfied' for item in view['conclusions'])


@pytest.mark.parametrize('subject,academic,graduation,award', [
    ('NS-013', 'satisfied', 'unresolved', 'unresolved'),
    ('NS-014', 'satisfied', 'satisfied', 'unresolved'),
    ('NS-015', 'satisfied', 'satisfied', 'awarded'),
])
def test_three_distinct_completion_boundaries(cases, subject, academic, graduation, award):
    report = cases[subject]['report']
    assert report['qualification_completion']['outcome'] == academic
    assert report['graduation_eligibility_assessment']['outcome'] == graduation
    assert report['qualification_award_assessment']['outcome'] == award
    html = render(cases[subject])['dashboard']
    assert 'Eligibility does not establish a formal award' in html
    assert ('Award evidence supplied' in html) == (award == 'awarded')


def test_entry_and_history_do_not_infer_institutional_decisions(cases):
    assert 'This is not an admission decision' in render(cases['NS-011'])['curriculum']
    assert 'not a current enrolment decision' in render(cases['NS-012'])['evidence']


def test_presentation_changes_cannot_change_or_hide_truth(cases):
    config = {'institution_name': 'Another school', 'records_name': 'Another register',
              'navigation': {'evidence': 'My evidence'}, 'curriculum_groups': [{'title': 'Nothing', 'identities': ['absent']}]}
    before = copy.deepcopy(cases['NS-006'])
    original, changed = render(before), render(before, config)
    assert original['counts'] == changed['counts']
    assert changed['unchanged'] and before == cases['NS-006']
    assert 'Other represented requirements' in changed['curriculum']


def test_same_components_render_uct_ppe_and_document_locators(cases):
    with TestClient(backend.app) as client:
        response = client.post('/analyse/json', json={'institution_id': 'uct', 'release_id': '2026',
                              'faculty': 'uct_humanities', 'programme_key': 'bsocsc_ppe', 'student_id': 'PPE', 'results': []})
    assert response.status_code == 200
    rendered = render({'report': response.json()}, {})
    assert 'Page ' in rendered['sources']
    assert 'Northstar' not in rendered['sources']
    assert 'PPE' in rendered['curriculum'] or 'Economics' in rendered['curriculum']
    assert 'Record RX-' in render(cases['NS-001'])['sources']


def test_domain_service_failure_is_not_academic_failure():
    class UnavailableRecognition(StudentRecords):
        def fetch(self, institution_id, subject_reference):
            native = super().fetch(institution_id, subject_reference)
            native['domains']['recognition'] = None
            return native

    app = FastAPI()
    install(app, backend.analyse_json, records=UnavailableRecognition())
    with TestClient(app) as client:
        result = request(client, 'NS-005')
    assert any(row['state'] == 'UNAVAILABLE_OR_MALFORMED' for row in result['retrieval'])
    core = next(item for item in result['report']['student_reasoning_view']['conclusions'] if item['identity'].endswith('core'))
    assert core['outcome'] == 'unresolved'
    assert 'Some information could not be retrieved or used' in render(result)['evidence']


def test_directory_is_secondary_metadata_not_expected_answers():
    with TestClient(backend.app) as client:
        data = client.get('/api/northstar/presentation').json()
    assert len(data['cases']) == 15
    assert all(set(row) == {'subject', 'label'} for row in data['cases'])


def test_shared_renderer_has_no_institution_or_student_branch():
    text = (REPO / 'static/student-portal.js').read_text()
    assert not re.search(r'\b(northstar|uct|ns-00|found-x7)\b', text, re.I)
    assert 'studentConclusionCard' in text
    assert 'fetch(' not in text
    assert 'academic_year' not in text
    assert 'aria-current' in (REPO / 'static/northstar.js').read_text()
    assert 'focus-visible' in (REPO / 'static/northstar.css').read_text()
