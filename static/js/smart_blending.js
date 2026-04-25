// 智能混煤页面 JavaScript

const SMART_BLENDING_STORAGE_KEY = 'smartBlendingPreferencesV1';
const LEGACY_ALGORITHM_STORAGE_KEY = 'algorithmSettings';

const DEFAULT_CONSTRAINTS = {
    heat_target: 6800,
    heat_min: 6000,
    heat_max: 7800,
    ash_min: 0.0,
    ash_max: 20.0,
    volatile_min: 8.0,
    volatile_max: 40.0,
    fixed_carbon_min: 50.0,
    fixed_carbon_max: 85.0,
    sulfur_min: 0.0,
    sulfur_max: 1.2,
    price_min: 0,
    price_max: 1500
};

const DEFAULT_GLOBAL_RATIO_CONSTRAINTS = {
    min: 0,
    max: 100
};

const DEFAULT_GA_PARAMS = {
    population_size: 500,
    max_generations: 3000,
    mutation_rate: 0.2,
    crossover_rate: 0.85,
    tournament_size: 7,
    elite_ratio: 0.1,
    early_stopping_patience: 200,
    constraint_penalty_factor: 1500,
    parallel_workers: 4,
    diversity_factor: 0.1,
    adaptive_mutation: true,
    parallel_computing: true
};

const CONSTRAINT_FIELD_MAP = {
    heatTarget: 'heat_target',
    heatMin: 'heat_min',
    heatMax: 'heat_max',
    ashMin: 'ash_min',
    ashMax: 'ash_max',
    volatileMin: 'volatile_min',
    volatileMax: 'volatile_max',
    fixedCarbonMin: 'fixed_carbon_min',
    fixedCarbonMax: 'fixed_carbon_max',
    sulfurMin: 'sulfur_min',
    sulfurMax: 'sulfur_max',
    priceMin: 'price_min',
    priceMax: 'price_max'
};

const CONSTRAINT_LIMITS = {
    heat_target: { min: 0, max: 20000 },
    heat_min: { min: 0, max: 20000 },
    heat_max: { min: 0, max: 20000 },
    ash_min: { min: 0, max: 100 },
    ash_max: { min: 0, max: 100 },
    volatile_min: { min: 0, max: 100 },
    volatile_max: { min: 0, max: 100 },
    fixed_carbon_min: { min: 0, max: 100 },
    fixed_carbon_max: { min: 0, max: 100 },
    sulfur_min: { min: 0, max: 100 },
    sulfur_max: { min: 0, max: 100 },
    price_min: { min: 0, max: 100000 },
    price_max: { min: 0, max: 100000 }
};

const GA_FIELD_MAP = {
    populationSize: 'population_size',
    maxGenerations: 'max_generations',
    mutationRate: 'mutation_rate',
    crossoverRate: 'crossover_rate',
    tournamentSize: 'tournament_size',
    eliteRatio: 'elite_ratio',
    earlyStoppingPatience: 'early_stopping_patience',
    constraintPenaltyFactor: 'constraint_penalty_factor',
    parallelWorkers: 'parallel_workers',
    diversityFactor: 'diversity_factor',
    adaptiveMutation: 'adaptive_mutation',
    parallelComputing: 'parallel_computing'
};

let selectedCoals = new Set();
let allCoals = [];
let filteredCoals = [];
let currentCoalPage = 1;
let coalPageSize = 10;
let optimizationInProgress = false;
let exportInProgress = false;
let latestDisplayedResult = null;
let lastOptimizationResult = null;
let smartBlendingPreferences = createDefaultPreferences();
let ratioChartInstance = null;
let performanceChartInstance = null;
let constraintChartInstance = null;
let autoSaveStatusTimer = null;
let constraintSettingsModalInstance = null;

document.addEventListener('DOMContentLoaded', function() {
    initializeSmartBlendingPage();
});

function initializeSmartBlendingPage() {
    smartBlendingPreferences = loadPreferences();
    selectedCoals = new Set(smartBlendingPreferences.selectedCoalIds);

    applyPreferencesToDom();
    setupBlendingEventListeners();
    updateSelectedCoalCount();
    updateConstraintQuickSummary();
    updateConstraintModalSummary();
    updateQuickResultSummary();
    updateActionButtonsState();
    syncWorkspaceStatus('info', '等待选择煤种，当前配置将在本地自动保存。', '选择至少两种煤后即可直接开始优化');
    loadCoalsForBlending();
}

function createDefaultPreferences() {
    return {
        version: 1,
        selectedCoalIds: [],
        constraints: { ...DEFAULT_CONSTRAINTS },
        globalRatioConstraints: { ...DEFAULT_GLOBAL_RATIO_CONSTRAINTS },
        ratioConstraintsByCoalId: {},
        gaParams: { ...DEFAULT_GA_PARAMS }
    };
}

function loadPreferences() {
    const defaults = createDefaultPreferences();
    let savedPreferences = null;
    let legacySettings = null;

    try {
        const raw = localStorage.getItem(SMART_BLENDING_STORAGE_KEY);
        if (raw) {
            savedPreferences = JSON.parse(raw);
        }
    } catch (error) {
        console.error('读取智能混煤本地配置失败:', error);
    }

    try {
        const rawLegacy = localStorage.getItem(LEGACY_ALGORITHM_STORAGE_KEY);
        if (rawLegacy) {
            legacySettings = JSON.parse(rawLegacy);
        }
    } catch (error) {
        console.error('读取旧版算法配置失败:', error);
    }

    const merged = {
        ...defaults,
        ...(savedPreferences || {}),
        constraints: {
            ...defaults.constraints,
            ...(savedPreferences?.constraints || {})
        },
        globalRatioConstraints: {
            ...defaults.globalRatioConstraints,
            ...(savedPreferences?.globalRatioConstraints || {})
        },
        ratioConstraintsByCoalId: {
            ...(savedPreferences?.ratioConstraintsByCoalId || {})
        },
        gaParams: {
            ...defaults.gaParams,
            ...(legacySettings || {}),
            ...(savedPreferences?.gaParams || {})
        }
    };

    const sanitized = sanitizePreferences(merged);

    if (legacySettings) {
        persistPreferences(sanitized, {
            silent: true,
            statusText: '已迁移旧版算法设置，下次进入将自动恢复'
        });
        localStorage.removeItem(LEGACY_ALGORITHM_STORAGE_KEY);
    }

    if (savedPreferences) {
        setAutoSaveStatus('已加载上次保存的配置', 'info');
    } else if (!legacySettings) {
        setAutoSaveStatus('使用系统默认配置，修改后将自动保存', 'muted');
    }

    return sanitized;
}

function sanitizePreferences(preferences) {
    const result = createDefaultPreferences();

    result.version = Number.isFinite(Number(preferences?.version)) ? Number(preferences.version) : 1;
    result.constraints = sanitizeConstraints(preferences?.constraints);
    result.globalRatioConstraints = sanitizeRatioConstraint(
        preferences?.globalRatioConstraints,
        DEFAULT_GLOBAL_RATIO_CONSTRAINTS
    );
    result.gaParams = sanitizeGaParams(preferences?.gaParams);
    result.selectedCoalIds = Array.isArray(preferences?.selectedCoalIds)
        ? [...new Set(preferences.selectedCoalIds.map(id => Number(id)).filter(Number.isInteger))]
        : [];

    const ratioConstraintsByCoalId = {};
    const rawRatioConstraints = preferences?.ratioConstraintsByCoalId || {};
    Object.keys(rawRatioConstraints).forEach(coalId => {
        const numericCoalId = Number(coalId);
        if (!Number.isInteger(numericCoalId)) {
            return;
        }
        ratioConstraintsByCoalId[String(numericCoalId)] = sanitizeRatioConstraint(
            rawRatioConstraints[coalId],
            result.globalRatioConstraints
        );
    });
    result.ratioConstraintsByCoalId = ratioConstraintsByCoalId;

    return result;
}

function sanitizeConstraints(rawConstraints = {}) {
    return {
        heat_target: sanitizeNumber(rawConstraints.heat_target, DEFAULT_CONSTRAINTS.heat_target, { min: 0, max: 20000 }),
        heat_min: sanitizeNumber(rawConstraints.heat_min, DEFAULT_CONSTRAINTS.heat_min, { min: 0, max: 20000 }),
        heat_max: sanitizeNumber(rawConstraints.heat_max, DEFAULT_CONSTRAINTS.heat_max, { min: 0, max: 20000 }),
        ash_min: sanitizeNumber(rawConstraints.ash_min, DEFAULT_CONSTRAINTS.ash_min, { min: 0, max: 100 }),
        ash_max: sanitizeNumber(rawConstraints.ash_max, DEFAULT_CONSTRAINTS.ash_max, { min: 0, max: 100 }),
        volatile_min: sanitizeNumber(rawConstraints.volatile_min, DEFAULT_CONSTRAINTS.volatile_min, { min: 0, max: 100 }),
        volatile_max: sanitizeNumber(rawConstraints.volatile_max, DEFAULT_CONSTRAINTS.volatile_max, { min: 0, max: 100 }),
        fixed_carbon_min: sanitizeNumber(rawConstraints.fixed_carbon_min, DEFAULT_CONSTRAINTS.fixed_carbon_min, { min: 0, max: 100 }),
        fixed_carbon_max: sanitizeNumber(rawConstraints.fixed_carbon_max, DEFAULT_CONSTRAINTS.fixed_carbon_max, { min: 0, max: 100 }),
        sulfur_min: sanitizeNumber(rawConstraints.sulfur_min, DEFAULT_CONSTRAINTS.sulfur_min, { min: 0, max: 100 }),
        sulfur_max: sanitizeNumber(rawConstraints.sulfur_max, DEFAULT_CONSTRAINTS.sulfur_max, { min: 0, max: 100 }),
        price_min: sanitizeNumber(rawConstraints.price_min, DEFAULT_CONSTRAINTS.price_min, { min: 0, max: 100000 }),
        price_max: sanitizeNumber(rawConstraints.price_max, DEFAULT_CONSTRAINTS.price_max, { min: 0, max: 100000 })
    };
}

function sanitizeGaParams(rawParams = {}) {
    return {
        population_size: sanitizeInteger(rawParams.population_size, DEFAULT_GA_PARAMS.population_size, { min: 1, max: 20000 }),
        max_generations: sanitizeInteger(rawParams.max_generations, DEFAULT_GA_PARAMS.max_generations, { min: 1, max: 20000 }),
        mutation_rate: sanitizeNumber(rawParams.mutation_rate, DEFAULT_GA_PARAMS.mutation_rate, { min: 0, max: 1 }),
        crossover_rate: sanitizeNumber(rawParams.crossover_rate, DEFAULT_GA_PARAMS.crossover_rate, { min: 0, max: 1 }),
        tournament_size: sanitizeInteger(rawParams.tournament_size, DEFAULT_GA_PARAMS.tournament_size, { min: 2, max: 100 }),
        elite_ratio: sanitizeNumber(rawParams.elite_ratio, DEFAULT_GA_PARAMS.elite_ratio, { min: 0, max: 1 }),
        early_stopping_patience: sanitizeInteger(rawParams.early_stopping_patience, DEFAULT_GA_PARAMS.early_stopping_patience, { min: 1, max: 100000 }),
        constraint_penalty_factor: sanitizeNumber(rawParams.constraint_penalty_factor, DEFAULT_GA_PARAMS.constraint_penalty_factor, { min: 0, max: 1000000 }),
        parallel_workers: sanitizeInteger(rawParams.parallel_workers, DEFAULT_GA_PARAMS.parallel_workers, { min: 1, max: 128 }),
        diversity_factor: sanitizeNumber(rawParams.diversity_factor, DEFAULT_GA_PARAMS.diversity_factor, { min: 0, max: 1 }),
        adaptive_mutation: Boolean(rawParams.adaptive_mutation ?? DEFAULT_GA_PARAMS.adaptive_mutation),
        parallel_computing: Boolean(rawParams.parallel_computing ?? DEFAULT_GA_PARAMS.parallel_computing)
    };
}

function sanitizeRatioConstraint(rawConstraint, fallbackConstraint) {
    const fallback = fallbackConstraint || DEFAULT_GLOBAL_RATIO_CONSTRAINTS;
    const minValue = sanitizeNumber(rawConstraint?.min, fallback.min, { min: 0, max: 100 });
    const maxValue = sanitizeNumber(rawConstraint?.max, fallback.max, { min: 0, max: 100 });
    return normalizeRatioConstraint(minValue, maxValue);
}

function sanitizeNumber(value, fallback, options = {}) {
    const numericValue = Number(value);
    if (!Number.isFinite(numericValue)) {
        return fallback;
    }

    const min = options.min ?? -Infinity;
    const max = options.max ?? Infinity;
    return Math.min(max, Math.max(min, numericValue));
}

function sanitizeInteger(value, fallback, options = {}) {
    return Math.round(sanitizeNumber(value, fallback, options));
}

function normalizeRatioConstraint(minValue, maxValue) {
    let min = sanitizeNumber(minValue, DEFAULT_GLOBAL_RATIO_CONSTRAINTS.min, { min: 0, max: 100 });
    let max = sanitizeNumber(maxValue, DEFAULT_GLOBAL_RATIO_CONSTRAINTS.max, { min: 0, max: 100 });

    if (min >= max) {
        if (max >= 100) {
            min = 99;
            max = 100;
        } else {
            max = Math.min(100, min + 1);
        }
    }

    return {
        min: Number(min.toFixed(1)),
        max: Number(max.toFixed(1))
    };
}

function persistPreferences(preferences = smartBlendingPreferences, options = {}) {
    smartBlendingPreferences = sanitizePreferences(preferences);
    selectedCoals = new Set(smartBlendingPreferences.selectedCoalIds);

    try {
        localStorage.setItem(SMART_BLENDING_STORAGE_KEY, JSON.stringify(smartBlendingPreferences));
        if (!options.silent) {
            setAutoSaveStatus(options.statusText || '已自动保存当前配置', 'success');
        } else if (options.statusText) {
            setAutoSaveStatus(options.statusText, 'info');
        }
    } catch (error) {
        console.error('保存智能混煤配置失败:', error);
        setAutoSaveStatus('本地保存失败，请检查浏览器存储权限', 'error');
    }
}

function setAutoSaveStatus(message, tone = 'muted') {
    const statusElement = document.getElementById('autoSaveStatus');
    if (!statusElement) {
        return;
    }

    statusElement.textContent = message;
    statusElement.className = 'small';

    if (tone === 'success') {
        statusElement.classList.add('text-success');
    } else if (tone === 'error') {
        statusElement.classList.add('text-danger');
    } else if (tone === 'info') {
        statusElement.classList.add('text-primary');
    } else {
        statusElement.classList.add('text-muted');
    }

    if (autoSaveStatusTimer) {
        clearTimeout(autoSaveStatusTimer);
    }

    if (tone !== 'muted') {
        autoSaveStatusTimer = setTimeout(() => {
            statusElement.textContent = '当前配置将在下次自动恢复';
            statusElement.className = 'small text-muted';
        }, 2500);
    }
}

function applyPreferencesToDom() {
    Object.entries(CONSTRAINT_FIELD_MAP).forEach(([elementId, preferenceKey]) => {
        const element = document.getElementById(elementId);
        if (element) {
            element.value = smartBlendingPreferences.constraints[preferenceKey];
        }
    });

    const globalMin = document.getElementById('globalRatioMin');
    const globalMax = document.getElementById('globalRatioMax');
    if (globalMin) {
        globalMin.value = smartBlendingPreferences.globalRatioConstraints.min;
    }
    if (globalMax) {
        globalMax.value = smartBlendingPreferences.globalRatioConstraints.max;
    }

    Object.entries(GA_FIELD_MAP).forEach(([elementId, preferenceKey]) => {
        const element = document.getElementById(elementId);
        if (!element) {
            return;
        }
        if (element.type === 'checkbox') {
            element.checked = smartBlendingPreferences.gaParams[preferenceKey];
        } else {
            element.value = smartBlendingPreferences.gaParams[preferenceKey];
        }
    });
}

function setupBlendingEventListeners() {
    const searchInput = document.getElementById('coalSearchInput');
    if (searchInput) {
        searchInput.addEventListener('keypress', function(event) {
            if (event.key === 'Enter') {
                searchCoalsForBlending();
            }
        });
    }

    document.getElementById('coalSearchBtn')?.addEventListener('click', searchCoalsForBlending);
    document.getElementById('coalRefreshBtn')?.addEventListener('click', refreshCoalList);

    document.getElementById('coalPageSize')?.addEventListener('change', function() {
        coalPageSize = parseInt(this.value, 10) || 10;
        currentCoalPage = 1;
        displayCoalsForBlending();
    });

    document.getElementById('coalTypeFilter')?.addEventListener('change', searchCoalsForBlending);
    document.getElementById('optimizationTarget')?.addEventListener('change', handleOptimizationTargetChanged);

    document.querySelectorAll('.constraint-input').forEach(input => {
        input.addEventListener('change', handleConstraintInputsChanged);
        input.addEventListener('blur', handleConstraintInputsChanged);
    });

    document.querySelectorAll('.algorithm-setting-input').forEach(input => {
        const eventName = input.type === 'checkbox' ? 'change' : 'change';
        input.addEventListener(eventName, handleAlgorithmSettingsChanged);
    });

    document.getElementById('resetConstraintsBtn')?.addEventListener('click', resetConstraintSettings);
    document.getElementById('applyGlobalRatioBtn')?.addEventListener('click', applyGlobalRatioConstraints);
    document.getElementById('saveAlgorithmSettingsBtn')?.addEventListener('click', saveAlgorithmSettings);
    document.getElementById('resetAlgorithmSettingsBtn')?.addEventListener('click', resetAlgorithmSettings);
    document.getElementById('scrollToResultsBtn')?.addEventListener('click', scrollToResultsSection);
    document.getElementById('scrollToResultsBtnMobile')?.addEventListener('click', scrollToResultsSection);
    document.getElementById('backToWorkspaceBtn')?.addEventListener('click', scrollToWorkspaceSection);
    document.getElementById('exportReportBtn')?.addEventListener('click', exportOptimizationReport);
    document.getElementById('copyShareResultBtn')?.addEventListener('click', copyShareableResultText);

    document.querySelectorAll('.start-optimization-btn').forEach(button => {
        button.addEventListener('click', function() {
            openConstraintSettingsModal(this.dataset.openReason || 'start');
        });
    });

    document.querySelectorAll('.open-constraint-settings-btn').forEach(button => {
        button.addEventListener('click', function() {
            openConstraintSettingsModal(this.dataset.openReason || 'edit');
        });
    });

    document.getElementById('confirmOptimizationBtn')?.addEventListener('click', startOptimization);
}

async function loadCoalsForBlending() {
    try {
        showLoadingState('加载煤种数据...');
        const response = await fetch('/api/coals?page_size=0');
        const result = await response.json();

        if (result.status === 'success') {
            allCoals = Array.isArray(result.data) ? result.data : [];
            filteredCoals = [...allCoals];
            reconcilePreferencesWithCoalData();
            displayCoalsForBlending();
            updateSelectedCoalCount();
            updateConstraintQuickSummary();
        } else {
            showErrorMessage('加载煤种数据失败: ' + result.message);
        }
    } catch (error) {
        showErrorMessage('网络错误: ' + error.message);
    } finally {
        hideLoadingState();
    }
}

function reconcilePreferencesWithCoalData() {
    const validCoalIds = new Set(allCoals.map(coal => Number(coal.id)));
    const filteredSelectedIds = smartBlendingPreferences.selectedCoalIds.filter(id => validCoalIds.has(Number(id)));

    const filteredRatioConstraints = {};
    Object.keys(smartBlendingPreferences.ratioConstraintsByCoalId).forEach(coalId => {
        if (validCoalIds.has(Number(coalId))) {
            filteredRatioConstraints[coalId] = sanitizeRatioConstraint(
                smartBlendingPreferences.ratioConstraintsByCoalId[coalId],
                smartBlendingPreferences.globalRatioConstraints
            );
        }
    });

    smartBlendingPreferences.selectedCoalIds = filteredSelectedIds;
    smartBlendingPreferences.ratioConstraintsByCoalId = filteredRatioConstraints;
    selectedCoals = new Set(filteredSelectedIds);

    persistPreferences(smartBlendingPreferences, { silent: true });
}

function displayCoalsForBlending() {
    const tbody = document.getElementById('coalSelectionTableBody');
    if (!tbody) {
        return;
    }

    const totalPages = Math.max(1, Math.ceil(filteredCoals.length / coalPageSize));
    currentCoalPage = Math.min(Math.max(currentCoalPage, 1), totalPages);

    const startIndex = (currentCoalPage - 1) * coalPageSize;
    const endIndex = Math.min(startIndex + coalPageSize, filteredCoals.length);
    const pageCoals = filteredCoals.slice(startIndex, endIndex);

    tbody.innerHTML = '';

    if (pageCoals.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" class="text-center text-muted">暂无煤种数据</td></tr>';
        updateCoalPagination();
        updateCoalStatistics();
        updateSelectedCoalCount();
        return;
    }

    pageCoals.forEach(coal => {
        tbody.appendChild(createCoalSelectionRow(coal));
        applyRatioValidationClasses(Number(coal.id), true);
    });

    updateCoalPagination();
    updateCoalStatistics();
    updateSelectedCoalCount();
}

function createCoalSelectionRow(coal) {
    const row = document.createElement('tr');
    const isSelected = selectedCoals.has(Number(coal.id));
    const ratioConstraint = getRatioConstraintForCoal(coal.id);
    row.className = isSelected ? 'is-selected' : '';

    row.innerHTML = `
        <td>
            <input class="form-check-input" type="checkbox" value="${coal.id}"
                   ${isSelected ? 'checked' : ''} onchange="toggleCoalSelection(${coal.id})">
        </td>
        <td class="coal-name-cell">
            <div class="coal-name-main">
                <span class="coal-name-text">${coal.name}</span>
                ${isSelected ? '<span class="coal-selected-flag"><i class="bi bi-check-circle-fill"></i>已选</span>' : ''}
            </div>
            <div class="coal-name-submeta">
                <span class="badge bg-secondary">${coal.type}</span>
                <span>ID ${coal.id}</span>
            </div>
        </td>
        <td class="metric-cell"><strong>¥${coal.price.toFixed(2)}</strong></td>
        <td class="metric-cell"><strong>${coal.calorific_value}</strong><div class="small text-muted">kcal/kg</div></td>
        <td class="metric-cell">${coal.ash_content.toFixed(2)}%</td>
        <td class="metric-cell">${coal.volatile_matter.toFixed(2)}%</td>
        <td class="metric-cell">${coal.total_sulfur.toFixed(2)}%</td>
        <td class="ratio-constraints-cell">
            <div class="ratio-constraints-wrapper">
                <div class="input-group input-group-sm ratio-input-group">
                    <span class="input-group-text ratio-constraint-label">下限</span>
                    <input type="number" class="form-control ratio-min ratio-constraint-input" value="${ratioConstraint.min}"
                           min="0" max="100" step="0.1" data-coal-id="${coal.id}" placeholder="${ratioConstraint.min}"
                           onchange="handleRatioConstraintInput(${coal.id}, 'min', this.value)" title="配比下限 (%)">
                    <span class="input-group-text">%</span>
                </div>
                <div class="input-group input-group-sm ratio-input-group">
                    <span class="input-group-text ratio-constraint-label">上限</span>
                    <input type="number" class="form-control ratio-max ratio-constraint-input" value="${ratioConstraint.max}"
                           min="0" max="100" step="0.1" data-coal-id="${coal.id}" placeholder="${ratioConstraint.max}"
                           onchange="handleRatioConstraintInput(${coal.id}, 'max', this.value)" title="配比上限 (%)">
                    <span class="input-group-text">%</span>
                </div>
            </div>
        </td>
        <td>
            <button class="btn btn-sm detail-button" onclick="viewCoalDetailForBlending(${coal.id})" title="查看详情">
                <i class="bi bi-eye"></i>
            </button>
        </td>
    `;

    applyRatioValidationClasses(Number(coal.id), true);
    return row;
}

function getRatioConstraintForCoal(coalId) {
    return smartBlendingPreferences.ratioConstraintsByCoalId[String(coalId)]
        || smartBlendingPreferences.globalRatioConstraints
        || DEFAULT_GLOBAL_RATIO_CONSTRAINTS;
}

function toggleCoalSelection(coalId) {
    const numericCoalId = Number(coalId);
    if (selectedCoals.has(numericCoalId)) {
        selectedCoals.delete(numericCoalId);
    } else {
        selectedCoals.add(numericCoalId);
    }

    smartBlendingPreferences.selectedCoalIds = Array.from(selectedCoals);
    persistPreferences(smartBlendingPreferences);
    invalidateOptimizationResults('选煤已调整，请重新运行优化计算。');
    displayCoalsForBlending();
    updateSelectedCoalCount();
    updateActionButtonsState();
}

function updateSelectedCoalCount() {
    const count = selectedCoals.size;
    updateTextContent('selectedCount', count);
    updateTextContent('selectedCountFooter', count);
    updateTextContent('sidebarSelectedCount', count);
    updateTextContent('mobileSelectedCount', count);
    updateTextContent('heroSelectedCount', count);

    const selectedCoalNames = allCoals
        .filter(coal => selectedCoals.has(Number(coal.id)))
        .map(coal => coal.name);

    renderSelectedCoalPreview('selectedCoalPreview', selectedCoalNames);
    renderSelectedCoalPreview('selectedCoalInlinePreview', selectedCoalNames);
    renderSelectedCoalPreview('constraintModalSelectedPreview', selectedCoalNames);
    updateTextContent('constraintModalSelectedCount', count);

    const heroSelectedHint = document.getElementById('heroSelectedHint');
    if (heroSelectedHint) {
        if (count >= 2) {
            heroSelectedHint.textContent = `已满足启动条件，当前选煤范围可进入优化计算`;
        } else if (count === 1) {
            heroSelectedHint.textContent = '再选择 1 种煤即可开始优化计算';
        } else {
            heroSelectedHint.textContent = '至少选择 2 种煤后即可开始优化';
        }
    }

    if (count >= 2) {
        syncWorkspaceStatus('info', `已选择 ${count} 种煤，可以开始优化。`, '点击开始优化后会先弹出约束与求解设置模态，确认后再执行计算');
    } else if (!latestDisplayedResult) {
        syncWorkspaceStatus('info', '等待选择煤种，当前配置将在本地自动保存。', '选择至少两种煤后即可直接开始优化');
    }

    updateConstraintModalSummary();
}

function renderSelectedCoalPreview(elementId, selectedCoalNames = [], maxVisible = 6) {
    const previewContainer = document.getElementById(elementId);
    if (!previewContainer) {
        return;
    }

    previewContainer.innerHTML = '';

    if (selectedCoalNames.length === 0) {
        previewContainer.innerHTML = '<span class="text-muted small">尚未选择煤种</span>';
        return;
    }

    selectedCoalNames.slice(0, maxVisible).forEach(name => {
        const pill = document.createElement('span');
        pill.className = 'selected-coal-pill';
        pill.textContent = name;
        previewContainer.appendChild(pill);
    });

    if (selectedCoalNames.length > maxVisible) {
        const more = document.createElement('span');
        more.className = 'selected-coal-pill selected-coal-pill--muted';
        more.textContent = `+${selectedCoalNames.length - maxVisible}`;
        previewContainer.appendChild(more);
    }
}

function updateCoalPagination() {
    const pagination = document.getElementById('coalPagination');
    if (!pagination) {
        return;
    }

    const totalPages = Math.ceil(filteredCoals.length / coalPageSize);
    pagination.innerHTML = '';

    if (totalPages <= 1) {
        return;
    }

    const pageItems = [];

    pageItems.push(createPaginationItem('上一页', currentCoalPage - 1, currentCoalPage === 1));

    const startPage = Math.max(1, currentCoalPage - 2);
    const endPage = Math.min(totalPages, currentCoalPage + 2);

    if (startPage > 1) {
        pageItems.push(createPaginationItem('1', 1, false, currentCoalPage === 1));
        if (startPage > 2) {
            pageItems.push(createPaginationEllipsis());
        }
    }

    for (let page = startPage; page <= endPage; page += 1) {
        pageItems.push(createPaginationItem(String(page), page, false, currentCoalPage === page));
    }

    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            pageItems.push(createPaginationEllipsis());
        }
        pageItems.push(createPaginationItem(String(totalPages), totalPages, false, currentCoalPage === totalPages));
    }

    pageItems.push(createPaginationItem('下一页', currentCoalPage + 1, currentCoalPage === totalPages));

    pageItems.forEach(item => pagination.appendChild(item));
}

function createPaginationItem(label, page, disabled, active = false) {
    const item = document.createElement('li');
    item.className = `page-item ${disabled ? 'disabled' : ''} ${active ? 'active' : ''}`;
    item.innerHTML = `<a class="page-link" href="#">${label}</a>`;
    if (!disabled) {
        item.addEventListener('click', function(event) {
            event.preventDefault();
            changeCoalPage(page);
        });
    }
    return item;
}

function createPaginationEllipsis() {
    const item = document.createElement('li');
    item.className = 'page-item disabled';
    item.innerHTML = '<span class="page-link">...</span>';
    return item;
}

function updateCoalStatistics() {
    const startIndex = filteredCoals.length > 0 ? (currentCoalPage - 1) * coalPageSize + 1 : 0;
    const endIndex = Math.min(currentCoalPage * coalPageSize, filteredCoals.length);

    updateTextContent('coalStartIndex', startIndex);
    updateTextContent('coalEndIndex', endIndex);
    updateTextContent('coalTotalItems', filteredCoals.length);
}

function changeCoalPage(page) {
    const totalPages = Math.ceil(filteredCoals.length / coalPageSize);
    if (page < 1 || page > totalPages) {
        return;
    }
    currentCoalPage = page;
    displayCoalsForBlending();
}

function searchCoalsForBlending() {
    const searchTerm = (document.getElementById('coalSearchInput')?.value || '').trim().toLowerCase();
    const typeFilter = document.getElementById('coalTypeFilter')?.value || '';

    filteredCoals = allCoals.filter(coal => {
        const matchesSearch = !searchTerm
            || coal.name.toLowerCase().includes(searchTerm)
            || coal.type.toLowerCase().includes(searchTerm);

        const matchesType = !typeFilter || coal.type === typeFilter;
        return matchesSearch && matchesType;
    });

    currentCoalPage = 1;
    displayCoalsForBlending();
}

function refreshCoalList() {
    loadCoalsForBlending();
}

function handleConstraintInputsChanged() {
    syncConstraintPreferencesFromDom();
    persistPreferences(smartBlendingPreferences);
    invalidateOptimizationResults('约束条件已调整，请重新运行优化计算。');
    updateConstraintQuickSummary();
    updateConstraintModalSummary();
    syncWorkspaceStatus('info', '约束条件已更新，系统会自动保存本次配置。', '当前仍可继续调整后再开始优化');
}

function handleOptimizationTargetChanged() {
    updateConstraintModalSummary();
    invalidateOptimizationResults('优化目标已调整，请重新运行优化计算。');
    syncWorkspaceStatus('info', '优化目标已更新。', '确认约束与求解设置后即可开始本次优化');
}

function syncConstraintPreferencesFromDom() {
    const nextConstraints = { ...smartBlendingPreferences.constraints };
    Object.entries(CONSTRAINT_FIELD_MAP).forEach(([elementId, preferenceKey]) => {
        const element = document.getElementById(elementId);
        nextConstraints[preferenceKey] = sanitizeNumber(
            element?.value,
            DEFAULT_CONSTRAINTS[preferenceKey],
            CONSTRAINT_LIMITS[preferenceKey]
        );

        if (element) {
            element.value = nextConstraints[preferenceKey];
        }
    });

    const nextGlobalRatioConstraints = normalizeRatioConstraint(
        sanitizeNumber(document.getElementById('globalRatioMin')?.value, DEFAULT_GLOBAL_RATIO_CONSTRAINTS.min, { min: 0, max: 100 }),
        sanitizeNumber(document.getElementById('globalRatioMax')?.value, DEFAULT_GLOBAL_RATIO_CONSTRAINTS.max, { min: 0, max: 100 })
    );

    document.getElementById('globalRatioMin').value = nextGlobalRatioConstraints.min;
    document.getElementById('globalRatioMax').value = nextGlobalRatioConstraints.max;

    smartBlendingPreferences.constraints = nextConstraints;
    smartBlendingPreferences.globalRatioConstraints = nextGlobalRatioConstraints;
}

function resetConstraintSettings() {
    smartBlendingPreferences.constraints = { ...DEFAULT_CONSTRAINTS };
    smartBlendingPreferences.globalRatioConstraints = { ...DEFAULT_GLOBAL_RATIO_CONSTRAINTS };

    Object.keys(smartBlendingPreferences.ratioConstraintsByCoalId).forEach(coalId => {
        smartBlendingPreferences.ratioConstraintsByCoalId[coalId] = {
            ...DEFAULT_GLOBAL_RATIO_CONSTRAINTS
        };
    });

    applyPreferencesToDom();
    displayCoalsForBlending();
    updateConstraintQuickSummary();
    updateConstraintModalSummary();
    persistPreferences(smartBlendingPreferences, {
        statusText: '约束条件已恢复为默认值'
    });
    invalidateOptimizationResults('约束条件已恢复默认值，请重新运行优化计算。');
    syncWorkspaceStatus('info', '约束条件已恢复为默认值。', '你可以直接开始优化，或继续微调参数');
    showSuccessMessage('约束条件已恢复为默认值');
}

function applyGlobalRatioConstraints() {
    syncConstraintPreferencesFromDom();

    const globalConstraint = sanitizeRatioConstraint(
        smartBlendingPreferences.globalRatioConstraints,
        DEFAULT_GLOBAL_RATIO_CONSTRAINTS
    );

    smartBlendingPreferences.globalRatioConstraints = globalConstraint;
    allCoals.forEach(coal => {
        smartBlendingPreferences.ratioConstraintsByCoalId[String(coal.id)] = {
            min: globalConstraint.min,
            max: globalConstraint.max
        };
    });

    document.getElementById('globalRatioMin').value = globalConstraint.min;
    document.getElementById('globalRatioMax').value = globalConstraint.max;

    displayCoalsForBlending();
    updateConstraintModalSummary();
    persistPreferences(smartBlendingPreferences, {
        statusText: `已应用全局配比约束 ${globalConstraint.min}% - ${globalConstraint.max}%`
    });
    invalidateOptimizationResults('全局配比约束已调整，请重新运行优化计算。');
    showSuccessMessage(`已将全局配比约束 (${globalConstraint.min}% - ${globalConstraint.max}%) 应用到所有煤种`);
}

function handleRatioConstraintInput(coalId, field, value) {
    const key = String(coalId);
    const currentConstraint = getRatioConstraintForCoal(coalId);

    let nextMin = currentConstraint.min;
    let nextMax = currentConstraint.max;

    if (field === 'min') {
        nextMin = sanitizeNumber(value, currentConstraint.min, { min: 0, max: 100 });
    } else {
        nextMax = sanitizeNumber(value, currentConstraint.max, { min: 0, max: 100 });
    }

    const normalized = normalizeRatioConstraint(nextMin, nextMax);

    if (field === 'min' && Number(normalized.min) !== Number(nextMin)) {
        showWarningMessage('配比下限已自动修正到有效范围内');
    } else if (field === 'max' && Number(normalized.max) !== Number(nextMax)) {
        showWarningMessage('配比上限已自动修正到有效范围内');
    } else if (nextMin >= nextMax) {
        showWarningMessage('配比下限不能大于或等于上限，系统已自动调整');
    }

    smartBlendingPreferences.ratioConstraintsByCoalId[key] = normalized;
    updateVisibleRatioInputs(Number(coalId), normalized);
    applyRatioValidationClasses(Number(coalId), true);
    persistPreferences(smartBlendingPreferences);
    invalidateOptimizationResults('单煤配比约束已调整，请重新运行优化计算。');
}

function updateVisibleRatioInputs(coalId, constraint) {
    const minInput = document.querySelector(`.ratio-min[data-coal-id="${coalId}"]`);
    const maxInput = document.querySelector(`.ratio-max[data-coal-id="${coalId}"]`);

    if (minInput) {
        minInput.value = constraint.min;
    }
    if (maxInput) {
        maxInput.value = constraint.max;
    }
}

function applyRatioValidationClasses(coalId, isValid) {
    const minInput = document.querySelector(`.ratio-min[data-coal-id="${coalId}"]`);
    const maxInput = document.querySelector(`.ratio-max[data-coal-id="${coalId}"]`);

    [minInput, maxInput].forEach(input => {
        if (!input) {
            return;
        }
        input.classList.remove('constraint-validation-error', 'constraint-validation-success');
        input.classList.add(isValid ? 'constraint-validation-success' : 'constraint-validation-error');
    });
}

function getAllRatioConstraints() {
    const ratioConstraints = {};
    allCoals.forEach(coal => {
        ratioConstraints[coal.id] = getRatioConstraintForCoal(coal.id);
    });
    return ratioConstraints;
}

function validateAllRatioConstraints() {
    const selectedCoalArray = Array.from(selectedCoals);
    if (selectedCoalArray.length < 2) {
        showWarningMessage('请至少选择两种煤进行混配优化');
        return false;
    }

    let totalMinRatio = 0;
    let totalMaxRatio = 0;

    selectedCoalArray.forEach(coalId => {
        const constraint = getRatioConstraintForCoal(coalId);
        totalMinRatio += constraint.min || 0;
        totalMaxRatio += constraint.max || 100;
    });

    if (totalMinRatio > 100) {
        showWarningMessage(`所有选中煤种的配比下限总和为 ${totalMinRatio.toFixed(1)}%，超过了100%，无法进行优化计算`);
        return false;
    }

    if (totalMaxRatio < 100) {
        showWarningMessage(`所有选中煤种的配比上限总和为 ${totalMaxRatio.toFixed(1)}%，不足100%，无法进行优化计算`);
        return false;
    }

    return true;
}

function handleAlgorithmSettingsChanged() {
    syncAlgorithmPreferencesFromDom();
    persistPreferences(smartBlendingPreferences);
    invalidateOptimizationResults('算法参数已调整，请重新运行优化计算。');
}

function syncAlgorithmPreferencesFromDom() {
    const nextGaParams = { ...smartBlendingPreferences.gaParams };

    Object.entries(GA_FIELD_MAP).forEach(([elementId, preferenceKey]) => {
        const element = document.getElementById(elementId);
        if (!element) {
            return;
        }

        if (element.type === 'checkbox') {
            nextGaParams[preferenceKey] = element.checked;
        } else {
            const fallback = DEFAULT_GA_PARAMS[preferenceKey];
            const min = element.min !== '' ? Number(element.min) : 0;
            const max = element.max !== '' ? Number(element.max) : 1000000;
            const numericValue = preferenceKey.includes('rate') || preferenceKey.includes('ratio') || preferenceKey.includes('factor')
                ? sanitizeNumber(element.value, fallback, { min, max })
                : sanitizeInteger(element.value, fallback, { min, max });

            nextGaParams[preferenceKey] = numericValue;
            element.value = numericValue;
        }
    });

    smartBlendingPreferences.gaParams = sanitizeGaParams(nextGaParams);
}

function saveAlgorithmSettings() {
    syncAlgorithmPreferencesFromDom();
    persistPreferences(smartBlendingPreferences, {
        statusText: '算法设置已保存并将在下次自动加载'
    });
    invalidateOptimizationResults('算法设置已保存，请重新运行优化计算。');
    syncWorkspaceStatus('info', '算法设置已保存。', '当前配置已自动同步到本地，下次进入会继续保留');
    showSuccessMessage('算法设置已保存');

    const modalElement = document.getElementById('algorithmSettingsModal');
    const modal = bootstrap.Modal.getInstance(modalElement);
    if (modal) {
        modal.hide();
    }
}

function resetAlgorithmSettings() {
    smartBlendingPreferences.gaParams = { ...DEFAULT_GA_PARAMS };
    applyPreferencesToDom();
    persistPreferences(smartBlendingPreferences, {
        statusText: '算法设置已恢复为默认值'
    });
    invalidateOptimizationResults('算法设置已恢复默认值，请重新运行优化计算。');
    syncWorkspaceStatus('info', '算法设置已恢复为默认值。', '本次遗传算法参数已经回到推荐配置');
    showSuccessMessage('算法设置已重置为默认值');
}

function buildOptimizationRequestData() {
    syncConstraintPreferencesFromDom();
    syncAlgorithmPreferencesFromDom();

    smartBlendingPreferences.selectedCoalIds = Array.from(selectedCoals);
    persistPreferences(smartBlendingPreferences, { silent: true });
    updateConstraintQuickSummary();
    updateConstraintModalSummary();

    const ratioConstraints = {};
    Array.from(selectedCoals).forEach(coalId => {
        ratioConstraints[String(coalId)] = getRatioConstraintForCoal(coalId);
    });

    return {
        optimization_target: document.getElementById('optimizationTarget')?.value || '喷煤性价比最优',
        selected_coal_ids: Array.from(selectedCoals),
        constraints: {
            ...smartBlendingPreferences.constraints,
            ratio_constraints: ratioConstraints
        },
        ga_params: { ...smartBlendingPreferences.gaParams }
    };
}

async function startOptimization() {
    if (optimizationInProgress) {
        showWarningMessage('优化计算正在进行中，请稍候...');
        return;
    }

    if (!validateAllRatioConstraints()) {
        return;
    }

    const requestData = buildOptimizationRequestData();
    hideConstraintSettingsModal();

    try {
        optimizationInProgress = true;
        updateActionButtonsState();
        showLoadingState('正在进行优化计算，请稍候...');
        syncWorkspaceStatus('info', '正在执行智能混煤优化计算。', '系统正在搜索满足约束的最低成本方案');

        const response = await fetch('/api/optimization', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });

        const result = await response.json();

        if (['success', 'no_feasible_solution', 'search_failed'].includes(result.status)) {
            displayOptimizationResults(result.status, result.result, result.message);
            scrollToResultsSection();

            if (result.status === 'success') {
                showSuccessMessage('喷煤性价比优化完成！');
            } else if (result.status === 'no_feasible_solution') {
                showWarningMessage(result.message || '当前约束下不存在可行混煤方案');
            } else {
                showWarningMessage(result.message || '遗传算法未能生成满足约束的解');
            }
        } else {
            clearOptimizationResults();
            updateQuickResultSummary('error', null, result.message || '优化计算失败');
            updateActionButtonsState();
            syncWorkspaceStatus('danger', '优化计算失败。', result.message || '请检查约束和网络状态后重试');
            showErrorMessage('优化计算失败: ' + result.message);
        }
    } catch (error) {
        clearOptimizationResults();
        updateQuickResultSummary('error', null, error.message || '请检查网络连接后重试');
        syncWorkspaceStatus('danger', '优化请求未完成。', error.message || '请检查网络连接后重试');
        showErrorMessage('网络错误: ' + error.message);
    } finally {
        optimizationInProgress = false;
        updateActionButtonsState();
        hideLoadingState();
    }
}

function openConstraintSettingsModal(reason = 'edit') {
    applyPreferencesToDom();
    updateConstraintQuickSummary();
    updateConstraintModalSummary();
    updateActionButtonsState();

    if (!constraintSettingsModalInstance) {
        const modalElement = document.getElementById('constraintSettingsModal');
        if (!modalElement) {
            return;
        }
        constraintSettingsModalInstance = new bootstrap.Modal(modalElement);
    }

    if (reason === 'start') {
        syncWorkspaceStatus('info', '请先确认约束与求解设置。', '在弹窗中确认工艺边界、配比约束和优化目标后再开始计算');
    }

    constraintSettingsModalInstance.show();
}

function hideConstraintSettingsModal() {
    const modalElement = document.getElementById('constraintSettingsModal');
    const modal = bootstrap.Modal.getInstance(modalElement) || constraintSettingsModalInstance;
    if (modal) {
        modal.hide();
    }
}

function updateConstraintModalSummary() {
    const objectiveElement = document.getElementById('constraintModalObjectiveSummary');
    if (objectiveElement) {
        objectiveElement.textContent = document.getElementById('optimizationTarget')?.value || '喷煤性价比最优';
    }
}

function displayOptimizationResults(status, data, message) {
    latestDisplayedResult = data || null;
    lastOptimizationResult = data?.is_feasible ? data : null;

    const ratios = [];
    const coalNames = Array.isArray(data?.coal_names) ? data.coal_names : [];
    const optimalRatios = Array.isArray(data?.optimal_ratios) ? data.optimal_ratios : [];

    for (let i = 0; i < coalNames.length; i += 1) {
        ratios.push({
            coal_name: coalNames[i],
            percentage: (optimalRatios[i] || 0) * 100
        });
    }

    updateRatioTable(ratios, status);
    updatePerformanceIndicators(data);
    updateAlgorithmInfo(data);
    renderConstraintStatus(data);
    updateCharts(data);
    updateQuickResultSummary(status, data, message);
    updateActionButtonsState();
}

function updateRatioTable(ratios, status) {
    const tbody = document.querySelector('.result-table tbody');
    if (!tbody) {
        return;
    }

    tbody.innerHTML = '';
    const significantRatios = ratios.filter(ratio => ratio.percentage > 0.1);

    if (significantRatios.length === 0) {
        const emptyMessage = status === 'success'
            ? '无有效配比数据'
            : '当前未生成可展示的推荐配比';
        tbody.innerHTML = `<tr><td colspan="3" class="text-center text-muted">${emptyMessage}</td></tr>`;
        return;
    }

    significantRatios.forEach((ratio, index) => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>
                <div class="ratio-coal-name">
                    <span class="ratio-rank">${index + 1}</span>
                    <div>
                        <span class="ratio-name">${ratio.coal_name}</span>
                        <span class="ratio-name-sub">推荐占比 ${ratio.percentage.toFixed(2)}%</span>
                    </div>
                </div>
            </td>
            <td><strong class="ratio-percentage">${ratio.percentage.toFixed(2)}%</strong></td>
            <td>
                <div class="progress ratio-progress">
                    <div class="progress-bar bg-success" role="progressbar"
                          style="width: ${ratio.percentage}%"
                          aria-valuenow="${ratio.percentage}"
                         aria-valuemin="0" aria-valuemax="100">
                        ${ratio.percentage.toFixed(1)}%
                    </div>
                </div>
            </td>
        `;
        tbody.appendChild(row);
    });
}

function updatePerformanceIndicators(data) {
    const elements = {
        '.total-price': formatNumeric(data?.total_price, value => `¥${value.toFixed(2)}/吨`),
        '.total-heat': formatNumeric(data?.total_heat, value => `${value.toFixed(0)} kcal/kg`),
        '.total-ash': formatNumeric(data?.total_ash, value => `${value.toFixed(2)}%`),
        '.total-fixed-carbon': formatNumeric(data?.total_fixed_carbon, value => `${value.toFixed(2)}%`),
        '.total-volatile': formatNumeric(data?.total_volatile, value => `${value.toFixed(2)}%`),
        '.total-sulfur': formatNumeric(data?.total_sulfur, value => `${value.toFixed(2)}%`),
        '.objective-type': data?.objective_type === 'pci_cost_effective_v1'
            ? '喷煤性价比最优（可行域最低成本）'
            : (data?.optimization_target || '--'),
        '.feasibility-status': data?.is_feasible ? '可行，且满足全部硬约束' : '不可行或未找到可行解'
    };

    Object.keys(elements).forEach(selector => {
        const element = document.querySelector(selector);
        if (element) {
            element.textContent = elements[selector];
        }
    });

    updateTextContent('resultsHeroCost', elements['.total-price']);
    updateTextContent('resultsHeroHeat', elements['.total-heat']);
}

function updateAlgorithmInfo(data) {
    const elements = {
        '.iterations': Number.isFinite(data?.iterations) ? data.iterations : '--',
        '.time-taken': formatNumeric(data?.time_taken, value => value.toFixed(2)),
        '.fitness-value': formatNumeric(data?.fitness_value, value => value.toFixed(4))
    };

    Object.keys(elements).forEach(selector => {
        const element = document.querySelector(selector);
        if (element) {
            element.textContent = elements[selector];
        }
    });
}

function renderConstraintStatus(data) {
    const container = document.querySelector('.constraint-status-list');
    if (!container) {
        return;
    }

    const violations = Array.isArray(data?.constraint_violations) ? data.constraint_violations : [];
    const activeConstraints = Array.isArray(data?.active_constraints) ? data.active_constraints : [];
    const diagnosis = Array.isArray(data?.diagnosis) ? data.diagnosis : [];

    container.innerHTML = '';

    if (data?.is_feasible) {
        const successBadge = document.createElement('span');
        successBadge.className = 'badge bg-success constraint-badge';
        successBadge.innerHTML = '<i class="bi bi-check-circle me-1"></i>全部硬约束满足';
        container.appendChild(successBadge);

        activeConstraints.slice(0, 6).forEach(item => {
            const badge = document.createElement('span');
            badge.className = 'badge bg-warning text-dark constraint-badge';
            badge.innerHTML = `<i class="bi bi-exclamation-triangle me-1"></i>活跃约束: ${item}`;
            container.appendChild(badge);
        });
        return;
    }

    if (violations.length === 0 && diagnosis.length === 0) {
        const badge = document.createElement('span');
        badge.className = 'badge bg-secondary constraint-badge';
        badge.innerHTML = '<i class="bi bi-info-circle me-1"></i>暂无约束诊断信息';
        container.appendChild(badge);
        return;
    }

    violations.slice(0, 8).forEach(item => {
        const badge = document.createElement('span');
        badge.className = 'badge bg-danger constraint-badge';
        badge.innerHTML = `<i class="bi bi-x-circle me-1"></i>${toViolationText(item)}`;
        container.appendChild(badge);
    });

    diagnosis.slice(0, 4).forEach(item => {
        const badge = document.createElement('span');
        badge.className = 'badge bg-secondary constraint-badge';
        badge.innerHTML = `<i class="bi bi-info-circle me-1"></i>${toViolationText(item)}`;
        container.appendChild(badge);
    });
}

function updateCharts(data) {
    if (typeof Chart === 'undefined') {
        return;
    }

    createSimpleRatioChart(data);

    renderPerformanceChart(data);
    renderConstraintChart(data);
}

function createSimpleRatioChart(data) {
    const ratioChart = document.getElementById('ratioChart');
    if (!ratioChart) {
        return;
    }

    if (ratioChartInstance) {
        ratioChartInstance.destroy();
        ratioChartInstance = null;
    }

    const labels = Array.isArray(data?.coal_names) ? data.coal_names : [];
    const ratios = Array.isArray(data?.optimal_ratios) ? data.optimal_ratios.map(ratio => Number((ratio * 100).toFixed(2))) : [];

    if (labels.length === 0 || ratios.length === 0) {
        ratioChart.innerHTML = `
            <div class="d-flex align-items-center justify-content-center h-100">
                <p class="text-muted">当前暂无可视化配比结果</p>
            </div>
        `;
        return;
    }

    ratioChart.innerHTML = '';
    const canvas = document.createElement('canvas');
    ratioChart.appendChild(canvas);

    const colors = ['#1e40af', '#f97316', '#16a34a', '#dc2626', '#0f766e', '#ca8a04', '#0ea5e9', '#7c3aed'];

    try {
        ratioChartInstance = new Chart(canvas, {
            type: 'doughnut',
            data: {
                labels,
                datasets: [{
                    data: ratios,
                    backgroundColor: colors.slice(0, labels.length),
                    borderWidth: 2,
                    borderColor: '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '58%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 15,
                            usePointStyle: true,
                            boxWidth: 8
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label(context) {
                                return `${context.label}: ${context.parsed}%`;
                            }
                        }
                    }
                }
            }
        });
    } catch (error) {
        console.error('创建配比饼图失败:', error);
            ratioChart.innerHTML = `
                <div class="d-flex align-items-center justify-content-center h-100">
                    <div class="text-center">
                        <h6>配比结果</h6>
                        ${labels.map((name, index) => `<p>${name}: ${ratios[index]}%</p>`).join('')}
                    </div>
                </div>
            `;
    }
}

function renderPerformanceChart(data) {
    const performanceChart = document.getElementById('performanceChart');
    if (!performanceChart) {
        return;
    }

    if (performanceChartInstance) {
        performanceChartInstance.destroy();
        performanceChartInstance = null;
    }

    const diagnostics = buildMetricDiagnostics(data);
    if (diagnostics.length === 0) {
        performanceChart.innerHTML = `
            <div class="result-empty-state d-flex justify-content-center align-items-center h-100">
                <div class="text-center">
                    <p class="mb-2 fw-semibold">等待关键指标</p>
                    <p class="text-muted mb-0">选择至少两种煤并检查约束后开始优化</p>
                </div>
            </div>
        `;
        return;
    }

    performanceChart.innerHTML = '';
    const canvas = document.createElement('canvas');
    performanceChart.appendChild(canvas);

    performanceChartInstance = new Chart(canvas, {
        type: 'bar',
        data: {
            labels: diagnostics.map(item => item.label),
            datasets: [{
                label: '指标匹配度',
                data: diagnostics.map(item => item.score),
                backgroundColor: diagnostics.map(item => item.satisfied ? 'rgba(16, 185, 129, 0.72)' : 'rgba(245, 158, 11, 0.72)'),
                borderColor: diagnostics.map(item => item.satisfied ? 'rgba(16, 185, 129, 1)' : 'rgba(245, 158, 11, 1)'),
                borderWidth: 1.5,
                borderRadius: 8,
                barThickness: 16
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    beginAtZero: true,
                    max: 100,
                    grid: {
                        color: 'rgba(203, 213, 225, 0.45)'
                    },
                    ticks: {
                        callback(value) {
                            return `${value}%`;
                        }
                    }
                },
                y: {
                    grid: {
                        display: false
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label(context) {
                            const item = diagnostics[context.dataIndex];
                            return `${item.rawText} | ${item.satisfied ? '满足约束' : '偏离约束'}`;
                        }
                    }
                }
            }
        }
    });
}

function renderConstraintChart(data) {
    const constraintChart = document.getElementById('constraintChart');
    if (!constraintChart) {
        return;
    }

    if (constraintChartInstance) {
        constraintChartInstance.destroy();
        constraintChartInstance = null;
    }

    const diagnostics = buildMetricDiagnostics(data);
    if (diagnostics.length === 0) {
        constraintChart.innerHTML = `
            <div class="result-empty-state d-flex justify-content-center align-items-center h-100">
                <div class="text-center">
                    <p class="mb-2 fw-semibold">等待约束诊断</p>
                    <p class="text-muted mb-0">选择至少两种煤并检查约束后开始优化</p>
                </div>
            </div>
        `;
        return;
    }

    constraintChart.innerHTML = '';
    const canvas = document.createElement('canvas');
    constraintChart.appendChild(canvas);

    constraintChartInstance = new Chart(canvas, {
        type: 'bar',
        data: {
            labels: diagnostics.map(item => item.label),
            datasets: [{
                label: '约束状态',
                data: diagnostics.map(item => item.satisfied ? 100 : Math.max(12, item.score)),
                backgroundColor: diagnostics.map(item => item.satisfied ? 'rgba(16, 185, 129, 0.75)' : 'rgba(239, 68, 68, 0.72)'),
                borderRadius: 8,
                borderSkipped: false,
                barThickness: 18
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    ticks: {
                        callback(value) {
                            return `${value}%`;
                        }
                    },
                    grid: {
                        color: 'rgba(203, 213, 225, 0.45)'
                    }
                },
                x: {
                    grid: {
                        display: false
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label(context) {
                            const item = diagnostics[context.dataIndex];
                            return `${item.rawText} | ${item.satisfied ? '满足约束' : '需要调整'}`;
                        }
                    }
                }
            }
        }
    });
}

function buildMetricDiagnostics(data) {
    if (!data) {
        return [];
    }

    const constraints = smartBlendingPreferences.constraints || {};
    const metricConfigs = [
        {
            label: '热值',
            value: data.total_heat,
            min: constraints.heat_min,
            max: constraints.heat_max,
            target: constraints.heat_target,
            formatter: value => `${value.toFixed(0)} kcal/kg`
        },
        {
            label: '灰分',
            value: data.total_ash,
            min: constraints.ash_min,
            max: constraints.ash_max,
            formatter: value => `${value.toFixed(2)}%`
        },
        {
            label: '挥发分',
            value: data.total_volatile,
            min: constraints.volatile_min,
            max: constraints.volatile_max,
            formatter: value => `${value.toFixed(2)}%`
        },
        {
            label: '固定碳',
            value: data.total_fixed_carbon,
            min: constraints.fixed_carbon_min,
            max: constraints.fixed_carbon_max,
            formatter: value => `${value.toFixed(2)}%`
        },
        {
            label: '硫分',
            value: data.total_sulfur,
            min: constraints.sulfur_min,
            max: constraints.sulfur_max,
            formatter: value => `${value.toFixed(2)}%`
        },
        {
            label: '价格',
            value: data.total_price,
            min: constraints.price_min,
            max: constraints.price_max,
            formatter: value => `¥${value.toFixed(2)}/吨`
        }
    ];

    return metricConfigs
        .filter(item => Number.isFinite(item.value))
        .map(item => {
            const min = Number.isFinite(item.min) ? item.min : item.value;
            const max = Number.isFinite(item.max) ? item.max : item.value;
            const safeRange = Math.max(max - min, 1);
            const satisfied = item.value >= min && item.value <= max;
            let score;

            if (Number.isFinite(item.target) && satisfied) {
                const distance = Math.abs(item.value - item.target);
                score = Math.max(0, 100 - (distance / safeRange) * 100);
            } else if (satisfied) {
                const marginToBoundary = Math.min(item.value - min, max - item.value);
                score = Math.min(100, 65 + (Math.max(marginToBoundary, 0) / safeRange) * 35);
            } else {
                const deviation = item.value < min ? (min - item.value) : (item.value - max);
                score = Math.max(0, 100 - (deviation / safeRange) * 100);
            }

            return {
                ...item,
                satisfied,
                score: Number(score.toFixed(1)),
                rawText: `${item.label} ${item.formatter(item.value)}`
            };
        });
}

function updateConstraintQuickSummary() {
    const container = document.getElementById('constraintQuickSummary');
    if (!container) {
        return;
    }

    const constraints = smartBlendingPreferences.constraints;
    const chips = [
        `热值 ${constraints.heat_min} - ${constraints.heat_max} kcal/kg`,
        `灰分 ${constraints.ash_min} - ${constraints.ash_max}%`,
        `挥发分 ${constraints.volatile_min} - ${constraints.volatile_max}%`,
        `固定碳 ${constraints.fixed_carbon_min} - ${constraints.fixed_carbon_max}%`,
        `硫分 ${constraints.sulfur_min} - ${constraints.sulfur_max}%`,
        `价格 ${constraints.price_min} - ${constraints.price_max} 元/吨`,
        `单煤配比 ${smartBlendingPreferences.globalRatioConstraints.min}% - ${smartBlendingPreferences.globalRatioConstraints.max}%`
    ];

    container.innerHTML = '';
    chips.forEach(text => {
        const chip = document.createElement('div');
        chip.className = 'summary-chip';
        chip.textContent = text;
        container.appendChild(chip);
    });
}

function updateQuickResultSummary(status = null, data = null, message = '') {
    const statusElement = document.getElementById('sidebarResultStatus');
    const objectiveElement = document.getElementById('sidebarResultObjective');
    const priceElement = document.getElementById('sidebarResultPrice');
    const heatElement = document.getElementById('sidebarResultHeat');
    const feasibilityElement = document.getElementById('sidebarResultFeasibility');
    const diagnosisElement = document.getElementById('sidebarResultDiagnosis');
    const badgeElement = document.getElementById('sidebarResultBadge');
    const metaElement = document.getElementById('sidebarResultMeta');
    const heroHeadlineElement = document.getElementById('heroResultHeadline');
    const heroHintElement = document.getElementById('heroResultHint');
    const resultsHeroStatus = document.getElementById('resultsHeroStatus');
    const resultsHeroStatusHint = document.getElementById('resultsHeroStatusHint');
    const resultsHeroConstraint = document.getElementById('resultsHeroConstraint');
    const resultsHeroAlgorithm = document.getElementById('resultsHeroAlgorithm');

    if (!statusElement || !objectiveElement || !priceElement || !heatElement || !diagnosisElement || !feasibilityElement) {
        return;
    }

      const applySummaryState = ({
          badgeTone = 'pending',
          badgeText = '待计算',
          statusText = '等待优化计算',
          statusClass = 'quick-result-status',
          diagnosisText = '选择至少两种煤并检查约束后开始优化，这里会先显示结论摘要。',
          metaText = '尚无计算结果',
          feasibilityText = '待计算',
          heroHeadlineText = '等待优化结论',
          heroHintText = '选择至少两种煤并检查约束后开始优化，系统会先给出是否可直接投用的判断',
          overviewStatusClass = '',
          overviewConstraintText = '待诊断',
          overviewAlgorithmText = '选择至少两种煤并检查约束后开始优化。'
      }) => {
        statusElement.textContent = statusText;
        statusElement.className = statusClass;
        diagnosisElement.textContent = diagnosisText;
        feasibilityElement.textContent = feasibilityText;

        if (badgeElement) {
            badgeElement.textContent = badgeText;
            badgeElement.setAttribute('data-tone', badgeTone);
        }

        if (metaElement) {
            metaElement.textContent = metaText;
        }

        if (heroHeadlineElement) {
            heroHeadlineElement.textContent = heroHeadlineText;
        }

        if (heroHintElement) {
            heroHintElement.textContent = heroHintText;
        }

        if (resultsHeroStatus) {
            resultsHeroStatus.textContent = statusText;
            resultsHeroStatus.className = `result-overview-card__value ${overviewStatusClass}`.trim();
        }

        if (resultsHeroStatusHint) {
            resultsHeroStatusHint.textContent = diagnosisText;
        }

        if (resultsHeroConstraint) {
            resultsHeroConstraint.textContent = overviewConstraintText;
        }

        if (resultsHeroAlgorithm) {
            resultsHeroAlgorithm.textContent = overviewAlgorithmText;
        }
    };

    if (!data) {
        if (status === 'error' && message) {
            objectiveElement.textContent = '喷煤性价比最优';
            priceElement.textContent = '--';
            heatElement.textContent = '--';
            applySummaryState({
                badgeTone: 'danger',
                badgeText: '计算失败',
                statusText: '优化计算失败',
                statusClass: 'quick-result-status is-danger',
                diagnosisText: message,
                metaText: '请检查网络、约束或服务状态后重试',
                feasibilityText: '未生成结果',
                heroHeadlineText: '优化计算失败',
                heroHintText: message,
                overviewStatusClass: 'is-danger',
                overviewConstraintText: '执行失败',
                overviewAlgorithmText: message
            });
            syncWorkspaceStatus('danger', '优化计算失败。', message);
            return;
        }
        objectiveElement.textContent = '喷煤性价比最优';
        priceElement.textContent = '--';
        heatElement.textContent = '--';
        applySummaryState();
        return;
    }

    objectiveElement.textContent = data.objective_type === 'pci_cost_effective_v1'
        ? '喷煤性价比最优'
        : (data.optimization_target || '喷煤性价比最优');
    priceElement.textContent = formatNumeric(data.total_price, value => `¥${value.toFixed(2)}/吨`);
    heatElement.textContent = formatNumeric(data.total_heat, value => `${value.toFixed(0)} kcal/kg`);

    if (status === 'success' && data.is_feasible) {
        const diagnosisText = data.active_constraints?.length
            ? `活跃约束：${data.active_constraints.slice(0, 3).join('、')}`
            : '当前方案满足全部硬约束，并且存在一定操作余量。';
        const metaParts = [];
        const heroHintParts = [];
        if (Number.isFinite(data.iterations)) {
            metaParts.push(`${data.iterations} 代`);
        }
        if (Number.isFinite(data.time_taken)) {
            metaParts.push(`${data.time_taken.toFixed(2)} 秒`);
        }
        if (Number.isFinite(data.total_price)) {
            heroHintParts.push(`吨煤成本 ¥${data.total_price.toFixed(2)}`);
        }
        if (Number.isFinite(data.total_heat)) {
            heroHintParts.push(`综合热值 ${data.total_heat.toFixed(0)} kcal/kg`);
        }
        applySummaryState({
            badgeTone: 'success',
            badgeText: '可行推荐',
            statusText: '已找到满足约束的推荐方案',
            statusClass: 'quick-result-status is-success',
            diagnosisText,
            metaText: metaParts.length > 0 ? `计算完成 | ${metaParts.join(' | ')}` : '计算完成',
            feasibilityText: '满足全部硬约束',
            heroHeadlineText: '已生成可行推荐方案',
            heroHintText: heroHintParts.join('，') || '右侧决策面板已生成关键指标与约束摘要',
            overviewStatusClass: 'is-success',
            overviewConstraintText: '全部约束满足',
            overviewAlgorithmText: metaParts.length > 0 ? `计算摘要：${metaParts.join('，')}` : '已生成推荐方案'
        });
        syncWorkspaceStatus('success', '已生成推荐方案，可以查看详细结果。', '右侧已给出结论，底部详情区可继续查看配比和约束明细');
        return;
    }

    if (status === 'no_feasible_solution') {
        applySummaryState({
            badgeTone: 'warning',
            badgeText: '无可行解',
            statusText: '当前约束无可行解',
            statusClass: 'quick-result-status is-warning',
            metaText: '建议优先检查边界最紧的工艺约束',
            feasibilityText: '当前约束不可行',
            heroHeadlineText: '当前约束下无可行解',
            heroHintText: '建议放宽约束范围，或调整选煤组合后重新计算',
            overviewStatusClass: 'is-warning',
            overviewConstraintText: '约束冲突',
            overviewAlgorithmText: '建议先放宽边界最紧的工艺约束，再重新计算'
        });
        syncWorkspaceStatus('warning', '当前约束组合下没有可行解。', '建议适当放宽约束范围或调整煤种组合后重试');
    } else if (status === 'search_failed') {
        applySummaryState({
            badgeTone: 'warning',
            badgeText: '搜索未命中',
            statusText: '可行域存在，但本次搜索未命中',
            statusClass: 'quick-result-status is-warning',
            metaText: '可尝试重新计算或调整算法参数',
            feasibilityText: '本次搜索未找到解',
            heroHeadlineText: '搜索未命中可行方案',
            heroHintText: '可尝试重新计算，或适当放宽约束 / 微调算法参数',
            overviewStatusClass: 'is-warning',
            overviewConstraintText: '搜索未命中',
            overviewAlgorithmText: '可保留当前约束，尝试重算或调整遗传算法参数'
        });
        syncWorkspaceStatus('warning', '本次搜索未找到满足约束的可行解。', '可尝试重新计算，或放宽约束/调整遗传算法参数');
    } else {
        applySummaryState({
            badgeTone: 'warning',
            badgeText: '结果待复核',
            statusText: '当前结果不可直接用于生产',
            statusClass: 'quick-result-status is-warning',
            metaText: '请优先查看约束诊断与详细结果区',
            feasibilityText: '需人工复核',
            heroHeadlineText: '当前结果不可直接投用',
            heroHintText: '请优先查看右侧诊断摘要与底部约束详情',
            overviewStatusClass: 'is-warning',
            overviewConstraintText: '需人工复核',
            overviewAlgorithmText: '请结合约束诊断、配比表和性能指标进一步判断'
        });
        syncWorkspaceStatus('warning', '当前结果不可直接用于生产。', '请优先查看右侧诊断摘要与底部约束详情');
    }

    const diagnosisTexts = [
        ...(Array.isArray(data.constraint_violations) ? data.constraint_violations.slice(0, 2).map(toViolationText) : []),
        ...(Array.isArray(data.diagnosis) ? data.diagnosis.slice(0, 2).map(toViolationText) : [])
    ].filter(Boolean);

    diagnosisElement.textContent = diagnosisTexts.join('；') || message || '请适当放宽约束范围或调整煤种组合后重试。';
}

function updateActionButtonsState() {
    const canStart = !optimizationInProgress && selectedCoals.size >= 2;
    const canScrollToResults = Boolean(latestDisplayedResult);
    const canExport = Boolean(lastOptimizationResult) && !exportInProgress;

    document.querySelectorAll('.start-optimization-btn').forEach(button => {
        button.disabled = !canStart;
        button.innerHTML = optimizationInProgress
            ? '<i class="bi bi-hourglass-split me-2"></i>计算中...'
            : (button.classList.contains('btn-sm')
                ? '<i class="bi bi-play-circle me-1"></i>开始优化'
                : '<i class="bi bi-play-circle me-2"></i>开始优化计算');
    });

    document.querySelectorAll('.open-constraint-settings-btn').forEach(button => {
        button.disabled = optimizationInProgress;
    });

    const confirmOptimizationBtn = document.getElementById('confirmOptimizationBtn');
    if (confirmOptimizationBtn) {
        confirmOptimizationBtn.disabled = !canStart;
        confirmOptimizationBtn.innerHTML = optimizationInProgress
            ? '<i class="bi bi-hourglass-split me-2"></i>计算中...'
            : '<i class="bi bi-play-circle me-2"></i>开始优化计算';
    }

    const scrollButtons = [
        document.getElementById('scrollToResultsBtn'),
        document.getElementById('scrollToResultsBtnMobile')
    ];
    scrollButtons.forEach(button => {
        if (button) {
            button.disabled = !canScrollToResults;
        }
    });

    const exportBtn = document.getElementById('exportReportBtn');
    const copyBtn = document.getElementById('copyShareResultBtn');
    if (exportBtn) {
        exportBtn.disabled = !canExport;
    }
    if (copyBtn) {
        copyBtn.disabled = !Boolean(lastOptimizationResult);
    }
}

function invalidateOptimizationResults(statusMessage) {
    if (!latestDisplayedResult && !lastOptimizationResult) {
        return;
    }
    clearOptimizationResults();
    updateQuickResultSummary();
    updateActionButtonsState();
    if (statusMessage) {
        syncWorkspaceStatus('info', statusMessage, '请基于最新配置重新运行优化，避免沿用旧结果');
    }
}

function clearOptimizationResults() {
    latestDisplayedResult = null;
    lastOptimizationResult = null;
    updateRatioTable([], null);
    resetPerformanceIndicators();
    resetAlgorithmInfo();
    renderConstraintStatus(null);
    resetCharts();
}

function resetPerformanceIndicators() {
    const resetMap = {
        '.total-price': '--',
        '.total-heat': '--',
        '.total-ash': '--',
        '.total-fixed-carbon': '--',
        '.total-volatile': '--',
        '.total-sulfur': '--',
        '.objective-type': '--',
        '.feasibility-status': '--',
        '#resultsHeroCost': '--',
        '#resultsHeroHeat': '--'
    };

    Object.entries(resetMap).forEach(([selector, value]) => {
        const element = document.querySelector(selector);
        if (element) {
            element.textContent = value;
        }
    });
}

function resetAlgorithmInfo() {
    const resetMap = {
        '.iterations': '--',
        '.time-taken': '--',
        '.fitness-value': '--'
    };

    Object.entries(resetMap).forEach(([selector, value]) => {
        const element = document.querySelector(selector);
        if (element) {
            element.textContent = value;
        }
    });
}

function resetCharts() {
    const ratioChart = document.getElementById('ratioChart');
    const performanceChart = document.getElementById('performanceChart');
    const constraintChart = document.getElementById('constraintChart');

    if (ratioChartInstance) {
        ratioChartInstance.destroy();
        ratioChartInstance = null;
    }

    if (performanceChartInstance) {
        performanceChartInstance.destroy();
        performanceChartInstance = null;
    }

    if (constraintChartInstance) {
        constraintChartInstance.destroy();
        constraintChartInstance = null;
    }

    if (ratioChart) {
        ratioChart.innerHTML = `
            <div class="result-empty-state d-flex justify-content-center align-items-center h-100">
                <div class="text-center">
                    <p class="mb-2 fw-semibold">等待生成推荐配比</p>
                    <p class="text-muted mb-0">选择至少两种煤并检查约束后开始优化</p>
                </div>
            </div>
        `;
    }

    if (performanceChart) {
        performanceChart.innerHTML = `
            <div class="result-empty-state d-flex justify-content-center align-items-center h-100">
                <div class="text-center">
                    <p class="mb-2 fw-semibold">等待关键指标</p>
                    <p class="text-muted mb-0">选择至少两种煤并检查约束后开始优化</p>
                </div>
            </div>
        `;
    }

    if (constraintChart) {
        constraintChart.innerHTML = `
            <div class="result-empty-state d-flex justify-content-center align-items-center h-100">
                <div class="text-center">
                    <p class="mb-2 fw-semibold">等待约束诊断</p>
                    <p class="text-muted mb-0">选择至少两种煤并检查约束后开始优化</p>
                </div>
            </div>
        `;
    }
}

function syncWorkspaceStatus(tone, text, hint = '') {
    const bar = document.getElementById('workspaceStatusBar');
    const textElement = document.getElementById('workspaceStatusText');
    const hintElement = document.getElementById('workspaceStatusHint');
    const heroStatusPill = document.getElementById('heroStatusPill');
    if (!bar || !textElement || !hintElement) {
        return;
    }

    bar.setAttribute('data-tone', tone || 'info');
    textElement.textContent = text || '等待进一步操作';
    hintElement.textContent = hint || '';

    if (heroStatusPill) {
        heroStatusPill.setAttribute('data-tone', tone || 'info');
        heroStatusPill.textContent = (text || '等待进一步操作').replace(/[。！!?]$/, '').split('，')[0];
    }
}

function scrollToResultsSection() {
    const section = document.getElementById('resultsSection');
    if (section) {
        section.scrollIntoView({
            behavior: 'smooth',
            block: 'start'
        });
    }
}

function scrollToWorkspaceSection() {
    const section = document.getElementById('blendingWorkspace');
    if (section) {
        section.scrollIntoView({
            behavior: 'smooth',
            block: 'start'
        });
    }
}

function viewCoalDetailForBlending(coalId) {
    const coal = allCoals.find(item => Number(item.id) === Number(coalId));
    if (!coal) {
        return;
    }

    const detailContent = document.getElementById('coalDetailContent');
    if (!detailContent) {
        return;
    }

    detailContent.innerHTML = `
        <div class="row">
            <div class="col-md-6">
                <h6>基本信息</h6>
                <table class="table table-bordered">
                    <tbody>
                        <tr><th>煤种名称</th><td>${coal.name}</td></tr>
                        <tr><th>煤种类型</th><td>${coal.type}</td></tr>
                        <tr><th>价格(元/吨)</th><td>¥${coal.price.toFixed(2)}</td></tr>
                    </tbody>
                </table>
            </div>
            <div class="col-md-6">
                <h6>技术指标</h6>
                <table class="table table-bordered">
                    <tbody>
                        <tr><th>热值(kcal/kg)</th><td>${coal.calorific_value}</td></tr>
                        <tr><th>灰分(%)</th><td>${coal.ash_content.toFixed(2)}</td></tr>
                        <tr><th>挥发分(%)</th><td>${coal.volatile_matter.toFixed(2)}</td></tr>
                        <tr><th>固定碳(%)</th><td>${coal.fixed_carbon.toFixed(2)}</td></tr>
                        <tr><th>全硫(%)</th><td>${coal.total_sulfur.toFixed(2)}</td></tr>
                        <tr><th>全水分(%)</th><td>${coal.moisture ? coal.moisture.toFixed(2) : '未知'}</td></tr>
                        <tr><th>空干基水分(%)</th><td>${coal.mad ? coal.mad.toFixed(2) : '未知'}</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    `;

    const modal = new bootstrap.Modal(document.getElementById('coalDetailModal'));
    modal.show();
}

function formatNumeric(value, formatter, fallback = '--') {
    return Number.isFinite(value) ? formatter(value) : fallback;
}

function toViolationText(violation) {
    if (!violation) {
        return '约束诊断不可用';
    }
    if (typeof violation === 'string') {
        return violation;
    }
    if (violation.message) {
        return violation.message;
    }
    if (violation.label && violation.detail) {
        return `${violation.label}: ${violation.detail}`;
    }
    if (violation.label && Number.isFinite(violation.actual) && Number.isFinite(violation.expected)) {
        return `${violation.label}: ${violation.actual.toFixed(4)} ${violation.operator || ''} ${violation.expected.toFixed(4)}`;
    }
    return JSON.stringify(violation);
}

function updateTextContent(elementId, value) {
    const element = document.getElementById(elementId);
    if (element) {
        element.textContent = value;
    }
}

function showLoadingState(message) {
    console.log('Loading:', message);
}

function hideLoadingState() {
    console.log('Loading complete');
}

function showSuccessMessage(message) {
    alert('成功: ' + message);
}

function showErrorMessage(message) {
    alert('错误: ' + message);
}

function showWarningMessage(message) {
    alert('警告: ' + message);
}

function formatShareTimestamp(date = new Date()) {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
}

function buildShareableResultText(data) {
    const ratioEntries = Object.entries(data.blending_ratio || {})
        .filter(([, ratio]) => Number.isFinite(ratio) && ratio > 0)
        .sort((a, b) => b[1] - a[1]);
    const activeConstraints = Array.isArray(data.active_constraints) ? data.active_constraints.filter(Boolean) : [];
    const violations = Array.isArray(data.constraint_violations) ? data.constraint_violations : [];
    const diagnosis = Array.isArray(data.diagnosis) ? data.diagnosis.filter(Boolean) : [];

    const lines = [
        '【喷煤混配优化结果】',
        `目标：${data.objective_type === 'pci_cost_effective_v1' ? '喷煤性价比最优（可行域最低成本）' : (data.optimization_target || '喷煤性价比最优')}`,
        `结论：${data.is_feasible ? '已找到满足全部硬约束的推荐方案' : '当前结果不可直接用于生产'}`,
        '',
        '一、推荐配比'
    ];

    if (ratioEntries.length === 0) {
        lines.push('暂无有效配比结果');
    } else {
        ratioEntries.forEach(([name, ratio], index) => {
            lines.push(`${index + 1}. ${name} ${((ratio || 0) * 100).toFixed(2)}%`);
        });
    }

    lines.push(
        '',
        '二、关键指标',
        `吨煤成本：¥${Number.isFinite(data.total_price) ? data.total_price.toFixed(2) : '--'}`,
        `综合热值：${Number.isFinite(data.total_heat) ? data.total_heat.toFixed(0) : '--'} kcal/kg`,
        `综合灰分：${Number.isFinite(data.total_ash) ? data.total_ash.toFixed(2) : '--'}%`,
        `综合挥发分：${Number.isFinite(data.total_volatile) ? data.total_volatile.toFixed(2) : '--'}%`,
        `综合固定碳：${Number.isFinite(data.total_fixed_carbon) ? data.total_fixed_carbon.toFixed(2) : '--'}%`,
        `综合硫分：${Number.isFinite(data.total_sulfur) ? data.total_sulfur.toFixed(2) : '--'}%`,
        `约束可行性：${data.constraints_satisfied ? '满足' : '不满足'}`
    );

    lines.push('', '三、约束说明');
    if (data.constraints_satisfied) {
        lines.push('全部硬约束满足');
        if (activeConstraints.length > 0) {
            lines.push(`活跃约束：${activeConstraints.join('、')}`);
        }
    } else if (violations.length > 0) {
        violations.slice(0, 5).forEach((item, index) => {
            lines.push(`${index + 1}. ${toViolationText(item)}`);
        });
    } else if (diagnosis.length > 0) {
        diagnosis.slice(0, 5).forEach((item, index) => {
            lines.push(`${index + 1}. ${toViolationText(item)}`);
        });
    } else {
        lines.push('暂无详细约束诊断');
    }

    lines.push(
        '',
        '四、计算信息',
        `迭代次数：${Number.isFinite(data.iterations) ? data.iterations : '--'}`,
        `计算耗时：${Number.isFinite(data.time_taken) ? data.time_taken.toFixed(2) : '--'} 秒`,
        `生成时间：${formatShareTimestamp()}`,
        '',
        '说明：以上内容为纯文本格式，可直接粘贴到短信或微信。'
    );

    return lines.join('\n');
}

function fallbackCopyText(text) {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', 'readonly');
    textarea.style.position = 'fixed';
    textarea.style.left = '-9999px';
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();

    let copied = false;
    try {
        copied = document.execCommand('copy');
    } catch (error) {
        console.error('execCommand copy failed:', error);
    }

    document.body.removeChild(textarea);
    return copied;
}

function showCopySuccessState() {
    showSuccessMessage('分享文本已复制，可直接粘贴到短信或微信。');

    const copyBtn = document.getElementById('copyShareResultBtn');
    if (!copyBtn) {
        return;
    }

    const originalHtml = copyBtn.innerHTML;
    copyBtn.innerHTML = '<i class="bi bi-check-lg me-1"></i>已复制';
    copyBtn.classList.remove('btn-outline-secondary');
    copyBtn.classList.add('btn-success');

    setTimeout(() => {
        copyBtn.innerHTML = originalHtml;
        copyBtn.classList.remove('btn-success');
        copyBtn.classList.add('btn-outline-secondary');
    }, 2000);
}

function copyShareableResultText() {
    if (!lastOptimizationResult) {
        showWarningMessage('没有可分享的优化结果，请先运行优化计算。');
        return;
    }

    const shareText = buildShareableResultText(lastOptimizationResult);

    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(shareText).then(() => {
            showCopySuccessState();
        }).catch(error => {
            console.error('Clipboard API copy failed:', error);
            if (fallbackCopyText(shareText)) {
                showCopySuccessState();
            } else {
                showErrorMessage('复制失败，请检查浏览器剪贴板权限。');
            }
        });
        return;
    }

    if (fallbackCopyText(shareText)) {
        showCopySuccessState();
    } else {
        showErrorMessage('复制失败，当前浏览器不支持自动复制。');
    }
}

function exportOptimizationReport() {
    if (exportInProgress) {
        return;
    }

    if (!lastOptimizationResult) {
        showWarningMessage('没有可导出的优化结果，请先运行优化计算。');
        return;
    }

    exportInProgress = true;
    updateActionButtonsState();

    const exportBtn = document.getElementById('exportReportBtn');
    const originalText = exportBtn?.innerHTML || '';
    if (exportBtn) {
        exportBtn.innerHTML = '<i class="bi bi-hourglass-split me-1"></i>导出中...';
    }

    const userConstraints = {
        ...smartBlendingPreferences.constraints
    };

    fetch('/api/optimization/export/current', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            result: lastOptimizationResult,
            constraints: userConstraints
        })
    })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const contentDisposition = response.headers.get('Content-Disposition');
            let filename = '智能混煤方案_报告.xlsx';
            if (contentDisposition) {
                const filenameStarMatch = contentDisposition.match(/filename\*=UTF-8''(.+)/);
                if (filenameStarMatch && filenameStarMatch[1]) {
                    try {
                        filename = decodeURIComponent(filenameStarMatch[1]);
                    } catch (error) {
                        console.error('解码 filename* 失败:', error);
                    }
                } else {
                    const filenameMatch = contentDisposition.match(/filename="([^"]+)"/);
                    if (filenameMatch && filenameMatch[1]) {
                        filename = filenameMatch[1];
                    }
                }
            }

            return response.blob().then(blob => ({ blob, filename }));
        })
        .then(({ blob, filename }) => {
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.style.display = 'none';
            link.href = url;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(link);

            showSuccessMessage('优化报告已成功导出！');
        })
        .catch(error => {
            console.error('导出报告失败:', error);
            showErrorMessage(`导出失败: ${error.message}`);
        })
        .finally(() => {
            exportInProgress = false;
            if (exportBtn) {
                exportBtn.innerHTML = originalText;
            }
            updateActionButtonsState();
        });
}
