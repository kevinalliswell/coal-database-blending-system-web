// 置换比计算页面JavaScript文件

// 全局变量
let contributionChart = null;
let ratioProgressTimer = null;

// DOM加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    initializePage();
    bindEvents();
    loadFromLocalStorage();
});

// 初始化页面
function initializePage() {
    // 初始化计算类型切换
    updateCalculationSections({ keepResults: true });
    
    // 初始化图表
    initializeChart();

    setRatioStatus('info', '选择计算模式并确认参数后即可开始。', '参数会自动保存在本地浏览器，方便下一次继续计算。');
}

// 绑定事件
function bindEvents() {
    // 计算类型切换
    const calculationTypeRadios = document.querySelectorAll('input[name="calculationType"]');
    calculationTypeRadios.forEach(radio => {
        radio.addEventListener('change', () => {
            updateCalculationSections();
            saveToLocalStorage();
        });
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
        input.addEventListener('input', () => {
            saveToLocalStorage();
            markParametersDirty();
        });
    });

    const checkboxInputs = document.querySelectorAll('input[type="checkbox"]');
    checkboxInputs.forEach(input => {
        input.addEventListener('change', () => {
            saveToLocalStorage();
            markParametersDirty();
        });
    });
}

// 更新计算章节显示
function updateCalculationSections(options = {}) {
    const selectedType = getSelectedCalculationType();
    const theorySection = document.getElementById('theorySection');
    const actualSection = document.getElementById('actualSection');
    const isTheory = selectedType === 'theory';
    const meta = getModeMeta(selectedType);
    
    setElementHidden(theorySection, !isTheory);
    setElementHidden(actualSection, isTheory);

    document.querySelectorAll('[data-mode-card]').forEach(card => {
        card.classList.toggle('is-active', card.dataset.modeCard === selectedType);
    });

    updateTextContent('ratioModeLabel', meta.label);
    updateTextContent('ratioModeHint', meta.hint);
    updateTextContent('ratioModeBadge', meta.badge);

    if (!options.keepStatus) {
        setRatioStatus('info', meta.readyText, meta.readyHint);
    }

    if (!options.keepResults) {
        setElementHidden(document.getElementById('resultsSection'), true);
        updateTextContent('ratioLastResultValue', '--');
        updateTextContent('ratioLastResultLabel', '等待重新计算');
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
    
    if (!Number.isNaN(min) && value < min) {
        showAlert(`输入值不能小于 ${min}`, 'warning');
        input.focus();
        return false;
    }
    
    if (!Number.isNaN(max) && value > max) {
        showAlert(`输入值不能大于 ${max}`, 'warning');
        input.focus();
        return false;
    }
    
    return true;
}

// 执行计算
async function performCalculation() {
    const selectedType = getSelectedCalculationType();
    const calculateBtn = document.getElementById('calculateBtn');

    if (!validateVisibleNumberInputs()) {
        return;
    }
    
    // 显示计算中状态
    setCalculateButtonLoading(true);
    setRatioStatus('info', '正在计算置换比，请稍候。', '系统正在提交参数、等待接口返回并写入历史记录。');
    showRatioProgress(true);
    
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
        setElementHidden(document.getElementById('resultsSection'), false);
        setRatioStatus('success', `${getModeMeta(selectedType).label}计算完成。`, '结果已返回，当前记录已写入置换比历史。');
        showAlert('计算完成，结果已展开。', 'success');
        
        // 滚动到结果区域
        document.getElementById('resultsSection').scrollIntoView({ 
            behavior: 'smooth',
            block: 'start'
        });
        
    } catch (error) {
        showAlert('计算过程中出现错误: ' + error.message, 'danger');
        setRatioStatus('danger', '计算失败，请检查参数或稍后重试。', error.message);
    } finally {
        // 恢复按钮状态
        setCalculateButtonLoading(false);
        showRatioProgress(false);
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
    const ratioText = Number(result.ratio).toFixed(6);

    // 显示主要结果
    document.getElementById('resultTitle').textContent = 
        calculationType === 'theory' ? '理论置换比' : '实际置换比';
    document.getElementById('mainResultValue').textContent = ratioText;
    updateTextContent('ratioLastResultValue', ratioText);
    updateTextContent('ratioLastResultLabel', `${getModeMeta(calculationType).label}最新结果`);
    
    // 显示详细计算过程
    displayCalculationDetails(result.details);
    
    // 更新图表
    updateContributionChart(result.details);
    
    // 显示特定类型的结果
    if (calculationType === 'theory') {
        displayTheoryResults(result);
        setElementHidden(document.getElementById('theoryResults'), false);
        setElementHidden(document.getElementById('actualResults'), true);
    } else {
        displayActualResults(result);
        setElementHidden(document.getElementById('theoryResults'), true);
        setElementHidden(document.getElementById('actualResults'), false);
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
    const canvas = document.getElementById('contributionChart');
    if (!canvas || typeof Chart === 'undefined') {
        return;
    }

    const ctx = canvas.getContext('2d');
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
    if (!contributionChart) {
        return;
    }

    const labels = [];
    const data = [];
    
    // 根据计算类型选择不同的参数
    const selectedType = getSelectedCalculationType();
    
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
    const selectedType = getSelectedCalculationType();
    
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
    setElementHidden(document.getElementById('resultsSection'), true);
    updateTextContent('ratioLastResultValue', '--');
    updateTextContent('ratioLastResultLabel', '等待重新计算');
    saveToLocalStorage();
    setRatioStatus('info', '当前模式参数已重置。', '可以直接开始计算，或先加载示例数据。');
    
    showAlert('参数已重置为默认值', 'info');
}

// 加载示例数据
function loadExampleData() {
    const selectedType = getSelectedCalculationType();
    
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
    
    saveToLocalStorage();
    setRatioStatus('info', '示例数据已加载。', '确认参数后点击开始计算。');
    showAlert('示例数据已加载', 'success');
}

// 导出结果
function exportResults() {
    const selectedType = getSelectedCalculationType();
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
    const selectedType = getSelectedCalculationType();
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

// 本地存储相关函数
function saveToLocalStorage() {
    const data = {
        calculationType: getSelectedCalculationType()
    };
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
            if (params.calculationType) {
                const savedRadio = document.querySelector(`input[name="calculationType"][value="${params.calculationType}"]`);
                if (savedRadio) {
                    savedRadio.checked = true;
                }
            }

            Object.entries(params).forEach(([key, value]) => {
                if (key === 'calculationType') {
                    return;
                }

                const element = document.getElementById(key);
                if (element) {
                    if (element.type === 'checkbox') {
                        element.checked = value;
                    } else {
                        element.value = value;
                    }
                }
            });
            updateCalculationSections({ keepResults: true });
        } catch (error) {
            showAlert('本地参数读取失败，已使用页面默认值', 'warning');
        }
    }
}

// 工具函数
function getSelectedCalculationType() {
    return document.querySelector('input[name="calculationType"]:checked')?.value || 'theory';
}

function getModeMeta(type = getSelectedCalculationType()) {
    if (type === 'actual') {
        return {
            label: '实际置换比',
            hint: '基于焦比、煤比变化和生产修正计算',
            badge: '生产数据模型',
            readyText: '当前为实际置换比模式，请确认生产数据后开始。',
            readyHint: '可启用生产因素修正，纳入产量、渣比和碳效率变化。'
        };
    }

    return {
        label: '理论置换比',
        hint: '基于煤粉、焦炭和高炉工艺参数计算',
        badge: '理论模型',
        readyText: '当前为理论置换比模式，请确认煤粉、焦炭和高炉参数。',
        readyHint: '理论模式会返回碳量平衡、热量平衡和贡献图。'
    };
}

function updateTextContent(id, value) {
    const element = document.getElementById(id);
    if (element) {
        element.textContent = value;
    }
}

function setElementHidden(element, hidden) {
    if (!element) {
        return;
    }

    element.hidden = Boolean(hidden);
}

function setRatioStatus(tone, text, hint) {
    const statusBar = document.getElementById('ratioStatusBar');
    const statusPill = document.getElementById('ratioStatusPill');

    if (statusBar) {
        statusBar.dataset.tone = tone || 'info';
    }

    if (statusPill) {
        statusPill.dataset.tone = tone || 'info';
        statusPill.textContent = getStatusLabel(tone, text);
    }

    updateTextContent('ratioStatusText', text);
    updateTextContent('ratioStatusHint', hint || '');
}

function getStatusLabel(tone, text) {
    if (tone === 'success') {
        return '计算完成';
    }
    if (tone === 'danger') {
        return '计算失败';
    }
    if (tone === 'warning') {
        return '请检查参数';
    }
    return text?.includes('正在') ? '计算中' : '等待计算';
}

function markParametersDirty() {
    setRatioStatus('info', '参数已更新，结果需重新计算。', '点击开始计算后会刷新结果并保存新的历史记录。');
}

function validateVisibleNumberInputs() {
    const inputs = Array.from(document.querySelectorAll('.calculation-section:not([hidden]) input[type="number"]'));
    return inputs.every(input => validateInput({ target: input }));
}

function setCalculateButtonLoading(isLoading) {
    const calculateBtn = document.getElementById('calculateBtn');
    if (!calculateBtn) {
        return;
    }

    calculateBtn.disabled = isLoading;
    calculateBtn.innerHTML = isLoading
        ? '<span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>计算中...'
        : '<i class="bi bi-calculator me-2"></i>开始计算';
}

function showRatioProgress(visible) {
    const panel = document.getElementById('ratioProgressPanel');
    const bar = document.getElementById('ratioProgressBar');
    if (!panel || !bar) {
        return;
    }

    window.clearInterval(ratioProgressTimer);
    ratioProgressTimer = null;

    if (!visible) {
        panel.classList.add('d-none');
        bar.style.width = '16%';
        updateTextContent('ratioProgressTitle', '正在请求计算接口');
        updateTextContent('ratioProgressMeta', '通常几秒内完成');
        return;
    }

    let progress = 16;
    panel.classList.remove('d-none');
    bar.style.width = `${progress}%`;
    updateTextContent('ratioProgressTitle', '正在计算置换比');
    updateTextContent('ratioProgressMeta', '正在处理参数');

    ratioProgressTimer = window.setInterval(() => {
        progress = Math.min(progress + 12, 88);
        bar.style.width = `${progress}%`;
        updateTextContent('ratioProgressMeta', progress >= 70 ? '等待服务端返回结果' : '正在写入计算历史');
    }, 420);
}

function formatValue(value) {
    if (typeof value === 'number') {
        return value.toFixed(6);
    }
    return value;
}

function showAlert(message, type = 'info') {
    const container = getToastContainer();

    if (!window.bootstrap?.Toast) {
        console[type === 'danger' ? 'error' : 'log'](message);
        return;
    }

    const toast = document.createElement('div');
    toast.className = 'toast coal-toast';
    toast.role = 'alert';
    toast.innerHTML = `
        <div class="toast-header">
            <i class="bi bi-info-circle text-${type} me-2"></i>
            <strong class="me-auto">系统提示</strong>
            <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
        <div class="toast-body">${escapeHtml(message)}</div>
    `;

    container.appendChild(toast);
    toast.addEventListener('hidden.bs.toast', () => toast.remove());
    bootstrap.Toast.getOrCreateInstance(toast, { delay: type === 'danger' ? 5200 : 3200 }).show();
}

function getToastContainer() {
    let container = document.getElementById('replacementRatioToastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'replacementRatioToastContainer';
        container.className = 'toast-container position-fixed top-0 end-0 p-3';
        document.body.appendChild(container);
    }
    return container;
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
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
