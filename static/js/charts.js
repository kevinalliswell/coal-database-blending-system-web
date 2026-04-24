// 图表初始化和管理
function initializeCharts() {
    // 配比饼图
    initRatioChart();
    
    // 性能雷达图
    initPerformanceChart();
    
    // 约束满足条形图
    initConstraintChart();
}

// 初始化配比饼图
function initRatioChart() {
    const ratioCtx = document.createElement('canvas');
    document.getElementById('ratioChart').innerHTML = '';
    document.getElementById('ratioChart').appendChild(ratioCtx);
    
    new Chart(ratioCtx, {
        type: 'pie',
        data: {
            labels: ['包钢矿业洗末煤 S1.0', '昊华1#烟煤'],
            datasets: [{
                data: [65.39, 34.61],
                backgroundColor: ['#1e40af', '#f97316'],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

// 初始化性能雷达图
function initPerformanceChart() {
    const performanceCtx = document.createElement('canvas');
    document.getElementById('performanceChart').innerHTML = '';
    document.getElementById('performanceChart').appendChild(performanceCtx);
    
    new Chart(performanceCtx, {
        type: 'radar',
        data: {
            labels: ['热值', '灰分', '挥发分', '固定碳', '硫含量', '价格'],
            datasets: [{
                label: '混煤性能',
                data: [0.86, 0.35, 0.46, 0.87, 0.21, 0.25],
                backgroundColor: 'rgba(14, 165, 233, 0.2)',
                borderColor: 'rgba(14, 165, 233, 1)',
                pointBackgroundColor: 'rgba(14, 165, 233, 1)',
                pointBorderColor: '#fff',
                pointHoverBackgroundColor: '#fff',
                pointHoverBorderColor: 'rgba(14, 165, 233, 1)'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                r: {
                    angleLines: {
                        display: true
                    },
                    suggestedMin: 0,
                    suggestedMax: 1
                }
            }
        }
    });
}

// 初始化约束满足条形图
function initConstraintChart() {
    const constraintCtx = document.createElement('canvas');
    document.getElementById('constraintChart').innerHTML = '';
    document.getElementById('constraintChart').appendChild(constraintCtx);
    
    new Chart(constraintCtx, {
        type: 'bar',
        data: {
            labels: ['热值', '灰分', '挥发分', '固定碳', '硫含量', '价格'],
            datasets: [{
                label: '约束满足度',
                data: [100, 90, 95, 85, 99, 80],
                backgroundColor: [
                    'rgba(16, 185, 129, 0.7)',
                    'rgba(16, 185, 129, 0.7)',
                    'rgba(16, 185, 129, 0.7)',
                    'rgba(16, 185, 129, 0.7)',
                    'rgba(16, 185, 129, 0.7)',
                    'rgba(16, 185, 129, 0.7)'
                ],
                borderColor: [
                    'rgba(16, 185, 129, 1)',
                    'rgba(16, 185, 129, 1)',
                    'rgba(16, 185, 129, 1)',
                    'rgba(16, 185, 129, 1)',
                    'rgba(16, 185, 129, 1)',
                    'rgba(16, 185, 129, 1)'
                ],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    title: {
                        display: true,
                        text: '满足度 (%)'
                    }
                }
            }
        }
    });
}

// 导出图表为图片
function exportChart(chartId, fileName) {
    const canvas = document.querySelector(`#${chartId} canvas`);
    if (!canvas) return;
    
    const link = document.createElement('a');
    link.download = fileName;
    link.href = canvas.toDataURL('image/png');
    link.click();
}

// 更新图表数据
function updateChartData(chartId, newData) {
    const chartContainer = document.getElementById(chartId);
    if (!chartContainer) return;
    
    const canvas = chartContainer.querySelector('canvas');
    if (!canvas) return;
    
    const chart = Chart.getChart(canvas);
    if (!chart) return;
    
    chart.data = newData;
    chart.update();
}
