"""Exact presentation equivalence to the four helpers at d734183, without the shell."""

import json
import re
import subprocess
from pathlib import Path

import pytest
from test_northstar_student_interface import cases as cases
from test_ppe_pilot_fidelity_repair import report as ppe_report

ROOT = Path(__file__).resolve().parents[1]

# Frozen pre-extraction implementations: only an equivalence oracle, never production.
BASELINE = r'''
const esc = value => String(value ?? "").replace(/[&<>"']/g, character => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[character]));
const titleCase = value => String(value || "")
  .replaceAll("_", " ")
  .replace(/\b\w/g, character => character.toUpperCase());
const asArray = value => Array.isArray(value) ? value : [];
function studentConclusionCard(item, presentation = {}) {
  return StudentLanguage.card(item, typeof presentation === "object" ? presentation : {});
}
'''


def compare(expression, data=None):
    script = r'''
const fs = require('fs'), vm = require('vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const outputs = [input.baseline, fs.readFileSync('static/student-shared.js', 'utf8')].map(source => {
  const context = {data: input.data};
  vm.createContext(context);
  vm.runInContext(source, context);
  vm.runInContext(fs.readFileSync('static/student-language.js', 'utf8'), context);
  const before = JSON.stringify(context.data);
  const result = vm.runInContext(input.expression, context);
  if (before !== JSON.stringify(context.data)) throw new Error('Projection mutated');
  return result;
});
process.stdout.write(JSON.stringify(outputs));
'''
    result = subprocess.run(['node', '-e', script], input=json.dumps({
        'baseline': BASELINE, 'expression': expression, 'data': data,
    }), capture_output=True, text=True, encoding='utf-8', cwd=ROOT, check=True)
    before, after = json.loads(result.stdout)
    assert after == before
    return after


def test_primitive_values_and_lexical_contract():
    result = compare(r'''(() => {
      const array = [1, 'x'];
      return {
        escaped: [undefined, null, '', '&<>"\'', 0, false].map(esc),
        arrays: [undefined, null, 4, 'x', {}, array].map(asArray),
        sameArray: asArray(array) === array,
        titles: [undefined, null, '', 'nsc_MATHS', 'already-UPPER', 'two  words', 0].map(titleCase),
        lexical: Object.prototype.hasOwnProperty.call(globalThis, 'esc'),
        bridge: typeof globalThis.studentConclusionCard
      };
    })()''')
    assert result['escaped'] == ['', '', '', '&amp;&lt;&gt;&quot;&#39;', '0', 'false']
    assert result['arrays'] == [[], [], [], [], [], [1, 'x']]
    assert result['sameArray']
    assert result['titles'] == ['', '', '', 'Nsc MATHS', 'Already-UPPER', 'Two  Words', '']
    assert not result['lexical']
    assert result['bridge'] == 'function'


@pytest.mark.parametrize('subject', [f'NS-{i:03}' for i in range(1, 16)] + ['PPE'])
def test_real_projection_card_html_is_identical(cases, subject):
    report = ppe_report() if subject == 'PPE' else cases[subject]['report']
    items = report['student_reasoning_view']['conclusions']
    rendered = compare('data.map(item => studentConclusionCard(item))', items)
    assert len(rendered) == len(items)
    assert all(isinstance(html, str) for html in rendered)


def test_bridge_forwards_context_and_array_map_index_without_interpretation():
    result = compare('''(() => {
      StudentLanguage.card = (item, context) => ({sameItem: item === data, context});
      return [studentConclusionCard(data), studentConclusionCard(data, 3),
              studentConclusionCard(data, {institution_name: 'Other', label: '<&>'}),
              studentConclusionCard(data, null)];
    })()''', {'outcome': 'conflict', 'source_missing': True})
    assert all(row['sameItem'] for row in result)
    assert [row['context'] for row in result] == [{}, {}, {'institution_name': 'Other', 'label': '<&>'}, None]


def test_only_four_neutral_interfaces_and_no_shell_dependency():
    source = (ROOT / 'static/student-shared.js').read_text(encoding='utf-8')
    assert re.findall(r'^(?:const|function) (\w+)', source, re.M) == [
        'esc', 'titleCase', 'asArray', 'studentConclusionCard']
    assert not re.search(r'\b(uct|northstar|faculty|document|window|fetch|state)\b',
                         '\n'.join(line for line in source.splitlines() if not line.strip().startswith('//')), re.I)
    shell = (ROOT / 'static/app.js').read_text(encoding='utf-8')
    for name in ['esc', 'asArray', 'titleCase', 'studentConclusionCard']:
        assert not re.search(rf'^(?:const|function) {name}\b', shell, re.M)
    assert 'data-projection-only' not in shell
    assert '/static/app.js' not in (ROOT / 'static/northstar.html').read_text(encoding='utf-8')
