const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

test('reviewer receives criterion-specific anchors with evidence', async () => {
  const elements = new Map();
  const make = () => ({ children: [], dataset: {}, listeners: {}, value: '',
    append(...children) { this.children.push(...children); },
    replaceChildren() { this.children = []; },
    addEventListener(type, fn) { this.listeners[type] = fn; } });
  const get = id => { if (!elements.has(id)) elements.set(id, make()); return elements.get(id); };
  const context = { URLSearchParams, FormData: class { get() { return 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'; } },
    window: { location: { search: '' } },
    document: { getElementById: get, createElement: make },
    InterviewAPI: { requireAuth: () => true, request: async path => {
      if (path.endsWith('/evidence')) return { assessment: {
        dimensions: { E_verification: { label: 'Verification', weight: 20, status: 'not_assessed' } },
        dimension_anchors: { E_verification: { 3: 'Checks relevant regressions', 4: 'Uses an independent oracle' } }
      }, external_evaluation: { payload: { manual_requirements: [] } } };
      if (path.endsWith('/appeals')) return { appeals: [] };
      return { reviews: [] };
    } } };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(__dirname + '/interview-grading.js', 'utf8'), context);
  await get('load').listeners.submit({ preventDefault() {}, target: {} });
  const field = get('criteria').children[0];
  assert.equal(field.children[0].textContent, 'Verification (20%)');
  const guide = field.children[1];
  assert.equal(guide.children[0].textContent, 'Scoring anchors');
  assert.equal(guide.children[2].textContent, '4 / 4: Uses an independent oracle');
});
