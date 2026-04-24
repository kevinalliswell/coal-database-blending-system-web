// 煤种数据管理页面JavaScript

// 全局变量
let currentPage = 1;
let pageSize = 10;
let totalItems = 0;
let allCoals = [];
let filteredCoals = [];
let currentEditCoalId = null;

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    initializePage();
});

// 初始化页面
function initializePage() {
    loadCoals();
    setupEventListeners();
}

// 设置事件监听器
function setupEventListeners() {
    // 搜索框回车事件
    document.getElementById('searchInput').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            searchCoals();
        }
    });

    // 页面大小改变事件
    document.getElementById('pageSizeSelect').addEventListener('change', function() {
        pageSize = parseInt(this.value);
        currentPage = 1;
        displayCoals();
    });

    // 全选checkbox事件
    document.getElementById('selectAll').addEventListener('change', function() {
        const checkboxes = document.querySelectorAll('tbody input[type="checkbox"]');
        checkboxes.forEach(checkbox => {
            checkbox.checked = this.checked;
        });
        updateSelectedCount();
    });
}

// 加载煤种数据
async function loadCoals() {
    try {
        showLoading();
        const response = await fetch('/api/coals?page_size=0'); // 获取所有数据
        const result = await response.json();
        
        if (result.status === 'success') {
            allCoals = result.data;
            filteredCoals = [...allCoals];
            totalItems = filteredCoals.length;
            displayCoals();
        } else {
            showError('加载煤种数据失败: ' + result.message);
        }
    } catch (error) {
        showError('网络错误: ' + error.message);
    } finally {
        hideLoading();
    }
}

// 显示煤种数据
function displayCoals() {
    const tbody = document.getElementById('coalTableBody');
    const startIndex = (currentPage - 1) * pageSize;
    const endIndex = Math.min(startIndex + pageSize, filteredCoals.length);
    const pageCoals = filteredCoals.slice(startIndex, endIndex);

    // 清空表格
    tbody.innerHTML = '';

    if (pageCoals.length === 0) {
        tbody.innerHTML = '<tr><td colspan="11" class="text-center text-muted">暂无数据</td></tr>';
        updatePagination();
        updateStatistics();
        return;
    }

    // 添加数据行
    pageCoals.forEach(coal => {
        const row = createCoalRow(coal);
        tbody.appendChild(row);
    });

    updatePagination();
    updateStatistics();
    updateSelectedCount();
}

// 创建煤种数据行
function createCoalRow(coal) {
    const row = document.createElement('tr');
    row.innerHTML = `
        <td>
            <input class="form-check-input" type="checkbox" value="${coal.id}" onchange="updateSelectedCount()">
        </td>
        <td>${coal.id}</td>
        <td>${coal.name}</td>
        <td>
            <span class="badge bg-secondary">${coal.type}</span>
        </td>
        <td>¥${coal.price.toFixed(2)}</td>
        <td>${coal.calorific_value}</td>
        <td>${coal.ash_content.toFixed(2)}%</td>
        <td>${coal.volatile_matter.toFixed(2)}%</td>
        <td>${coal.fixed_carbon.toFixed(2)}%</td>
        <td>${coal.total_sulfur.toFixed(2)}%</td>
        <td>
            <button class="btn btn-sm btn-outline-primary me-1" onclick="viewCoalDetail(${coal.id})" title="查看详情">
                <i class="bi bi-eye"></i>
            </button>
            <button class="btn btn-sm btn-outline-warning me-1" onclick="editCoal(${coal.id})" title="编辑">
                <i class="bi bi-pencil"></i>
            </button>
            <button class="btn btn-sm btn-outline-danger" onclick="deleteCoal(${coal.id})" title="删除">
                <i class="bi bi-trash"></i>
            </button>
        </td>
    `;
    return row;
}

// 更新分页
function updatePagination() {
    const pagination = document.getElementById('pagination');
    const totalPages = Math.ceil(filteredCoals.length / pageSize);
    
    pagination.innerHTML = '';

    if (totalPages <= 1) return;

    // 上一页
    const prevItem = document.createElement('li');
    prevItem.className = `page-item ${currentPage === 1 ? 'disabled' : ''}`;
    prevItem.innerHTML = `<a class="page-link" href="#" onclick="changePage(${currentPage - 1})">上一页</a>`;
    pagination.appendChild(prevItem);

    // 页码按钮
    const startPage = Math.max(1, currentPage - 2);
    const endPage = Math.min(totalPages, currentPage + 2);

    if (startPage > 1) {
        const firstItem = document.createElement('li');
        firstItem.className = 'page-item';
        firstItem.innerHTML = '<a class="page-link" href="#" onclick="changePage(1)">1</a>';
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
        pageItem.className = `page-item ${i === currentPage ? 'active' : ''}`;
        pageItem.innerHTML = `<a class="page-link" href="#" onclick="changePage(${i})">${i}</a>`;
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
        lastItem.innerHTML = `<a class="page-link" href="#" onclick="changePage(${totalPages})">${totalPages}</a>`;
        pagination.appendChild(lastItem);
    }

    // 下一页
    const nextItem = document.createElement('li');
    nextItem.className = `page-item ${currentPage === totalPages ? 'disabled' : ''}`;
    nextItem.innerHTML = `<a class="page-link" href="#" onclick="changePage(${currentPage + 1})">下一页</a>`;
    pagination.appendChild(nextItem);
}

// 更新统计信息
function updateStatistics() {
    const startIndex = (currentPage - 1) * pageSize + 1;
    const endIndex = Math.min(currentPage * pageSize, filteredCoals.length);
    
    document.getElementById('startIndex').textContent = filteredCoals.length > 0 ? startIndex : 0;
    document.getElementById('endIndex').textContent = endIndex;
    document.getElementById('totalItems').textContent = filteredCoals.length;
    document.getElementById('totalCount').textContent = `总计: ${filteredCoals.length} 条`;
}

// 更新选中数量
function updateSelectedCount() {
    const selectedCheckboxes = document.querySelectorAll('tbody input[type="checkbox"]:checked');
    const count = selectedCheckboxes.length;
    
    // 更新全选checkbox状态
    const selectAllCheckbox = document.getElementById('selectAll');
    const totalCheckboxes = document.querySelectorAll('tbody input[type="checkbox"]');
    
    if (count === 0) {
        selectAllCheckbox.indeterminate = false;
        selectAllCheckbox.checked = false;
    } else if (count === totalCheckboxes.length) {
        selectAllCheckbox.indeterminate = false;
        selectAllCheckbox.checked = true;
    } else {
        selectAllCheckbox.indeterminate = true;
    }
}

// 切换页面
function changePage(page) {
    if (page >= 1 && page <= Math.ceil(filteredCoals.length / pageSize)) {
        currentPage = page;
        displayCoals();
    }
}

// 搜索煤种
function searchCoals() {
    const searchTerm = document.getElementById('searchInput').value.toLowerCase().trim();
    const typeFilter = document.getElementById('typeFilter').value;
    
    filteredCoals = allCoals.filter(coal => {
        const matchesSearch = !searchTerm || 
            coal.name.toLowerCase().includes(searchTerm) ||
            coal.supplier.toLowerCase().includes(searchTerm);
        const matchesType = !typeFilter || coal.type === typeFilter;
        
        return matchesSearch && matchesType;
    });
    
    currentPage = 1;
    displayCoals();
}

// 重置搜索
function resetSearch() {
    document.getElementById('searchInput').value = '';
    document.getElementById('typeFilter').value = '';
    filteredCoals = [...allCoals];
    currentPage = 1;
    displayCoals();
}

// 查看煤种详情
function viewCoalDetail(coalId) {
    const coal = allCoals.find(c => c.id === coalId);
    if (!coal) return;

    // 填充详情模态框
    document.getElementById('detailCoalName').textContent = coal.name;
    document.getElementById('detailCoalType').textContent = coal.type;
    document.getElementById('detailSupplier').textContent = coal.supplier || '未填写';
    document.getElementById('detailPrice').textContent = `¥${coal.price.toFixed(2)}`;
    document.getElementById('detailCalorificValue').textContent = coal.calorific_value;
    document.getElementById('detailAshContent').textContent = `${coal.ash_content.toFixed(2)}%`;
    document.getElementById('detailVolatileMatter').textContent = `${coal.volatile_matter.toFixed(2)}%`;
    document.getElementById('detailFixedCarbon').textContent = `${coal.fixed_carbon.toFixed(2)}%`;
    document.getElementById('detailTotalSulfur').textContent = `${coal.total_sulfur.toFixed(2)}%`;
    document.getElementById('detailMoisture').textContent = coal.moisture ? `${coal.moisture.toFixed(2)}%` : '未填写';
    document.getElementById('detailMad').textContent = coal.mad ? `${coal.mad.toFixed(2)}%` : '未填写';
    document.getElementById('detailHgi').textContent = coal.hgi || '未填写';
    document.getElementById('detailBurnoutRate').textContent = coal.burnout_rate ? `${coal.burnout_rate.toFixed(2)}%` : '未填写';
    document.getElementById('detailCarbonContent').textContent = coal.carbon_content ? `${coal.carbon_content.toFixed(2)}%` : '未填写';
    document.getElementById('detailHydrogenContent').textContent = coal.hydrogen_content ? `${coal.hydrogen_content.toFixed(2)}%` : '未填写';
    document.getElementById('detailNitrogenContent').textContent = coal.nitrogen_content ? `${coal.nitrogen_content.toFixed(2)}%` : '未填写';

    // 设置编辑按钮
    document.getElementById('editFromDetailBtn').onclick = () => editCoalFromDetail(coalId);

    // 显示模态框
    const modal = new bootstrap.Modal(document.getElementById('coalDetailModal'));
    modal.show();
}

// 编辑煤种
function editCoal(coalId) {
    const coal = allCoals.find(c => c.id === coalId);
    if (!coal) return;

    currentEditCoalId = coalId;

    // 填充编辑表单
    const form = document.getElementById('editCoalForm');
    form.querySelector('[name="coal_id"]').value = coalId;
    form.querySelector('[name="name"]').value = coal.name;
    form.querySelector('[name="type"]').value = coal.type;
    form.querySelector('[name="supplier"]').value = coal.supplier || '';
    form.querySelector('[name="price"]').value = coal.price;
    form.querySelector('[name="calorific_value"]').value = coal.calorific_value;
    form.querySelector('[name="ash_content"]').value = coal.ash_content;
    form.querySelector('[name="volatile_matter"]').value = coal.volatile_matter;
    form.querySelector('[name="fixed_carbon"]').value = coal.fixed_carbon;
    form.querySelector('[name="total_sulfur"]').value = coal.total_sulfur;
    form.querySelector('[name="moisture"]').value = coal.moisture || '';
    form.querySelector('[name="mad"]').value = coal.mad || '';
    form.querySelector('[name="hgi"]').value = coal.hgi || '';
    form.querySelector('[name="burnout_rate"]').value = coal.burnout_rate || '';
    form.querySelector('[name="carbon_content"]').value = coal.carbon_content || '';
    form.querySelector('[name="hydrogen_content"]').value = coal.hydrogen_content || '';
    form.querySelector('[name="nitrogen_content"]').value = coal.nitrogen_content || '';

    // 显示编辑模态框
    const modal = new bootstrap.Modal(document.getElementById('editCoalModal'));
    modal.show();
}

// 从详情页编辑
function editCoalFromDetail(coalId) {
    // 隐藏详情模态框
    const detailModal = bootstrap.Modal.getInstance(document.getElementById('coalDetailModal'));
    detailModal.hide();
    
    // 显示编辑模态框
    setTimeout(() => {
        editCoal(coalId);
    }, 300);
}

// 删除煤种
async function deleteCoal(coalId) {
    const coal = allCoals.find(c => c.id === coalId);
    if (!coal) return;

    if (confirm(`确定要删除煤种"${coal.name}"吗？此操作不可撤销。`)) {
        try {
            showLoading();
            
            const response = await fetch(`/api/coals/${coalId}`, {
                method: 'DELETE'
            });
            
            const result = await response.json();
            
            if (result.status === 'success') {
                showSuccess('煤种删除成功');
                loadCoals(); // 重新加载数据
            } else {
                showError('删除失败: ' + result.message);
            }
        } catch (error) {
            showError('网络错误: ' + error.message);
        } finally {
            hideLoading();
        }
    }
}

// 保存新煤种
async function saveCoal() {
    const form = document.getElementById('addCoalForm');
    if (!form.checkValidity()) {
        form.reportValidity();
        return;
    }

    const formData = new FormData(form);
    const coalData = {};
    for (let [key, value] of formData.entries()) {
        if (value !== '') {
            coalData[key] = value;
        }
    }

    try {
        showLoading();
        
        const response = await fetch('/api/coals', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(coalData)
        });
        
        const result = await response.json();
        
        if (result.status === 'success') {
            showSuccess('煤种添加成功');
            const modal = bootstrap.Modal.getInstance(document.getElementById('addCoalModal'));
            modal.hide();
            form.reset();
            loadCoals(); // 重新加载数据
        } else {
            showError('添加失败: ' + result.message);
        }
    } catch (error) {
        showError('网络错误: ' + error.message);
    } finally {
        hideLoading();
    }
}

// 更新煤种
async function updateCoal() {
    const form = document.getElementById('editCoalForm');
    if (!form.checkValidity()) {
        form.reportValidity();
        return;
    }

    const formData = new FormData(form);
    const coalData = {};
    for (let [key, value] of formData.entries()) {
        if (key !== 'coal_id' && value !== '') {
            coalData[key] = value;
        }
    }

    try {
        showLoading();
        
        const response = await fetch(`/api/coals/${currentEditCoalId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(coalData)
        });
        
        const result = await response.json();
        
        if (result.status === 'success') {
            showSuccess('煤种更新成功');
            const modal = bootstrap.Modal.getInstance(document.getElementById('editCoalModal'));
            modal.hide();
            loadCoals(); // 重新加载数据
        } else {
            showError('更新失败: ' + result.message);
        }
    } catch (error) {
        showError('网络错误: ' + error.message);
    } finally {
        hideLoading();
    }
}

// 批量删除
async function batchDelete() {
    const selectedCheckboxes = document.querySelectorAll('tbody input[type="checkbox"]:checked');
    if (selectedCheckboxes.length === 0) {
        showWarning('请选择要删除的煤种');
        return;
    }

    const selectedIds = Array.from(selectedCheckboxes).map(cb => parseInt(cb.value));
    
    if (confirm(`确定要删除选中的 ${selectedIds.length} 个煤种吗？此操作不可撤销。`)) {
        try {
            showLoading();
            
            const response = await fetch('/api/coals/batch_delete', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ coal_ids: selectedIds })
            });
            
            const result = await response.json();
            
            if (result.status === 'success') {
                showSuccess(result.message);
                loadCoals(); // 重新加载数据
            } else {
                showError('批量删除失败: ' + result.message);
            }
        } catch (error) {
            showError('网络错误: ' + error.message);
        } finally {
            hideLoading();
        }
    }
}

// 批量导出
async function exportSelected() {
    const selectedCheckboxes = document.querySelectorAll('tbody input[type="checkbox"]:checked');
    if (selectedCheckboxes.length === 0) {
        showWarning('请选择要导出的煤种');
        return;
    }

    const selectedIds = Array.from(selectedCheckboxes).map(cb => parseInt(cb.value));
    
    try {
        showLoading();
        
        const response = await fetch('/api/coals/export', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                coal_ids: selectedIds,
                export_all: false 
            })
        });
        
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = `选中煤种导出_${new Date().toISOString().slice(0, 10)}.xlsx`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            showSuccess('导出成功');
        } else {
            const result = await response.json();
            showError('导出失败: ' + result.message);
        }
    } catch (error) {
        showError('网络错误: ' + error.message);
    } finally {
        hideLoading();
    }
}

// 导出全部
async function exportAll() {
    if (allCoals.length === 0) {
        showWarning('没有可导出的数据');
        return;
    }

    try {
        showLoading();
        
        const response = await fetch('/api/coals/export', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ export_all: true })
        });
        
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = `全部煤种导出_${new Date().toISOString().slice(0, 10)}.xlsx`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            showSuccess('导出成功');
        } else {
            const result = await response.json();
            showError('导出失败: ' + result.message);
        }
    } catch (error) {
        showError('网络错误: ' + error.message);
    } finally {
        hideLoading();
    }
}

// 下载导入模板
async function downloadTemplate() {
    try {
        showLoading();
        
        const response = await fetch('/api/coals/template');
        
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = '煤种数据导入模板.xlsx';
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            showSuccess('模板下载成功');
        } else {
            const result = await response.json();
            showError('下载模板失败: ' + result.message);
        }
    } catch (error) {
        showError('网络错误: ' + error.message);
    } finally {
        hideLoading();
    }
}

// 上传文件
async function uploadFile() {
    const fileInput = document.getElementById('importFile');
    const file = fileInput.files[0];
    
    if (!file) {
        showWarning('请选择要上传的文件');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    const progressDiv = document.getElementById('importProgress');
    const resultDiv = document.getElementById('importResult');
    const uploadBtn = document.getElementById('uploadBtn');
    
    // 显示进度条
    progressDiv.style.display = 'block';
    resultDiv.style.display = 'none';
    uploadBtn.disabled = true;

    try {
        const response = await fetch('/api/coals/upload', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        // 隐藏进度条
        progressDiv.style.display = 'none';
        resultDiv.style.display = 'block';
        
        if (result.status === 'success') {
            resultDiv.className = 'alert alert-success';
            resultDiv.innerHTML = `<i class="bi bi-check-circle me-2"></i>${result.message}`;
            
            // 重新加载数据
            loadCoals();
            
            // 重置文件输入
            fileInput.value = '';
        } else {
            resultDiv.className = 'alert alert-danger';
            resultDiv.innerHTML = `<i class="bi bi-exclamation-circle me-2"></i>${result.message}`;
        }
    } catch (error) {
        progressDiv.style.display = 'none';
        resultDiv.style.display = 'block';
        resultDiv.className = 'alert alert-danger';
        resultDiv.innerHTML = `<i class="bi bi-exclamation-circle me-2"></i>网络错误: ${error.message}`;
    } finally {
        uploadBtn.disabled = false;
    }
}

// 工具函数
function showLoading() {
    // 可以添加全局加载指示器
    console.log('Loading...');
}

function hideLoading() {
    // 隐藏全局加载指示器
    console.log('Loading complete');
}

function showSuccess(message) {
    // 使用更好的通知方式，这里先用alert
    alert('成功: ' + message);
}

function showError(message) {
    // 使用更好的通知方式，这里先用alert
    alert('错误: ' + message);
}

function showWarning(message) {
    // 使用更好的通知方式，这里先用alert
    alert('警告: ' + message);
}