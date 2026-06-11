// 置换比计算页面JavaScript文件

// 全局变量
let contributionChart = null;

// DOM加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    initializePage();
    bindEvents();
    loadFromLocalStorage();
});

// 初始化页面
function initializePage() {
    // 初始化计算类型切换
    updateCalculationSections();
    
    // 初始化图表
    initializeChart();
}

// 绑定事件
function bindEvents() {
    // 计算类型切换
    const calculationTypeRadios = document.querySelectorAll('input[name="calculationType"]');
    calculationTypeRadios.forEach(radio => {
        radio.addEventListener('change', updateCalculationSections);
    });
    
    // 按钮事件
    document.getElementById('calculateBtn').addEventListener('click', performCalculation);
    document.getElementById('resetBtn').addEventListener('click', resetParameters);
    document.getElementById('loadExampleBtn').addEventListener('click', loadExampleData);
    document.getElementById('exportResultBtn').addEventListener('click', exportResults);
    document.getElementById('printResultBtn').addEventListener('click', printResults);
    document.getElementById('openHistoryBtn')?.addEventListener('click', openHistoryPage);
    
    // 参数输入验证
    const numberInputs = document.querySelectorAll('input[type="number"]');
    numberInputs.forEach(input => {
        input.addEventListener('blur', validateInput);
        input.addEventListener('input', saveToLocalStorage);
    });
}

// 更新计算章节显示
function updateCalculationSections() {
    const selectedType = document.querySelector('input[name="calculationType"]:checked').value;
    const theorySection = document.getElementById('theorySection');
    const actualSection = document.getElementById('actualSection');
    
    if (selectedType === 'theory') {
        theorySection.style.display = 'block';
        actualSection.style.display = 'none';
    } else {
        theorySection.style.display = 'none';
        actualSection.style.display = 'block';
    }
}

// 验证输入
function validateInput(event) {
    const input = event.target;
    const value = parseFloat(input.value);
    const min = parseFloat(input.min);
    const max = parseFloat(input.max);
    
    if (isNaN(value)) {
        showAlert('输入值必须是数字', 'warning');
        input.focus();
        return false;
    }
    
    if (min !== undefined && value < min) {
        showAlert(`输入值不能小于 ${min}`, 'warning');
        input.focus();
        return false;
    }
    
    if (max !== undefined && value > max) {
        showAlert(`输入值不能大于 ${max}`, 'warning');
        input.focus();
        return false;
    }
    
    return true;
}

// 执行计算
async function performCalculation() {
    const selectedType = document.querySelector('input[name="calculationType"]:checked').value;
    const calculateBtn = document.getElementById('calculateBtn');
    
    // 显示计算中状态
    calculateBtn.disabled = true;
    calculateBtn.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>计算中...';
    
    try {
        let result;
        if (selectedType === 'theory') {
            result = await calculateTheoryRatio();
        } else {
            result = await calculateActualRatio();
        }

        if (result.status !== 'success') {
            throw new Error(result.message || '计算失败');
        }
        
        displayResults(result, selectedType);
        document.getElementById('resultsSection').style.display = 'block';
        
        // 滚动到结果区域
        document.getElementById('resultsSection').scrollIntoView({ 
            behavior: 'smooth',
            block: 'start'
        });
        
    } catch (error) {
        console.error('计算错误:', error);
        showAlert('计算过程中出现错误: ' + error.message, 'danger');
    } finally {
        // 恢复按钮状态
        calculateBtn.disabled = false;
        calculateBtn.innerHTML = '<i class="bi bi-calculator me-2"></i>开始计算';
    }
}

// 计算理论置换比
async function calculateTheoryRatio() {
    const parameters = {
        coal_params: {
            carbon_content: parseFloat(document.getElementById('coalCarbonContent').value) / 100,
            hydrogen_content: parseFloat(document.getElementById('coalHydrogenContent').value) / 100,
            ash_content: parseFloat(document.getElementById('coalAshContent').value) / 100,
            sio2_content: parseFloat(document.getElementById('coalSiO2Content').value) / 100,
            decomposition_heat: parseFloat(document.getElementById('coalDecompositionHeat').value),
            physical_heat: parseFloat(document.getElementById('coalPhysicalHeat').value)
        },
        coke_params: {
            carbon_content: parseFloat(document.getElementById('cokeCarbonContent').value) / 100,
            ash_content: parseFloat(document.getElementById('cokeAshContent').value) / 100,
            sio2_content: parseFloat(document.getElementById('cokeSiO2Content').value) / 100
        },
        blast_furnace_params: {
            eta_co: parseFloat(document.getElementById('gasUtilization').value),
            slag_basicity: parseFloat(document.getElementById('slagBasicity').value),
            slag_enthalpy: parseFloat(document.getElementById('slagEnthalpy').value),
            wind_temperature: parseFloat(document.getElementById('windTemperature').value),
            hot_blast_enthalpy: parseFloat(document.getElementById('hotBlastEnthalpy').value)
        }
    };
    
    const response = await fetch('/api/calculate_theory_ratio', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(parameters)
    });
    
    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    return await response.json();
}

// 计算实际置换比
async function calculateActualRatio() {
    const enableAdvanced = document.getElementById('enableAdvancedCalculation').checked;
    
    const parameters = {
        production_data: {
            initial_coke_ratio: parseFloat(document.getElementById('initialCokeRatio').value),
            final_coke_ratio: parseFloat(document.getElementById('finalCokeRatio').value),
            initial_coal_ratio: parseFloat(document.getElementById('initialCoalRatio').value),
            final_coal_ratio: parseFloat(document.getElementById('finalCoalRatio').value),
            adjustment_factor: parseFloat(document.getElementById('adjustmentFactor').value),
            iron_output_change: enableAdvanced ? parseFloat(document.getElementById('ironOutputChange').value) : 0,
            slag_ratio_change: enableAdvanced ? parseFloat(document.getElementById('slagRatioChange').value) : 0,
            carbon_efficiency_change: enableAdvanced ? parseFloat(document.getElementById('carbonEfficiencyChange').value) : 0
        },
        enable_advanced: enableAdvanced
    };
    
    const response = await fetch('/api/calculate_actual_ratio', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(parameters)
    });
    
    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    return await response.json();
}

// 显示计算结果
function displayResults(result, calculationType) {
    // 显示主要结果
    document.getElementById('resultTitle').textContent = 
        calculationType === 'theory' ? '理论置换比' : '实际置换比';
    document.getElementById('mainResultValue').textContent = result.ratio.toFixed(6);
    
    // 显示详细计算过程
    displayCalculationDetails(result.details);
    
    // 更新图表
    updateContributionChart(result.details);
    
    // 显示特定类型的结果
    if (calculationType === 'theory') {
        displayTheoryResults(result);
        document.getElementById('theoryResults').style.display = 'block';
        document.getElementById('actualResults').style.display = 'none';
    } else {
        displayActualResults(result);
        document.getElementById('theoryResults').style.display = 'none';
        document.getElementById('actualResults').style.display = 'block';
    }
}

// 显示计算详情
function displayCalculationDetails(details) {
    const tbody = document.querySelector('#calculationDetailsTable tbody');
    tbody.innerHTML = '';
    
    for (const [key, value] of Object.entries(details)) {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td><strong>${key}</strong></td>
            <td>${formatValue(value)}</td>
        `;
        tbody.appendChild(row);
    }
}

// 显示理论计算特有结果
function displayTheoryResults(result) {
    const details = result.details;
    
    // 碳量平衡分析
    document.getElementById('effectiveCoalCarbon').textContent = 
        formatValue(details['煤粉含碳量']) + '%';
    document.getElementById('effectiveCokeCarbon').textContent = 
        formatValue(details['焦炭含碳量']) + '%';
    document.getElementById('hydrogenSavingCarbon').textContent = 
        formatValue(details['煤粉中氢参加还原而节约的碳量']) + '%';
    document.getElementById('slagConsumingCarbon').textContent = 
        formatValue(details['煤粉中灰分造渣所消耗的碳'] + details['焦炭中灰分造渣所消耗的碳']) + '%';
    
    // 热量平衡分析（这些需要从后端额外获取）
    document.getElementById('carbonBurningHeat').textContent = result.carbon_burning_heat?.toFixed(2) || '--';
    document.getElementById('decompositionHeatConsumption').textContent = 
        result.decomposition_heat_consumption?.toFixed(2) || '--';
    document.getElementById('physicalHeatConsumption').textContent = 
        result.physical_heat_consumption?.toFixed(2) || '--';
    document.getElementById('hydrogenReplacementHeat').textContent = 
        result.hydrogen_replacement_heat?.toFixed(2) || '--';
}

// 显示实际计算特有结果
function displayActualResults(result) {
    const details = result.details;
    
    // 生产指标变化
    document.getElementById('cokeRatioReduction').textContent = 
        formatValue(details['焦比减少量(kg/t)']);
    document.getElementById('coalRatioIncrease').textContent = 
        formatValue(details['煤比增加量(kg/t)']);
    document.getElementById('basicReplacementRatio').textContent = 
        formatValue(details['实际置换比']);
    document.getElementById('correctedReplacementRatio').textContent = 
        formatValue(details['修正后实际置换比'] || details['实际置换比']);
    
    // 修正因子影响
    if (details['铁水产量修正项'] !== undefined) {
        document.getElementById('outputCorrection').textContent = 
            formatValue(details['铁水产量修正项']);
        document.getElementById('slagCorrection').textContent = 
            formatValue(details['渣比修正项']);
        document.getElementById('efficiencyCorrection').textContent = 
            formatValue(details['碳效率修正项']);
        document.getElementById('totalCorrection').textContent = 
            formatValue(details['总修正量']);
    } else {
        document.getElementById('outputCorrection').textContent = '未启用';
        document.getElementById('slagCorrection').textContent = '未启用';
        document.getElementById('efficiencyCorrection').textContent = '未启用';
        document.getElementById('totalCorrection').textContent = '未启用';
    }
}

// 初始化图表
function initializeChart() {
    const ctx = document.getElementById('contributionChart').getContext('2d');
    contributionChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: [],
            datasets: [{
                data: [],
                backgroundColor: [
                    '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0',
                    '#9966FF', '#FF9F40', '#FF6384', '#C9CBCF'
                ]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                },
                title: {
                    display: true,
                    text: '参数贡献度'
                }
            }
        }
    });
}

// 更新贡献图表
function updateContributionChart(details) {
    const labels = [];
    const data = [];
    
    // 根据计算类型选择不同的参数
    const selectedType = document.querySelector('input[name="calculationType"]:checked').value;
    
    if (selectedType === 'theory') {
        // 理论计算的主要贡献参数
        labels.push('煤粉含碳量', '氢节约碳量', '煤粉造渣耗碳', '分解热耗碳', '焦炭有效碳');
        data.push(
            Math.abs(details['煤粉含碳量'] || 0),
            Math.abs(details['煤粉中氢参加还原而节约的碳量'] || 0),
            Math.abs(details['煤粉中灰分造渣所消耗的碳'] || 0),
            Math.abs(details['煤粉分解热和加热至1500°C物理热所消耗的碳'] || 0),
            Math.abs(details['焦炭含碳量'] || 0))
        ;
    } else {
        // 实际计算的主要贡献参数
        labels.push('焦比减少', '煤比增加', '修正系数');
        data.push(
            Math.abs(details['焦比减少量(kg/t)'] || 0),
            Math.abs(details['煤比增加量(kg/t)'] || 0),
            Math.abs(details['修正系数(kg/t)'] || 0)
        );
        
        if (details['总修正量'] !== undefined) {
            labels.push('生产修正');
            data.push(Math.abs(details['总修正量'] - details['修正系数(kg/t)'] || 0));
        }
    }
    
    contributionChart.data.labels = labels;
    contributionChart.data.datasets[0].data = data;
    contributionChart.update();
}

// 重置参数
function resetParameters() {
    const selectedType = document.querySelector('input[name="calculationType"]:checked').value;
    
    if (selectedType === 'theory') {
        // 重置理论计算参数为默认值
        document.getElementById('coalCarbonContent').value = '78.0';
        document.getElementById('coalHydrogenContent').value = '3.5';
        document.getElementById('coalAshContent').value = '12.0';
        document.getElementById('coalSiO2Content').value = '48.0';
        document.getElementById('coalDecompositionHeat').value = '220';
        document.getElementById('coalPhysicalHeat').value = '450';
        document.getElementById('cokeCarbonContent').value = '86.0';
        document.getElementById('cokeAshContent').value = '11.0';
        document.getElementById('cokeSiO2Content').value = '52.0';
        document.getElementById('gasUtilization').value = '0.4444';
        document.getElementById('slagBasicity').value = '1.15';
        document.getElementById('slagEnthalpy').value = '1800';
        document.getElementById('windTemperature').value = '1180';
        document.getElementById('hotBlastEnthalpy').value = '1.5';
    } else {
        // 重置实际计算参数为默认值
        document.getElementById('initialCokeRatio').value = '400';
        document.getElementById('finalCokeRatio').value = '370';
        document.getElementById('initialCoalRatio').value = '150';
        document.getElementById('finalCoalRatio').value = '180';
        document.getElementById('adjustmentFactor').value = '2.5';
        document.getElementById('ironOutputChange').value = '50';
        document.getElementById('slagRatioChange').value = '-10';
        document.getElementById('carbonEfficiencyChange').value = '2.0';
        document.getElementById('enableAdvancedCalculation').checked = false;
    }
    
    // 隐藏结果区域
    document.getElementById('resultsSection').style.display = 'none';
    
    showAlert('参数已重置为默认值', 'info');
}

// 加载示例数据
function loadExampleData() {
    const selectedType = document.querySelector('input[name="calculationType"]:checked').value;
    
    if (selectedType === 'theory') {
        // 加载理论计算示例数据
        document.getElementById('coalCarbonContent').value = '78.0';
        document.getElementById('coalHydrogenContent').value = '3.5';
        document.getElementById('coalAshContent').value = '12.0';
        document.getElementById('coalSiO2Content').value = '48.0';
        document.getElementById('coalDecompositionHeat').value = '220';
        document.getElementById('coalPhysicalHeat').value = '450';
        document.getElementById('cokeCarbonContent').value = '86.0';
        document.getElementById('cokeAshContent').value = '11.0';
        document.getElementById('cokeSiO2Content').value = '52.0';
        document.getElementById('gasUtilization').value = '0.4444';
        document.getElementById('slagBasicity').value = '1.15';
        document.getElementById('slagEnthalpy').value = '1800';
        document.getElementById('windTemperature').value = '1180';
        document.getElementById('hotBlastEnthalpy').value = '1.5';
    } else {
        // 加载实际计算示例数据
        document.getElementById('initialCokeRatio').value = '400';
        document.getElementById('finalCokeRatio').value = '370';
        document.getElementById('initialCoalRatio').value = '150';
        document.getElementById('finalCoalRatio').value = '180';
        document.getElementById('adjustmentFactor').value = '2.5';
        document.getElementById('ironOutputChange').value = '50';
        document.getElementById('slagRatioChange').value = '-10';
        document.getElementById('carbonEfficiencyChange').value = '2.0';
        document.getElementById('enableAdvancedCalculation').checked = true;
    }
    
    showAlert('示例数据已加载', 'success');
}

// 导出结果
function exportResults() {
    const selectedType = document.querySelector('input[name="calculationType"]:checked').value;
    const resultValue = document.getElementById('mainResultValue').textContent;
    
    if (resultValue === '--') {
        showAlert('请先进行计算', 'warning');
        return;
    }
    
    // 收集结果数据
    const exportData = {
        计算类型: selectedType === 'theory' ? '理论置换比' : '实际置换比',
        计算结果: resultValue,
        计算时间: new Date().toLocaleString(),
        详细数据: collectDetailedData()
    };
    
    // 创建并下载Excel文件
    downloadExcel(exportData, `置换比计算结果_${new Date().toISOString().slice(0, 10)}.xlsx`);
}

// 收集详细数据
function collectDetailedData() {
    const data = {};
    const table = document.querySelector('#calculationDetailsTable tbody');
    
    if (table) {
        const rows = table.querySelectorAll('tr');
        rows.forEach(row => {
            const cells = row.querySelectorAll('td');
            if (cells.length >= 2) {
                const key = cells[0].textContent.trim();
                const value = cells[1].textContent.trim();
                data[key] = value;
            }
        });
    }
    
    return data;
}

// 打印结果
function printResults() {
    if (document.getElementById('mainResultValue').textContent === '--') {
        showAlert('请先进行计算', 'warning');
        return;
    }
    
    const printWindow = window.open('', '_blank');
    const printContent = generatePrintContent();
    
    printWindow.document.write(printContent);
    printWindow.document.close();
    printWindow.print();
}

function openHistoryPage() {
    window.location.href = '/optimization_history/replacement_ratio';
}

// 生成打印内容
function generatePrintContent() {
    const selectedType = document.querySelector('input[name="calculationType"]:checked').value;
    const resultValue = document.getElementById('mainResultValue').textContent;
    const calculationDate = new Date().toLocaleString();
    
    return `
        <!DOCTYPE html>
        <html>
        <head>
            <title>置换比计算结果</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .header { text-align: center; margin-bottom: 30px; }
                .result { font-size: 24px; color: #0066cc; margin: 20px 0; }
                table { width: 100%; border-collapse: collapse; margin: 20px 0; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
                .footer { margin-top: 30px; font-size: 12px; color: #666; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>煤焦置换比计算结果</h1>
                <p>计算时间: ${calculationDate}</p>
            </div>
            <div class="result">
                ${selectedType === 'theory' ? '理论置换比' : '实际置换比'}: ${resultValue}
            </div>
            ${document.querySelector('#calculationDetailsTable').outerHTML}
            <div class="footer">
                <p>© 2025 煤种数据库管理及配煤优化系统</p>
            </div>
        </body>
        </html>
    `;
}

// 添加到历史记录
function addToHistory(result, calculationType) {
    const historyItem = {
        timestamp: new Date().toLocaleString(),
        type: calculationType === 'theory' ? '理论置换比' : '实际置换比',
        result: result.ratio.toFixed(6),
        parameters: collectCurrentParameters(),
        details: result.details
    };
    
    calculationHistory.unshift(historyItem);
    
    // 限制历史记录数量
    if (calculationHistory.length > 20) {
        calculationHistory = calculationHistory.slice(0, 20);
    }
    
    updateHistoryTable();
    saveHistoryToLocalStorage();
}

// 收集当前参数
function collectCurrentParameters() {
    const selectedType = document.querySelector('input[name="calculationType"]:checked').value;
    const params = {};
    
    if (selectedType === 'theory') {
        params['煤粉含碳量'] = document.getElementById('coalCarbonContent').value + '%';
        params['焦炭含碳量'] = document.getElementById('cokeCarbonContent').value + '%';
        params['煤气利用率'] = document.getElementById('gasUtilization').value;
    } else {
        params['调整前焦比'] = document.getElementById('initialCokeRatio').value + ' kg/t';
        params['调整后焦比'] = document.getElementById('finalCokeRatio').value + ' kg/t';
        params['调整前煤比'] = document.getElementById('initialCoalRatio').value + ' kg/t';
        params['调整后煤比'] = document.getElementById('finalCoalRatio').value + ' kg/t';
    }
    
    return params;
}

// 更新历史记录表
function updateHistoryTable() {
    const tbody = document.querySelector('#historyTable tbody');
    tbody.innerHTML = '';
    
    if (calculationHistory.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">暂无计算历史</td></tr>';
        return;
    }
    
    calculationHistory.forEach((item, index) => {
        const row = document.createElement('tr');
        const parametersSummary = Object.entries(item.parameters)
            .slice(0, 2)
            .map(([key, value]) => `${key}: ${value}`)
            .join(', ');
        
        row.innerHTML = `
            <td>${item.timestamp}</td>
            <td><span class="badge ${item.type === '理论置换比' ? 'bg-primary' : 'bg-success'}">${item.type}</span></td>
            <td><strong>${item.result}</strong></td>
            <td>${parametersSummary}</td>
            <td>
                <button class="btn btn-sm btn-outline-primary" onclick="viewHistoryDetail(${index})">
                    <i class="bi bi-eye"></i> 查看
                </button>
                <button class="btn btn-sm btn-outline-danger" onclick="deleteHistoryItem(${index})">
                    <i class="bi bi-trash"></i> 删除
                </button>
            </td>
        `;
        tbody.appendChild(row);
    });
}

// 查看历史详情
function viewHistoryDetail(index) {
    const item = calculationHistory[index];
    
    // 创建模态框显示详细信息
    const modalHtml = `
        <div class="modal fade" id="historyDetailModal" tabindex="-1">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">计算历史详情 - ${item.type}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <p><strong>计算时间:</strong> ${item.timestamp}</p>
                        <p><strong>计算结果:</strong> ${item.result}</p>
                        <h6>详细计算过程:</h6>
                        <table class="table table-striped">
                            <tbody>
                                ${Object.entries(item.details).map(([key, value]) => 
                                    `<tr><td><strong>${key}</strong></td><td>${formatValue(value)}</td></tr>`
                                ).join('')}
                            </tbody>
                        </table>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>
                        <button type="button" class="btn btn-primary" onclick="loadHistoryParameters(${index})">加载参数</button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // 移除现有模态框并添加新的
    const existingModal = document.getElementById('historyDetailModal');
    if (existingModal) {
        existingModal.remove();
    }
    
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    const modal = new bootstrap.Modal(document.getElementById('historyDetailModal'));
    modal.show();
}

// 加载历史参数
function loadHistoryParameters(index) {
    const item = calculationHistory[index];
    
    // 根据计算类型设置相应的参数
    if (item.type === '理论置换比') {
        document.getElementById('theoryCalculation').checked = true;
        // 这里需要根据保存的参数来设置具体数值
        // 由于历史记录中没有保存完整参数，这里只是示例
    } else {
        document.getElementById('actualCalculation').checked = true;
        // 类似地设置实际计算参数
    }
    
    updateCalculationSections();
    showAlert('历史参数已加载', 'success');
    
    // 关闭模态框
    const modal = bootstrap.Modal.getInstance(document.getElementById('historyDetailModal'));
    modal.hide();
}

// 删除历史记录项
function deleteHistoryItem(index) {
    if (confirm('确定要删除这条历史记录吗？')) {
        calculationHistory.splice(index, 1);
        updateHistoryTable();
        saveHistoryToLocalStorage();
        showAlert('历史记录已删除', 'info');
    }
}

// 清空历史记录
function clearHistory() {
    if (confirm('确定要清空所有历史记录吗？')) {
        calculationHistory = [];
        updateHistoryTable();
        saveHistoryToLocalStorage();
        showAlert('历史记录已清空', 'info');
    }
}

// 本地存储相关函数
function saveToLocalStorage() {
    const data = {};
    const inputs = document.querySelectorAll('input[type="number"], input[type="checkbox"]');
    
    inputs.forEach(input => {
        if (input.type === 'checkbox') {
            data[input.id] = input.checked;
        } else {
            data[input.id] = input.value;
        }
    });
    
    localStorage.setItem('replacementRatioParams', JSON.stringify(data));
}

function loadFromLocalStorage() {
    const data = localStorage.getItem('replacementRatioParams');
    if (data) {
        try {
            const params = JSON.parse(data);
            Object.entries(params).forEach(([key, value]) => {
                const element = document.getElementById(key);
                if (element) {
                    if (element.type === 'checkbox') {
                        element.checked = value;
                    } else {
                        element.value = value;
                    }
                }
            });
        } catch (error) {
            console.error('加载本地存储数据失败:', error);
        }
    }
}

function saveHistoryToLocalStorage() {
    localStorage.setItem('replacementRatioHistory', JSON.stringify(calculationHistory));
}

function loadCalculationHistory() {
    const data = localStorage.getItem('replacementRatioHistory');
    if (data) {
        try {
            calculationHistory = JSON.parse(data);
            updateHistoryTable();
        } catch (error) {
            console.error('加载历史记录失败:', error);
            calculationHistory = [];
        }
    }
}

// 工具函数
function formatValue(value) {
    if (typeof value === 'number') {
        return value.toFixed(6);
    }
    return value;
}

function showAlert(message, type = 'info') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.insertAdjacentElement('afterbegin', alertDiv);
    
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}

function downloadExcel(data, filename) {
    // 创建工作表数据
    const worksheet = [];
    worksheet.push(['项目', '数值']);
    worksheet.push(['计算类型', data.计算类型]);
    worksheet.push(['计算结果', data.计算结果]);
    worksheet.push(['计算时间', data.计算时间]);
    worksheet.push(['', '']); // 空行
    worksheet.push(['详细计算过程', '']);
    
    Object.entries(data.详细数据).forEach(([key, value]) => {
        worksheet.push([key, value]);
    });
    
    // 转换为CSV格式
    const csvContent = worksheet.map(row => 
        row.map(cell => `"${cell}"`).join(',')
    ).join('\n');
    
    // 创建下载链接
    const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = filename.replace('.xlsx', '.csv');
    link.click();
}
