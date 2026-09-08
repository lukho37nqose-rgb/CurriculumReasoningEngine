"""Legibility cannot change canonical truth or erase institutional boundaries."""

import hashlib
import json
from html.parser import HTMLParser

import pytest
from test_northstar_student_interface import cases as cases
from test_northstar_student_interface import render

from curriculum_advisor.legibility import requirement_instructions
from northstar.package import ROOT, read_package


class StudentText(HTMLParser):
    def __init__(self, html, expanded=True):
        super().__init__()
        self.expanded, self.depth, self.summary = expanded, 0, 0
        self.words = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == 'details':
            self.depth += 1
        if tag == 'summary':
            self.summary += 1

    def handle_endtag(self, tag):
        if tag == 'details':
            self.depth -= 1
        if tag == 'summary':
            self.summary -= 1

    def handle_data(self, data):
        if self.expanded or self.depth == 0 or self.summary:
            self.words.append(data)

    @property
    def text(self):
        return ' '.join(self.words)


@pytest.mark.parametrize('subject', [f'NS-{i:03}' for i in range(1, 16)])
def test_canonical_report_identical_to_pre_legibility_snapshot(cases, subject):
    before = json.loads((ROOT.parent / 'artifacts/northstar-legibility/before/canonical-digests.json').read_text())
    report = {key: value for key, value in cases[subject]['report'].items()
              if key not in ('student_reasoning_view', 'advisor_reasoning_view')}
    assert hashlib.sha256(json.dumps(report, sort_keys=True).encode()).hexdigest() == before[subject]


@pytest.mark.parametrize('subject', [f'NS-{i:03}' for i in range(1, 16)])
def test_normal_navigation_has_no_technical_tokens_even_expanded(cases, subject):
    rendered = render(cases[subject])
    for section in ['dashboard', 'curriculum', 'evidence', 'sources', 'help']:
        text = StudentText(rendered[section]).text
        assert not any(token in text for token in ['choose_n', 'DIRECT_RULE_SOURCE', 'COVERAGE_', 'assessment_complete',
                                                  'curriculum:', 'NS-V1-', 'REC-NS-', 'record_id', 'unverified', 'authority:'])
    normal = StudentText(rendered['curriculum'], expanded=False).text
    assert 'Ways of Inquiry' not in normal  # Supporting course lists are behind Why.
    assert 'Where this comes from' in normal
    assert 'institutionally confirmed' in normal


def test_governed_instructions_preserve_all_singleton_choice_and_credit():
    names = {r['code']: r['name'] for r in read_package('courses.json')}
    rules = {r['id']: r for r in read_package('degree_requirements.json')['programmes']['systems_inquiry']['curriculum_rules']}
    assert requirement_instructions(rules['foundation'], names) == 'Complete FOUND-X7 - Ways of Inquiry.'
    assert 'Complete every listed course' in requirement_instructions(rules['core'], names)
    assert 'Complete one course from this group' in requirement_instructions(rules['studio'], names)
    assert 'at least 15 credits' in requirement_instructions(rules['studio_credit'], names)
    assert 'at least 2 of these preparation options' in requirement_instructions(rules['route_choices'], names)
    assert requirement_instructions({'type': 'unknown', 'label': 'Source required'}, {}) == 'Source required'


@pytest.mark.parametrize('subject,expected', [
    ('NS-002', 'You do not meet this requirement yet.'),
    ('NS-003', 'does not have enough information to decide'),
    ('NS-006', 'will not choose one automatically'),
    ('NS-004', 'includes an institutional recognition decision that counts toward this requirement'),
    ('NS-005', 'Recognition information may affect this result'),
    ('NS-008', 'course achievement meets the represented achievement requirement'),
    ('NS-009', 'external subject result meets'),
    ('NS-010', 'supplied information establishes a qualifying prior qualification'),
    ('NS-011', 'This is not an admission decision'),
])
def test_plain_explanations_are_supported_by_existing_result(cases, subject, expected):
    assert expected in StudentText(render(cases[subject])['curriculum']).text


def test_qualification_recognition_and_local_completion_are_not_conflated(cases):
    text = StudentText(render(cases['NS-015'])['curriculum']).text
    assert 'Recognition is not a new course attempt or mark' in text
    assert 'exact qualification match, not equivalence' in text
    assert 'Systems Foundations' in text
    assert 'Award evidence supplied' in text
    assert 'CRE did not confer it' in text


def test_completed_alternative_does_not_mark_unused_choice_as_failed(cases):
    html = render(cases['NS-007'])['curriculum']
    assert 'Complete one course from this group' in html
    assert 'ALT-V8 - Inquiry Studio' in html
    assert 'PATH-Z9 - Systems Studio' in html
    assert 'ALT-V8 is not' not in html


def test_source_evidence_and_inspector_remain_separate(cases):
    rendered = render(cases['NS-015'])
    assert 'Northstar Academic Rules Registry' in rendered['sources']
    assert 'Northstar synthetic student register' not in rendered['sources']
    assert 'Northstar synthetic student register' in rendered['evidence']
    script = (ROOT.parent / 'static/northstar.js').read_text()
    assert 'advisor_reasoning_view' in script
    assert 'source_relationships' in script
    assert 'payload.subject_reference' in script
    assert 'payload.subject_reference' not in next(line for line in script.splitlines() if 'ns("release").textContent' in line)


def test_condensed_dashboard_does_not_repeat_aggregate_actions(cases):
    text = StudentText(render(cases['NS-003'])['dashboard'], expanded=False).text
    assert 'not a percentage' in text
    assert 'What needs attention' in text
    assert 'Representation authority' not in text
    assert 'Your next steps' not in text


def test_no_student_case_specific_logic_in_shared_language():
    text = (ROOT.parent / 'static/student-language.js').read_text()
    assert 'NS-0' not in text and 'Northstar' not in text and 'FOUND-X7' not in text
    assert 'fetch(' not in text
    assert 'assessment_complete =' not in text
