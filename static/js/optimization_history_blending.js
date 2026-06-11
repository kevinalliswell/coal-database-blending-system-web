let blendingHistoryModal = null;

document.addEventListener('DOMContentLoaded', function () {
    document.getElementById('refreshBlendingHistoryBtn')?.addEventListener('click', loadBlendingHistory);
    loadBlendingHistory();
});

async function loadBlendingHistory() {
    const tbody = document.getElementById('blendingHistoryTableBody');
    if (!tbody) {
        return;
    }

    tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted">正在加载历史记录...</td></tr>';

    try {
        const response = await fetch('/api/optimization/history');
        const result = await response.json();

        if (!response.ok || result.status !== 'success') {
            throw new Error(result.message || '加载历史记录失败');
        }

        renderBlendingHistoryRows(result.data || []);
    } catch (error) {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center text-danger">${escapeHtml(error.message)}</td></tr>`;
    }
}

function renderBlendingHistoryRows(items) {
    const tbody = document.getElementById('blendingHistoryTableBody');
    if (!tbody) {
        return;
    }

    if (!Array.isArray(items) || items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8"><div class="history-empty-state">暂无混煤优化历史记录</div></td></tr>';
        return;
    }

    tbody.innerHTML = items.map(item => {
        const ratioItems = Array.isArray(item.ratio_items) ? item.ratio_items : [];
        const ratioSummary = ratioItems.slice(0, 4).map(ratioItem => (
            `<span class="history-chip">${escapeHtml(ratioItem.coal_name)} ${formatPercentage(ratioItem.ratio_percent)}</span>`
        )).join('');

        return `
            <tr>
                <td>${escapeHtml(item.date || '--')}</td>
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
                    <button class="btn btn-sm btn-outline-primary" onclick="showBlendingHistoryDetail(${item.id})">
                        <i class="bi bi-eye me-1"></i>查看详情
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

async function showBlendingHistoryDetail(historyId) {
    const content = document.getElementById('blendingHistoryDetailContent');
    if (!content) {
        return;
    }

    content.innerHTML = '<div class="text-center text-muted py-4">正在加载详情...</div>';
    getBlendingHistoryModal().show();

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
                <div class="table-responsive">
                    <table class="table table-sm table-striped align-middle mb-0">
                        <tbody>
                            ${resultRows.map(([label, value]) => `
                                <tr>
                                    <th class="text-muted fw-semibold">${escapeHtml(label)}</th>
                                    <td>${escapeHtml(value)}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
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
        </div>
    `;
}

function getBlendingHistoryModal() {
    if (!blendingHistoryModal) {
        blendingHistoryModal = new bootstrap.Modal(document.getElementById('blendingHistoryDetailModal'));
    }

    return blendingHistoryModal;
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
    return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}
