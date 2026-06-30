/**
 * 车辆调度AI算法评测系统 - 前端主应用
 */

const API_BASE = '/api';
let currentMapData = null;
let currentTasksData = null;
let currentLocomotivesData = null;
let currentHyperParams = null;
let currentScheduleResult = null;
let isScheduleRunning = false;
let scheduleCompleted = false;

document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initMap();
    loadAllData();
    loadStrategies();
    loadBatchIds();
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
        const response = await fetch(API_BASE + url, options);
        return await response.json();
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
    const list = document.getElementById('locomotivesList');
    if (!list) return;

    const typeFilter = document.getElementById('locoTypeFilter')?.value || '';
    const filtered = locomotives.filter(l => !typeFilter || l.traction_type === typeFilter);

    if (filtered.length === 0) {
        list.innerHTML = '<p class="text-muted">暂无机车</p>';
        return;
    }

    list.innerHTML = filtered.map(loco => {
        const isElectric = loco.traction_type === 'electric';
        return `
            <div class="loco-item">
                <div class="loco-header">
                    <span class="task-id">${loco.id}</span>
                    <span class="vehicle-type ${loco.traction_type}">${isElectric ? '电动机车' : '柴油机车'}</span>
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
    if (!resultDiv) return;

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
        const makespan = result.makespan || 100;
        const locoAssignments = {};
        assignments.forEach(a => {
            if (!locoAssignments[a.locomotive_id]) {
                locoAssignments[a.locomotive_id] = [];
            }
            locoAssignments[a.locomotive_id].push(a);
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
                const left = (task.start_time / makespan) * 100;
                const width = ((task.unloading_end - task.start_time) / makespan) * 100;
                const color = colors[idx % colors.length];
                html += `
                    <div class="timeline-task" style="left:${left}%;width:${width}%;background:${color};"
                         title="${task.task_id}: ${task.start_time}-${task.unloading_end}">
                        ${task.task_id}
                    </div>
                `;
            });
            html += '</div></div>';
        });
        html += '</div>';
    }

    html += '<h4 style="margin-top:20px;margin-bottom:10px;">任务分配详情</h4>';
    html += '<table class="comparison-table"><tr><th>任务ID</th><th>机车</th><th>开始</th><th>装货结束</th><th>运输结束</th><th>卸货结束</th></tr>';
    assignments.forEach(a => {
        html += `<tr><td>${a.task_id}</td><td>${a.locomotive_id}</td><td>${a.start_time}</td><td>${a.loading_end}</td><td>${a.transport_end}</td><td>${a.unloading_end}</td></tr>`;
    });
    html += '</table>';

    resultDiv.innerHTML = html;
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
        <div class="task-item" onclick="viewRunDetail(${run.id})" style="cursor:pointer;">
            <div class="task-header">
                <span class="task-id">${run.batch_id}</span>
                <span class="task-type ${run.solve_status === 'optimal' ? 'normal' : 'temporary'}">${run.strategy_display_name || run.strategy_name}</span>
            </div>
            <div class="task-details">
                <div>工期: ${run.makespan || '-'} 分钟 | 求解时间: ${run.solve_time || 0}s</div>
                <div>任务数: ${run.num_tasks || 0} | 机车数: ${run.num_locomotives || 0}</div>
                <div>状态: ${run.solve_status} | ${run.created_at}</div>
            </div>
        </div>
    `).join('');
}

function viewRunDetail(runId) {
    apiCall('/runs/' + runId).then(result => {
        if (result.success && result.data) {
            alert('运行记录详情已获取，可扩展查看');
            console.log(result.data);
        }
    });
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
    const list = document.getElementById('logsList');
    if (!list) return;

    if (logs.length === 0) {
        list.innerHTML = '<p class="text-muted">暂无日志</p>';
        return;
    }

    list.innerHTML = logs.map(log => `
        <div class="log-item ${log.log_level}">
            <span class="log-time">${log.created_at}</span>
            <span class="log-level">[${log.log_level}]</span>
            <span>${log.message}</span>
        </div>
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
    const runBtn = document.getElementById('mapRunBtn');
    const pauseBtn = document.getElementById('mapPauseBtn');
    const resumeBtn = document.getElementById('mapResumeBtn');
    if (runBtn) {
        runBtn.disabled = running && !paused;
        runBtn.style.opacity = (running && !paused) ? '0.5' : '1';
        runBtn.style.cursor = (running && !paused) ? 'not-allowed' : 'pointer';
        runBtn.title = (running && !paused) ? '调度进行中，请先暂停' : '执行调度';
    }
    if (pauseBtn) {
        pauseBtn.disabled = !running || paused;
        pauseBtn.style.opacity = (!running || paused) ? '0.5' : '1';
    }
    if (resumeBtn) {
        resumeBtn.disabled = !paused;
        resumeBtn.disabled = !paused;
        resumeBtn.style.opacity = !paused ? '0.5' : '1';
    }
}

async function mapRunSchedule() {
    const runBtn = document.getElementById('mapRunBtn');
    if (runBtn && runBtn.disabled) {
        alert('调度进行中或已暂停，请先点击继续或等待完成');
        return;
    }
    const strategy = document.getElementById('mapStrategySelect').value;

    updateMapButtons(true, false);

    const result = await apiCall('/schedule/run', 'POST', {
        strategy,
        use_hot_start: false
    });

    if (result.success && result.data) {
        currentScheduleResult = result.data;
        scheduleCompleted = false;
        document.getElementById('currentBatch').textContent = `批次: ${result.data.batch_id || '-'}`;

        if (result.data.assignments && result.data.assignments.length > 0 && dynamicMap) {
            dynamicMap.setProgressCallback((progress) => {
                if (progress >= 100) {
                    scheduleCompleted = true;
                    updateMapButtons(false, false);
                }
            });
            dynamicMap.playSchedule(result.data.assignments);
            isScheduleRunning = true;
            updateMapButtons(true, false);
            updateVehicleStatusPanel();
        } else {
            updateMapButtons(false, false);
        }
    } else {
        alert('调度失败: ' + (result.error || '未知错误'));
        updateMapButtons(false, false);
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
