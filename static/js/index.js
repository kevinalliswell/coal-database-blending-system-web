// 首页JavaScript文件

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    initializeHomePage();
});

// 初始化首页
function initializeHomePage() {
    loadSystemStatistics();
    loadRecentActivities();
}

// 加载系统统计
async function loadSystemStatistics() {
    try {
        // 加载煤种总数
        const response = await fetch('/api/coals?page_size=0');
        const result = await response.json();
        
        if (result.status === 'success') {
            document.getElementById('totalCoals').textContent = result.pagination.total;
        }
        
        // 模拟其他统计数据
        document.getElementById('totalOptimizations').textContent = '156';
        document.getElementById('totalCalculations').textContent = '89';
        document.getElementById('avgTime').textContent = '12.5';
        
    } catch (error) {
        console.error('加载统计数据失败:', error);
        // 显示默认值
        document.getElementById('totalCoals').textContent = '--';
        document.getElementById('totalOptimizations').textContent = '--';
        document.getElementById('totalCalculations').textContent = '--';
        document.getElementById('avgTime').textContent = '--';
    }
}

// 加载最近活动
function loadRecentActivities() {
    // 模拟最近活动数据
    const activities = [
        {
            type: 'optimization',
            title: '完成智能混煤优化',
            description: '优化了3种煤的配比，获得最优方案',
            time: '2小时前',
            icon: 'bi-cpu-fill',
            color: 'text-success'
        },
        {
            type: 'coal_add',
            title: '添加新煤种',
            description: '添加了"神华洗精煤"数据',
            time: '4小时前',
            icon: 'bi-plus-circle-fill',
            color: 'text-primary'
        },
        {
            type: 'calculation',
            title: '置换比计算',
            description: '计算了理论置换比87.5%',
            time: '6小时前',
            icon: 'bi-calculator-fill',
            color: 'text-warning'
        },
        {
            type: 'export',
            title: '导出优化报告',
            description: '导出了Excel格式的优化报告',
            time: '1天前',
            icon: 'bi-download',
            color: 'text-info'
        }
    ];
    
    const activitiesContainer = document.getElementById('recentActivities');
    activitiesContainer.innerHTML = '';
    
    activities.forEach(activity => {
        const activityItem = document.createElement('div');
        activityItem.className = 'list-group-item list-group-item-action';
        activityItem.innerHTML = `
            <div class="d-flex w-100 justify-content-between">
                <div class="d-flex align-items-center">
                    <i class="bi ${activity.icon} ${activity.color} me-3"></i>
                    <div>
                        <h6 class="mb-1">${activity.title}</h6>
                        <p class="mb-0 text-muted small">${activity.description}</p>
                    </div>
                </div>
                <small class="text-muted">${activity.time}</small>
            </div>
        `;
        activitiesContainer.appendChild(activityItem);
    });
}

// 检查更新
function checkForUpdates() {
    // 模拟检查更新
    const button = event.target;
    const originalText = button.innerHTML;
    
    button.disabled = true;
    button.innerHTML = '<i class="bi bi-hourglass-split me-1"></i>检查中...';
    
    setTimeout(() => {
        button.disabled = false;
        button.innerHTML = originalText;
        alert('系统已是最新版本！');
    }, 2000);
}

// 定期刷新统计数据（每5分钟）
setInterval(loadSystemStatistics, 5 * 60 * 1000); 