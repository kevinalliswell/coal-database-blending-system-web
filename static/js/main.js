// 当页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    // 绑定开始优化计算按钮事件
    document.querySelector('.btn-success.btn-lg').addEventListener('click', function() {
        startOptimization(this);
    });
    
    // 初始化表单验证
    initFormValidation();
    
    // 初始化煤种表格交互
    initCoalTableInteractions();
});

// 开始优化计算
function startOptimization(button) {
    // 显示加载状态
    button.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>计算中...';
    button.disabled = true;
    
    // 收集表单数据
    const formData = collectFormData();
    
    // 在实际应用中，这里应该发送AJAX请求到后端
    // 这里使用setTimeout模拟后端处理时间
    setTimeout(() => {
        // 恢复按钮状态
        button.innerHTML = '<i class="bi bi-play-circle me-2"></i>开始优化计算';
        button.disabled = false;
        
        // 显示结果（这里应该是从后端获取的数据）
        initializeCharts();
        
        // 滚动到结果区域
        document.querySelector('.result-card').scrollIntoView({ behavior: 'smooth' });
        
        // 显示成功消息
        showAlert('优化计算完成！找到最优混煤方案。', 'success');
    }, 3000);
}

// 收集表单数据
function collectFormData() {
    const data = {
        optimization_target: document.querySelector('select').value,
        population_size: document.querySelector('input[placeholder="输入种群大小"]')?.value || 500,
        max_generations: document.querySelector('input[placeholder="输入最大迭代次数"]')?.value || 3000,
        mutation_rate: document.querySelector('input[placeholder="输入变异率"]')?.value || 0.2,
        crossover_rate: document.querySelector('input[placeholder="输入交叉率"]')?.value || 0.85,
        adaptive_mutation: document.getElementById('adaptiveMutation').checked,
        parallel_computing: document.getElementById('parallelComputing').checked,
        constraints: {
            heat_value: document.querySelector('input[placeholder="输入目标热值"]')?.value || 6000,
            heat_min: document.querySelector('input[placeholder="输入热值下限"]')?.value || 5800,
            heat_max: document.querySelector('input[placeholder="输入热值上限"]')?.value || 6500,
            ash_min: document.querySelector('input[placeholder="输入灰分下限"]')?.value || 8.0,
            ash_limit: document.querySelector('input[placeholder="输入灰分上限"]')?.value || 18.0,
            volatile_min: document.querySelector('input[placeholder="输入挥发分下限"]')?.value || 15.0,
            volatile_max: document.querySelector('input[placeholder="输入挥发分上限"]')?.value || 35.0,
            fixed_carbon_min: document.querySelector('input[placeholder="输入固定碳下限"]')?.value || 55.0,
            fixed_carbon_max: document.querySelector('input[placeholder="输入固定碳上限"]')?.value || 75.0,
            sulfur_min: document.querySelector('input[placeholder="输入硫含量下限"]')?.value || 0.4,
            sulfur_limit: document.querySelector('input[placeholder="输入硫含量上限"]')?.value || 0.8,
            price_min: document.querySelector('input[placeholder="输入价格下限"]')?.value || 450,
            price_limit: document.querySelector('input[placeholder="输入价格上限"]')?.value || 800
        },
        selected_coals: getSelectedCoals()
    };
    
    return data;
}

// 获取选中的煤种
function getSelectedCoals() {
    const selectedCoals = [];
    const checkboxes = document.querySelectorAll('.coal-table input[type="checkbox"]');
    
    checkboxes.forEach((checkbox, index) => {
        if (checkbox.checked) {
            const row = checkbox.closest('tr');
            const name = row.cells[1].textContent;
            const type = row.cells[2].textContent;
            const price = parseFloat(row.cells[3].textContent);
            
            selectedCoals.push({
                name,
                type,
                price
            });
        }
    });
    
    return selectedCoals;
}

// 初始化表单验证
function initFormValidation() {
    const forms = document.querySelectorAll('form');
    
    forms.forEach(form => {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
                showAlert('请检查表单中的错误', 'danger');
            }
            form.classList.add('was-validated');
        });
    });
}

// 初始化煤种表格交互
function initCoalTableInteractions() {
    // 删除煤种按钮
    const deleteButtons = document.querySelectorAll('.coal-table .btn-outline-danger');
    deleteButtons.forEach(button => {
        button.addEventListener('click', function() {
            if (confirm('确定要删除这个煤种吗？')) {
                const row = this.closest('tr');
                row.remove();
                showAlert('煤种已删除', 'warning');
            }
        });
    });
}

// 显示提示消息
function showAlert(message, type) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.setAttribute('role', 'alert');
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    // 插入到页面顶部
    const container = document.querySelector('.container');
    container.insertBefore(alertDiv, container.firstChild);
    
    // 5秒后自动消失
    setTimeout(() => {
        alertDiv.classList.remove('show');
        setTimeout(() => alertDiv.remove(), 150);
    }, 5000);
}
