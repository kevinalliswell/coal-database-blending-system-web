let replacementRatioHistoryModal = null;

document.addEventListener('DOMContentLoaded', function () {
    document.getElementById('refreshReplacementRatioHistoryBtn')?.addEventListener('click', loadReplacementRatioHistory);
    loadReplacementRatioHistory();
});

async function loadReplacementRatioHistory() {
    const tbody = document.getElementById('replacementRatioHistoryTableBody');
    if (!tbody) {
        return;
    }

    tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">正在加载历史记录...</td></tr>';

    try {
        const response = await fetch('/api/replacement_ratio/history');
        const result = await response.json();

        if (!response.ok || result.status !== 'success') {
            throw new Error(result.message || '加载历史记录失败');
        }

        renderReplacementRatioHistoryRows(result.data || []);
    } catch (error) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center text-danger">${escapeHtml(error.message)}</td></tr>`;
    }
}

function renderReplacementRatioHistoryRows(items) {
    const tbody = document.getElementById('replacementRatioHistoryTableBody');
    if (!tbody) {
        return;
    }

    if (!Array.isArray(items) || items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6"><div class="history-empty-state">暂无置换比历史记录</div></td></tr>';
        return;
    }

    tbody.innerHTML = items.map(item => `
        <tr>
            <td>${escapeHtml(item.date || '--')}</td>
            <td>${renderTypeText(item.calculation_type)}</td>
            <td>
                <span class="history-badge" data-tone="info">${renderModeText(item.calculation_mode)}</span>
            </td>
            <td>${formatRatio(item.ratio_value)}</td>
            <td>${escapeHtml(item.parameter_summary || '--')}</td>
            <td>
                <button class="btn btn-sm btn-outline-primary" onclick="showReplacementRatioHistoryDetail(${item.id})">
                    <i class="bi bi-eye me-1"></i>查看详情
                </button>
            </td>
        </tr>
    `).join('');
}

async function showReplacementRatioHistoryDetail(historyId) {
    const content = document.getElementById('replacementRatioHistoryDetailContent');
    if (!content) {
        return;
    }

    content.innerHTML = '<div class="text-center text-muted py-4">正在加载详情...</div>';
    getReplacementRatioHistoryModal().show();

    try {
        const response = await fetch(`/api/replacement_ratio/history/${historyId}`);
        const result = await response.json();

        if (!response.ok || result.status !== 'success') {
            throw new Error(result.message || '加载详情失败');
        }

        content.innerHTML = buildReplacementRatioHistoryDetailHtml(result.data || {});
    } catch (error) {
        content.innerHTML = `<div class="alert alert-danger mb-0">${escapeHtml(error.message)}</div>`;
    }
}

function buildReplacementRatioHistoryDetailHtml(item) {
    return `
        <div class="history-detail-grid">
            <div class="history-detail-card">
                <h6>摘要信息</h6>
                <div class="history-stat-list">
                    <div class="history-stat-item"><span>记录时间</span><strong>${escapeHtml(item.date || '--')}</strong></div>
                    <div class="history-stat-item"><span>计算类型</span><strong>${renderTypeText(item.calculation_type)}</strong></div>
                    <div class="history-stat-item"><span>模式</span><strong>${renderModeText(item.calculation_mode)}</strong></div>
                    <div class="history-stat-item"><span>置换比结果</span><strong>${formatRatio(item.ratio_value)}</strong></div>
                </div>
            </div>
            <div class="history-detail-card">
                <h6>关键参数摘要</h6>
                <p class="mb-0">${escapeHtml(item.parameter_summary || '--')}</p>
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

function getReplacementRatioHistoryModal() {
    if (!replacementRatioHistoryModal) {
        replacementRatioHistoryModal = new bootstrap.Modal(document.getElementById('replacementRatioHistoryDetailModal'));
    }

    return replacementRatioHistoryModal;
}

function prettyJson(value) {
    return JSON.stringify(value, null, 2);
}

function renderTypeText(calculationType) {
    return calculationType === 'theory' ? '理论置换比' : '实际置换比';
}

function renderModeText(calculationMode) {
    if (calculationMode === 'advanced') {
        return '高级实际';
    }
    if (calculationMode === 'basic') {
        return '基础实际';
    }
    return '理论';
}

function formatRatio(value) {
    return Number.isFinite(Number(value)) ? Number(value).toFixed(6) : '--';
}

function escapeHtml(value) {
    return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}
