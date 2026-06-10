import subprocess
from pathlib import Path


def run_smart_blending_script(extra_script):
    script_path = Path("static/js/smart_blending.js")
    script = script_path.read_text(encoding="utf-8")
    harness = r"""
const elements = new Map();
const queryElements = new Map();

function makeElement(id) {
  return {
    id,
    textContent: '',
    innerHTML: '',
    className: '',
    attributes: {},
    style: {},
    dataset: {},
    children: [],
    disabled: false,
    value: '',
    addEventListener() {},
    appendChild(child) { this.children.push(child); },
    setAttribute(name, value) { this.attributes[name] = value; },
    querySelector() { return null; },
    querySelectorAll() { return []; },
    scrollIntoView() {},
    classList: {
      add() {},
      remove() {},
      toggle() {},
      contains() { return false; },
    },
  };
}

function getQueryElement(selector) {
  if (!queryElements.has(selector)) {
    queryElements.set(selector, makeElement(selector));
  }
  return queryElements.get(selector);
}

const documentStub = {
  addEventListener() {},
  createElement(tag) { return makeElement(tag); },
  querySelector(selector) { return getQueryElement(selector); },
  querySelectorAll() { return []; },
  getElementById(id) {
    if (!elements.has(id)) {
      elements.set(id, makeElement(id));
    }
    return elements.get(id);
  },
};

global.document = documentStub;
global.window = { localStorage: { getItem() { return null; }, setItem() {}, removeItem() {} } };
global.localStorage = global.window.localStorage;
global.bootstrap = {
  Modal: {
    getInstance() { return { hide() {}, show() {} }; },
    getOrCreateInstance() { return { show() {}, hide() {} }; },
  },
};
global.Chart = function() { return { destroy() {}, update() {} }; };
global.fetch = async () => ({ ok: true, json: async () => ({ status: 'success', data: [] }) });
global.alert = function() {};
global.navigator = { clipboard: { writeText: async () => {} } };
"""
    result = subprocess.run(
        ["node", "-e", harness + "\n" + script + "\n" + extra_script],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    return result


def test_quick_result_summary_default_state_does_not_throw():
    run_smart_blending_script("updateQuickResultSummary();\n")


def test_pareto_solutions_render_and_can_be_selected():
    extra_script = r"""
const data = {
  objective_type: 'pci_pareto_nsga2_v1',
  optimization_target: '多目标Pareto最优',
  is_feasible: true,
  constraints_satisfied: true,
  coal_names: ['经济煤', '高热值煤', '低硫煤'],
  optimal_ratios: [0.5, 0.3, 0.2],
  blending_ratio: {'经济煤': 0.5, '高热值煤': 0.3, '低硫煤': 0.2},
  total_price: 580,
  total_heat: 6400,
  total_ash: 10.2,
  total_volatile: 22,
  total_fixed_carbon: 65,
  total_sulfur: 0.55,
  iterations: 30,
  time_taken: 0.2,
  fitness_value: 0.14,
  active_constraints: [],
  constraint_violations: [],
  diagnosis: [],
  recommended_solution: {
    solution_id: 'pareto_001',
    optimal_ratios: [0.5, 0.3, 0.2],
    total_price: 580,
    total_heat: 6400,
    total_ash: 10.2,
    total_volatile: 22,
    total_fixed_carbon: 65,
    total_sulfur: 0.55,
    quality_penalty: 0.14,
    objective_values: {cost: 580, heat: 6400, quality_penalty: 0.14}
  },
  pareto_solutions: [
    {
      solution_id: 'pareto_001',
      optimal_ratios: [0.5, 0.3, 0.2],
      total_price: 580,
      total_heat: 6400,
      total_ash: 10.2,
      total_volatile: 22,
      total_fixed_carbon: 65,
      total_sulfur: 0.55,
      quality_penalty: 0.14,
      objective_values: {cost: 580, heat: 6400, quality_penalty: 0.14}
    },
    {
      solution_id: 'pareto_002',
      optimal_ratios: [0.2, 0.7, 0.1],
      total_price: 650,
      total_heat: 6800,
      total_ash: 9.4,
      total_volatile: 21,
      total_fixed_carbon: 67,
      total_sulfur: 0.44,
      quality_penalty: 0.08,
      objective_values: {cost: 650, heat: 6800, quality_penalty: 0.08}
    }
  ]
};

displayOptimizationResults('success', data, 'ok');
const paretoBody = document.querySelector('.pareto-solutions-table tbody');
if (!paretoBody.innerHTML.includes('pareto_002')) {
  throw new Error('Pareto table did not render second solution');
}

selectParetoSolution('pareto_002');
if (latestDisplayedResult.total_heat !== 6800) {
  throw new Error('Selecting Pareto solution did not update displayed result');
}
if (latestDisplayedResult.blending_ratio['高热值煤'] !== 0.7) {
  throw new Error('Selecting Pareto solution did not update blending ratio');
}
"""
    run_smart_blending_script(extra_script)
