let blendingHistoryModal = null;
let blendingHistoryItems = [];

document.addEventListener('DOMContentLoaded', function () {
    document.getElementById('refreshBlendingHistoryBtn')?.addEventListener('click', loadBlendingHistory);
    document.getElementById('blendingHistorySearch')?.addEventListener('input', renderFilteredBlendingHistory);
    document.getElementById('blendingFeasibilityFilter')?.addEventListener('change', renderFilteredBlendingHistory);
    document.getElementById('clearBlendingHistoryFiltersBtn')?.addEventListener('click', clearBlendingHistoryFilters);
    document.getElementById('blendingHistoryTableBody')?.addEventListener('click', handleBlendingHistoryTableClick);

    loadBlendingHistory();
});

async function loadBlendingHistory() {
    const tbody = document.getElementById('blendingHistoryTableBody');
    if (!tbody) {
        return;
    }

    setBlendingHistoryStatus('info', '正在加载混煤优化历史...', '历史记录来自 SQLite，可按煤种、时间和可行性快速筛选。');
    setBlendingHistoryLoading(true);

    try {
        const response = await fetch('/api/optimization/history');
        const result = await response.json();

        if (!response.ok || result.status !== 'success') {
            throw new Error(result.message || '加载历史记录失败');
        }

        blendingHistoryItems = Array.isArray(result.data) ? result.data : [];
        updateBlendingHistoryStats(blendingHistoryItems);
        renderFilteredBlendingHistory();
        setBlendingHistoryStatus('success', '混煤优化历史已加载。', `共 ${blendingHistoryItems.length} 条 SQLite 历史记录。`);
    } catch (error) {
        blendingHistoryItems = [];
        updateBlendingHistoryStats([]);
        tbody.innerHTML = `<tr><td colspan="8" class="text-center text-danger">${escapeHtml(error.message)}</td></tr>`;
        updateTextContent('blendingHistoryTableSummary', '加载失败');
        setBlendingHistoryStatus('danger', '混煤优化历史加载失败。', error.message);
        showHistoryToast(error.message, 'danger');
    } finally {
        setBlendingHistoryLoading(false);
    }
}

function renderFilteredBlendingHistory() {
    renderBlendingHistoryRows(getFilteredBlendingHistoryItems());
}

function getFilteredBlendingHistoryItems() {
    const keyword = normalizeText(document.getElementById('blendingHistorySearch')?.value || '');
    const feasibility = document.getElementById('blendingFeasibilityFilter')?.value || 'all';

    return blendingHistoryItems.filter(item => {
        const matchesFeasibility =
            feasibility === 'all' ||
            (feasibility === 'feasible' && item.constraints_satisfied) ||
            (feasibility === 'infeasible' && !item.constraints_satisfied);

        if (!matchesFeasibility) {
            return false;
        }

        if (!keyword) {
            return true;
        }

        return normalizeText([
            item.date,
            item.total_price,
            item.total_heat,
            item.total_ash,
            item.total_sulfur,
            item.constraints_satisfied ? '可行' : '不可行',
            ...(Array.isArray(item.ratio_items) ? item.ratio_items.map(ratioItem => ratioItem.coal_name) : [])
        ].join(' ')).includes(keyword);
    });
}

function renderBlendingHistoryRows(items) {
    const tbody = document.getElementById('blendingHistoryTableBody');
    if (!tbody) {
        return;
    }

    if (!Array.isArray(items) || items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8"><div class="history-empty-state">当前筛选条件下暂无混煤优化历史记录</div></td></tr>';
        updateTextContent('blendingHistoryTableSummary', `显示 0 / ${blendingHistoryItems.length} 条记录`);
        return;
    }

    tbody.innerHTML = items.map(item => {
        const ratioItems = Array.isArray(item.ratio_items) ? item.ratio_items : [];
        const ratioSummary = ratioItems.slice(0, 4).map(ratioItem => (
            `<span class="history-chip">${escapeHtml(ratioItem.coal_name)} ${formatPercentage(ratioItem.ratio_percent)}</span>`
        )).join('');

        return `
            <tr>
                <td class="history-time-cell">${escapeHtml(item.date || '--')}</td>
                <td>
                    <div class="history-table-summary">
                        ${ratioSummary || '<span class="text-muted">暂无配比摘要</span>'}
                    </div>
                </td>
                <td>${formatCurrency(item.total_price)}</td>
                <td>${formatMetric(item.total_heat, 'kcal/kg', 0)}</td>
                <td>${formatMetric(item.total_ash, '%', 2)}</td>
                <td>${formatMetric(item.total_sulfur, '%', 2)}</td>
                <td>
                    <span class="history-badge" data-tone="${item.constraints_satisfied ? 'success' : 'warning'}">
                        ${item.constraints_satisfied ? '可行' : '不可行'}
                    </span>
                </td>
                <td>
                    <button class="btn btn-sm btn-outline-primary" type="button" data-history-action="detail" data-history-id="${escapeHtml(item.id)}">
                        <i class="bi bi-eye me-1"></i>详情
                    </button>
                </td>
            </tr>
        `;
    }).join('');

    updateTextContent('blendingHistoryTableSummary', `显示 ${items.length} / ${blendingHistoryItems.length} 条记录`);
}

function clearBlendingHistoryFilters() {
    const search = document.getElementById('blendingHistorySearch');
    const filter = document.getElementById('blendingFeasibilityFilter');
    if (search) {
        search.value = '';
    }
    if (filter) {
        filter.value = 'all';
    }
    renderFilteredBlendingHistory();
}

function handleBlendingHistoryTableClick(event) {
    const button = event.target.closest('[data-history-action="detail"]');
    if (!button) {
        return;
    }

    showBlendingHistoryDetail(button.dataset.historyId);
}

async function showBlendingHistoryDetail(historyId) {
    const content = document.getElementById('blendingHistoryDetailContent');
    if (!content || !historyId) {
        return;
    }

    content.innerHTML = '<div class="text-center text-muted py-4">正在加载详情...</div>';
    showBlendingHistoryModal();

    try {
        const response = await fetch(`/api/optimization/history/${historyId}`);
        const result = await response.json();

        if (!response.ok || result.status !== 'success') {
            throw new Error(result.message || '加载详情失败');
        }

        content.innerHTML = buildBlendingHistoryDetailHtml(result.data || {});
    } catch (error) {
        content.innerHTML = `<div class="alert alert-danger mb-0">${escapeHtml(error.message)}</div>`;
    }
}

function buildBlendingHistoryDetailHtml(item) {
    const ratioItems = Array.isArray(item.ratio_items) ? item.ratio_items : [];
    const resultPayload = item.result_payload || {};
    const resultData = resultPayload.result || {};
    const resultRows = [
        ['记录时间', item.date || '--'],
        ['优化目标', resultData.optimization_target || '--'],
        ['可行性', item.constraints_satisfied ? '可行' : '不可行'],
        ['总价', formatCurrency(item.total_price)],
        ['热值', formatMetric(item.total_heat, 'kcal/kg', 0)],
        ['灰分', formatMetric(item.total_ash, '%', 2)],
        ['挥发分', formatMetric(item.total_volatile, '%', 2)],
        ['固定碳', formatMetric(item.total_fixed_carbon, '%', 2)],
        ['硫分', formatMetric(item.total_sulfur, '%', 2)],
        ['性价比指标', formatPlainNumber(item.performance_price_ratio, 4)],
        ['迭代次数', formatInteger(item.iterations)],
        ['计算耗时', formatMetric(item.time_taken, 's', 2)],
        ['适应度', formatPlainNumber(item.fitness_value, 4)],
    ];

    return `
        <div class="history-detail-grid">
            <div class="history-detail-card">
                <h6>主要结果</h6>
                <div class="history-stat-list">
                    ${resultRows.map(([label, value]) => `
                        <div class="history-stat-item">
                            <span>${escapeHtml(label)}</span>
                            <strong>${escapeHtml(value)}</strong>
                        </div>
                    `).join('')}
                </div>
            </div>
            <div class="history-detail-card">
                <h6>煤种与配比</h6>
                <div class="table-responsive">
                    <table class="table table-sm table-striped align-middle mb-0">
                        <thead>
                            <tr>
                                <th>煤种</th>
                                <th>配比</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${ratioItems.length > 0 ? ratioItems.map(ratioItem => `
                                <tr>
                                    <td>${escapeHtml(ratioItem.coal_name)}</td>
                                    <td>${formatPercentage(ratioItem.ratio_percent)}</td>
                                </tr>
                            `).join('') : '<tr><td colspan="2" class="text-center text-muted">暂无配比数据</td></tr>'}
                        </tbody>
                    </table>
                </div>
            </div>
            <div class="history-detail-card">
                <h6>请求快照</h6>
                <pre class="history-json">${escapeHtml(prettyJson(item.request_payload || {}))}</pre>
            </div>
            <div class="history-detail-card">
                <h6>结果快照</h6>
                <pre class="history-json">${escapeHtml(prettyJson(item.result_payload || {}))}</pre>
            </div>
        </div>
    `;
}

function updateBlendingHistoryStats(items) {
    const feasibleItems = items.filter(item => item.constraints_satisfied);
    const costItems = items.filter(item => Number.isFinite(Number(item.total_price)));
    const avgCost = costItems.length
        ? costItems.reduce((sum, item) => sum + Number(item.total_price), 0) / costItems.length
        : null;

    updateTextContent('blendingHistoryCount', String(items.length));
    updateTextContent('blendingFeasibleCount', String(feasibleItems.length));
    updateTextContent('blendingAvgCost', avgCost === null ? '--' : formatCurrency(avgCost));
    updateTextContent('blendingLastRun', items[0]?.date || '暂无记录');
}

function setBlendingHistoryLoading(isLoading) {
    const tbody = document.getElementById('blendingHistoryTableBody');
    const refreshBtn = document.getElementById('refreshBlendingHistoryBtn');
    if (tbody && isLoading) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted">正在加载历史记录...</td></tr>';
    }
    if (refreshBtn) {
        refreshBtn.disabled = isLoading;
        refreshBtn.innerHTML = isLoading
            ? '<span class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span>加载中'
            : '<i class="bi bi-arrow-repeat me-1"></i>刷新';
    }
}

function setBlendingHistoryStatus(tone, text, hint) {
    const statusBar = document.getElementById('blendingHistoryStatusBar');
    if (statusBar) {
        statusBar.dataset.tone = tone || 'info';
    }
    updateTextContent('blendingHistoryStatusText', text);
    updateTextContent('blendingHistoryStatusHint', hint || '');
}

function showBlendingHistoryModal() {
    const modalElement = document.getElementById('blendingHistoryDetailModal');
    if (!modalElement) {
        return;
    }

    if (!window.bootstrap?.Modal) {
        modalElement.classList.add('show');
        modalElement.style.display = 'block';
        modalElement.removeAttribute('aria-hidden');
        return;
    }

    if (!blendingHistoryModal) {
        blendingHistoryModal = new bootstrap.Modal(modalElement);
    }

    blendingHistoryModal.show();
}

function showHistoryToast(message, type = 'info') {
    if (!window.bootstrap?.Toast) {
        return;
    }

    const container = document.getElementById('blendingHistoryToastContainer');
    if (!container) {
        return;
    }

    const toast = document.createElement('div');
    toast.className = 'toast coal-toast';
    toast.role = 'alert';
    toast.innerHTML = `
        <div class="toast-header">
            <i class="bi bi-info-circle text-${type} me-2"></i>
            <strong class="me-auto">历史记录</strong>
            <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
        <div class="toast-body">${escapeHtml(message)}</div>
    `;
    container.appendChild(toast);
    toast.addEventListener('hidden.bs.toast', () => toast.remove());
    bootstrap.Toast.getOrCreateInstance(toast, { delay: type === 'danger' ? 5200 : 3200 }).show();
}

function updateTextContent(id, value) {
    const element = document.getElementById(id);
    if (element) {
        element.textContent = value;
    }
}

function normalizeText(value) {
    return String(value ?? '').trim().toLowerCase();
}

function prettyJson(value) {
    return JSON.stringify(value, null, 2);
}

function formatPlainNumber(value, digits) {
    return Number.isFinite(Number(value)) ? Number(value).toFixed(digits) : '--';
}

function formatInteger(value) {
    return Number.isFinite(Number(value)) ? String(Math.round(Number(value))) : '--';
}

function formatCurrency(value) {
    return Number.isFinite(Number(value)) ? `¥${Number(value).toFixed(2)}` : '--';
}

function formatMetric(value, unit, digits) {
    return Number.isFinite(Number(value)) ? `${Number(value).toFixed(digits)} ${unit}` : '--';
}

function formatPercentage(value) {
    return Number.isFinite(Number(value)) ? `${Number(value).toFixed(2)}%` : '--';
}

function escapeHtml(value) {
    return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}
