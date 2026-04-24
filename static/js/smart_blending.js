// 智能混煤页面JavaScript文件

// 全局变量
let selectedCoals = new Set(); // 选中的煤种ID
let allCoals = []; // 所有煤种数据
let filteredCoals = []; // 过滤后的煤种数据
let currentCoalPage = 1; // 当前页码
let coalPageSize = 10; // 每页显示数量
let optimizationInProgress = false; // 是否正在优化
let lastOptimizationResult = null; // 最后一次优化结果
let exportInProgress = false; // 是否正在导出

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    initializeSmartBlendingPage();
});

// 初始化页面
function initializeSmartBlendingPage() {
    loadCoalsForBlending();
    setupBlendingEventListeners();
    loadAlgorithmSettings();
}

// 设置事件监听器
function setupBlendingEventListeners() {
    // 搜索框回车事件
    document.getElementById('coalSearchInput').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            searchCoalsForBlending();
        }
    });

    // 页面大小改变事件
    document.getElementById('coalPageSize').addEventListener('change', function() {
        coalPageSize = parseInt(this.value);
        currentCoalPage = 1;
        displayCoalsForBlending();
    });

    // 类型筛选改变事件
    document.getElementById('coalTypeFilter').addEventListener('change', function() {
        searchCoalsForBlending();
    });

    // 绑定导出按钮事件（防止重复绑定）
    const exportBtn = document.getElementById('exportReportBtn');
    if (exportBtn && !exportBtn.hasAttribute('data-event-bound')) {
        exportBtn.addEventListener('click', exportOptimizationReport);
        exportBtn.setAttribute('data-event-bound', 'true');
        console.log('导出按钮事件已绑定');
    }

    // 绑定复制分享按钮事件
    const copyBtn = document.getElementById('copyShareResultBtn');
    if (copyBtn && !copyBtn.hasAttribute('data-event-bound')) {
        copyBtn.addEventListener('click', copyShareableResultText);
        copyBtn.setAttribute('data-event-bound', 'true');
        console.log('复制分享按钮事件已绑定');
    }
}

// 加载煤种数据用于混煤
async function loadCoalsForBlending() {
    try {
        showLoadingState('加载煤种数据...');
        const response = await fetch('/api/coals?page_size=0');
        const result = await response.json();
        
        if (result.status === 'success') {
            allCoals = result.data;
            filteredCoals = [...allCoals];
            displayCoalsForBlending();
        } else {
            showErrorMessage('加载煤种数据失败: ' + result.message);
        }
    } catch (error) {
        showErrorMessage('网络错误: ' + error.message);
    } finally {
        hideLoadingState();
    }
}

// 显示煤种数据用于混煤选择
function displayCoalsForBlending() {
    const tbody = document.getElementById('coalSelectionTableBody');
    const startIndex = (currentCoalPage - 1) * coalPageSize;
    const endIndex = Math.min(startIndex + coalPageSize, filteredCoals.length);
    const pageCoals = filteredCoals.slice(startIndex, endIndex);

    // 清空表格
    tbody.innerHTML = '';

    if (pageCoals.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10" class="text-center text-muted">暂无煤种数据</td></tr>';
        updateCoalPagination();
        updateCoalStatistics();
        return;
    }

    // 添加数据行
    pageCoals.forEach(coal => {
        const row = createCoalSelectionRow(coal);
        tbody.appendChild(row);
    });

    updateCoalPagination();
    updateCoalStatistics();
    updateSelectedCoalCount();
}

// 创建煤种选择行
function createCoalSelectionRow(coal) {
    const row = document.createElement('tr');
    const isSelected = selectedCoals.has(coal.id);
    
    row.innerHTML = `
        <td>
            <input class="form-check-input" type="checkbox" value="${coal.id}" 
                   ${isSelected ? 'checked' : ''} onchange="toggleCoalSelection(${coal.id})">
        </td>
        <td>${coal.name}</td>
        <td>
            <span class="badge bg-secondary">${coal.type}</span>
        </td>
        <td>¥${coal.price.toFixed(2)}</td>
        <td>${coal.calorific_value}</td>
        <td>${coal.ash_content.toFixed(2)}%</td>
        <td>${coal.volatile_matter.toFixed(2)}%</td>
        <td>${coal.total_sulfur.toFixed(2)}%</td>
        <td class="ratio-constraints-cell">
            <div class="ratio-constraints-wrapper">
                <div class="input-group input-group-sm ratio-input-group">
                    <span class="input-group-text ratio-constraint-label">下限</span>
                    <input type="number" class="form-control ratio-min ratio-constraint-input" value="5" min="0" max="100" step="0.1" 
                           data-coal-id="${coal.id}" placeholder="5" 
                           onchange="validateRatioConstraints(${coal.id})" title="配比下限 (%)">
                    <span class="input-group-text">%</span>
                </div>
                <div class="input-group input-group-sm ratio-input-group">
                    <span class="input-group-text ratio-constraint-label">上限</span>
                    <input type="number" class="form-control ratio-max ratio-constraint-input" value="80" min="0" max="100" step="0.1" 
                           data-coal-id="${coal.id}" placeholder="80"
                           onchange="validateRatioConstraints(${coal.id})" title="配比上限 (%)">
                    <span class="input-group-text">%</span>
                </div>
            </div>
        </td>
        <td>
            <button class="btn btn-sm btn-outline-primary" onclick="viewCoalDetailForBlending(${coal.id})" title="查看详情">
                <i class="bi bi-eye"></i>
            </button>
        </td>
    `;
    return row;
}

// 切换煤种选择状态
function toggleCoalSelection(coalId) {
    if (selectedCoals.has(coalId)) {
        selectedCoals.delete(coalId);
    } else {
        selectedCoals.add(coalId);
    }
    updateSelectedCoalCount();
}

// 更新选中煤种数量
function updateSelectedCoalCount() {
    const selectedCount = document.getElementById('selectedCount');
    if (selectedCount) {
        selectedCount.textContent = selectedCoals.size;
    }
}

// 更新煤种分页
function updateCoalPagination() {
    const pagination = document.getElementById('coalPagination');
    const totalPages = Math.ceil(filteredCoals.length / coalPageSize);
    
    pagination.innerHTML = '';

    if (totalPages <= 1) return;

    // 上一页
    const prevItem = document.createElement('li');
    prevItem.className = `page-item ${currentCoalPage === 1 ? 'disabled' : ''}`;
    prevItem.innerHTML = `<a class="page-link" href="#" onclick="changeCoalPage(${currentCoalPage - 1})">上一页</a>`;
    pagination.appendChild(prevItem);

    // 页码按钮
    const startPage = Math.max(1, currentCoalPage - 2);
    const endPage = Math.min(totalPages, currentCoalPage + 2);

    if (startPage > 1) {
        const firstItem = document.createElement('li');
        firstItem.className = 'page-item';
        firstItem.innerHTML = '<a class="page-link" href="#" onclick="changeCoalPage(1)">1</a>';
        pagination.appendChild(firstItem);

        if (startPage > 2) {
            const ellipsis = document.createElement('li');
            ellipsis.className = 'page-item disabled';
            ellipsis.innerHTML = '<span class="page-link">...</span>';
            pagination.appendChild(ellipsis);
        }
    }

    for (let i = startPage; i <= endPage; i++) {
        const pageItem = document.createElement('li');
        pageItem.className = `page-item ${i === currentCoalPage ? 'active' : ''}`;
        pageItem.innerHTML = `<a class="page-link" href="#" onclick="changeCoalPage(${i})">${i}</a>`;
        pagination.appendChild(pageItem);
    }

    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            const ellipsis = document.createElement('li');
            ellipsis.className = 'page-item disabled';
            ellipsis.innerHTML = '<span class="page-link">...</span>';
            pagination.appendChild(ellipsis);
        }

        const lastItem = document.createElement('li');
        lastItem.className = 'page-item';
        lastItem.innerHTML = `<a class="page-link" href="#" onclick="changeCoalPage(${totalPages})">${totalPages}</a>`;
        pagination.appendChild(lastItem);
    }

    // 下一页
    const nextItem = document.createElement('li');
    nextItem.className = `page-item ${currentCoalPage === totalPages ? 'disabled' : ''}`;
    nextItem.innerHTML = `<a class="page-link" href="#" onclick="changeCoalPage(${currentCoalPage + 1})">下一页</a>`;
    pagination.appendChild(nextItem);
}

// 更新煤种统计信息
function updateCoalStatistics() {
    const startIndex = (currentCoalPage - 1) * coalPageSize + 1;
    const endIndex = Math.min(currentCoalPage * coalPageSize, filteredCoals.length);
    
    document.getElementById('coalStartIndex').textContent = filteredCoals.length > 0 ? startIndex : 0;
    document.getElementById('coalEndIndex').textContent = endIndex;
    document.getElementById('coalTotalItems').textContent = filteredCoals.length;
}

// 切换煤种页面
function changeCoalPage(page) {
    if (page < 1 || page > Math.ceil(filteredCoals.length / coalPageSize)) return;
    currentCoalPage = page;
    displayCoalsForBlending();
}

// 搜索煤种用于混煤
function searchCoalsForBlending() {
    const searchTerm = document.getElementById('coalSearchInput').value.toLowerCase();
    const typeFilter = document.getElementById('coalTypeFilter').value;

    filteredCoals = allCoals.filter(coal => {
        const matchesSearch = !searchTerm || 
            coal.name.toLowerCase().includes(searchTerm) ||
            coal.type.toLowerCase().includes(searchTerm);
        
        const matchesType = !typeFilter || coal.type === typeFilter;
        
        return matchesSearch && matchesType;
    });

    currentCoalPage = 1;
    displayCoalsForBlending();
}

// 刷新煤种列表
function refreshCoalList() {
    loadCoalsForBlending();
}

// 应用全局配比约束到所有煤种
function applyGlobalRatioConstraints() {
    const globalMin = parseFloat(document.getElementById('globalRatioMin').value) || 5;
    const globalMax = parseFloat(document.getElementById('globalRatioMax').value) || 80;
    
    // 验证全局约束的合理性
    if (globalMin < 0 || globalMin > 100) {
        showWarningMessage('配比下限必须在0-100%之间');
        return;
    }
    if (globalMax < 0 || globalMax > 100) {
        showWarningMessage('配比上限必须在0-100%之间');
        return;
    }
    if (globalMin >= globalMax) {
        showWarningMessage('配比下限不能大于或等于上限');
        return;
    }
    
    // 应用到所有煤种的配比约束输入框
    const ratioMinInputs = document.querySelectorAll('.ratio-min');
    const ratioMaxInputs = document.querySelectorAll('.ratio-max');
    
    ratioMinInputs.forEach(input => {
        input.value = globalMin;
    });
    
    ratioMaxInputs.forEach(input => {
        input.value = globalMax;
    });
    
    showSuccessMessage(`已将全局配比约束 (${globalMin}% - ${globalMax}%) 应用到所有煤种`);
}

// 验证配比约束的合理性
function validateRatioConstraints(coalId) {
    const minInput = document.querySelector(`.ratio-min[data-coal-id="${coalId}"]`);
    const maxInput = document.querySelector(`.ratio-max[data-coal-id="${coalId}"]`);
    
    if (!minInput || !maxInput) return;
    
    const minValue = parseFloat(minInput.value) || 0;
    const maxValue = parseFloat(maxInput.value) || 100;
    
    // 重置样式
    minInput.classList.remove('constraint-validation-error', 'constraint-validation-success');
    maxInput.classList.remove('constraint-validation-error', 'constraint-validation-success');
    
    // 验证范围
    if (minValue < 0) {
        minInput.value = 0;
        minInput.classList.add('constraint-validation-error');
        showWarningMessage('配比下限不能小于0%');
        return;
    }
    if (minValue > 100) {
        minInput.value = 100;
        minInput.classList.add('constraint-validation-error');
        showWarningMessage('配比下限不能大于100%');
        return;
    }
    if (maxValue < 0) {
        maxInput.value = 0;
        maxInput.classList.add('constraint-validation-error');
        showWarningMessage('配比上限不能小于0%');
        return;
    }
    if (maxValue > 100) {
        maxInput.value = 100;
        maxInput.classList.add('constraint-validation-error');
        showWarningMessage('配比上限不能大于100%');
        return;
    }
    
    // 验证下限不能大于上限
    if (minValue >= maxValue) {
        const coal = allCoals.find(c => c.id === coalId);
        const coalName = coal ? coal.name : `煤种${coalId}`;
        minInput.classList.add('constraint-validation-error');
        maxInput.classList.add('constraint-validation-error');
        showWarningMessage(`${coalName}的配比下限不能大于或等于上限`);
        
        // 自动调整
        if (minValue >= maxValue) {
            if (minValue < 100) {
                maxInput.value = Math.min(100, minValue + 10);
            } else {
                minInput.value = Math.max(0, maxValue - 10);
            }
        }
    } else {
        // 验证通过，添加成功样式
        minInput.classList.add('constraint-validation-success');
        maxInput.classList.add('constraint-validation-success');
    }
}

// 获取所有煤种的配比约束
function getAllRatioConstraints() {
    const constraints = {};
    const ratioMinInputs = document.querySelectorAll('.ratio-min');
    const ratioMaxInputs = document.querySelectorAll('.ratio-max');
    
    ratioMinInputs.forEach(input => {
        const coalId = parseInt(input.getAttribute('data-coal-id'));
        if (!constraints[coalId]) constraints[coalId] = {};
        constraints[coalId].min = parseFloat(input.value) || 5;
    });
    
    ratioMaxInputs.forEach(input => {
        const coalId = parseInt(input.getAttribute('data-coal-id'));
        if (!constraints[coalId]) constraints[coalId] = {};
        constraints[coalId].max = parseFloat(input.value) || 80;
    });
    
    return constraints;
}

// 验证所有配比约束的总体合理性
function validateAllRatioConstraints() {
    const selectedCoalArray = Array.from(selectedCoals);
    if (selectedCoalArray.length === 0) {
        showWarningMessage('请至少选择一种煤进行混合');
        return false;
    }
    
    const constraints = getAllRatioConstraints();
    let totalMinRatio = 0;
    let totalMaxRatio = 0;
    
    // 计算所有选中煤种的最小和最大配比总和
    selectedCoalArray.forEach(coalId => {
        if (constraints[coalId]) {
            totalMinRatio += constraints[coalId].min || 0;
            totalMaxRatio += constraints[coalId].max || 100;
        }
    });
    
    // 检查是否可能达到100%的总配比
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

// 查看煤种详情（用于混煤选择）
function viewCoalDetailForBlending(coalId) {
    const coal = allCoals.find(c => c.id === coalId);
    if (!coal) return;

    const detailContent = document.getElementById('coalDetailContent');
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

    new bootstrap.Modal(document.getElementById('coalDetailModal')).show();
}

// 开始优化计算
async function startOptimization(button) {
    if (optimizationInProgress) {
        showWarningMessage('优化计算正在进行中，请稍候...');
        return;
    }

    // 检查是否选择了煤种
    if (selectedCoals.size < 2) {
        showWarningMessage('请至少选择两种煤进行混配优化');
        return;
    }
    
    // 验证配比约束
    if (!validateAllRatioConstraints()) {
        return;
    }

    // 收集约束条件
    const constraints = {
        heat_target: parseFloat(document.getElementById('heatTarget').value),
        heat_min: parseFloat(document.getElementById('heatMin').value),
        heat_max: parseFloat(document.getElementById('heatMax').value),
        ash_min: parseFloat(document.getElementById('ashMin').value),
        ash_max: parseFloat(document.getElementById('ashMax').value),
        volatile_min: parseFloat(document.getElementById('volatileMin').value),
        volatile_max: parseFloat(document.getElementById('volatileMax').value),
        fixed_carbon_min: parseFloat(document.getElementById('fixedCarbonMin').value),
        fixed_carbon_max: parseFloat(document.getElementById('fixedCarbonMax').value),
        sulfur_min: parseFloat(document.getElementById('sulfurMin').value),
        sulfur_max: parseFloat(document.getElementById('sulfurMax').value),
        price_min: parseFloat(document.getElementById('priceMin').value),
        price_max: parseFloat(document.getElementById('priceMax').value),
        ratio_constraints: getAllRatioConstraints()
    };

    // 收集算法参数
    const gaParams = getAlgorithmParameters();

    // 获取优化目标
    const optimizationTarget = document.getElementById('optimizationTarget').value;

    try {
        optimizationInProgress = true;
        button.disabled = true;
        button.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>计算中...';

        showLoadingState('正在进行优化计算，请稍候...');

        const requestData = {
            optimization_target: optimizationTarget,
            selected_coal_ids: Array.from(selectedCoals),
            constraints: constraints,
            ga_params: gaParams
        };

        console.log('发送优化请求数据:', requestData);

        const response = await fetch('/api/optimization', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });

        console.log('收到响应:', response.status, response.statusText);

        const result = await response.json();
        console.log('解析的JSON结果:', result);

        if (['success', 'no_feasible_solution', 'search_failed'].includes(result.status)) {
            console.log('优化请求返回:', result.status, result.message);
            displayOptimizationResults(result.result);

            const allowExport = result.status === 'success';
            document.getElementById('exportReportBtn').disabled = !allowExport;
            document.getElementById('copyShareResultBtn').disabled = !allowExport;

            if (result.status === 'success') {
                showSuccessMessage('喷煤性价比优化完成！');
            } else if (result.status === 'no_feasible_solution') {
                lastOptimizationResult = null;
                showWarningMessage(result.message || '当前约束下不存在可行混煤方案');
            } else {
                lastOptimizationResult = null;
                showWarningMessage(result.message || '遗传算法未能生成满足约束的解');
            }
        } else {
            console.error('优化失败:', result.message);
            lastOptimizationResult = null;
            document.getElementById('exportReportBtn').disabled = true;
            document.getElementById('copyShareResultBtn').disabled = true;
            showErrorMessage('优化计算失败: ' + result.message);
        }

    } catch (error) {
        showErrorMessage('网络错误: ' + error.message);
    } finally {
        optimizationInProgress = false;
        button.disabled = false;
        button.innerHTML = '<i class="bi bi-play-circle me-2"></i>开始优化计算';
        hideLoadingState();
    }
}

// 获取算法参数
function getAlgorithmParameters() {
    return {
        population_size: parseInt(document.getElementById('populationSize')?.value || 500),
        max_generations: parseInt(document.getElementById('maxGenerations')?.value || 3000),
        mutation_rate: parseFloat(document.getElementById('mutationRate')?.value || 0.2),
        crossover_rate: parseFloat(document.getElementById('crossoverRate')?.value || 0.85),
        tournament_size: parseInt(document.getElementById('tournamentSize')?.value || 7),
        elite_ratio: parseFloat(document.getElementById('eliteRatio')?.value || 0.1),
        early_stopping_patience: parseInt(document.getElementById('earlyStoppingPatience')?.value || 200),
        constraint_penalty_factor: parseFloat(document.getElementById('constraintPenaltyFactor')?.value || 1500),
        parallel_workers: parseInt(document.getElementById('parallelWorkers')?.value || 4),
        diversity_factor: parseFloat(document.getElementById('diversityFactor')?.value || 0.1),
        adaptive_mutation: document.getElementById('adaptiveMutation')?.checked ?? true,
        parallel_computing: document.getElementById('parallelComputing')?.checked ?? true
    };
}

// 显示优化结果
function displayOptimizationResults(data) {
    console.log('接收到的优化结果数据:', data);

    if (data?.is_feasible) {
        lastOptimizationResult = data;
    }

    const ratios = [];
    const coalNames = Array.isArray(data?.coal_names) ? data.coal_names : [];
    const optimalRatios = Array.isArray(data?.optimal_ratios) ? data.optimal_ratios : [];
    for (let i = 0; i < coalNames.length; i++) {
        ratios.push({
            coal_name: coalNames[i],
            percentage: (optimalRatios[i] || 0) * 100
        });
    }

    updateRatioTable(ratios);
    updatePerformanceIndicators(data);
    updateAlgorithmInfo(data);
    renderConstraintStatus(data);
    updateCharts(data);
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

// 更新配比表格
function updateRatioTable(ratios) {
    const tbody = document.querySelector('.result-table tbody');
    if (!tbody) {
        console.error('找不到配比表格的tbody元素');
        return;
    }
    
    tbody.innerHTML = '';
    
    // 只显示有意义的配比（大于0.1%）
    const significantRatios = ratios.filter(ratio => ratio.percentage > 0.1);
    
    if (significantRatios.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" class="text-center text-muted">无有效配比数据</td></tr>';
        return;
    }
    
    significantRatios.forEach(ratio => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${ratio.coal_name}</td>
            <td>${ratio.percentage.toFixed(2)}%</td>
            <td>
                <div class="progress" style="height: 20px;">
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

// 更新性能指标
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
        } else {
            console.error(`找不到元素: ${selector}`);
        }
    });
}

// 更新算法信息
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
        } else {
            console.error(`找不到元素: ${selector}`);
        }
    });
}

function renderConstraintStatus(data) {
    const container = document.querySelector('.constraint-status-list');
    if (!container) return;

    const violations = Array.isArray(data?.constraint_violations) ? data.constraint_violations : [];
    const activeConstraints = Array.isArray(data?.active_constraints) ? data.active_constraints : [];
    const diagnosis = Array.isArray(data?.diagnosis) ? data.diagnosis : [];

    container.innerHTML = '';

    if (data?.is_feasible) {
        const successBadge = document.createElement('span');
        successBadge.className = 'badge bg-success constraint-badge';
        successBadge.innerHTML = '<i class="bi bi-check-circle me-1"></i>全部硬约束满足';
        container.appendChild(successBadge);

        if (activeConstraints.length > 0) {
            activeConstraints.slice(0, 6).forEach(item => {
                const badge = document.createElement('span');
                badge.className = 'badge bg-warning text-dark constraint-badge';
                badge.innerHTML = `<i class="bi bi-exclamation-triangle me-1"></i>活跃约束: ${item}`;
                container.appendChild(badge);
            });
        }
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

// 更新图表
function updateCharts(optimizationResult) {
    console.log('开始更新图表, 数据:', optimizationResult);

    if (typeof Chart === 'undefined') {
        console.error('Chart.js 未加载');
        return;
    }

    createSimpleCharts(optimizationResult);
}

// 简化的图表创建函数
function createSimpleCharts(data) {
    console.log('创建简化图表');
    
    // 更新配比饼图
    createSimpleRatioChart(data);
    
    // 清空其他图表区域，显示文本内容
    const performanceChart = document.getElementById('performanceChart');
    if (performanceChart) {
        performanceChart.innerHTML = `
            <div class="d-flex align-items-center justify-content-center h-100">
                <div class="text-center">
                    <h6>喷煤性价比结果</h6>
                    <p>目标: ${data.objective_type === 'pci_cost_effective_v1' ? '可行域最低成本' : (data.optimization_target || '--')}</p>
                    <p>热值: ${formatNumeric(data.total_heat, value => value.toFixed(0) + ' kcal/kg')}</p>
                    <p>灰分: ${formatNumeric(data.total_ash, value => value.toFixed(2) + '%')}</p>
                    <p>成本: ${formatNumeric(data.total_price, value => '¥' + value.toFixed(2) + '/吨')}</p>
                </div>
            </div>
        `;
    }
    
    const constraintChart = document.getElementById('constraintChart');
    if (constraintChart) {
        const violations = Array.isArray(data?.constraint_violations) ? data.constraint_violations : [];
        const diagnosis = Array.isArray(data?.diagnosis) ? data.diagnosis : [];
        const statusText = data?.is_feasible ? '全部硬约束满足' : '当前方案不可行';
        const detailLines = data?.is_feasible
            ? (data?.active_constraints?.length ? data.active_constraints.slice(0, 3).map(item => `<p>活跃约束: ${item}</p>`).join('') : '<p>当前可行解存在约束余量</p>')
            : [...violations, ...diagnosis].slice(0, 3).map(item => `<p>${toViolationText(item)}</p>`).join('');
        constraintChart.innerHTML = `
            <div class="d-flex align-items-center justify-content-center h-100">
                <div class="text-center">
                    <h6>${data?.is_feasible ? '可行性检查通过' : '约束诊断'}</h6>
                    <p>迭代次数: ${Number.isFinite(data?.iterations) ? data.iterations : '--'}</p>
                    <p>计算耗时: ${formatNumeric(data?.time_taken, value => value.toFixed(2) + '秒')}</p>
                    <p>${statusText}</p>
                    ${detailLines}
                </div>
            </div>
        `;
    }
}

// 创建简化的配比饼图
function createSimpleRatioChart(data) {
    const ratioChart = document.getElementById('ratioChart');
    if (!ratioChart) return;
    
    // 清空容器
    ratioChart.innerHTML = '';
    
    // 创建canvas
    const canvas = document.createElement('canvas');
    ratioChart.appendChild(canvas);
    
    // 准备数据
    const labels = data.coal_names;
    const ratios = data.optimal_ratios.map(ratio => (ratio * 100).toFixed(2));
    
    // 生成颜色
    const colors = [
        '#1e40af',
        '#f97316', 
        '#16a34a',
        '#dc2626',
        '#7c3aed'
    ].slice(0, labels.length);
    
    try {
        new Chart(canvas, {
            type: 'pie',
            data: {
                labels: labels,
                datasets: [{
                    data: ratios,
                    backgroundColor: colors,
                    borderWidth: 2,
                    borderColor: '#fff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 15,
                            usePointStyle: true
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `${context.label}: ${context.parsed}%`;
                            }
                        }
                    }
                }
            }
        });
        console.log('配比饼图创建成功');
    } catch (error) {
        console.error('创建配比饼图失败:', error);
        ratioChart.innerHTML = `
            <div class="d-flex align-items-center justify-content-center h-100">
                <div class="text-center">
                    <h6>配比结果</h6>
                    ${labels.map((name, i) => `<p>${name}: ${ratios[i]}%</p>`).join('')}
                </div>
            </div>
        `;
    }
}

// 加载算法设置
function loadAlgorithmSettings() {
    // 从localStorage加载保存的算法设置
    const settings = localStorage.getItem('algorithmSettings');
    if (settings) {
        const params = JSON.parse(settings);
        
        Object.keys(params).forEach(key => {
            const element = document.getElementById(key);
            if (element) {
                if (element.type === 'checkbox') {
                    element.checked = params[key];
                } else {
                    element.value = params[key];
                }
            }
        });
    }
}

// 保存算法设置
function saveAlgorithmSettings() {
    const params = getAlgorithmParameters();
    localStorage.setItem('algorithmSettings', JSON.stringify(params));
    
    showSuccessMessage('算法设置已保存');
    
    const modal = bootstrap.Modal.getInstance(document.getElementById('algorithmSettingsModal'));
    modal.hide();
}

// 重置算法设置
function resetAlgorithmSettings() {
    if (confirm('确定要重置算法设置为默认值吗？')) {
        document.getElementById('populationSize').value = 500;
        document.getElementById('maxGenerations').value = 3000;
        document.getElementById('mutationRate').value = 0.2;
        document.getElementById('crossoverRate').value = 0.85;
        document.getElementById('tournamentSize').value = 7;
        document.getElementById('eliteRatio').value = 0.1;
        document.getElementById('earlyStoppingPatience').value = 200;
        document.getElementById('constraintPenaltyFactor').value = 1500;
        document.getElementById('parallelWorkers').value = 4;
        document.getElementById('diversityFactor').value = 0.1;
        document.getElementById('adaptiveMutation').checked = true;
        document.getElementById('parallelComputing').checked = true;
        
        showSuccessMessage('算法设置已重置为默认值');
    }
}

// 工具函数
function showLoadingState(message) {
    console.log('Loading:', message);
    // 这里可以显示加载动画
}

function hideLoadingState() {
    console.log('Loading complete');
    // 这里可以隐藏加载动画
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
    } else {
        if (violations.length > 0) {
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
    if (!copyBtn) return;

    const originalHtml = copyBtn.innerHTML;
    copyBtn.innerHTML = `<i class="bi bi-check-lg me-1"></i>已复制`;
    copyBtn.classList.remove('btn-outline-secondary');
    copyBtn.classList.add('btn-success');

    setTimeout(() => {
        copyBtn.innerHTML = originalHtml;
        copyBtn.classList.remove('btn-success');
        copyBtn.classList.add('btn-outline-secondary');
    }, 2000);
}

// --- 新增：复制分享结果为文本 ---
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

// 导出优化报告
function exportOptimizationReport() {
    console.log('导出按钮被点击');
    
    // 防止重复点击
    if (exportInProgress) {
        console.log('导出正在进行中，忽略重复点击');
        return;
    }
    
    console.log('lastOptimizationResult:', lastOptimizationResult);
    
    if (!lastOptimizationResult) {
        console.log('没有优化结果数据');
        showWarningMessage('没有可导出的优化结果，请先运行优化计算。');
        return;
    }
    
    console.log('开始导出优化报告');
    exportInProgress = true;
    
    // 显示加载状态
    const exportBtn = document.getElementById('exportReportBtn');
    const originalText = exportBtn.innerHTML;
    exportBtn.innerHTML = '<i class="bi bi-hourglass-split me-1"></i>导出中...';
    exportBtn.disabled = true;
    
    // 收集用户设置的约束条件
    const userConstraints = {
        heat_target: parseFloat(document.getElementById('heatTarget')?.value) || 6000,
        heat_min: parseFloat(document.getElementById('heatMin')?.value) || 5800,
        heat_max: parseFloat(document.getElementById('heatMax')?.value) || 6500,
        ash_min: parseFloat(document.getElementById('ashMin')?.value) || 8.0,
        ash_max: parseFloat(document.getElementById('ashMax')?.value) || 18.0,
        volatile_min: parseFloat(document.getElementById('volatileMin')?.value) || 15.0,
        volatile_max: parseFloat(document.getElementById('volatileMax')?.value) || 35.0,
        fixed_carbon_min: parseFloat(document.getElementById('fixedCarbonMin')?.value) || 55.0,
        fixed_carbon_max: parseFloat(document.getElementById('fixedCarbonMax')?.value) || 75.0,
        sulfur_min: parseFloat(document.getElementById('sulfurMin')?.value) || 0.4,
        sulfur_max: parseFloat(document.getElementById('sulfurMax')?.value) || 0.8,
        price_min: parseFloat(document.getElementById('priceMin')?.value) || 450,
        price_max: parseFloat(document.getElementById('priceMax')?.value) || 800
    };
    
    console.log('用户设置的约束条件:', userConstraints);

    // 发送导出请求
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
        
        // 获取文件名
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = '智能混煤方案_报告.xlsx'; // 默认文件名
        if (contentDisposition) {
            // 尝试从UTF-8编码的filename*中解码
            const filenameStarMatch = contentDisposition.match(/filename\*=UTF-8''(.+)/);
            if (filenameStarMatch && filenameStarMatch[1]) {
                try {
                    filename = decodeURIComponent(filenameStarMatch[1]);
                } catch (e) {
                    console.error('解码filename*失败:', e);
                }
            } else {
                // 如果没有filename*，再尝试从filename中获取
                const filenameMatch = contentDisposition.match(/filename="([^"]+)"/);
                if (filenameMatch && filenameMatch[1]) {
                    filename = filenameMatch[1];
                }
            }
        }
        
        return response.blob().then(blob => ({ blob, filename }));
    })
    .then(({ blob, filename }) => {
        // 创建下载链接
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        showSuccessMessage('优化报告已成功导出！');
    })
    .catch(error => {
        console.error('导出报告失败:', error);
        showErrorMessage(`导出失败: ${error.message}`);
    })
    .finally(() => {
        // 恢复按钮状态和导出标志
        exportInProgress = false;
        exportBtn.innerHTML = originalText;
        exportBtn.disabled = false;
        console.log('按钮状态已恢复，导出标志已重置');
    });
}
