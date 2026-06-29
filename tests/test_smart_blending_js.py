import subprocess
import tempfile
from pathlib import Path


def run_smart_blending_script(extra_script):
    script_path = Path("static/js/smart_blending.js")
    script = script_path.read_text(encoding="utf-8")
    harness = r"""
const elements = new Map();
const queryElements = new Map();

function makeElement(id) {
  const element = {
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
  };
  element.classList = {
    add(...names) {
      const classes = new Set(element.className.split(/\s+/).filter(Boolean));
      names.forEach(name => classes.add(name));
      element.className = Array.from(classes).join(' ');
    },
    remove(...names) {
      const classes = new Set(element.className.split(/\s+/).filter(Boolean));
      names.forEach(name => classes.delete(name));
      element.className = Array.from(classes).join(' ');
    },
    toggle(name, force) {
      const classes = new Set(element.className.split(/\s+/).filter(Boolean));
      const shouldAdd = force === undefined ? !classes.has(name) : Boolean(force);
      if (shouldAdd) {
        classes.add(name);
      } else {
        classes.delete(name);
      }
      element.className = Array.from(classes).join(' ');
      return shouldAdd;
    },
    contains(name) {
      return element.className.split(/\s+/).filter(Boolean).includes(name);
    },
  };
  return element;
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
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8', dir=Path.cwd()) as temp_file:
        temp_file.write(harness)
        temp_file.write("\n")
        temp_file.write(script)
        temp_file.write("\n")
        temp_file.write(extra_script)
        temp_path = temp_file.name

    try:
        result = subprocess.run(
            ["node", temp_path],
            text=True,
            encoding='utf-8',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    finally:
        Path(temp_path).unlink(missing_ok=True)

    assert result.returncode == 0, result.stderr
    return result


def test_quick_result_summary_default_state_does_not_throw():
    run_smart_blending_script("updateQuickResultSummary();\n")


def test_optimization_progress_panel_updates_waiting_feedback():
    extra_script = r"""
const requestData = {
  selected_coal_ids: [1, 6],
  ga_params: {
    population_size: 500,
    max_generations: 3000
  }
};

showLoadingState('正在进行优化计算，请稍候...', requestData);
updateOptimizationProgress(requestData);

const title = document.getElementById('optimizationProgressTitle');
const meta = document.getElementById('optimizationProgressMeta');
const hint = document.getElementById('optimizationProgressHint');
const bar = document.getElementById('optimizationProgressBar');

if (!title.textContent.includes('快速扫描') && !title.textContent.includes('Pareto')) {
  throw new Error('Optimization progress title was not updated');
}
if (!meta.textContent.includes('已等待')) {
  throw new Error('Optimization progress meta was not updated');
}
if (!hint.textContent.includes('几秒')) {
  throw new Error('Optimization progress hint was not updated');
}
if (!bar.style.width || !bar.style.width.endsWith('%')) {
  throw new Error('Optimization progress bar width was not updated');
}

hideLoadingState();
"""
    run_smart_blending_script(extra_script)


def test_view_results_button_warns_until_result_exists():
    extra_script = r"""
let warningMessage = '';
global.alert = function(message) { warningMessage = message; };
document.getElementById('resultsSection').classList.add('d-none');

scrollToResultsSection();

if (!warningMessage) {
  throw new Error('View results did not warn when no result exists');
}
if (document.getElementById('resultsSection').classList.contains('d-none') === false) {
  throw new Error('Results section should stay hidden before optimization');
}
if (document.getElementById('workspaceStatusBar').attributes['data-tone'] !== 'warning') {
  throw new Error('Workspace status was not updated to warning');
}
"""
    run_smart_blending_script(extra_script)


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
document.getElementById('resultsSection').classList.add('d-none');
displayOptimizationResults('success', data, 'ok');
if (document.getElementById('resultsSection').classList.contains('d-none')) {
  throw new Error('Results section stayed hidden after optimization result');
}
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
