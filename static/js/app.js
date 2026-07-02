/**
 * 车辆调度AI算法评测系统 - 前端主应用
 */

const API_BASE = '/api';

// 全局错误处理
window.onerror = function(msg, url, line, col, error) {
    console.error('Global error:', msg, url, line, col, error);
    alert('JS错误: ' + msg + ' (行' + line + ')');
    return false;
};

let currentMapData = null;
let currentTasksData = null;
let currentLocomotivesData = null;
let currentHyperParams = null;
let currentScheduleResult = null;
let isScheduleRunning = false;
let scheduleCompleted = false;
let isScheduleRequesting = false; // 防止重复请求
let isScheduleComputed = false; // 是否已完成算法运算
let isSchedulePlaying = false; // 防止重复播放

document.addEventListener('DOMContentLoaded', () => {
    try {
        initTabs();
        initMap();
        loadAllData();
        loadStrategies();
        loadBatchIds();
        
        // 绑定地图按钮
        const computeBtn = document.getElementById('mapComputeBtn');
        if (computeBtn) {
            computeBtn.addEventListener('click', mapComputeSchedule);
        }
        const runBtn = document.getElementById('mapRunBtn');
        if (runBtn) {
            runBtn.addEventListener('click', mapPlaySchedule);
        }
        const pauseBtn = document.getElementById('mapPauseBtn');
        if (pauseBtn) pauseBtn.addEventListener('click', mapPauseSchedule);
        const resumeBtn = document.getElementById('mapResumeBtn');
        if (resumeBtn) resumeBtn.addEventListener('click', mapResumeSchedule);
        const stopBtn = document.getElementById('mapStopBtn');
        if (stopBtn) stopBtn.addEventListener('click', mapStopSchedule);
    } catch (e) {
        console.error('DOMContentLoaded error:', e);
        alert('页面初始化错误: ' + e.message);
    }
});

function initTabs() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabId = btn.dataset.tab;

            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));

            btn.classList.add('active');
            document.getElementById(`tab-${tabId}`).classList.add('active');

            if (tabId === 'tasks') loadTasks();
            if (tabId === 'locomotives') loadLocomotives();
            if (tabId === 'history') loadHistory();
            if (tabId === 'logs') loadLogs();
            if (tabId === 'scheduling') loadHyperParams();
        });
    });
}

async function apiCall(url, method = 'GET', data = null) {
    const fullUrl = API_BASE + url;
    console.log('[apiCall]', method, fullUrl, data);
    try {
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json'
            }
        };
        if (data) {
            options.body = JSON.stringify(data);
        }
        const response = await fetch(fullUrl, options);
        const result = await response.json();
        console.log('[apiCall] response:', result.success ? 'success' : 'failed');
        return result;
    } catch (error) {
        console.error('API调用失败:', error);
        return { success: false, error: error.message };
    }
}

async function loadAllData() {
    await Promise.all([
        loadMapConfig(),
        loadTasksData(),
        loadLocomotivesData(),
        loadHyperParams()
    ]);
    updateVehicleStatusPanel();
}

async function loadMapConfig() {
    const result = await apiCall('/config/map');
    if (result.success && result.data) {
        currentMapData = result.data;
        if (dynamicMap) {
            dynamicMap.setData(result.data.nodes || [], result.data.edges || []);
        }
    }
    return result;
}

async function loadTasksData() {
    const result = await apiCall('/config/tasks');
    if (result.success && result.data) {
        currentTasksData = result.data;
    }
    return result;
}

async function loadLocomotivesData() {
    const result = await apiCall('/config/locomotives');
    if (result.success && result.data) {
        currentLocomotivesData = result.data;
        if (dynamicMap) {
            dynamicMap.setVehicles(result.data.locomotives || []);
        }
    }
    return result;
}

async function loadHyperParams() {
    const result = await apiCall('/config/hyper-params');
    if (result.success && result.data) {
        currentHyperParams = result.data;
        renderHyperParamsForm(result.data);
    }
    return result;
}

function renderHyperParamsForm(params) {
    const form = document.getElementById('hyperParamsForm');
    if (!form) return;

    const labels = {
        travel_time_precision: '行程时间精度(分钟)',
        default_priority: '默认优先级',
        BigM: 'BigM值',
        slope_factor_uphill: '上坡减速因子',
        slope_factor_downhill: '下坡加速因子',
        switch_pass_time: '道岔通过时间',
        loading_time: '装货时间(分钟)',
        unloading_time: '卸货时间(分钟)',
        battery_low_threshold: '电量低阈值(kWh)',
        fuel_low_threshold: '油量低阈值(L)',
        energy_consumption_rate: '能源消耗率'
    };

    form.innerHTML = Object.entries(params).map(([key, value]) => `
        <div class="form-item">
            <label>${labels[key] || key}</label>
            <input type="number" id="hp_${key}" value="${value}" step="any">
        </div>
    `).join('');
}

async function saveHyperParams() {
    const params = {};
    document.querySelectorAll('[id^="hp_"]').forEach(input => {
        const key = input.id.replace('hp_', '');
        params[key] = parseFloat(input.value) || 0;
    });

    const result = await apiCall('/config/hyper-params', 'POST', params);
    if (result.success) {
        alert('超参数保存成功');
    } else {
        alert('保存失败: ' + result.error);
    }
}

function updateVehicleStatusPanel() {
    const panel = document.getElementById('vehicleStatusList');
    if (!panel || !currentLocomotivesData) return;

    const locos = currentLocomotivesData.locomotives || [];
    if (locos.length === 0) {
        panel.innerHTML = '<p class="text-muted">暂无车辆数据</p>';
        return;
    }

    panel.innerHTML = locos.map(loco => {
        const isElectric = loco.traction_type === 'electric';
        const energy = isElectric ? loco.battery : loco.fuel_tank;
        const maxEnergy = isElectric ? 1000 : 500;
        const energyPercent = Math.min(100, (energy / maxEnergy) * 100);
        const isBusy = loco.current_task !== null && loco.current_task !== undefined;
        const statusText = isBusy ? '执行中' : (loco.is_schedulable ? '空闲' : '不可调度');
        const statusClass = isBusy ? 'status-busy' : 'status-idle';

        return `
            <div class="vehicle-card">
                <div class="vehicle-card-header">
                    <span class="vehicle-id">${loco.id}</span>
                    <span class="vehicle-type ${loco.traction_type}">${isElectric ? '电车' : '油车'}</span>
                </div>
                <div class="vehicle-status">
                    状态: <span class="status-badge ${statusClass}">${statusText}</span>
                </div>
                <div class="vehicle-status">
                    位置: ${loco.initial_node || '未知'}
                </div>
                <div class="vehicle-status">
                    载重: ${loco.Q}吨 | 速度: ${loco.max_speed}m/min
                </div>
                ${loco.current_task ? `<div class="vehicle-status">任务: ${loco.current_task} (${loco.task_phase || '-'})</div>` : ''}
                <div class="energy-bar">
                    <div class="energy-fill ${loco.traction_type}" style="width: ${energyPercent}%"></div>
                </div>
                <div style="font-size:11px;color:#999;margin-top:4px;">
                    ${isElectric ? '电量' : '油量'}: ${energy} ${isElectric ? 'kWh' : 'L'}
                </div>
            </div>
        `;
    }).join('');
}

async function loadStrategies() {
    const result = await apiCall('/strategies');
    if (result.success && result.data) {
        const select = document.getElementById('strategySelect');
        if (select) {
            select.innerHTML = Object.entries(result.data).map(([key, info]) =>
                `<option value="${key}">${info.name}</option>`
            ).join('');
        }
    }
}

async function loadTasks() {
    const result = await apiCall('/config/tasks');
    if (result.success && result.data) {
        currentTasksData = result.data;
        renderTasksList(result.data.tasks || []);
    }
}

function renderTasksList(tasks) {
    const list = document.getElementById('tasksList');
    if (!list) return;

    const typeFilter = document.getElementById('taskTypeFilter')?.value || '';
    const statusFilter = document.getElementById('taskStatusFilter')?.value || '';

    const filtered = tasks.filter(t => {
        if (typeFilter && t.task_type !== typeFilter) return false;
        if (statusFilter && t.status !== statusFilter) return false;
        return true;
    });

    if (filtered.length === 0) {
        list.innerHTML = '<p class="text-muted">暂无任务</p>';
        return;
    }

    list.innerHTML = filtered.map(task => `
        <div class="task-item">
            <div class="task-header">
                <span class="task-id">${task.id} ${task.name || ''}</span>
                <div>
                    <span class="task-type ${task.task_type}">${getTaskTypeText(task.task_type)}</span>
                    <span class="priority-badge">P${task.priority}</span>
                </div>
            </div>
            <div class="task-details">
                <div>状态: ${getStatusText(task.status)}</div>
                <div>路径: ${task.start_node} → ${task.end_node}</div>
                <div>物料: ${task.material_weight}吨</div>
                ${task.depends_on && task.depends_on.length > 0 ? `<div>依赖: ${task.depends_on.join(', ')}</div>` : ''}
                ${task.bound_locomotive ? `<div>绑定机车: ${task.bound_locomotive}</div>` : ''}
            </div>
        </div>
    `).join('');
}

function getTaskTypeText(type) {
    const map = { normal: '普通', temporary: '临时', emergency: '紧急' };
    return map[type] || type;
}

function getStatusText(status) {
    const map = { pending: '待执行', running: '执行中', paused: '已暂停', completed: '已完成' };
    return map[status] || status;
}

async function loadLocomotives() {
    const result = await apiCall('/config/locomotives');
    if (result.success && result.data) {
        currentLocomotivesData = result.data;
        renderLocomotivesList(result.data.locomotives || []);
    }
}

function renderLocomotivesList(locomotives) {
    const list = document.getElementById('locomotive-list');
    if (!list) {
        // fallback: try old ID
        const oldList = document.getElementById('locomotivesList');
        if (oldList) {
            return renderLocomotivesListOld(locomotives, oldList);
        }
        return;
    }

    if (locomotives.length === 0) {
        list.innerHTML = '<p class="text-muted">暂无机车</p>';
        return;
    }

    list.innerHTML = locomotives.map(loco => {
        const isElectric = loco.traction_type === 'electric';
        return `
            <div class="loco-item">
                <div class="loco-header">
                    <span class="task-id">${loco.id}</span>
                    <span class="vehicle-type ${loco.traction_type}">${isElectric ? '电动机车' : '柴油机车'}</span>
                    <button class="btn btn-sm btn-primary" onclick="editLocomotive('${loco.id}')">编辑</button>
                </div>
                <div class="loco-details">
                    <div>最大速度: ${loco.max_speed} m/min</div>
                    <div>载重能力: ${loco.Q} 吨</div>
                    <div>当前位置: ${loco.initial_node}</div>
                    <div>状态: ${loco.is_powered_on ? '🟢 开机' : '🔴 关机'} | ${loco.is_schedulable ? '可调度' : '不可调度'}</div>
                    ${isElectric ? `<div>电池: ${loco.battery} kWh</div>` : `<div>油量: ${loco.fuel_tank} L</div>`}
                    ${loco.current_task ? `<div>当前任务: ${loco.current_task} (${loco.task_phase || '-'})</div>` : ''}
                </div>
            </div>
        `;
    }).join('');
}

function renderLocomotivesListOld(locomotives, list) {
    if (locomotives.length === 0) {
        list.innerHTML = '<p class="text-muted">暂无机车</p>';
        return;
    }

    list.innerHTML = locomotives.map(loco => {
        const isElectric = loco.traction_type === 'electric';
        return `
            <div class="loco-item">
                <div class="loco-header">
                    <span class="task-id">${loco.id}</span>
                    <span class="vehicle-type ${loco.traction_type}">${isElectric ? '电动机车' : '柴油机车'}</span>
                    <button class="btn btn-sm btn-primary" onclick="editLocomotive('${loco.id}')">编辑</button>
                </div>
                <div class="loco-details">
                    <div>最大速度: ${loco.max_speed} m/min</div>
                    <div>载重能力: ${loco.Q} 吨</div>
                    <div>当前位置: ${loco.initial_node}</div>
                    <div>状态: ${loco.is_powered_on ? '电机' : '关机'} | ${loco.is_schedulable ? '可调度' : '不可调度'}</div>
                    ${isElectric ? `<div>电池: ${loco.battery} kWh</div>` : `<div>油量: ${loco.fuel_tank} L</div>`}
                    ${loco.current_task ? `<div>当前任务: ${loco.current_task} (${loco.task_phase || '-'})</div>` : ''}
                </div>
            </div>
        `;
    }).join('');
}

async function runSchedule() {
    const strategy = document.getElementById('strategySelect').value;
    const useHotStart = document.getElementById('hotStartCheck').checked;

    const resultDiv = document.getElementById('scheduleResult');
    resultDiv.innerHTML = '<p>⏳ 正在调度求解中...</p>';

    const result = await apiCall('/schedule/run', 'POST', {
        strategy,
        use_hot_start: useHotStart
    });

    if (result.success && result.data) {
        currentScheduleResult = result.data;
        document.getElementById('currentBatch').textContent = `批次: ${result.data.batch_id || '-'}`;
        renderScheduleResult(result.data);

        if (result.data.assignments && result.data.assignments.length > 0 && dynamicMap) {
            dynamicMap.playSchedule(result.data.assignments);
            isScheduleRunning = true;
        }
    } else {
        resultDiv.innerHTML = `<p style="color:red;">❌ 调度失败: ${result.error}</p>`;
    }
}

function renderScheduleResult(result) {
    const resultDiv = document.getElementById('scheduleResult');
    if (!resultDiv) {
        console.error('[renderScheduleResult] scheduleResult div not found');
        return;
    }

    // 确保dashboard tab是激活的
    const dashboardTab = document.getElementById('tab-dashboard');
    if (dashboardTab && !dashboardTab.classList.contains('active')) {
        dashboardTab.classList.add('active');
    }

    // 显示结果面板
    resultDiv.style.display = 'block';

    const assignments = result.assignments || [];

    let html = `
        <div class="result-summary">
            <div class="result-card">
                <div class="value">${result.makespan || 0}</div>
                <div class="label">总工期(分钟)</div>
            </div>
            <div class="result-card">
                <div class="value">${result.num_tasks || 0}</div>
                <div class="label">任务数</div>
            </div>
            <div class="result-card">
                <div class="value">${result.solve_time || 0}s</div>
                <div class="label">求解时间</div>
            </div>
            <div class="result-card">
                <div class="value">${result.solve_status || '-'}</div>
                <div class="label">求解状态</div>
            </div>
        </div>
    `;

    if (assignments.length > 0) {
        try {
            const makespan = result.makespan || 100;
            const locoAssignments = {};
            assignments.forEach(a => {
                const lid = a.locomotive_id || '未知';
                if (!locoAssignments[lid]) {
                    locoAssignments[lid] = [];
                }
                locoAssignments[lid].push(a);
            });

            html += '<div class="timeline">';
            Object.entries(locoAssignments).forEach(([locoId, tasks]) => {
                html += `
                    <div class="timeline-loco">
                        <div class="timeline-loco-name">${locoId}</div>
                        <div class="timeline-bar">
                `;
                const colors = ['#667eea', '#f59e0b', '#10b981', '#ef4444', '#8b5cf6', '#06b6d4'];
                tasks.forEach((task, idx) => {
                    const st = task.start_time || 0;
                    const ue = task.unloading_end || (st + 1);
                    const left = Math.max(0, (st / makespan) * 100);
                    const width = Math.max(1, ((ue - st) / makespan) * 100);
                    const color = colors[idx % colors.length];
                    html += `
                        <div class="timeline-task" style="left:${left}%;width:${width}%;background:${color};"
                             title="${task.task_id || '-'}: ${st}-${ue}">
                            ${task.task_id || '-'}
                        </div>
                    `;
                });
                html += '</div></div>';
            });
            html += '</div>';
        } catch (e) {
            console.error('[renderScheduleResult] timeline error:', e);
            html += '<p style="color:red;">时间线渲染失败: ' + e.message + '</p>';
        }
    }

    html += '<h4 style="margin-top:20px;margin-bottom:10px;">任务分配详情</h4>';
    html += '<table class="comparison-table"><tr><th>任务ID</th><th>机车</th><th>开始</th><th>装货结束</th><th>运输结束</th><th>卸货结束</th></tr>';
    try {
        assignments.forEach(a => {
            html += `<tr><td>${a.task_id || '-'}</td><td>${a.locomotive_id || '-'}</td><td>${a.start_time !== undefined ? a.start_time : '-'}</td><td>${a.loading_end !== undefined ? a.loading_end : '-'}</td><td>${a.transport_end !== undefined ? a.transport_end : '-'}</td><td>${a.unloading_end !== undefined ? a.unloading_end : '-'}</td></tr>`;
        });
    } catch (e) {
        console.error('[renderScheduleResult] table error:', e);
        html += `<tr><td colspan="6" style="color:red;">表格渲染失败: ${e.message}</td></tr>`;
    }
    html += '</table>';

    resultDiv.innerHTML = html;
    console.log('[renderScheduleResult] rendered', assignments.length, 'tasks');
}

function pauseSchedule() {
    if (dynamicMap) {
        dynamicMap.pauseSchedule();
        isScheduleRunning = false;
    }
}

function resumeSchedule() {
    if (dynamicMap) {
        dynamicMap.resumeSchedule();
        isScheduleRunning = true;
    }
}

async function runComparison() {
    const strategies = Array.from(document.querySelectorAll('.compare-strategy:checked'))
        .map(cb => cb.value);

    if (strategies.length === 0) {
        alert('请至少选择一种策略');
        return;
    }

    const resultDiv = document.getElementById('comparisonResult');
    resultDiv.innerHTML = '<p>⏳ 正在进行多策略对比...</p>';

    const result = await apiCall('/schedule/compare', 'POST', { strategies });

    if (result.success && result.data) {
        renderComparisonResult(result.data);
    } else {
        resultDiv.innerHTML = `<p style="color:red;">❌ 对比失败: ${result.error}</p>`;
    }
}

function renderComparisonResult(comparison) {
    const resultDiv = document.getElementById('comparisonResult');
    if (!resultDiv) return;

    const strategies = comparison.strategies || [];
    const bestStrategy = comparison.best_strategy;
    const fastestStrategy = comparison.fastest_strategy;

    let html = `
        <div class="result-summary">
            <div class="result-card">
                <div class="value">${comparison.best_makespan || '-'}</div>
                <div class="label">最优工期(分钟)</div>
            </div>
            <div class="result-card">
                <div class="value">${bestStrategy || '-'}</div>
                <div class="label">最优策略</div>
            </div>
            <div class="result-card">
                <div class="value">${comparison.fastest_time || '-'}s</div>
                <div class="label">最快求解时间</div>
            </div>
            <div class="result-card">
                <div class="value">${strategies.length}</div>
                <div class="label">对比策略数</div>
            </div>
        </div>
    `;

    html += '<table class="comparison-table"><tr><th>策略</th><th>工期</th><th>求解时间</th><th>任务数</th><th>状态</th></tr>';
    strategies.forEach(s => {
        const isBest = s.name === bestStrategy;
        const isFastest = s.name === fastestStrategy;
        html += `<tr>
            <td>${s.display_name || s.name}
                ${isBest ? '<span class="best-marker">最优</span>' : ''}
                ${isFastest && !isBest ? '<span class="best-marker" style="background:#ff9800;">最快</span>' : ''}
            </td>
            <td>${s.makespan || '-'}</td>
            <td>${s.solve_time !== undefined && s.solve_time !== null ? s.solve_time + 's' : '-'}</td>
            <td>${s.num_tasks || 0}</td>
            <td>${s.solve_status || '-'}</td>
        </tr>`;
    });
    html += '</table>';

    if (comparison.analysis && comparison.analysis.improvements) {
        html += '<h4 style="margin-top:20px;">📊 与基准策略对比分析</h4>';
        html += '<table class="comparison-table"><tr><th>策略</th><th>工期比</th><th>加速比</th><th>工期差</th><th>时间差</th></tr>';
        comparison.analysis.improvements.forEach(imp => {
            html += `<tr>
                <td>${imp.display_name || imp.strategy}</td>
                <td>${imp.makespan_ratio}</td>
                <td>${imp.speedup_ratio}x</td>
                <td>${imp.makespan_diff > 0 ? '+' : ''}${imp.makespan_diff}</td>
                <td>${imp.time_diff > 0 ? '+' : ''}${imp.time_diff.toFixed(2)}s</td>
            </tr>`;
        });
        html += '</table>';
    }

    resultDiv.innerHTML = html;
}

function addNodeModal() {
    showModal('添加节点', `
        <div class="modal-form">
            <label>节点ID<input id="nodeId" placeholder="如: S1"></label>
            <label>节点名称<input id="nodeName" placeholder="可选"></label>
            <label>类型
                <select id="nodeType">
                    <option value="station">车站</option>
                    <option value="fuel_station">加油站</option>
                    <option value="charge_station">充电站</option>
                    <option value="material_station">物料站</option>
                    <option value="switch">道岔</option>
                </select>
            </label>
            <label>X坐标<input type="number" id="nodeX" value="100"></label>
            <label>Y坐标<input type="number" id="nodeY" value="100"></label>
        </div>
    `, async () => {
        const node = {
            id: document.getElementById('nodeId').value,
            name: document.getElementById('nodeName').value,
            type: document.getElementById('nodeType').value,
            x: parseFloat(document.getElementById('nodeX').value),
            y: parseFloat(document.getElementById('nodeY').value)
        };
        const result = await apiCall('/nodes/add', 'POST', node);
        if (result.success) {
            await loadMapConfig();
            closeModal();
        } else {
            alert('添加失败: ' + result.error);
        }
    });
}

function deleteNodeModal() {
    const nodeList = dynamicMap && dynamicMap.nodes ? dynamicMap.nodes : [];
    if (nodeList.length === 0) {
        alert('暂无节点可删除');
        return;
    }
    const options = nodeList.map(n => `<option value="${n.id}">${n.id}${n.name ? ' - ' + n.name : ''}</option>`).join('');
    showModal('删除节点', `
        <div class="modal-form">
            <label>选择节点<select id="deleteNodeId">${options}</select></label>
            <p style="color:#f44336;font-size:12px;margin-top:8px;">删除节点将同时删除相关边，此操作不可撤销。</p>
        </div>
    `, async () => {
        const nodeId = document.getElementById('deleteNodeId').value;
        const result = await apiCall('/nodes/delete', 'POST', { id: nodeId });
        if (result.success) {
            await loadMapConfig();
            closeModal();
        } else {
            alert('删除失败: ' + (result.error || '未知错误'));
        }
    });
}

function addEdgeModal() {
    showModal('添加边', `
        <div class="modal-form">
            <label>起点<input id="edgeFrom" placeholder="节点ID"></label>
            <label>终点<input id="edgeTo" placeholder="节点ID"></label>
            <label>长度(米)<input type="number" id="edgeLength" value="500"></label>
            <label>限速(m/min)<input type="number" id="edgeSpeed" value="600"></label>
            <label>坡度<input type="number" id="edgeSlope" value="0" step="0.01"></label>
            <label>方向
                <select id="edgeDirection">
                    <option value="bidirectional">双向</option>
                    <option value="forward">正向(上行)</option>
                    <option value="backward">反向(下行)</option>
                </select>
            </label>
        </div>
    `, async () => {
        const edge = {
            from: document.getElementById('edgeFrom').value,
            to: document.getElementById('edgeTo').value,
            length: parseFloat(document.getElementById('edgeLength').value),
            speed_limit: parseFloat(document.getElementById('edgeSpeed').value),
            slope: parseFloat(document.getElementById('edgeSlope').value),
            direction: document.getElementById('edgeDirection').value
        };
        const result = await apiCall('/edges/add', 'POST', edge);
        if (result.success) {
            await loadMapConfig();
            closeModal();
        } else {
            alert('添加失败: ' + result.error);
        }
    });
}

function addTaskModal() {
    showModal('添加任务', `
        <div class="modal-form">
            <label>任务ID<input id="taskId" placeholder="如: T001"></label>
            <label>任务名称<input id="taskName" placeholder="可选"></label>
            <label>类型
                <select id="taskType">
                    <option value="normal">普通任务</option>
                    <option value="temporary">临时任务</option>
                    <option value="emergency">紧急任务</option>
                </select>
            </label>
            <label>优先级(1-99,1最高)<input type="number" id="taskPriority" value="50" min="1" max="99"></label>
            <label>起点节点<input id="taskStart" placeholder="节点ID"></label>
            <label>终点节点<input id="taskEnd" placeholder="节点ID"></label>
            <label>物料重量(吨)<input type="number" id="taskWeight" value="10"></label>
            <label>状态
                <select id="taskStatus">
                    <option value="pending">待执行</option>
                    <option value="running">执行中</option>
                    <option value="paused">已暂停</option>
                </select>
            </label>
            <label>依赖任务(逗号分隔)<input id="taskDeps" placeholder="如: T001,T002"></label>
            <label>绑定机车(可选,热启动用)<input id="taskBoundLoco" placeholder="机车ID"></label>
        </div>
    `, async () => {
        const depsStr = document.getElementById('taskDeps').value.trim();
        const depends_on = depsStr ? depsStr.split(',').map(s => s.trim()) : [];
        const boundLoco = document.getElementById('taskBoundLoco').value.trim();

        const task = {
            id: document.getElementById('taskId').value,
            name: document.getElementById('taskName').value,
            task_type: document.getElementById('taskType').value,
            priority: parseInt(document.getElementById('taskPriority').value),
            start_node: document.getElementById('taskStart').value,
            end_node: document.getElementById('taskEnd').value,
            material_weight: parseFloat(document.getElementById('taskWeight').value),
            status: document.getElementById('taskStatus').value,
            depends_on
        };
        if (boundLoco) task.bound_locomotive = boundLoco;

        const result = await apiCall('/tasks/add', 'POST', task);
        if (result.success) {
            await loadTasksData();
            loadTasks();
            closeModal();
        } else {
            alert('添加失败: ' + result.error);
        }
    });
}

function addLocomotiveModal(type) {
    const isElectric = type === 'electric';
    const title = isElectric ? '添加电动机车' : '添加柴油机车';

    showModal(title, `
        <div class="modal-form">
            <label>机车ID<input id="locoId" placeholder="如: L001"></label>
            <label>最大速度(m/min)<input type="number" id="locoSpeed" value="800"></label>
            <label>载重能力(吨)<input type="number" id="locoCapacity" value="50"></label>
            <label>初始位置<input id="locoNode" placeholder="节点ID"></label>
            ${isElectric
                ? '<label>电池容量(kWh)<input type="number" id="locoBattery" value="1000"></label>'
                : '<label>油箱容量(L)<input type="number" id="locoFuel" value="500"></label>'
            }
            <label><input type="checkbox" id="locoPowered" checked> 开机状态</label>
            <label><input type="checkbox" id="locoSchedulable" checked> 可调度</label>
            <label>绑定任务ID(热启动用)<input id="locoTask" placeholder="可选"></label>
            <label>任务阶段
                <select id="locoPhase">
                    <option value="">空闲</option>
                    <option value="going_to_start">前往起点</option>
                    <option value="loading">装货中</option>
                    <option value="transporting">运输中</option>
                    <option value="unloading">卸货中</option>
                </select>
            </label>
        </div>
    `, async () => {
        const loco = {
            id: document.getElementById('locoId').value,
            traction_type: type,
            max_speed: parseFloat(document.getElementById('locoSpeed').value),
            Q: parseFloat(document.getElementById('locoCapacity').value),
            initial_node: document.getElementById('locoNode').value,
            is_powered_on: document.getElementById('locoPowered').checked,
            is_schedulable: document.getElementById('locoSchedulable').checked,
            current_task: document.getElementById('locoTask').value || null,
            task_phase: document.getElementById('locoPhase').value || null
        };
        if (isElectric) {
            loco.battery = parseFloat(document.getElementById('locoBattery').value);
        } else {
            loco.fuel_tank = parseFloat(document.getElementById('locoFuel').value);
        }

        const result = await apiCall('/locomotives/add', 'POST', loco);
        if (result.success) {
            await loadLocomotivesData();
            loadLocomotives();
            updateVehicleStatusPanel();
            closeModal();
        } else {
            alert('添加失败: ' + result.error);
        }
    });
}

function triggerEmergencyModal() {
    showModal('触发紧急任务', `
        <div class="modal-form">
            <label>紧急任务ID<input id="emergencyId" placeholder="如: E001"></label>
            <label>起点节点<input id="emergencyStart" placeholder="节点ID"></label>
            <label>终点节点<input id="emergencyEnd" placeholder="节点ID"></label>
            <label>物料重量(吨)<input type="number" id="emergencyWeight" value="10"></label>
        </div>
        <p style="color:#dc3545;font-size:12px;margin-top:10px;">
            ⚠️ 触发紧急任务将暂停所有非紧急任务，优先执行紧急任务
        </p>
    `, async () => {
        const task = {
            id: document.getElementById('emergencyId').value,
            task_type: 'emergency',
            priority: 1,
            start_node: document.getElementById('emergencyStart').value,
            end_node: document.getElementById('emergencyEnd').value,
            material_weight: parseFloat(document.getElementById('emergencyWeight').value),
            status: 'pending'
        };
        const result = await apiCall('/emergency/trigger', 'POST', task);
        if (result.success) {
            alert(`紧急任务已触发，暂停${result.data.paused_tasks.length}个任务`);
            await loadTasksData();
            loadTasks();
            closeModal();
        } else {
            alert('触发失败: ' + result.error);
        }
    });
}

function boostPriorityModal() {
    showModal('提升任务优先级', `
        <div class="modal-form">
            <label>任务ID<input id="boostTaskId" placeholder="任务ID"></label>
            <label>提升幅度(数值越小优先级越高)<input type="number" id="boostAmount" value="10" min="1"></label>
        </div>
    `, async () => {
        const taskId = document.getElementById('boostTaskId').value;
        const boostAmount = parseInt(document.getElementById('boostAmount').value);
        const result = await apiCall('/tasks/boost-priority', 'POST', {
            task_id: taskId,
            boost_amount: boostAmount
        });
        if (result.success) {
            alert(`优先级提升: ${result.data.old_priority} → ${result.data.new_priority}`);
            await loadTasksData();
            loadTasks();
            closeModal();
        } else {
            alert('提升失败: ' + result.error);
        }
    });
}

async function checkDirectionLock() {
    const direction = document.getElementById('directionSelect').value;
    const result = await apiCall('/direction/check?direction=' + direction);
    const statusEl = document.getElementById('directionStatus');
    if (result.success && result.data) {
        const isAvail = result.data.is_available;
        statusEl.textContent = `方向状态: ${isAvail ? '可用' : '占用中'}`;
        statusEl.className = `direction-status ${isAvail ? '' : 'locked'}`;

        if (dynamicMap) {
            const lock = result.data.lock_status || { up: false, down: false };
            dynamicMap.setDirectionLock(lock.up, lock.down);
        }
    }
}

async function loadBatchIds() {
    const result = await apiCall('/batch-ids');
    if (result.success && result.data) {
        const select = document.getElementById('historyBatchSelect');
        if (select) {
            select.innerHTML = '<option value="">选择批次</option>' +
                result.data.map(id => `<option value="${id}">${id}</option>`).join('');
        }
    }
}

async function loadHistory() {
    const result = await apiCall('/query/runs?page=1&page_size=20');
    if (result.success && result.data) {
        renderHistoryList(result.data.data || []);
        renderPagination('historyPagination', result.data, (page) => loadHistoryPage(page));
    }
}

function loadHistoryPage(page) {
    apiCall('/query/runs?page=' + page + '&page_size=20').then(result => {
        if (result.success && result.data) {
            renderHistoryList(result.data.data || []);
            renderPagination('historyPagination', result.data, (p) => loadHistoryPage(p));
        }
    });
}

function renderHistoryList(runs) {
    const list = document.getElementById('historyList');
    if (!list) return;

    if (runs.length === 0) {
        list.innerHTML = '<p class="text-muted">暂无历史记录</p>';
        return;
    }

    list.innerHTML = runs.map(run => `
        <div class="history-item" id="history-item-${run.id}">
            <div class="task-item" onclick="toggleHistoryDetail(${run.id})" style="cursor:pointer;">
                <div class="task-header">
                    <span class="task-id">${run.batch_id}</span>
                    <span class="task-type ${run.solve_status === 'optimal' ? 'normal' : 'temporary'}">${run.strategy_display_name || run.strategy_name}</span>
                    <span class="expand-icon" id="expand-icon-${run.id}">▶</span>
                </div>
                <div class="task-details">
                    <div>工期: <strong>${run.makespan || '-'}</strong> 分钟 | 求解时间: ${run.solve_time || 0}s</div>
                    <div>任务数: ${run.num_tasks || 0} | 机车数: ${run.num_locomotives || 0}</div>
                    <div>状态: <span class="status-badge status-${run.solve_status}">${run.solve_status}</span> | ${run.created_at}</div>
                </div>
            </div>
            <div class="history-detail" id="history-detail-${run.id}" style="display:none;"></div>
        </div>
    `).join('');
}

// 缓存已加载的详情
const historyDetailCache = {};

async function toggleHistoryDetail(runId) {
    const detailDiv = document.getElementById('history-detail-' + runId);
    const icon = document.getElementById('expand-icon-' + runId);
    if (!detailDiv) return;

    // 如果已展开，则折叠
    if (detailDiv.style.display === 'block') {
        detailDiv.style.display = 'none';
        if (icon) icon.textContent = '▶';
        return;
    }

    // 展开
    detailDiv.style.display = 'block';
    if (icon) icon.textContent = '▼';

    // 如果已缓存，直接显示
    if (historyDetailCache[runId]) {
        detailDiv.innerHTML = historyDetailCache[runId];
        return;
    }

    // 显示加载中
    detailDiv.innerHTML = '<p style="text-align:center;padding:16px;color:#666;">加载中...</p>';

    try {
        const result = await apiCall('/runs/' + runId);
        if (result.success && result.data) {
            const html = buildHistoryDetailHTML(result.data);
            historyDetailCache[runId] = html;
            detailDiv.innerHTML = html;
        } else {
            detailDiv.innerHTML = '<p style="color:red;">加载失败: ' + (result.error || '未知错误') + '</p>';
        }
    } catch (e) {
        detailDiv.innerHTML = '<p style="color:red;">加载出错: ' + e.message + '</p>';
    }
}

function buildHistoryDetailHTML(data) {
    const assignments = data.assignments || [];
    const result = data.result || {};

    let html = '<div class="history-detail-content">';

    // 摘要卡片
    html += `
        <div class="result-summary" style="margin-bottom:12px;">
            <div class="result-card">
                <div class="value">${data.makespan || '-'}</div>
                <div class="label">总工期</div>
            </div>
            <div class="result-card">
                <div class="value">${data.solve_time || '-'}s</div>
                <div class="label">求解时间</div>
            </div>
            <div class="result-card">
                <div class="value">${data.num_tasks || '-'}</div>
                <div class="label">任务数</div>
            </div>
            <div class="result-card">
                <div class="value">${data.num_locomotives || '-'}</div>
                <div class="label">机车数</div>
            </div>
        </div>
    `;

    // 任务分配表格
    if (assignments.length > 0) {
        // 甘特图
        html += buildGanttChartHTML(assignments, data.makespan || 100);

        html += '<h4 style="margin:12px 0 8px;">任务分配详情</h4>';
        html += '<div class="table-scroll" style="max-height:400px;overflow-y:auto;">';
        html += '<table class="comparison-table"><thead><tr><th>任务ID</th><th>机车</th><th>路径</th><th>开始</th><th>装货结束</th><th>运输结束</th><th>卸货结束</th></tr></thead><tbody>';
        assignments.forEach(a => {
            const path = a.path ? (typeof a.path === 'string' ? a.path : JSON.parse(a.path || '[]').join(' → ')) : '-';
            html += `<tr>
                <td>${a.task_id || '-'}</td>
                <td>${a.locomotive_id || '-'}</td>
                <td style="font-size:11px;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${path}">${path}</td>
                <td>${a.start_time !== undefined ? a.start_time : '-'}</td>
                <td>${a.loading_end !== undefined ? a.loading_end : '-'}</td>
                <td>${a.transport_end !== undefined ? a.transport_end : '-'}</td>
                <td>${a.unloading_end !== undefined ? a.unloading_end : '-'}</td>
            </tr>`;
        });
        html += '</tbody></table></div>';
    } else {
        html += '<p class="text-muted">无任务分配记录</p>';
    }

    // 如果有result对象，显示额外信息
    if (result.assignments && result.assignments.length > 0) {
        html += '<h4 style="margin:12px 0 8px;">调度结果</h4>';
        if (result.solve_status) {
            html += `<p>求解状态: <strong>${result.solve_status}</strong></p>`;
        }
        if (result.message) {
            html += `<p>${result.message}</p>`;
        }
    }

    html += '</div>';
    return html;
}

function buildGanttChartHTML(assignments, makespan) {
    // 按机车分组
    const locoGroups = {};
    assignments.forEach(a => {
        const lid = a.locomotive_id || '未知';
        if (!locoGroups[lid]) locoGroups[lid] = [];
        locoGroups[lid].push(a);
    });

    const locoIds = Object.keys(locoGroups).sort();
    const colors = ['#667eea', '#f59e0b', '#10b981', '#ef4444', '#8b5cf6', '#06b6d4', '#ec4899', '#14b8a6', '#f97316', '#6366f1'];
    const rowHeight = 36;
    const labelWidth = 80;
    const chartHeight = locoIds.length * rowHeight + 40;

    // 生成时间刻度
    const tickCount = Math.min(10, makespan);
    const tickInterval = Math.ceil(makespan / tickCount);
    let ticks = '<div class="gantt-tick" style="left:0%">0</div>';
    for (let t = tickInterval; t < makespan; t += tickInterval) {
        const pct = (t / makespan) * 100;
        ticks += `<div class="gantt-tick" style="left:${pct}%">${t}</div>`;
    }
    const endPct = 100;
    ticks += `<div class="gantt-tick" style="left:${endPct}%">${makespan}</div>`;

    let html = '<h4 style="margin:12px 0 8px;">任务调度甘特图</h4>';
    html += '<div class="gantt-chart-wrapper">';
    html += `<div class="gantt-chart" style="height:${chartHeight}px;">`;

    // 时间轴
    html += `<div class="gantt-header" style="margin-left:${labelWidth}px;">${ticks}</div>`;

    // 机车行
    locoIds.forEach((locoId, idx) => {
        const tasks = locoGroups[locoId];
        const color = colors[idx % colors.length];
        const top = idx * rowHeight + 24;

        html += `<div class="gantt-row" style="top:${top}px;height:${rowHeight}px;">`;
        html += `<div class="gantt-label" style="width:${labelWidth}px;">${locoId}</div>`;
        html += `<div class="gantt-bar-area" style="margin-left:${labelWidth}px;">`;

        tasks.forEach(task => {
            const st = task.start_time || 0;
            const ue = task.unloading_end || (st + 1);
            const le = task.loading_end !== undefined ? task.loading_end : st;
            const te = task.transport_end !== undefined ? task.transport_end : le;

            const leftPct = (st / makespan) * 100;
            const widthPct = Math.max(2, ((ue - st) / makespan) * 100);

            // 阶段比例
            const totalDuration = ue - st || 1;
            const emptyPct = Math.max(0, ((le - st) / totalDuration) * 100);
            const loadPct = Math.max(0, ((le - st) / totalDuration) * 100); // 装货阶段
            const transPct = Math.max(0, ((te - le) / totalDuration) * 100); // 运输阶段
            const unloadPct = Math.max(0, ((ue - te) / totalDuration) * 100); // 卸货阶段

            html += `<div class="gantt-bar" style="left:${leftPct}%;width:${widthPct}%;background:${color};"
                title="${task.task_id || '-'}: 开始${st} → 装货完成${le} → 运输完成${te} → 卸货完成${ue}">`;

            // 内部阶段指示
            if (totalDuration > 0) {
                html += `<div class="gantt-phase gantt-phase-empty" style="width:${loadPct}%;" title="空驶+装货"></div>`;
                html += `<div class="gantt-phase gantt-phase-transport" style="width:${transPct}%;" title="运输"></div>`;
                html += `<div class="gantt-phase gantt-phase-unload" style="width:${unloadPct}%;" title="卸货"></div>`;
            }

            html += `<span class="gantt-bar-label">${task.task_id || '-'}</span>`;
            html += '</div>';
        });

        html += '</div></div>';
    });

    html += '</div></div>';

    // 图例
    html += '<div class="gantt-legend">';
    html += '<span class="gantt-legend-item"><span class="gantt-legend-color" style="background:rgba(255,255,255,0.5);"></span>空驶+装货</span>';
    html += '<span class="gantt-legend-item"><span class="gantt-legend-color" style="background:rgba(0,0,0,0.15);"></span>运输</span>';
    html += '<span class="gantt-legend-item"><span class="gantt-legend-color" style="background:rgba(0,0,0,0.3);"></span>卸货</span>';
    html += '</div>';

    return html;
}

async function loadBatchHistory() {
    const batchId = document.getElementById('historyBatchSelect').value;
    if (!batchId) return;

    const result = await apiCall('/batches/' + batchId);
    if (result.success && result.data) {
        console.log('批次历史:', result.data);
    }
}

function filterHistory() {
    loadHistory();
}

async function loadLogs() {
    const level = document.getElementById('logLevelFilter')?.value || '';
    const result = await apiCall('/query/logs?page=1&page_size=50' + (level ? '&log_level=' + level : ''));
    if (result.success && result.data) {
        renderLogsList(result.data.data || []);
        renderPagination('logsPagination', result.data, (page) => loadLogsPage(page));
    }
}

function loadLogsPage(page) {
    const level = document.getElementById('logLevelFilter')?.value || '';
    apiCall('/query/logs?page=' + page + '&page_size=50' + (level ? '&log_level=' + level : '')).then(result => {
        if (result.success && result.data) {
            renderLogsList(result.data.data || []);
            renderPagination('logsPagination', result.data, (p) => loadLogsPage(p));
        }
    });
}

function renderLogsList(logs) {
    const list = document.querySelector('#logs-table tbody');
    if (!list) return;

    if (logs.length === 0) {
        list.innerHTML = '<tr><td colspan="6" style="text-align:center;">暂无日志</td></tr>';
        return;
    }

    list.innerHTML = logs.map(log => `
        <tr class="log-level-${(log.log_level || '').toLowerCase()}">
            <td>${log.id}</td>
            <td>${log.created_at}</td>
            <td>${log.log_level || ''}</td>
            <td>${log.module || ''}</td>
            <td>${log.message || ''}</td>
            <td><button class="btn btn-danger btn-sm" onclick="deleteLog(${log.id})">删除</button></td>
        </tr>
    `).join('');
}

function renderPagination(containerId, data, onPageChange) {
    const container = document.getElementById(containerId);
    if (!container || !data.total_pages) return;

    const currentPage = data.page;
    const totalPages = data.total_pages;

    let html = '';
    for (let i = 1; i <= Math.min(totalPages, 10); i++) {
        html += `<button class="${i === currentPage ? 'active' : ''}" onclick="(${onPageChange.toString()})(${i})">${i}</button>`;
    }
    container.innerHTML = html;
}

function showStatistics() {
    apiCall('/statistics').then(result => {
        if (result.success && result.data) {
            const s = result.data;
            alert(`系统统计:\n\n总运行次数: ${s.total_runs}\n总批次数: ${s.total_batches}\n最优工期: ${s.best_makespan || '-'}\n\n策略统计:\n${(s.strategy_stats || []).map(st => `${st.strategy_name}: ${st.cnt}次, 平均工期${Math.round(st.avg_makespan)}`).join('\n')}`);
        }
    });
}

function showModal(title, bodyHtml, onConfirm) {
    const container = document.getElementById('modalContainer');
    container.innerHTML = `
        <div class="modal-overlay" onclick="if(event.target === this) closeModal()">
            <div class="modal">
                <div class="modal-header">
                    <h3>${title}</h3>
                    <button class="modal-close" onclick="closeModal()">&times;</button>
                </div>
                <div class="modal-body">${bodyHtml}</div>
                <div class="modal-footer">
                    <button class="btn btn-secondary" onclick="closeModal()">取消</button>
                    <button class="btn btn-primary" id="modalConfirmBtn">确定</button>
                </div>
            </div>
        </div>
    `;
    document.getElementById('modalConfirmBtn').onclick = onConfirm;
}

function closeModal() {
    document.getElementById('modalContainer').innerHTML = '';
}

function updateMapButtons(running, paused) {
    const computeBtn = document.getElementById('mapComputeBtn');
    const runBtn = document.getElementById('mapRunBtn');
    const pauseBtn = document.getElementById('mapPauseBtn');
    const resumeBtn = document.getElementById('mapResumeBtn');
    const stopBtn = document.getElementById('mapStopBtn');

    // 运算按钮：运算中或动画播放中禁用
    if (computeBtn) {
        computeBtn.disabled = isScheduleRequesting || (running && !paused);
        computeBtn.style.opacity = computeBtn.disabled ? '0.5' : '1';
        computeBtn.style.cursor = computeBtn.disabled ? 'not-allowed' : 'pointer';
        computeBtn.title = isScheduleRequesting ? '运算中...' : (running && !paused) ? '调度演示中，请先暂停' : '开始算法运算';
    }

    // 执行调度按钮：只有运算完成后才能点击
    if (runBtn) {
        const canRun = isScheduleComputed && !(running && !paused);
        runBtn.disabled = !canRun;
        runBtn.style.opacity = canRun ? '1' : '0.5';
        runBtn.style.cursor = canRun ? 'pointer' : 'not-allowed';
        runBtn.title = !isScheduleComputed ? '请先点击"开始运算"' : (running && !paused) ? '调度演示中，请先暂停' : '在地图上演示调度结果';
    }
    if (pauseBtn) {
        pauseBtn.disabled = !running || paused;
        pauseBtn.style.opacity = (!running || paused) ? '0.5' : '1';
    }
    if (resumeBtn) {
        resumeBtn.disabled = !paused;
        resumeBtn.style.opacity = !paused ? '0.5' : '1';
    }
    if (stopBtn) {
        stopBtn.disabled = !running && !paused;
        stopBtn.style.opacity = (!running && !paused) ? '0.5' : '1';
    }
}

async function mapComputeSchedule() {
    try {
        if (isScheduleRequesting) {
            console.log('[mapComputeSchedule] already requesting, skip');
            return;
        }
        isScheduleRequesting = true;
        console.log('[mapComputeSchedule] starting');

        const strategyEl = document.getElementById('mapStrategySelect');
        if (!strategyEl) {
            console.error('[mapComputeSchedule] mapStrategySelect not found');
            alert('找不到策略选择器');
            isScheduleRequesting = false;
            return;
        }
        const strategy = strategyEl.value;
        console.log('[mapComputeSchedule] strategy:', strategy);

        updateMapButtons(false, false);

        const resultDiv = document.getElementById('scheduleResult');
        if (resultDiv) {
            resultDiv.style.display = 'block';
            resultDiv.innerHTML = '<p style="text-align:center;padding:20px;">正在运算中，请稍候...</p>';
        }

        const result = await apiCall('/schedule/run', 'POST', {
            strategy,
            use_hot_start: false
        });

        if (result.success && result.data) {
            currentScheduleResult = result.data;
            isScheduleComputed = true;
            scheduleCompleted = false;
            isScheduleRequesting = false;

            const batchEl = document.getElementById('currentBatch');
            if (batchEl) batchEl.textContent = `批次: ${result.data.batch_id || '-'}`;

            try {
                renderScheduleResult(result.data);
                console.log('[mapComputeSchedule] renderScheduleResult done');
            } catch (e) {
                console.error('[mapComputeSchedule] renderScheduleResult error:', e);
                const resultDiv = document.getElementById('scheduleResult');
                if (resultDiv) {
                    resultDiv.innerHTML = `<div class="alert alert-error">渲染结果失败: ${e.message}</div>`;
                }
            }
            updateMapButtons(false, false);
            console.log('[mapComputeSchedule] done, makespan:', result.data.makespan, 'tasks:', result.data.num_tasks);
        } else {
            isScheduleRequesting = false;
            const errMsg = result.error || '未知错误';
            console.error('[mapComputeSchedule] API failed:', errMsg);
            alert('运算失败: ' + errMsg);
            updateMapButtons(false, false);
        }
    } catch (e) {
        console.error('mapComputeSchedule error:', e);
        alert('执行运算出错: ' + e.message);
        isScheduleRequesting = false;
        updateMapButtons(false, false);
    }
}

function mapPlaySchedule() {
    if (isSchedulePlaying) {
        console.log('[mapPlaySchedule] already playing, skip');
        return;
    }
    if (!currentScheduleResult || !currentScheduleResult.assignments || currentScheduleResult.assignments.length === 0) {
        alert('请先点击"开始运算"获取调度结果');
        return;
    }
    if (!dynamicMap) {
        alert('地图未初始化');
        return;
    }

    isSchedulePlaying = true;
    console.log('[mapPlaySchedule] starting animation');

    dynamicMap.setProgressCallback((progress) => {
        if (progress >= 100) {
            scheduleCompleted = true;
            isScheduleRunning = false;
            isSchedulePlaying = false;
            updateMapButtons(false, false);
            loadLogs();
        }
    });

    const speedEl = document.getElementById('mapSpeedSelect');
    const speed = speedEl ? parseFloat(speedEl.value) || 1 : 1;
    dynamicMap.playSchedule(currentScheduleResult.assignments, speed);
    isScheduleRunning = true;
    updateMapButtons(true, false);
    updateVehicleStatusPanel();
}

function onStrategyChange() {
    // 切换策略时重置运算状态
    if (isScheduleComputed) {
        isScheduleComputed = false;
        currentScheduleResult = null;
        updateMapButtons(false, false);
        const resultDiv = document.getElementById('scheduleResult');
        if (resultDiv) {
            resultDiv.style.display = 'none';
            resultDiv.innerHTML = '';
        }
    }
}

function mapPauseSchedule() {
    if (dynamicMap) {
        dynamicMap.pauseSchedule();
        isScheduleRunning = false;
        updateMapButtons(true, true);
    }
}

function mapResumeSchedule() {
    if (dynamicMap && !scheduleCompleted) {
        dynamicMap.resumeSchedule();
        isScheduleRunning = true;
        updateMapButtons(true, false);
    }
}

function mapStopSchedule() {
    if (dynamicMap) {
        dynamicMap.setProgressCallback(null);  // 先清除回调，防止stopSchedule触发loadLogs
        dynamicMap.stopSchedule();
        isScheduleRunning = false;
        scheduleCompleted = true;
        isSchedulePlaying = false;
        updateMapButtons(false, false);
        loadLogs();
    }
}

function changeSpeed() {
    const speed = parseFloat(document.getElementById('mapSpeedSelect').value);
    if (dynamicMap) {
        dynamicMap.setSpeed(speed);
    }
}

// ==================== 多策略对比（新版） ====================
const COMPARISON_STRATEGIES = [
    { key: 'cpsat', name: 'CP-SAT基准策略', isBaseline: true, desc: 'Dijkstra + Google OR-Tools CP-SAT约束规划' },
    { key: 'greedy', name: '贪心算法', isBaseline: false, desc: '基于优先级和最短路径的贪心调度' },
    { key: 'genetic', name: '遗传算法', isBaseline: false, desc: '进化算法搜索最优调度方案' },
    { key: 'simulated_annealing', name: '模拟退火', isBaseline: false, desc: '基于模拟退火的调度优化' }
];

let comparisonChartInstances = {};

function initComparisonTab() {
    const container = document.getElementById('strategy-checkboxes');
    if (!container) return;
    container.innerHTML = COMPARISON_STRATEGIES.map(s => `
        <label class="strategy-checkbox-item ${s.isBaseline ? 'baseline-strategy' : ''}">
            <input type="checkbox" class="cmp-checkbox" data-key="${s.key}"
                   ${s.isBaseline ? 'checked disabled' : ''}>
            <span class="strategy-name">${s.name}</span>
            <span class="strategy-desc">${s.desc}</span>
            ${s.isBaseline ? '<span class="baseline-tag">基准</span>' : ''}
        </label>
    `).join('');

    container.querySelectorAll('.cmp-checkbox:not([disabled])').forEach(cb => {
        cb.addEventListener('change', updateComparisonBtnState);
    });

    document.getElementById('btn-run-comparison').addEventListener('click', runComparisonV2);
    document.getElementById('btn-export-comparison').addEventListener('click', exportComparison);
}

function updateComparisonBtnState() {
    const checked = document.querySelectorAll('.cmp-checkbox:checked').length;
    const btn = document.getElementById('btn-run-comparison');
    if (btn) btn.disabled = checked < 2;
}

function getSelectedStrategies() {
    const checked = document.querySelectorAll('.cmp-checkbox:checked');
    return Array.from(checked).map(cb => cb.dataset.key);
}

function resetComparisonCharts() {
    Object.values(comparisonChartInstances).forEach(c => {
        try { c.destroy(); } catch (e) { }
    });
    comparisonChartInstances = {};
}

async function runComparisonV2() {
    const strategies = getSelectedStrategies();
    if (strategies.length < 2) {
        alert('请至少勾选基准策略和1个候选策略');
        return;
    }

    resetComparisonCharts();

    const progressDiv = document.getElementById('comparison-progress');
    const progressFill = document.getElementById('comparison-progress-fill');
    const progressText = document.getElementById('comparison-progress-text');
    const resultsDiv = document.getElementById('comparison-results');
    const btn = document.getElementById('btn-run-comparison');
    const btnExport = document.getElementById('btn-export-comparison');

    if (progressDiv) progressDiv.style.display = 'block';
    if (resultsDiv) resultsDiv.style.display = 'none';
    if (btn) btn.disabled = true;
    if (btnExport) btnExport.disabled = true;
    if (progressFill) progressFill.style.width = '0%';
    if (progressText) progressText.textContent = '正在运行...';

    const allResults = [];
    for (let i = 0; i < strategies.length; i++) {
        const key = strategies[i];
        const info = COMPARISON_STRATEGIES.find(s => s.key === key);
        if (progressText) progressText.textContent = `正在运行 ${info ? info.name : key}...`;
        if (progressFill) progressFill.style.width = `${Math.round((i / strategies.length) * 100)}%`;

        try {
            const resp = await fetch('/api/schedule/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ strategy: key })
            });
            const respData = await resp.json();
            const result = respData.success ? respData.data : respData;
            allResults.push(result);
        } catch (e) {
            allResults.push({ strategy_name: key, solve_status: 'error', error: e.message });
        }
    }

    if (progressFill) progressFill.style.width = '100%';
    if (progressText) progressText.textContent = '对比完成!';
    setTimeout(() => { if (progressDiv) progressDiv.style.display = 'none'; }, 1000);

    renderComparisonV2(allResults);
    if (btn) btn.disabled = false;
    if (btnExport) btnExport.disabled = false;
}

function renderComparisonV2(results) {
    const resultsDiv = document.getElementById('comparison-results');
    if (!resultsDiv) return;
    resultsDiv.style.display = 'block';

    const tbody = document.querySelector('#comparison-table tbody');
    if (tbody) {
        tbody.innerHTML = results.map(r => {
            const isBaseline = COMPARISON_STRATEGIES.find(s => s.key === r.strategy_name)?.isBaseline;
            const cls = isBaseline ? 'baseline-row' : '';
            const status = r.solve_status || 'error';
            const st = r.solve_time !== undefined && r.solve_time !== null ? r.solve_time.toFixed(4) : '-';
            const en = r.energy_consumption !== undefined ? r.energy_consumption : '-';
            const da = r.dynamic_adaptability !== undefined ? r.dynamic_adaptability : '-';
            return `<tr class="${cls}">
                <td>${r.strategy_display_name || r.strategy_name}</td>
                <td>${r.makespan !== undefined ? r.makespan : '-'}</td>
                <td>${st}</td>
                <td>${r.num_tasks || '-'}</td>
                <td class="status-${status}">${status}</td>
                <td>${en}</td>
                <td>${da}</td>
            </tr>`;
        }).join('');
    }

    const validResults = results.filter(r => r.solve_status !== 'error' && r.makespan >= 0);
    if (validResults.length === 0) return;

    const baseline = results.find(r => COMPARISON_STRATEGIES.find(s => s.key === r.strategy_name)?.isBaseline);
    const labels = validResults.map(r => r.strategy_display_name || r.strategy_name);
    const isBaselineFlags = validResults.map(r => COMPARISON_STRATEGIES.find(s => s.key === r.strategy_name)?.isBaseline || false);

    const barColors = labels.map((_, i) => isBaselineFlags[i] ? 'rgba(220, 53, 69, 0.8)' : 'rgba(54, 162, 235, 0.8)');
    const barBorders = labels.map((_, i) => isBaselineFlags[i] ? 'rgba(220, 53, 69, 1)' : 'rgba(54, 162, 235, 1)');

    const normalize = (values, invert) => {
        const max = Math.max(...values.filter(v => v !== undefined && v !== null), 1);
        const min = Math.min(...values.filter(v => v !== undefined && v !== null), 0);
        const range = max - min || 1;
        return values.map(v => {
            if (v === undefined || v === null) return 0;
            return invert ? Math.round((1 - (v - min) / range) * 100) : Math.round(((v - min) / range) * 100);
        });
    };

    const makespans = validResults.map(r => r.makespan);
    const solveTimes = validResults.map(r => r.solve_time);
    const energies = validResults.map(r => r.energy_consumption || 0);
    const adaptabilities = validResults.map(r => r.dynamic_adaptability || 0);

    // 求解速度柱状图
    const ctx1 = document.getElementById('chart-solve-time');
    if (ctx1) {
        comparisonChartInstances.solveTime = new Chart(ctx1, {
            type: 'bar', data: { labels, datasets: [{ label: '求解时间 (s)', data: solveTimes, backgroundColor: barColors, borderColor: barBorders, borderWidth: 1 }] },
            options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, title: { display: true, text: '秒' } } } }
        });
    }

    // Makespan 柱状图
    const ctx2 = document.getElementById('chart-makespan');
    if (ctx2) {
        comparisonChartInstances.makespan = new Chart(ctx2, {
            type: 'bar', data: { labels, datasets: [{ label: 'Makespan', data: makespans, backgroundColor: barColors, borderColor: barBorders, borderWidth: 1 }] },
            options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, title: { display: true, text: 'makespan' } } } }
        });
    }

    // 能耗柱状图
    const ctx3 = document.getElementById('chart-energy');
    if (ctx3) {
        comparisonChartInstances.energy = new Chart(ctx3, {
            type: 'bar', data: { labels, datasets: [{ label: '总能耗', data: energies, backgroundColor: barColors, borderColor: barBorders, borderWidth: 1 }] },
            options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, title: { display: true, text: '能耗' } } } }
        });
    }

    // 动态适应性柱状图
    const ctx4 = document.getElementById('chart-adaptability');
    if (ctx4) {
        comparisonChartInstances.adaptability = new Chart(ctx4, {
            type: 'bar', data: { labels, datasets: [{ label: '动态适应性', data: adaptabilities, backgroundColor: barColors, borderColor: barBorders, borderWidth: 1 }] },
            options: { responsive: true, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, title: { display: true, text: '适应性指数' } } } }
        });
    }

    // 雷达图
    const ctx5 = document.getElementById('chart-radar');
    if (ctx5) {
        const radarLabels = ['Makespan质量', '求解速度', '任务完成率', '能耗效率', '动态适应性'];
        const totalTasks = Math.max(...validResults.map(r => r.num_tasks || 1), 1);
        const radarDatasets = validResults.map((r, i) => ({
            label: r.strategy_display_name || r.strategy_name,
            data: [normalize(makespans, true)[i], normalize(solveTimes, true)[i], Math.round((r.num_tasks || 0) / totalTasks * 100), normalize(energies, true)[i], normalize(adaptabilities, false)[i]],
            backgroundColor: isBaselineFlags[i] ? 'rgba(220, 53, 69, 0.2)' : 'rgba(54, 162, 235, 0.2)',
            borderColor: isBaselineFlags[i] ? 'rgba(220, 53, 69, 1)' : 'rgba(54, 162, 235, 1)',
            borderWidth: 2
        }));
        comparisonChartInstances.radar = new Chart(ctx5, {
            type: 'radar', data: { labels: radarLabels, datasets: radarDatasets },
            options: { responsive: true, scales: { r: { beginAtZero: true, max: 100, ticks: { stepSize: 20 } } } }
        });
    }

    // 超越基准高亮
    if (baseline) {
        highlightBeatBaseline(results, baseline, labels, isBaselineFlags);
    }
}

function highlightBeatBaseline(results, baseline, labels, isBaselineFlags) {
    const tbody = document.querySelector('#comparison-table tbody');
    if (!tbody) return;
    const rows = tbody.querySelectorAll('tr');
    results.forEach((r, i) => {
        if (isBaselineFlags[i]) return;
        const row = rows[i];
        if (!row) return;
        let beat = false;
        if (r.makespan >= 0 && r.makespan < baseline.makespan) beat = true;
        if (r.solve_time !== undefined && r.solve_time < baseline.solve_time) beat = true;
        if (r.energy_consumption !== undefined && baseline.energy_consumption !== undefined && r.energy_consumption < baseline.energy_consumption) beat = true;
        if (r.dynamic_adaptability !== undefined && baseline.dynamic_adaptability !== undefined && r.dynamic_adaptability > baseline.dynamic_adaptability) beat = true;
        if (beat) {
            row.classList.add('beat-baseline');
            const cells = row.querySelectorAll('td');
            if (r.makespan >= 0 && r.makespan < baseline.makespan && cells[1]) cells[1].innerHTML += ' <span class="beat-badge">超越!</span>';
            if (r.solve_time !== undefined && r.solve_time < baseline.solve_time && cells[2]) cells[2].innerHTML += ' <span class="beat-badge">超越!</span>';
        }
    });
}

function exportComparison() {
    const tbody = document.querySelector('#comparison-table tbody');
    if (!tbody || !tbody.children.length) {
        alert('请先运行对比'); return;
    }
    const rows = tbody.querySelectorAll('tr');
    const data = [];
    rows.forEach(row => {
        const cells = row.querySelectorAll('td');
        if (cells.length >= 5) {
            data.push({
                strategy: (cells[0].textContent || '').replace(' 超越!', ''),
                makespan: (cells[1].textContent || '').replace(' 超越!', ''),
                solve_time: (cells[2].textContent || '').replace(' 超越!', ''),
                num_tasks: cells[3].textContent,
                status: cells[4].textContent,
                energy: cells[5] ? cells[5].textContent : '-',
                adaptability: cells[6] ? cells[6].textContent : '-'
            });
        }
    });
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'comparison_report.json'; a.click();
    URL.revokeObjectURL(url);
}

// ==================== 日志删除 ====================
async function deleteLog(logId) {
    if (!confirm('确定删除此日志?')) return;
    try {
        const resp = await fetch(`/api/logs/delete/${logId}`, { method: 'DELETE' });
        const data = await resp.json();
        if (data.success) {
            loadLogs();
        } else {
            alert('删除失败: ' + (data.error || '未知错误'));
        }
    } catch (e) {
        alert('删除失败: ' + e.message);
    }
}

async function clearAllLogs() {
    if (!confirm('确定清空所有日志? 此操作不可撤销!')) return;
    try {
        const resp = await fetch('/api/logs/clear', { method: 'POST' });
        const data = await resp.json();
        if (data.success) {
            alert(data.message);
            loadLogs();
        } else {
            alert('清空失败');
        }
    } catch (e) {
        alert('清空失败: ' + e.message);
    }
}

// ==================== 机车编辑 ====================
async function editLocomotive(locoId) {
    if (!currentLocomotivesData || !currentLocomotivesData.locomotives) {
        alert('机车数据未加载'); return;
    }
    const loco = currentLocomotivesData.locomotives.find(l => l.id === locoId);
    if (!loco) { alert('机车不存在'); return; }

    document.getElementById('loco-edit-id').value = loco.id;
    document.getElementById('loco-edit-traction').value = loco.traction_type || 'electric';
    document.getElementById('loco-edit-q').value = loco.Q || 50;
    document.getElementById('loco-edit-speed').value = loco.max_speed || 800;
    document.getElementById('loco-edit-initial-node').value = loco.initial_node || '';
    document.getElementById('loco-edit-battery').value = loco.battery || 0;
    document.getElementById('loco-edit-fuel').value = loco.fuel_tank || 0;
    document.getElementById('loco-edit-powered').checked = loco.is_powered_on !== false;
    document.getElementById('loco-edit-schedulable').checked = loco.is_schedulable !== false;

    const isElectric = (loco.traction_type || 'electric') === 'electric';
    document.getElementById('loco-edit-battery-group').style.display = isElectric ? '' : 'none';
    document.getElementById('loco-edit-fuel-group').style.display = isElectric ? 'none' : '';

    document.getElementById('loco-edit-traction').onchange = function () {
        const isElec = this.value === 'electric';
        document.getElementById('loco-edit-battery-group').style.display = isElec ? '' : 'none';
        document.getElementById('loco-edit-fuel-group').style.display = isElec ? 'none' : '';
    };

    document.getElementById('loco-edit-modal').style.display = 'flex';
}

async function saveLocoEdit(e) {
    e.preventDefault();
    const locoId = document.getElementById('loco-edit-id').value;
    const traction = document.getElementById('loco-edit-traction').value;
    const data = {
        id: locoId,
        traction_type: traction,
        Q: parseInt(document.getElementById('loco-edit-q').value) || 50,
        max_speed: parseInt(document.getElementById('loco-edit-speed').value) || 800,
        initial_node: document.getElementById('loco-edit-initial-node').value,
        is_powered_on: document.getElementById('loco-edit-powered').checked,
        is_schedulable: document.getElementById('loco-edit-powered').checked ? document.getElementById('loco-edit-schedulable').checked : false
    };
    if (traction === 'electric') {
        data.battery = parseInt(document.getElementById('loco-edit-battery').value) || 0;
    } else {
        data.fuel_tank = parseInt(document.getElementById('loco-edit-fuel').value) || 0;
    }

    try {
        const resp = await fetch('/api/locomotives/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        const result = await resp.json();
        if (result.success) {
            document.getElementById('loco-edit-modal').style.display = 'none';
            loadLocomotives();
            alert('机车属性更新成功');
        } else {
            alert('更新失败: ' + (result.error || '未知错误'));
        }
    } catch (ex) {
        alert('更新失败: ' + ex.message);
    }
}

function setupLocoEditModal() {
    const form = document.getElementById('loco-edit-form');
    if (form) form.addEventListener('submit', saveLocoEdit);
    const cancelBtn = document.getElementById('btn-cancel-edit-loco');
    if (cancelBtn) cancelBtn.addEventListener('click', () => {
        document.getElementById('loco-edit-modal').style.display = 'none';
    });
    const modal = document.getElementById('loco-edit-modal');
    if (modal) modal.addEventListener('click', function (e) {
        if (e.target === this) this.style.display = 'none';
    });

    // 关机状态联动: 取消开机时自动取消可调度
    const poweredCb = document.getElementById('loco-edit-powered');
    const schedulableCb = document.getElementById('loco-edit-schedulable');
    if (poweredCb && schedulableCb) {
        poweredCb.addEventListener('change', function () {
            if (!this.checked) {
                schedulableCb.checked = false;
            }
        });
    }
}

// ==================== 初始化更新 ====================
(function () {
    window.addEventListener('load', () => {
        initComparisonTab();
        setupLocoEditModal();
        // 绑定日志按钮
        const btnRefresh = document.getElementById('btn-refresh-logs');
        const btnClear = document.getElementById('btn-clear-logs');
        if (btnRefresh) btnRefresh.addEventListener('click', loadLogs);
        if (btnClear) btnClear.addEventListener('click', clearAllLogs);
    });
})();
