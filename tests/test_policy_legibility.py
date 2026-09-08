"""Language assertions are teach-back preparation, not human comprehension results."""
import json
import re
import subprocess
from pathlib import Path

import pytest
from test_northstar_human_legibility import StudentText
from test_northstar_student_interface import cases as cases
from test_northstar_student_interface import render as northstar_render
from test_ppe_pilot_fidelity_repair import projections, report, rule_data
from test_shared_student_workspace import render

ROOT = Path(__file__).resolve().parents[1]


def card(item, config=None):
    script = r'''
const fs = require('fs'), vm = require('vm');
const data = JSON.parse(fs.readFileSync(0, 'utf8'));
const before = JSON.stringify(data);
const context = {data, asArray: x => Array.isArray(x) ? x : [],
 esc: x => String(x ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;')};
vm.createContext(context);
vm.runInContext(fs.readFileSync('static/student-language.js', 'utf8'), context);
const output = vm.runInContext('({html: StudentLanguage.card(data.item, data.config), meaning: StudentLanguage.meaning(data.item, data.config), action: StudentLanguage.actionDetail(data.item, data.config)})', context);
output.unchanged = JSON.stringify(data) === before;
process.stdout.write(JSON.stringify(output));
'''
    result = subprocess.run(['node', '-e', script], cwd=ROOT, capture_output=True,
                            text=True, encoding='utf-8', check=True,
                            input=json.dumps({'item': item, 'config': config or {}}))
    return json.loads(result.stdout)


@pytest.mark.parametrize('state,expected', [
    ('satisfied', 'You meet this requirement.'),
    ('not_satisfied', 'You do not meet this requirement yet.'),
    ('unresolved', 'does not have enough information'),
    ('conflict', 'will not choose one automatically'),
    ('unsupported', 'not supported by CRE'),
])
def test_outcome_is_not_reconstructed_from_title_or_boolean(state, expected):
    item = {'identity': 'r', 'kind': 'curriculum', 'outcome': state, 'complete': True,
            'title': 'Complete six courses with 80 credits', 'assessment_complete': False}
    output = card(item)
    assert output['unchanged']
    assert expected in output['meaning']['text']
    assert 'not reconstructed the rule from its title' in output['html']
    assert 'You still need six' not in output['html']


@pytest.mark.parametrize('owner', ['UCT', 'Northstar', 'Another University'])
@pytest.mark.parametrize('token', ['SUPPLY_EVIDENCE', 'REVIEW_RECOGNITION', 'REVIEW_CONFLICT',
                                  'SEEK_INSTITUTIONAL_DECISION', 'POLICY_NOT_SUPPORTED', 'UNRESOLVED_NEXT_STEP'])
def test_actions_name_responsibility_without_office_or_procedure(owner, token):
    output = card({'outcome': 'unresolved', 'next_action': token}, {'institution_name': owner})
    assert output['unchanged']
    assert output['action']['needs']
    assert not re.search(r'\b(we|our|us)\b', StudentText(output['html']).text, re.I)
    assert not any(word in output['html'] for word in ['Dean', 'Registrar', 'upload by', 'approved automatically'])
    if token == 'SEEK_INSTITUTIONAL_DECISION':
        assert f'{owner} still needs to decide this.' in output['html']
        assert output['meaning']['label'] == 'Not enough information yet'
    if token == 'REVIEW_RECOGNITION':
        assert 'What to ask' in output['html']
        assert 'formally recognised toward this requirement' in output['html']


def test_met_does_not_acquire_a_to_do_list():
    output = card({'outcome': 'satisfied', 'next_action': 'NO_ACTION_CURRENTLY_REPRESENTED'})
    assert not output['action']
    assert 'What you can do' not in output['html']


@pytest.mark.parametrize('state', ['positive', 'unknown', 'negative', 'recognised'])
def test_ppe_exact_course_teach_back_not_third_year_aggregate(state):
    code = rule_data()['ppe_eco3025']['course_codes'][0]
    extra = {}
    if state == 'positive':
        extra['results'] = [{'code': code, 'mark': 70}]
    if state == 'negative':
        extra = {'academic_record_coverage': [{'course_codes': [code], 'coverage_state': 'complete',
                                               'authority': 'Synthetic registry', 'source_reference': 'Test snapshot'}],
                 'recognition_coverage': [{'course_codes': [code], 'authority': 'Synthetic registry',
                                           'source_reference': 'Test snapshot', 'verification_status': 'verified'}]}
    if state == 'recognised':
        extra['course_completion_recognition'] = [{'recognition_id': 'TEST-LANGUAGE', 'target_course_code': code,
            'source_learning_identity': 'EXT', 'authority': 'Synthetic registry',
            'source_reference': 'Test decision', 'verification_status': 'verified'}]
    canonical, student, _ = projections(report(**extra), 'ppe_eco3025')
    expected = {'positive': 'satisfied', 'unknown': 'unresolved', 'negative': 'not_satisfied', 'recognised': 'satisfied'}[state]
    assert canonical['outcome'] == expected
    output = card(student, {'institution_name': 'UCT', 'evidence_origin': 'manual_entry'})
    assert output['unchanged']
    assert all(label in output['html'] for label in ['Why?', 'What the rule requires', 'Where this comes from', 'Page'])
    assert 'A plain-language rule description is not available' in output['html']
    if state == 'negative':
        assert 'You do not meet this requirement yet' in output['html']
    if state == 'unknown':
        assert 'You do not meet' not in output['html']
    if state == 'recognised':
        assert 'recognition decision' in output['html']
        assert 'Recognition is not a new course attempt or mark' in output['html']
        assert 'You completed' not in output['html']


@pytest.mark.parametrize('subject', ['NS-001', 'NS-003', 'NS-006', 'NS-007', 'NS-011', 'NS-013', 'NS-014', 'NS-015'])
def test_flagship_public_rule_and_personal_answer_are_separate(cases, subject):
    output = northstar_render(cases[subject])
    assert output['unchanged']
    text = StudentText(output['curriculum']).text
    assert 'What the rule requires' in text and 'Complete one course from this group' in text
    assert 'Where this comes from' in text and 'Record RX-441' in text
    assert 'Why?' in text
    assert 'not an admission decision' in text
    assert 'Graduation eligibility is not formal approval' in text
    assert ('Award evidence supplied' in text) == (subject == 'NS-015')
    assert 'institutionally confirmed' in text
    normal = StudentText(output['curriculum'], expanded=False).text
    for token in ['assessment_complete', 'canonical outcome', 'coverage state', 'DIRECT_RULE_SOURCE',
                  'relationship type', 'release id', 'choose_n', 'all_of', 'witness authority']:
        assert token not in normal
    assert not re.search(r'\b(we|our|us)\b', normal, re.I)


@pytest.mark.parametrize('origin,expected', [('manual_entry', 'You supplied'),
    ('user_supplied', 'file you provided'), ('demo_record', 'Northstar supplied this demonstration record'),
    ('unknown', 'This information is available')])
def test_receipt_origin_is_not_use_or_authority(cases, origin, expected):
    output = render(cases['NS-001']['report'], {'institution_name': 'Northstar', 'evidence_origin': origin})
    assert 'Information available to CRE' in output['evidence']
    assert expected in output['evidence']
    assert 'Not every item is used for every answer' in output['evidence']
    assert 'does not establish its verification status' in output['evidence']
    assert output['unchanged']


def test_progression_condition_false_is_not_a_student_shortfall():
    result = card({'kind': 'progression', 'outcome': 'not_satisfied', 'consequence_established': False})
    assert result['meaning']['label'] == 'No issue identified by this rule'
    assert 'You do not meet' not in result['html']


def test_rule_description_and_locator_are_not_rewritten_for_student():
    instruction = 'Complete one course from this group: OPAQUE-A; OPAQUE-B.'
    source = {'title': 'Public register', 'relationship': 'INHERITED_POLICY_SOURCE',
              'locator': {'record_id': 'R-X', 'clause': 'ALPHA'}}
    item = {'identity': 'r', 'kind': 'curriculum', 'outcome': 'satisfied',
            'used_course_codes': ['OPAQUE-B'], 'source_references': [source]}
    output = card(item, {'requirement_instructions': {'r': instruction}})
    assert output['unchanged']
    assert instruction in output['html']
    assert 'Information supporting this result relates to: OPAQUE-B' in output['html']
    assert 'Inherited policy source, not a separate rule-level citation' in output['html']
    assert 'Record R-X' in output['html'] and 'Clause ALPHA' in output['html']
    assert 'OPAQUE-A is not' not in output['html']
