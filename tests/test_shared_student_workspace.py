"""Cross-institution product contract; no new academic evaluation path."""
import json
import subprocess
from pathlib import Path

import pytest
from test_northstar_student_interface import cases as cases
from test_ppe_pilot_fidelity_repair import report as ppe_report

ROOT = Path(__file__).resolve().parents[1]


def render(report, config):
    script = r'''
const fs = require('fs'), vm = require('vm');
const data = JSON.parse(fs.readFileSync(0, 'utf8'));
const context = {data, asArray: x => Array.isArray(x) ? x : [],
 esc: x => String(x ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;')};
vm.createContext(context);
for (const file of ['student-language', 'student-portal', 'student-workspace'])
 vm.runInContext(fs.readFileSync('static/' + file + '.js','utf8'),context);
vm.runInContext('function studentConclusionCard(item, config) {return StudentLanguage.card(item, config)}',context);
const before = JSON.stringify(data);
const output = vm.runInContext(`Object.fromEntries(['overview','curriculum','evidence','sources','explore','help'].map(key => [key,StudentWorkspace.renderSection(data.report,data.config,key)]))`,context);
output.tabs = vm.runInContext('StudentWorkspace.tabs(data.config)',context);
output.export = vm.runInContext('StudentWorkspace.exportText(data.report,data.config)',context);
output.errors = vm.runInContext('[0,401,413,422,429,503,500,"malformed"].map(StudentWorkspace.errorMessage)', context);
output.unchanged = before === JSON.stringify(data);
process.stdout.write(JSON.stringify(output));
'''
    output = subprocess.run(['node', '-e', script], input=json.dumps({'report': report, 'config': config}),
                            text=True, encoding='utf-8', capture_output=True, check=True, cwd=ROOT)
    return json.loads(output.stdout)


@pytest.mark.parametrize('subject', [f'NS-{i:03}' for i in range(1, 16)])
def test_shared_sections_preserve_every_northstar_projection(cases, subject):
    report = cases[subject]['report']
    output = render(report, {'institution_name': 'Northstar', 'evidence_origin': 'demo_record',
                             'capabilities': {'course_exploration': True}})
    assert output['unchanged']
    assert all(word in output['overview'] for word in ['Where am I?', 'What needs attention?', 'What can I do next?'])
    assert '<article' not in output['overview']  # Full conclusion collection belongs in Curriculum.
    for row in report['student_reasoning_view']['conclusions']:
        if row['kind'] == 'curriculum' and not row['legacy_compatibility']:
            assert output['curriculum'].count(f'<strong>{row["title"]}</strong>') == 1
    assert 'not a percentage' in output['overview']
    assert 'Record RX-441' in output['sources'] and 'Clause KAPPA' in output['sources']
    assert 'not an official academic record' in output['export']
    assert 'not live registration promises' in output['explore']


@pytest.mark.parametrize('origin', ['user_supplied', 'manual_entry', 'unknown', 'synthetic'])
def test_uct_origin_is_not_institutional_authority(origin):
    report = ppe_report()
    output = render(report, {'institution_name': 'UCT', 'evidence_origin': origin,
                             'capabilities': {'course_exploration': True}})
    assert output['unchanged']
    for section in ['overview', 'curriculum', 'evidence', 'help']:
        assert 'UCT supplied' not in output[section]
        assert 'The institution supplied' not in output[section]
    if origin in ['manual_entry', 'user_supplied']:
        expected = 'You supplied' if origin == 'manual_entry' else 'file you provided'
        assert expected in output['evidence']
    assert 'Page' in output['sources']
    assert 'not an admission decision' in output['export'] or 'Entry eligibility is not admission' in output['export']


@pytest.mark.parametrize('enabled', [True, False])
def test_exploration_is_capability_driven(cases, enabled):
    output = render(cases['NS-001']['report'], {'capabilities': {'course_exploration': enabled}})
    assert ('explore' in [row[0] for row in output['tabs']]) is enabled
    assert ('data-course-query' in output['explore']) is enabled


def test_shells_delegate_and_engine_has_no_product_dependency():
    for path in ['static/app.js', 'static/northstar.js']:
        assert 'StudentWorkspace.mount(' in (ROOT / path).read_text()
    shared = (ROOT / 'static/student-workspace.js').read_text()
    assert not any(token in shared.lower() for token in ['northstar', 'uct', 'found-x7', 'bsocsc_ppe'])
    assert 'graduation_status' not in shared
    for path in (ROOT / 'engine').glob('*.py'):
        assert 'StudentWorkspace' not in path.read_text(encoding='utf-8')


def test_presentation_config_does_not_modify_truth(cases):
    report = cases['NS-006']['report']
    for institution in ['Northstar', 'Another University']:
        output = render(report, {'institution_name': institution, 'evidence_origin': 'institution_supplied'})
        assert output['unchanged']
        assert 'Conflicting information' in output['curriculum']
        assert 'no qualifying witness' not in output['export']


@pytest.mark.parametrize('subject', ['NS-013', 'NS-014', 'NS-015'])
def test_completion_eligibility_award_are_distinct(cases, subject):
    output = render(cases[subject]['report'], {'institution_name': 'Northstar'})
    assert all(label in output['overview'] for label in ['Academic requirements', 'Graduation eligibility', 'Formal award'])
    assert ('Award evidence supplied' in output['curriculum']) is (subject == 'NS-015')


@pytest.mark.parametrize('relationship, expected', [
    ('DIRECT_RULE_SOURCE', 'Direct rule source'),
    ('INHERITED_POLICY_SOURCE', 'not a separate rule-level citation'),
    ('PACKAGE_SOURCE', 'not direct confirmation of this rule'),
])
def test_source_relationship_is_not_upgraded(relationship, expected):
    report = {'student_reasoning_view': {'source_directory': [{
        'title': 'Example source', 'status_language': 'Unverified source',
        'conclusion_links': [{'title': 'Example requirement', 'conclusion_id': 'r',
                              'relationship': relationship, 'locator': {'record_id': 'R-1'}}]}]}}
    output = render(report, {})
    assert expected in output['sources']
    assert 'Unverified source' in output['sources']
    assert 'data-conclusion-target="r"' in output['sources']
    assert 'Page' not in output['sources']


def test_error_and_export_boundaries(cases):
    output = render(cases['NS-003']['report'], {'evidence_origin': 'manual_entry'})
    assert 'information you supplied' in output['export']
    assert 'not fully verified' in output['export']
    assert 'does not establish its verification status' in output['export']
    assert all('Traceback' not in message and '{' not in message for message in output['errors'])
    assert 'no new academic conclusion' in output['errors'][0]
