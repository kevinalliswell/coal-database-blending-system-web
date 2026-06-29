// 首页真实运行态仪表盘

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('refreshDashboardBtn')?.addEventListener('click', refreshDashboard);
    refreshDashboard();
});

async function refreshDashboard() {
    const refreshButton = document.getElementById('refreshDashboardBtn');
    setButtonBusy(refreshButton, true);

    try {
        const [health, coals, blendingHistory, replacementHistory] = await Promise.all([
            fetchJson('/health'),
            fetchJson('/api/coals?page_size=0'),
            fetchJson('/api/optimization/history'),
            fetchJson('/api/replacement_ratio/history'),
        ]);

        const coalTotal = Number(coals?.pagination?.total ?? coals?.data?.length ?? health?.coal_count ?? 0);
        const blendingItems = Array.isArray(blendingHistory?.data) ? blendingHistory.data : [];
        const replacementItems = Array.isArray(replacementHistory?.data) ? replacementHistory.data : [];

        renderHealth(health, coalTotal);
        renderStats(coalTotal, blendingItems, replacementItems);
        renderRecentActivities(blendingItems, replacementItems);
        updateTextContent('lastRefreshChip', `已同步 ${formatTime(new Date())}`);
        updateTextContent('runtimeSyncAt', formatTime(new Date()));
    } catch (error) {
        setHealthTone('danger', '连接异常');
        renderRecentActivities([], [], error.message);
        notify(error.message, 'danger');
    } finally {
        setButtonBusy(refreshButton, false);
    }
}

async function fetchJson(url) {
    const response = await fetch(url);
    const payload = await response.json();
    if (!response.ok || payload.status === 'error') {
        throw new Error(payload.message || `${url} 请求失败`);
    }
    return payload;
}

function renderHealth(health, coalTotal) {
    setHealthTone('success', '运行正常');
    const storageMode = health?.storage_mode || 'sqlite';
    updateTextContent('storageModeChip', storageMode.toUpperCase());
    updateTextContent('runtimeApp', health?.app || '--');
    updateTextContent('runtimeStorage', storageMode);
    updateTextContent('runtimeCoalCount', coalTotal);
}

function renderStats(coalTotal, blendingItems, replacementItems) {
    updateTextContent('totalCoals', coalTotal);
    updateTextContent('totalOptimizations', blendingItems.length);
    updateTextContent('totalCalculations', replacementItems.length);

    const timeValues = blendingItems
        .map(item => Number(item.time_taken))
        .filter(value => Number.isFinite(value) && value >= 0);
    const avgTime = timeValues.length > 0
        ? timeValues.reduce((sum, value) => sum + value, 0) / timeValues.length
        : null;
    updateTextContent('avgTime', avgTime === null ? '--' : `${avgTime.toFixed(2)}s`);
}

function renderRecentActivities(blendingItems, replacementItems, errorMessage = '') {
    const container = document.getElementById('recentActivities');
    if (!container) {
        return;
    }

    if (errorMessage) {
        container.innerHTML = `<div class="alert alert-danger mb-0">${escapeHtml(errorMessage)}</div>`;
        return;
    }

    const activities = [
        ...blendingItems.slice(0, 5).map(item => ({
            kind: '混煤优化',
            title: item.constraints_satisfied ? '生成可行混煤方案' : '生成需复核混煤方案',
            description: buildBlendingDescription(item),
            date: item.date || '',
            href: `/optimization_history/blending`,
            tone: item.constraints_satisfied ? 'success' : 'warning',
            icon: 'bi-cpu-fill',
        })),
        ...replacementItems.slice(0, 5).map(item => ({
            kind: '置换比计算',
            title: renderReplacementMode(item),
            description: `${item.parameter_summary || '参数摘要暂缺'}，结果 ${formatRatio(item.ratio_value)}`,
            date: item.date || '',
            href: `/optimization_history/replacement_ratio`,
            tone: 'info',
            icon: 'bi-calculator-fill',
        })),
    ].sort((a, b) => new Date(b.date || 0) - new Date(a.date || 0)).slice(0, 6);

    if (activities.length === 0) {
        container.innerHTML = `
            <div class="history-empty-state">
                暂无历史活动。完成一次智能混煤或置换比计算后，这里会自动更新。
            </div>
        `;
        return;
    }

    container.innerHTML = activities.map(activity => `
        <a class="home-activity-item" href="${activity.href}">
            <span class="home-activity-item__icon" data-tone="${activity.tone}">
                <i class="bi ${activity.icon}"></i>
            </span>
            <span class="home-activity-item__content">
                <span class="home-activity-item__meta">${escapeHtml(activity.kind)} · ${escapeHtml(activity.date || '--')}</span>
                <strong>${escapeHtml(activity.title)}</strong>
                <span>${escapeHtml(activity.description)}</span>
            </span>
            <i class="bi bi-arrow-right-short home-activity-item__arrow"></i>
        </a>
    `).join('');
}

function buildBlendingDescription(item) {
    const ratioItems = Array.isArray(item.ratio_items) ? item.ratio_items : [];
    const coalSummary = ratioItems.slice(0, 2)
        .map(ratio => `${ratio.coal_name} ${formatPercent(ratio.ratio_percent)}`)
        .join('，');
    const price = Number.isFinite(Number(item.total_price)) ? `总价 ¥${Number(item.total_price).toFixed(2)}` : '总价暂缺';
    return coalSummary ? `${coalSummary}，${price}` : price;
}

function renderReplacementMode(item) {
    if (item.calculation_type === 'theory') {
        return '完成理论置换比计算';
    }
    if (item.calculation_mode === 'advanced') {
        return '完成高级实际置换比计算';
    }
    return '完成基础实际置换比计算';
}

function setHealthTone(tone, text) {
    const pill = document.getElementById('healthStatusPill');
    if (!pill) {
        return;
    }
    pill.dataset.tone = tone;
    const icon = tone === 'success' ? 'bi-check-circle' : (tone === 'danger' ? 'bi-exclamation-triangle' : 'bi-activity');
    pill.innerHTML = `<i class="bi ${icon} me-1"></i>${escapeHtml(text)}`;
}

function setButtonBusy(button, isBusy) {
    if (!button) {
        return;
    }
    button.disabled = isBusy;
    button.innerHTML = isBusy
        ? '<i class="bi bi-hourglass-split me-1"></i>同步中'
        : '<i class="bi bi-arrow-repeat me-1"></i>刷新';
}

function notify(message, tone = 'info') {
    const container = document.getElementById('homeToastContainer');
    if (!container) {
        return;
    }
    const toast = document.createElement('div');
    toast.className = 'toast coal-toast';
    toast.role = 'alert';
    toast.innerHTML = `
        <div class="toast-header">
            <i class="bi bi-info-circle text-${tone} me-2"></i>
            <strong class="me-auto">系统提示</strong>
            <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
        <div class="toast-body">${escapeHtml(message)}</div>
    `;
    container.appendChild(toast);
    toast.addEventListener('hidden.bs.toast', () => toast.remove());
    bootstrap.Toast.getOrCreateInstance(toast, { delay: 3600 }).show();
}

function updateTextContent(id, text) {
    const element = document.getElementById(id);
    if (element) {
        element.textContent = text;
    }
}

function formatRatio(value) {
    return Number.isFinite(Number(value)) ? Number(value).toFixed(6) : '--';
}

function formatPercent(value) {
    return Number.isFinite(Number(value)) ? `${Number(value).toFixed(2)}%` : '--';
}

function formatTime(date) {
    return date.toLocaleTimeString('zh-CN', { hour12: false });
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
