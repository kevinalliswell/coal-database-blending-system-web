// 煤种数据管理页面交互

let currentPage = 1;
let pageSize = 10;
let allCoals = [];
let filteredCoals = [];
let selectedCoalIds = new Set();
let currentEditCoalId = null;

document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    loadCoals();
});

function setupEventListeners() {
    document.addEventListener('click', handlePageActionClick);

    document.getElementById('searchInput')?.addEventListener('input', debounce(searchCoals, 180));
    document.getElementById('searchInput')?.addEventListener('keydown', event => {
        if (event.key === 'Enter') {
            event.preventDefault();
            searchCoals();
        }
    });

    document.getElementById('typeFilter')?.addEventListener('change', searchCoals);
    document.getElementById('pageSizeSelect')?.addEventListener('change', event => {
        pageSize = parseInt(event.target.value, 10) || 10;
        currentPage = 1;
        displayCoals();
    });

    document.getElementById('selectAll')?.addEventListener('change', event => {
        const checked = event.target.checked;
        document.querySelectorAll('#coalTableBody input[type="checkbox"]').forEach(checkbox => {
            checkbox.checked = checked;
            updateSelectionForId(Number(checkbox.value), checked);
        });
        displayCoals();
    });

    document.getElementById('coalTableBody')?.addEventListener('change', handleCoalTableChange);
    document.getElementById('coalTableBody')?.addEventListener('click', handleCoalTableClick);
    document.getElementById('editFromDetailBtn')?.addEventListener('click', handleEditFromDetailClick);

    document.getElementById('addCoalModal')?.addEventListener('hidden.bs.modal', () => {
        document.getElementById('addCoalForm')?.reset();
    });

    document.getElementById('editCoalModal')?.addEventListener('hidden.bs.modal', () => {
        currentEditCoalId = null;
        document.getElementById('editCoalForm')?.reset();
    });
}

function handlePageActionClick(event) {
    const button = event.target.closest('[data-action]');
    if (!button) {
        return;
    }

    const actions = {
        search: searchCoals,
        'reset-search': resetSearch,
        refresh: loadCoals,
        'export-selected': exportSelected,
        'export-all': exportAll,
        'batch-delete': batchDelete,
        'save-coal': saveCoal,
        'update-coal': updateCoal,
        'download-template': downloadTemplate,
        'upload-file': uploadFile,
    };

    const action = actions[button.dataset.action];
    if (action) {
        action();
    }
}

function handleCoalTableChange(event) {
    const checkbox = event.target.closest('[data-coal-select]');
    if (!checkbox) {
        return;
    }

    toggleCoalSelection(Number(checkbox.value), checkbox.checked);
}

function handleCoalTableClick(event) {
    const button = event.target.closest('[data-row-action]');
    if (!button) {
        return;
    }

    const coalId = Number(button.dataset.coalId);
    if (!Number.isFinite(coalId)) {
        return;
    }

    if (button.dataset.rowAction === 'detail') {
        viewCoalDetail(coalId);
    } else if (button.dataset.rowAction === 'edit') {
        editCoal(coalId);
    } else if (button.dataset.rowAction === 'delete') {
        deleteCoal(coalId);
    }
}

function handleEditFromDetailClick(event) {
    const coalId = Number(event.currentTarget.dataset.coalId);
    if (Number.isFinite(coalId)) {
        editCoalFromDetail(coalId);
    }
}

async function loadCoals() {
    showLoading('正在加载煤种数据...');
    try {
        const response = await fetch('/api/coals?page_size=0');
        const result = await response.json();

        if (!response.ok || result.status !== 'success') {
            throw new Error(result.message || '煤种数据加载失败');
        }

        allCoals = Array.isArray(result.data) ? result.data : [];
        syncSelectionWithData();
        renderTypeOptions();
        applyFilters();
        updateTextContent('lastLoadedAt', new Date().toLocaleTimeString('zh-CN', { hour12: false }));
    } catch (error) {
        notify(error.message, 'danger');
    } finally {
        hideLoading();
    }
}

function applyFilters() {
    const searchTerm = (document.getElementById('searchInput')?.value || '').trim().toLowerCase();
    const typeFilter = document.getElementById('typeFilter')?.value || '';

    filteredCoals = allCoals.filter(coal => {
        const searchFields = [
            coal.name,
            coal.type,
            coal.supplier,
            String(coal.id),
        ].map(value => String(value || '').toLowerCase());

        const matchesSearch = !searchTerm || searchFields.some(value => value.includes(searchTerm));
        const matchesType = !typeFilter || coal.type === typeFilter;
        return matchesSearch && matchesType;
    });

    const totalPages = Math.max(1, Math.ceil(filteredCoals.length / pageSize));
    if (currentPage > totalPages) {
        currentPage = totalPages;
    }

    displayCoals();
}

function displayCoals() {
    const tbody = document.getElementById('coalTableBody');
    if (!tbody) {
        return;
    }

    const totalPages = Math.max(1, Math.ceil(filteredCoals.length / pageSize));
    currentPage = Math.min(Math.max(currentPage, 1), totalPages);
    const startIndex = (currentPage - 1) * pageSize;
    const endIndex = Math.min(startIndex + pageSize, filteredCoals.length);
    const pageCoals = filteredCoals.slice(startIndex, endIndex);

    tbody.innerHTML = '';
    pageCoals.forEach(coal => tbody.appendChild(createCoalRow(coal)));

    const emptyState = document.getElementById('coalEmptyState');
    if (emptyState) {
        emptyState.hidden = pageCoals.length > 0;
    }

    updateStatistics(startIndex, endIndex);
    updatePagination(totalPages);
    updateSelectedCount();
}

function createCoalRow(coal) {
    const row = document.createElement('tr');
    const coalId = Number(coal.id);
    const selected = selectedCoalIds.has(coalId);
    row.className = selected ? 'is-selected' : '';
    row.innerHTML = `
        <td class="select-col">
            <input class="form-check-input" type="checkbox" value="${coalId}" ${selected ? 'checked' : ''}
                   data-coal-select title="选择煤种">
        </td>
        <td class="text-muted">${coalId}</td>
        <td class="coal-name-cell">
            <div class="coal-name-main">
                <span class="coal-name-text">${escapeHtml(coal.name)}</span>
                ${selected ? '<span class="coal-selected-flag"><i class="bi bi-check-circle-fill"></i>已选</span>' : ''}
            </div>
            <div class="coal-name-submeta">
                <span>${escapeHtml(coal.supplier || '未填写产地')}</span>
            </div>
        </td>
        <td><span class="badge bg-secondary">${escapeHtml(coal.type)}</span></td>
        <td class="metric-cell"><strong>${formatCurrency(coal.price)}</strong><div class="small text-muted">元/吨</div></td>
        <td class="metric-cell"><strong>${formatNumber(coal.calorific_value, 0)}</strong><div class="small text-muted">kcal/kg</div></td>
        <td class="metric-cell">${formatPercent(coal.ash_content)}</td>
        <td class="metric-cell">${formatPercent(coal.volatile_matter)}</td>
        <td class="metric-cell">${formatPercent(coal.fixed_carbon)}</td>
        <td class="metric-cell">${formatPercent(coal.total_sulfur)}</td>
        <td>
            <div class="coal-row-actions">
                <button class="btn btn-sm detail-button" type="button" data-row-action="detail" data-coal-id="${coalId}" title="查看详情">
                    <i class="bi bi-eye"></i>
                </button>
                <button class="btn btn-sm btn-outline-warning" type="button" data-row-action="edit" data-coal-id="${coalId}" title="编辑">
                    <i class="bi bi-pencil"></i>
                </button>
                <button class="btn btn-sm btn-outline-danger" type="button" data-row-action="delete" data-coal-id="${coalId}" title="删除">
                    <i class="bi bi-trash"></i>
                </button>
            </div>
        </td>
    `;
    return row;
}

function updatePagination(totalPages) {
    const pagination = document.getElementById('pagination');
    if (!pagination) {
        return;
    }

    pagination.innerHTML = '';
    if (totalPages <= 1) {
        return;
    }

    pagination.appendChild(createPageItem('上一页', currentPage - 1, currentPage === 1));

    const startPage = Math.max(1, currentPage - 2);
    const endPage = Math.min(totalPages, currentPage + 2);

    if (startPage > 1) {
        pagination.appendChild(createPageItem('1', 1));
        if (startPage > 2) {
            pagination.appendChild(createEllipsisItem());
        }
    }

    for (let page = startPage; page <= endPage; page += 1) {
        pagination.appendChild(createPageItem(String(page), page, false, page === currentPage));
    }

    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            pagination.appendChild(createEllipsisItem());
        }
        pagination.appendChild(createPageItem(String(totalPages), totalPages));
    }

    pagination.appendChild(createPageItem('下一页', currentPage + 1, currentPage === totalPages));
}

function createPageItem(label, page, disabled = false, active = false) {
    const item = document.createElement('li');
    item.className = `page-item ${disabled ? 'disabled' : ''} ${active ? 'active' : ''}`;
    const button = document.createElement('button');
    button.className = 'page-link';
    button.type = 'button';
    button.textContent = label;
    button.disabled = disabled;
    button.addEventListener('click', () => changePage(page));
    item.appendChild(button);
    return item;
}

function createEllipsisItem() {
    const item = document.createElement('li');
    item.className = 'page-item disabled';
    item.innerHTML = '<span class="page-link">...</span>';
    return item;
}

function updateStatistics(startIndex, endIndex) {
    const visibleStart = filteredCoals.length > 0 ? startIndex + 1 : 0;
    updateTextContent('startIndex', visibleStart);
    updateTextContent('endIndex', endIndex);
    updateTextContent('totalItems', filteredCoals.length);
    updateTextContent('totalCount', `总计: ${filteredCoals.length} 条`);
    updateTextContent('statTotalCoals', allCoals.length);
    updateTextContent('statFilteredCoals', filteredCoals.length);
    updateTextContent('filterSummary', buildFilterSummary());
}

function updateSelectedCount() {
    const visibleCheckboxes = Array.from(document.querySelectorAll('#coalTableBody input[type="checkbox"]'));
    const visibleCheckedCount = visibleCheckboxes.filter(checkbox => checkbox.checked).length;
    const selectAll = document.getElementById('selectAll');

    if (selectAll) {
        selectAll.checked = visibleCheckboxes.length > 0 && visibleCheckedCount === visibleCheckboxes.length;
        selectAll.indeterminate = visibleCheckedCount > 0 && visibleCheckedCount < visibleCheckboxes.length;
    }

    updateTextContent('selectedCountText', selectedCoalIds.size);
}

function buildFilterSummary() {
    const searchTerm = (document.getElementById('searchInput')?.value || '').trim();
    const typeFilter = document.getElementById('typeFilter')?.value || '';
    const parts = [];
    if (searchTerm) {
        parts.push(`关键词：${searchTerm}`);
    }
    if (typeFilter) {
        parts.push(`类型：${typeFilter}`);
    }
    return parts.length > 0 ? parts.join(' / ') : '未设置筛选条件';
}

function searchCoals() {
    currentPage = 1;
    applyFilters();
}

function resetSearch() {
    const searchInput = document.getElementById('searchInput');
    const typeFilter = document.getElementById('typeFilter');
    if (searchInput) {
        searchInput.value = '';
    }
    if (typeFilter) {
        typeFilter.value = '';
    }
    currentPage = 1;
    applyFilters();
}

function changePage(page) {
    const totalPages = Math.max(1, Math.ceil(filteredCoals.length / pageSize));
    if (page < 1 || page > totalPages || page === currentPage) {
        return;
    }
    currentPage = page;
    displayCoals();
}

function toggleCoalSelection(coalId, checked) {
    updateSelectionForId(Number(coalId), checked);
    displayCoals();
}

function updateSelectionForId(coalId, checked) {
    if (checked) {
        selectedCoalIds.add(coalId);
    } else {
        selectedCoalIds.delete(coalId);
    }
}

function syncSelectionWithData() {
    const validIds = new Set(allCoals.map(coal => Number(coal.id)));
    selectedCoalIds = new Set(Array.from(selectedCoalIds).filter(id => validIds.has(id)));
}

function renderTypeOptions() {
    const typeFilter = document.getElementById('typeFilter');
    if (!typeFilter) {
        return;
    }

    const currentValue = typeFilter.value;
    const types = Array.from(new Set(allCoals.map(coal => coal.type).filter(Boolean))).sort((a, b) => a.localeCompare(b, 'zh-CN'));
    typeFilter.innerHTML = '<option value="">全部类型</option>';
    types.forEach(type => {
        const option = document.createElement('option');
        option.value = type;
        option.textContent = type;
        typeFilter.appendChild(option);
    });
    typeFilter.value = types.includes(currentValue) ? currentValue : '';
}

function viewCoalDetail(coalId) {
    const coal = findCoal(coalId);
    if (!coal) {
        notify('煤种不存在或已被删除', 'warning');
        return;
    }

    updateTextContent('detailCoalName', coal.name);
    updateTextContent('detailCoalType', coal.type);
    updateTextContent('detailSupplier', coal.supplier || '未填写');
    updateTextContent('detailPrice', `${formatCurrency(coal.price)} 元/吨`);
    updateTextContent('detailCalorificValue', `${formatNumber(coal.calorific_value, 0)} kcal/kg`);
    updateTextContent('detailAshContent', formatPercent(coal.ash_content));
    updateTextContent('detailVolatileMatter', formatPercent(coal.volatile_matter));
    updateTextContent('detailFixedCarbon', formatPercent(coal.fixed_carbon));
    updateTextContent('detailTotalSulfur', formatPercent(coal.total_sulfur));
    updateTextContent('detailMoisture', formatOptionalPercent(coal.moisture));
    updateTextContent('detailMad', formatOptionalPercent(coal.mad));
    updateTextContent('detailHgi', valueOrDash(coal.hgi));
    updateTextContent('detailBurnoutRate', formatOptionalPercent(coal.burnout_rate));
    updateTextContent('detailCarbonContent', formatOptionalPercent(coal.carbon_content));
    updateTextContent('detailHydrogenContent', formatOptionalPercent(coal.hydrogen_content));
    updateTextContent('detailNitrogenContent', formatOptionalPercent(coal.nitrogen_content));

    const editButton = document.getElementById('editFromDetailBtn');
    if (editButton) {
        editButton.dataset.coalId = String(coalId);
    }

    bootstrap.Modal.getOrCreateInstance(document.getElementById('coalDetailModal')).show();
}

function editCoal(coalId) {
    const coal = findCoal(coalId);
    if (!coal) {
        notify('煤种不存在或已被删除', 'warning');
        return;
    }

    currentEditCoalId = Number(coalId);
    const form = document.getElementById('editCoalForm');
    fillCoalForm(form, coal);
    bootstrap.Modal.getOrCreateInstance(document.getElementById('editCoalModal')).show();
}

function editCoalFromDetail(coalId) {
    bootstrap.Modal.getInstance(document.getElementById('coalDetailModal'))?.hide();
    setTimeout(() => editCoal(coalId), 220);
}

async function deleteCoal(coalId) {
    const coal = findCoal(coalId);
    if (!coal) {
        notify('煤种不存在或已被删除', 'warning');
        return;
    }

    const confirmed = await confirmAction({
        title: '删除煤种',
        message: `确认删除“${coal.name}”？`,
        confirmText: '删除',
        tone: 'danger',
    });
    if (!confirmed) {
        return;
    }

    showLoading('正在删除煤种...');
    try {
        const response = await fetch(`/api/coals/${coalId}`, { method: 'DELETE' });
        const result = await response.json();
        if (!response.ok || result.status !== 'success') {
            throw new Error(result.message || '删除失败');
        }
        selectedCoalIds.delete(Number(coalId));
        notify('煤种删除成功', 'success');
        await loadCoals();
    } catch (error) {
        notify(error.message, 'danger');
    } finally {
        hideLoading();
    }
}

async function saveCoal() {
    const form = document.getElementById('addCoalForm');
    const coalData = collectCoalFormData(form);
    if (!coalData) {
        return;
    }

    showLoading('正在保存煤种...');
    try {
        const response = await fetch('/api/coals', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(coalData),
        });
        const result = await response.json();
        if (!response.ok || result.status !== 'success') {
            throw new Error(result.message || '添加失败');
        }

        bootstrap.Modal.getInstance(document.getElementById('addCoalModal'))?.hide();
        notify('煤种添加成功', 'success');
        await loadCoals();
    } catch (error) {
        notify(error.message, 'danger');
    } finally {
        hideLoading();
    }
}

async function updateCoal() {
    const form = document.getElementById('editCoalForm');
    const coalData = collectCoalFormData(form);
    if (!coalData || currentEditCoalId === null) {
        return;
    }

    showLoading('正在保存修改...');
    try {
        const response = await fetch(`/api/coals/${currentEditCoalId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(coalData),
        });
        const result = await response.json();
        if (!response.ok || result.status !== 'success') {
            throw new Error(result.message || '更新失败');
        }

        bootstrap.Modal.getInstance(document.getElementById('editCoalModal'))?.hide();
        notify('煤种更新成功', 'success');
        await loadCoals();
    } catch (error) {
        notify(error.message, 'danger');
    } finally {
        hideLoading();
    }
}

async function batchDelete() {
    if (selectedCoalIds.size === 0) {
        notify('请选择要删除的煤种', 'warning');
        return;
    }

    const confirmed = await confirmAction({
        title: '批量删除',
        message: `确认删除选中的 ${selectedCoalIds.size} 条煤种记录？`,
        confirmText: '批量删除',
        tone: 'danger',
    });
    if (!confirmed) {
        return;
    }

    showLoading('正在批量删除...');
    try {
        const response = await fetch('/api/coals/batch_delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ coal_ids: Array.from(selectedCoalIds) }),
        });
        const result = await response.json();
        if (!response.ok || result.status !== 'success') {
            throw new Error(result.message || '批量删除失败');
        }
        selectedCoalIds.clear();
        notify(result.message || '批量删除成功', 'success');
        await loadCoals();
    } catch (error) {
        notify(error.message, 'danger');
    } finally {
        hideLoading();
    }
}

async function exportSelected() {
    if (selectedCoalIds.size === 0) {
        notify('请选择要导出的煤种', 'warning');
        return;
    }

    await downloadExport({
        coal_ids: Array.from(selectedCoalIds),
        export_all: false,
    }, `选中煤种导出_${getDateStamp()}.xlsx`);
}

async function exportAll() {
    if (allCoals.length === 0) {
        notify('没有可导出的数据', 'warning');
        return;
    }

    await downloadExport({ export_all: true }, `全部煤种导出_${getDateStamp()}.xlsx`);
}

async function downloadExport(payload, filename) {
    showLoading('正在生成导出文件...');
    try {
        const response = await fetch('/api/coals/export', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        await handleFileResponse(response, filename);
        notify('导出成功', 'success');
    } catch (error) {
        notify(error.message, 'danger');
    } finally {
        hideLoading();
    }
}

async function downloadTemplate() {
    showLoading('正在下载模板...');
    try {
        const response = await fetch('/api/coals/template');
        await handleFileResponse(response, '煤种数据导入模板.xlsx');
        notify('模板下载成功', 'success');
    } catch (error) {
        notify(error.message, 'danger');
    } finally {
        hideLoading();
    }
}

async function uploadFile() {
    const fileInput = document.getElementById('importFile');
    const file = fileInput?.files?.[0];
    const progress = document.getElementById('importProgress');
    const resultBox = document.getElementById('importResult');
    const uploadBtn = document.getElementById('uploadBtn');

    if (!file) {
        notify('请选择要导入的文件', 'warning');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    if (progress) {
        progress.hidden = false;
    }
    if (resultBox) {
        resultBox.hidden = true;
        resultBox.textContent = '';
    }
    if (uploadBtn) {
        uploadBtn.disabled = true;
    }

    try {
        const response = await fetch('/api/coals/upload', {
            method: 'POST',
            body: formData,
        });
        const result = await response.json();
        if (!response.ok || result.status !== 'success') {
            throw new Error(result.message || '导入失败');
        }

        if (resultBox) {
            resultBox.className = 'alert alert-success mt-3';
            resultBox.textContent = result.message || '导入完成';
            resultBox.hidden = false;
        }
        fileInput.value = '';
        notify('导入完成', 'success');
        await loadCoals();
    } catch (error) {
        if (resultBox) {
            resultBox.className = 'alert alert-danger mt-3';
            resultBox.textContent = error.message;
            resultBox.hidden = false;
        }
        notify(error.message, 'danger');
    } finally {
        if (progress) {
            progress.hidden = true;
        }
        if (uploadBtn) {
            uploadBtn.disabled = false;
        }
    }
}

function collectCoalFormData(form) {
    if (!form) {
        return null;
    }
    if (!form.checkValidity()) {
        form.reportValidity();
        return null;
    }

    const data = {};
    const formData = new FormData(form);
    for (const [key, value] of formData.entries()) {
        if (key === 'coal_id') {
            continue;
        }
        if (value !== '') {
            data[key] = value;
        }
    }
    return data;
}

function fillCoalForm(form, coal) {
    if (!form || !coal) {
        return;
    }

    const fields = [
        'name',
        'type',
        'supplier',
        'price',
        'calorific_value',
        'ash_content',
        'volatile_matter',
        'fixed_carbon',
        'total_sulfur',
        'moisture',
        'mad',
        'hgi',
        'burnout_rate',
        'carbon_content',
        'hydrogen_content',
        'nitrogen_content',
    ];

    fields.forEach(field => {
        const input = form.querySelector(`[name="${field}"]`);
        if (input) {
            input.value = coal[field] ?? '';
        }
    });

    const idInput = form.querySelector('[name="coal_id"]');
    if (idInput) {
        idInput.value = coal.id;
    }
}

async function handleFileResponse(response, filename) {
    if (!response.ok) {
        let message = '文件生成失败';
        try {
            const result = await response.json();
            message = result.message || message;
        } catch (_error) {
            message = response.statusText || message;
        }
        throw new Error(message);
    }

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.style.display = 'none';
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(link);
}

function confirmAction({ title, message, confirmText = '确认', tone = 'danger' }) {
    return new Promise(resolve => {
        const modalEl = document.getElementById('confirmActionModal');
        const titleEl = document.getElementById('confirmActionTitle');
        const bodyEl = document.getElementById('confirmActionBody');
        const confirmBtn = document.getElementById('confirmActionBtn');

        if (!modalEl || !confirmBtn) {
            notify(message || '确认组件不可用，操作已取消', 'warning');
            resolve(false);
            return;
        }

        let confirmed = false;
        titleEl.textContent = title;
        bodyEl.textContent = message;
        confirmBtn.textContent = confirmText;
        confirmBtn.className = `btn btn-${tone}`;

        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        const onConfirm = () => {
            confirmed = true;
            modal.hide();
        };
        const onHidden = () => {
            confirmBtn.removeEventListener('click', onConfirm);
            modalEl.removeEventListener('hidden.bs.modal', onHidden);
            resolve(confirmed);
        };

        confirmBtn.addEventListener('click', onConfirm);
        modalEl.addEventListener('hidden.bs.modal', onHidden);
        modal.show();
    });
}

function showLoading(message = '正在处理...') {
    updateTextContent('loadingText', message);
    const overlay = document.getElementById('globalLoadingOverlay');
    if (overlay) {
        overlay.hidden = false;
    }
}

function hideLoading() {
    const overlay = document.getElementById('globalLoadingOverlay');
    if (overlay) {
        overlay.hidden = true;
    }
}

function notify(message, tone = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) {
        return;
    }

    const iconMap = {
        success: 'bi-check-circle',
        danger: 'bi-exclamation-triangle',
        warning: 'bi-exclamation-circle',
        info: 'bi-info-circle',
    };
    const toast = document.createElement('div');
    toast.className = 'toast coal-toast';
    toast.role = 'alert';
    toast.ariaLive = 'assertive';
    toast.ariaAtomic = 'true';
    toast.innerHTML = `
        <div class="toast-header">
            <i class="bi ${iconMap[tone] || iconMap.info} text-${tone} me-2"></i>
            <strong class="me-auto">系统提示</strong>
            <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
        <div class="toast-body">${escapeHtml(message)}</div>
    `;
    container.appendChild(toast);
    const instance = new bootstrap.Toast(toast, { delay: tone === 'danger' ? 5200 : 3200 });
    toast.addEventListener('hidden.bs.toast', () => toast.remove());
    instance.show();
}

function findCoal(coalId) {
    return allCoals.find(coal => Number(coal.id) === Number(coalId));
}

function formatNumber(value, digits = 2) {
    const number = Number(value);
    if (!Number.isFinite(number)) {
        return '--';
    }
    return number.toFixed(digits);
}

function formatCurrency(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) {
        return '--';
    }
    return `¥${number.toFixed(2)}`;
}

function formatPercent(value) {
    return `${formatNumber(value, 2)}%`;
}

function formatOptionalPercent(value) {
    if (value === null || value === undefined || value === '') {
        return '未填写';
    }
    return formatPercent(value);
}

function valueOrDash(value) {
    if (value === null || value === undefined || value === '') {
        return '未填写';
    }
    return String(value);
}

function updateTextContent(id, text) {
    const element = document.getElementById(id);
    if (element) {
        element.textContent = text;
    }
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function getDateStamp() {
    return new Date().toISOString().slice(0, 10);
}

function debounce(callback, delay) {
    let timerId = null;
    return (...args) => {
        window.clearTimeout(timerId);
        timerId = window.setTimeout(() => callback(...args), delay);
    };
}

function showSuccess(message) {
    notify(message, 'success');
}

function showError(message) {
    notify(message, 'danger');
}

function showWarning(message) {
    notify(message, 'warning');
}
