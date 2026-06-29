let replacementRatioHistoryModal = null;
let replacementRatioHistoryItems = [];

document.addEventListener('DOMContentLoaded', function () {
    document.getElementById('refreshReplacementRatioHistoryBtn')?.addEventListener('click', loadReplacementRatioHistory);
    document.getElementById('replacementRatioHistorySearch')?.addEventListener('input', renderFilteredReplacementRatioHistory);
    document.getElementById('replacementRatioModeFilter')?.addEventListener('change', renderFilteredReplacementRatioHistory);
    document.getElementById('clearReplacementRatioHistoryFiltersBtn')?.addEventListener('click', clearReplacementRatioHistoryFilters);
    document.getElementById('replacementRatioHistoryTableBody')?.addEventListener('click', handleReplacementRatioHistoryTableClick);

    loadReplacementRatioHistory();
});

async function loadReplacementRatioHistory() {
    const tbody = document.getElementById('replacementRatioHistoryTableBody');
    if (!tbody) {
        return;
    }

    setReplacementRatioHistoryStatus('info', '正在加载置换比历史...', '可按计算类型、模式和参数摘要筛选。');
    setReplacementRatioHistoryLoading(true);

    try {
        const response = await fetch('/api/replacement_ratio/history');
        const result = await response.json();

        if (!response.ok || result.status !== 'success') {
            throw new Error(result.message || '加载历史记录失败');
        }

        replacementRatioHistoryItems = Array.isArray(result.data) ? result.data : [];
        updateReplacementRatioHistoryStats(replacementRatioHistoryItems);
        renderFilteredReplacementRatioHistory();
        setReplacementRatioHistoryStatus('success', '置换比历史已加载。', `共 ${replacementRatioHistoryItems.length} 条 SQLite 历史记录。`);
    } catch (error) {
        replacementRatioHistoryItems = [];
        updateReplacementRatioHistoryStats([]);
        tbody.innerHTML = `<tr><td colspan="6" class="text-center text-danger">${escapeHtml(error.message)}</td></tr>`;
        updateTextContent('replacementRatioHistoryTableSummary', '加载失败');
        setReplacementRatioHistoryStatus('danger', '置换比历史加载失败。', error.message);
        showReplacementRatioHistoryToast(error.message, 'danger');
    } finally {
        setReplacementRatioHistoryLoading(false);
    }
}

function renderFilteredReplacementRatioHistory() {
    renderReplacementRatioHistoryRows(getFilteredReplacementRatioHistoryItems());
}

function getFilteredReplacementRatioHistoryItems() {
    const keyword = normalizeText(document.getElementById('replacementRatioHistorySearch')?.value || '');
    const mode = document.getElementById('replacementRatioModeFilter')?.value || 'all';

    return replacementRatioHistoryItems.filter(item => {
        const itemMode = item.calculation_mode || item.calculation_type;
        const matchesMode =
            mode === 'all' ||
            item.calculation_type === mode ||
            itemMode === mode;

        if (!matchesMode) {
            return false;
        }

        if (!keyword) {
            return true;
        }

        return normalizeText([
            item.date,
            renderTypeText(item.calculation_type),
            renderModeText(item.calculation_mode),
            item.ratio_value,
            item.parameter_summary
        ].join(' ')).includes(keyword);
    });
}

function renderReplacementRatioHistoryRows(items) {
    const tbody = document.getElementById('replacementRatioHistoryTableBody');
    if (!tbody) {
        return;
    }

    if (!Array.isArray(items) || items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6"><div class="history-empty-state">当前筛选条件下暂无置换比历史记录</div></td></tr>';
        updateTextContent('replacementRatioHistoryTableSummary', `显示 0 / ${replacementRatioHistoryItems.length} 条记录`);
        return;
    }

    tbody.innerHTML = items.map(item => `
        <tr>
            <td class="history-time-cell">${escapeHtml(item.date || '--')}</td>
            <td>${renderTypeText(item.calculation_type)}</td>
            <td>
                <span class="history-badge" data-tone="info">${renderModeText(item.calculation_mode)}</span>
            </td>
            <td class="history-ratio-value">${formatRatio(item.ratio_value)}</td>
            <td>${escapeHtml(item.parameter_summary || '--')}</td>
            <td>
                <button class="btn btn-sm btn-outline-primary" type="button" data-history-action="detail" data-history-id="${escapeHtml(item.id)}">
                    <i class="bi bi-eye me-1"></i>详情
                </button>
            </td>
        </tr>
    `).join('');

    updateTextContent('replacementRatioHistoryTableSummary', `显示 ${items.length} / ${replacementRatioHistoryItems.length} 条记录`);
}

function clearReplacementRatioHistoryFilters() {
    const search = document.getElementById('replacementRatioHistorySearch');
    const filter = document.getElementById('replacementRatioModeFilter');
    if (search) {
        search.value = '';
    }
    if (filter) {
        filter.value = 'all';
    }
    renderFilteredReplacementRatioHistory();
}

function handleReplacementRatioHistoryTableClick(event) {
    const button = event.target.closest('[data-history-action="detail"]');
    if (!button) {
        return;
    }

    showReplacementRatioHistoryDetail(button.dataset.historyId);
}

async function showReplacementRatioHistoryDetail(historyId) {
    const content = document.getElementById('replacementRatioHistoryDetailContent');
    if (!content || !historyId) {
        return;
    }

    content.innerHTML = '<div class="text-center text-muted py-4">正在加载详情...</div>';
    showReplacementRatioHistoryModal();

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

function updateReplacementRatioHistoryStats(items) {
    const theoryItems = items.filter(item => item.calculation_type === 'theory');
    const actualItems = items.filter(item => item.calculation_type === 'actual');
    const latest = items[0];

    updateTextContent('replacementHistoryCount', String(items.length));
    updateTextContent('replacementTheoryCount', String(theoryItems.length));
    updateTextContent('replacementActualCount', String(actualItems.length));
    updateTextContent(
        'replacementLastResult',
        latest ? `${formatRatio(latest.ratio_value)} / ${renderModeText(latest.calculation_mode)}` : '暂无记录'
    );
}

function setReplacementRatioHistoryLoading(isLoading) {
    const tbody = document.getElementById('replacementRatioHistoryTableBody');
    const refreshBtn = document.getElementById('refreshReplacementRatioHistoryBtn');
    if (tbody && isLoading) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">正在加载历史记录...</td></tr>';
    }
    if (refreshBtn) {
        refreshBtn.disabled = isLoading;
        refreshBtn.innerHTML = isLoading
            ? '<span class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span>加载中'
            : '<i class="bi bi-arrow-repeat me-1"></i>刷新';
    }
}

function setReplacementRatioHistoryStatus(tone, text, hint) {
    const statusBar = document.getElementById('replacementHistoryStatusBar');
    if (statusBar) {
        statusBar.dataset.tone = tone || 'info';
    }
    updateTextContent('replacementHistoryStatusText', text);
    updateTextContent('replacementHistoryStatusHint', hint || '');
}

function showReplacementRatioHistoryModal() {
    const modalElement = document.getElementById('replacementRatioHistoryDetailModal');
    if (!modalElement) {
        return;
    }

    if (!window.bootstrap?.Modal) {
        modalElement.classList.add('show');
        modalElement.style.display = 'block';
        modalElement.removeAttribute('aria-hidden');
        return;
    }

    if (!replacementRatioHistoryModal) {
        replacementRatioHistoryModal = new bootstrap.Modal(modalElement);
    }

    replacementRatioHistoryModal.show();
}

function showReplacementRatioHistoryToast(message, type = 'info') {
    if (!window.bootstrap?.Toast) {
        return;
    }

    const container = document.getElementById('replacementRatioHistoryToastContainer');
    if (!container) {
        return;
    }

    const toast = document.createElement('div');
    toast.className = 'toast coal-toast';
    toast.role = 'alert';
    toast.innerHTML = `
        <div class="toast-header">
            <i class="bi bi-info-circle text-${type} me-2"></i>
            <strong class="me-auto">置换比历史</strong>
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
    return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}
