import subprocess
from pathlib import Path


def test_quick_result_summary_default_state_does_not_throw():
    script_path = Path("static/js/smart_blending.js")
    script = script_path.read_text(encoding="utf-8")
    harness = r"""
const elements = new Map();
function makeElement(id) {
  return {
    id,
    textContent: '',
    className: '',
    attributes: {},
    style: {},
    dataset: {},
    children: [],
    addEventListener() {},
    appendChild(child) { this.children.push(child); },
    setAttribute(name, value) { this.attributes[name] = value; },
    querySelector() { return null; },
    querySelectorAll() { return []; },
    classList: {
      add() {},
      remove() {},
      toggle() {},
    },
  };
}
const documentStub = {
  addEventListener() {},
  createElement(tag) { return makeElement(tag); },
  querySelector() { return null; },
  querySelectorAll() { return []; },
  getElementById(id) {
    if (!elements.has(id)) {
      elements.set(id, makeElement(id));
    }
    return elements.get(id);
  },
};
global.document = documentStub;
global.window = { localStorage: { getItem() { return null; }, setItem() {} } };
global.localStorage = global.window.localStorage;
global.bootstrap = { Modal: { getOrCreateInstance() { return { show() {}, hide() {} }; } } };
global.Chart = function() { return { destroy() {}, update() {} }; };
global.fetch = async () => ({ ok: true, json: async () => ({ status: 'success', data: [] }) });
"""
    result = subprocess.run(
        ["node", "-e", harness + "\n" + script + "\nupdateQuickResultSummary();\n"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
