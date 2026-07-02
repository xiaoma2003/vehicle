/**
 * 动态地图渲染模块
 * 负责地图节点、边、车辆的动态展示
 */
class DynamicMap {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.nodes = [];
        this.edges = [];
        this.vehicles = [];
        this.assignments = [];
        this.scale = 1;
        this.offsetX = 0;
        this.offsetY = 0;
        this.isDragging = false;
        this.lastMouseX = 0;
        this.lastMouseY = 0;
        this.animationFrame = null;
        this.currentTime = 0;
        this.isPlaying = false;
        this.isPaused = false;
        this.pauseTime = 0;
        this.vehicleTrails = {};
        this.maxTime = 0;
        this.playStartTime = 0;
        this.animationDuration = 0;
        this.onProgressUpdate = null;
        this.coordDisplay = { x: 0, y: 0, visible: false };

        this.nodeColors = {
            station: '#667eea',
            fuel_station: '#ff9800',
            charge_station: '#4caf50',
            material_station: '#9c27b0',
            switch: '#795548'
        };

        this.nodeIcons = {
            station: '🏭',
            fuel_station: '⛽',
            charge_station: '🔋',
            material_station: '📦',
            switch: '🔀'
        };

        this.init();
    }

    init() {
        this.resize();
        window.addEventListener('resize', () => this.resize());
        this.canvas.addEventListener('mousedown', (e) => this.onMouseDown(e));
        this.canvas.addEventListener('mousemove', (e) => this.onMouseMove(e));
        this.canvas.addEventListener('mouseup', () => this.onMouseUp());
        this.canvas.addEventListener('mouseleave', () => { this.coordDisplay.visible = false; });
        this.canvas.addEventListener('wheel', (e) => this.onWheel(e));
        this.canvas.addEventListener('touchstart', (e) => this.onTouchStart(e));
        this.canvas.addEventListener('touchmove', (e) => this.onTouchMove(e));
        this.canvas.addEventListener('touchend', () => this.onMouseUp());
        this.animate();
    }

    resize() {
        const rect = this.canvas.parentElement.getBoundingClientRect();
        const w = rect.width > 0 ? rect.width : 800;
        const h = 650;
        if (this.canvas.width !== w) this.canvas.width = w;
        if (this.canvas.height !== h) this.canvas.height = h;
        this.canvas.style.width = w + 'px';
        this.canvas.style.height = h + 'px';
    }

    setData(nodes, edges) {
        this.nodes = nodes;
        this.edges = edges;
        this.resize();
        this.fitToView();
    }

    setVehicles(vehicles) {
        this.vehicles = vehicles;
    }

    setAssignments(assignments) {
        this.assignments = assignments;
    }

    setSpeed(speed) {
        this.speed = speed;
        this.animationDuration = Math.max(2000, this.maxTime * 15 / speed);
        if (this.isPlaying && !this.isPaused) {
            this.playStartTime = Date.now() - (this.currentTime / this.maxTime) * this.animationDuration;
        }
    }

    setProgressCallback(callback) {
        this.onProgressUpdate = callback;
    }

    fitToView() {
        if (this.nodes.length === 0) return;
        let minX = Infinity, maxX = -Infinity;
        let minY = Infinity, maxY = -Infinity;
        this.nodes.forEach(node => {
            minX = Math.min(minX, node.x || 0);
            maxX = Math.max(maxX, node.x || 0);
            minY = Math.min(minY, node.y || 0);
            maxY = Math.max(maxY, node.y || 0);
        });
        const padding = 120;
        const mapWidth = maxX - minX || 100;
        const mapHeight = maxY - minY || 100;
        const scaleX = (this.canvas.width - padding * 2) / mapWidth;
        const scaleY = (this.canvas.height - padding * 2) / mapHeight;
        this.scale = Math.min(scaleX, scaleY, 1.0);
        this.offsetX = (this.canvas.width - mapWidth * this.scale) / 2 - minX * this.scale;
        this.offsetY = (this.canvas.height - mapHeight * this.scale) / 2 - minY * this.scale;
    }

    worldToScreen(x, y) {
        return { x: x * this.scale + this.offsetX, y: y * this.scale + this.offsetY };
    }

    screenToWorld(x, y) {
        return { x: (x - this.offsetX) / this.scale, y: (y - this.offsetY) / this.scale };
    }

    onMouseDown(e) {
        const rect = this.canvas.getBoundingClientRect();
        this.isDragging = true;
        this.lastMouseX = e.clientX - rect.left;
        this.lastMouseY = e.clientY - rect.top;
        this.canvas.style.cursor = 'grabbing';
    }

    onTouchStart(e) {
        if (e.touches.length === 1) {
            const rect = this.canvas.getBoundingClientRect();
            this.isDragging = true;
            this.lastMouseX = e.touches[0].clientX - rect.left;
            this.lastMouseY = e.touches[0].clientY - rect.top;
        }
    }

    onMouseMove(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        const world = this.screenToWorld(x, y);
        this.coordDisplay = {
            x: Math.round(world.x),
            y: Math.round(world.y),
            screenX: x,
            screenY: y,
            visible: true
        };

        if (!this.isDragging) return;
        this.offsetX += x - this.lastMouseX;
        this.offsetY += y - this.lastMouseY;
        this.lastMouseX = x;
        this.lastMouseY = y;
    }

    onTouchMove(e) {
        if (!this.isDragging || e.touches.length !== 1) return;
        const rect = this.canvas.getBoundingClientRect();
        const x = e.touches[0].clientX - rect.left;
        const y = e.touches[0].clientY - rect.top;
        this.offsetX += x - this.lastMouseX;
        this.offsetY += y - this.lastMouseY;
        this.lastMouseX = x;
        this.lastMouseY = y;
    }

    onMouseUp() {
        this.isDragging = false;
        this.canvas.style.cursor = 'crosshair';
    }

    onWheel(e) {
        e.preventDefault();
        const rect = this.canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;
        const worldBefore = this.screenToWorld(mouseX, mouseY);
        const zoomFactor = e.deltaY > 0 ? 0.9 : 1.1;
        this.scale = Math.max(0.1, Math.min(3, this.scale * zoomFactor));
        const worldAfter = this.screenToWorld(mouseX, mouseY);
        this.offsetX += (worldAfter.x - worldBefore.x) * this.scale;
        this.offsetY += (worldAfter.y - worldBefore.y) * this.scale;
    }

    animate() {
        this.updatePlayback();
        this.draw();
        this.animationFrame = requestAnimationFrame(() => this.animate());
    }

    draw() {
        const ctx = this.ctx;
        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        this.drawBackground();
        this.drawGrid();
        this.drawEdges();
        this.drawNodeConnections();
        this.drawNodes();
        this.drawStaticVehicles();
        this.drawAssignments();
        this.drawScheduleOverlay();
        this.drawCoordinateDisplay();
    }

    drawBackground() {
        const ctx = this.ctx;
        const gradient = ctx.createLinearGradient(0, 0, 0, this.canvas.height);
        gradient.addColorStop(0, '#f8fafc');
        gradient.addColorStop(1, '#eef2f7');
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
    }

    drawGrid() {
        const ctx = this.ctx;
        ctx.strokeStyle = '#d8dee9';
        ctx.lineWidth = 0.5;
        const gridSize = 50 * this.scale;
        const startX = this.offsetX % gridSize;
        const startY = this.offsetY % gridSize;
        for (let x = startX; x < this.canvas.width; x += gridSize) {
            ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, this.canvas.height); ctx.stroke();
        }
        for (let y = startY; y < this.canvas.height; y += gridSize) {
            ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(this.canvas.width, y); ctx.stroke();
        }
    }

    drawEdges() {
        const ctx = this.ctx;
        this.edges.forEach(edge => {
            const fromNode = this.nodes.find(n => n.id === edge.from);
            const toNode = this.nodes.find(n => n.id === edge.to);
            if (!fromNode || !toNode) return;
            const from = this.worldToScreen(fromNode.x || 0, fromNode.y || 0);
            const to = this.worldToScreen(toNode.x || 0, toNode.y || 0);

            const direction = edge.direction || 'bidirectional';
            let color = '#a0a8b8';
            let lineWidth = 2;

            if (this.isPlaying) {
                const hasActiveVehicle = this.assignments.some(a => {
                    const path = a.path || [];
                    return path.includes(edge.from) && path.includes(edge.to);
                });
                if (hasActiveVehicle) {
                    color = '#667eea';
                    lineWidth = 2.5;
                }
            }

            // 方向颜色：上行(forward)红色，下行(backward)蓝色
            if (direction === 'forward') {
                color = '#e53e3e';
            } else if (direction === 'backward') {
                color = '#3182ce';
            }

            ctx.strokeStyle = color;
            ctx.lineWidth = lineWidth;
            ctx.lineCap = 'round';
            ctx.beginPath();
            ctx.moveTo(from.x, from.y);
            ctx.lineTo(to.x, to.y);
            ctx.stroke();

            if (direction !== 'bidirectional') {
                this.drawArrow(from, to, direction, color);
            }

            const midX = (from.x + to.x) / 2;
            const midY = (from.y + to.y) / 2;
            const angle = Math.atan2(to.y - from.y, to.x - from.x);
            const offsetX = Math.sin(angle) * 14;
            const offsetY = -Math.cos(angle) * 14;

            ctx.fillStyle = '#4a5568';
            ctx.font = 'bold 9px Arial';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(`${(edge.length || 0).toFixed(0)}m`, midX + offsetX, midY + offsetY);

            if (edge.speed_limit) {
                ctx.fillStyle = '#a0a8b8';
                ctx.font = '9px Arial';
                ctx.fillText(`${edge.speed_limit}`, midX - offsetX, midY - offsetY);
            }
        });
    }

    drawArrow(from, to, direction, color) {
        const ctx = this.ctx;
        const dx = to.x - from.x;
        const dy = to.y - from.y;
        const len = Math.sqrt(dx * dx + dy * dy);
        if (len === 0) return;
        const arrowSize = 6;
        const angle = Math.atan2(dy, dx);
        ctx.fillStyle = color;
        ctx.beginPath();
        const midX = (from.x + to.x) / 2;
        const midY = (from.y + to.y) / 2;
        ctx.moveTo(midX + arrowSize * Math.cos(angle), midY + arrowSize * Math.sin(angle));
        ctx.lineTo(midX + arrowSize * Math.cos(angle + 2.5), midY + arrowSize * Math.sin(angle + 2.5));
        ctx.lineTo(midX + arrowSize * Math.cos(angle - 2.5), midY + arrowSize * Math.sin(angle - 2.5));
        ctx.closePath();
        ctx.fill();
    }

    drawNodeConnections() {
        if (!this.isPlaying) return;
        const ctx = this.ctx;
        this.assignments.forEach(assignment => {
            const path = assignment.path || [];
            const loco = this.vehicles.find(v => v.id === assignment.locomotive_id);
            const isElectric = loco ? loco.traction_type === 'electric' : false;
            const trailColor = isElectric ? 'rgba(76,175,80,0.3)' : 'rgba(255,152,0,0.3)';

            for (let i = 0; i < path.length - 1; i++) {
                const fromNode = this.nodes.find(n => n.id === path[i]);
                const toNode = this.nodes.find(n => n.id === path[i + 1]);
                if (!fromNode || !toNode) continue;
                const from = this.worldToScreen(fromNode.x || 0, fromNode.y || 0);
                const to = this.worldToScreen(toNode.x || 0, toNode.y || 0);
                ctx.strokeStyle = trailColor;
                ctx.lineWidth = 6;
                ctx.lineCap = 'round';
                ctx.beginPath();
                ctx.moveTo(from.x, from.y);
                ctx.lineTo(to.x, to.y);
                ctx.stroke();
            }
        });
    }

    drawNodes() {
        const ctx = this.ctx;
        this.nodes.forEach(node => {
            const pos = this.worldToScreen(node.x || 0, node.y || 0);
            const color = this.nodeColors[node.type] || '#666';
            const icon = this.nodeIcons[node.type] || '📍';
            const radius = 14;

            ctx.beginPath();
            ctx.arc(pos.x, pos.y, radius, 0, Math.PI * 2);
            ctx.fillStyle = '#fff';
            ctx.fill();
            ctx.strokeStyle = color;
            ctx.lineWidth = 2;
            ctx.stroke();

            ctx.beginPath();
            ctx.arc(pos.x, pos.y, radius - 2, 0, Math.PI * 2);
            ctx.fillStyle = color + '20';
            ctx.fill();

            ctx.font = '12px Arial';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(icon, pos.x, pos.y);

            ctx.fillStyle = '#1a202c';
            ctx.font = 'bold 10px Arial';
            ctx.fillText(node.id || '', pos.x, pos.y + radius + 10);

            if (node.name) {
                ctx.fillStyle = '#718096';
                ctx.font = '9px Arial';
                ctx.fillText(node.name, pos.x, pos.y + radius + 20);
            }
        });
    }

    drawStaticVehicles() {
        if (this.isPlaying) return;
        const ctx = this.ctx;
        this.vehicles.forEach((vehicle, index) => {
            const node = this.nodes.find(n => n.id === vehicle.initial_node || vehicle.current_node);
            if (!node) return;
            const pos = this.worldToScreen(node.x || 0, node.y || 0);
            const offsetAngle = (index * 45) * Math.PI / 180;
            const offsetRadius = 20;
            const vx = pos.x + Math.cos(offsetAngle) * offsetRadius;
            const vy = pos.y + Math.sin(offsetAngle) * offsetRadius;

            const isElectric = vehicle.traction_type === 'electric';
            const vehicleColor = isElectric ? '#4caf50' : '#ff9800';
            const isBusy = vehicle.current_task !== null && vehicle.current_task !== undefined;

            ctx.beginPath();
            ctx.arc(vx, vy, 7, 0, Math.PI * 2);
            ctx.fillStyle = vehicleColor;
            ctx.fill();
            ctx.strokeStyle = isBusy ? '#f44336' : '#fff';
            ctx.lineWidth = 1.5;
            ctx.stroke();

            ctx.fillStyle = '#fff';
            ctx.font = '8px Arial';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(isElectric ? '⚡' : '⛽', vx, vy);

            ctx.fillStyle = '#1a202c';
            ctx.font = 'bold 9px Arial';
            ctx.fillText(vehicle.id, vx, vy - 16);
        });
    }

    drawAssignments() {
        if (!this.isPlaying || this.assignments.length === 0) return;
        const ctx = this.ctx;

        this.assignments.forEach(assignment => {
            const path = assignment.path || [];
            if (path.length < 2) return;

            const startTime = assignment.start_time || 0;
            const endTime = assignment.unloading_end || 100;
            if (this.currentTime < startTime || this.currentTime > endTime) return;

            const totalDuration = endTime - startTime;
            const elapsed = this.currentTime - startTime;
            const progress = Math.min(1, Math.max(0, elapsed / totalDuration));
            const easedProgress = this.easeInOutQuad(progress);

            const segCount = path.length - 1;
            const segProgress = easedProgress * segCount;
            const currentSeg = Math.min(segCount - 1, Math.floor(segProgress));
            const segFraction = segProgress - currentSeg;

            const fromNode = this.nodes.find(n => n.id === path[currentSeg]);
            const toNode = this.nodes.find(n => n.id === path[currentSeg + 1]);
            if (!fromNode || !toNode) return;

            const from = this.worldToScreen(fromNode.x || 0, fromNode.y || 0);
            const to = this.worldToScreen(toNode.x || 0, toNode.y || 0);
            const vehicleX = from.x + (to.x - from.x) * segFraction;
            const vehicleY = from.y + (to.y - from.y) * segFraction;

            const loco = this.vehicles.find(v => v.id === assignment.locomotive_id);
            const isElectric = loco ? loco.traction_type === 'electric' : false;
            const vehicleColor = isElectric ? '#4caf50' : '#ff9800';

            ctx.beginPath();
            ctx.arc(vehicleX, vehicleY, 8, 0, Math.PI * 2);
            ctx.fillStyle = vehicleColor;
            ctx.fill();
            ctx.strokeStyle = '#fff';
            ctx.lineWidth = 1.5;
            ctx.stroke();

            ctx.fillStyle = '#fff';
            ctx.font = 'bold 9px Arial';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(isElectric ? '⚡' : '⛽', vehicleX, vehicleY);

            ctx.fillStyle = vehicleColor;
            ctx.font = 'bold 9px Arial';
            ctx.textAlign = 'center';
            ctx.fillText(assignment.locomotive_id || '', vehicleX, vehicleY - 18);

            ctx.fillStyle = '#1a202c';
            ctx.font = '9px Arial';
            ctx.fillText(assignment.task_id || '', vehicleX, vehicleY - 28);
        });
    }

    drawScheduleOverlay() {
        if (!this.isPlaying || this.maxTime <= 0) return;
        const ctx = this.ctx;
        const progress = Math.min(100, Math.round((this.currentTime / this.maxTime) * 100));

        const barWidth = 220;
        const barHeight = 8;
        const barX = (this.canvas.width - barWidth) / 2;
        const barY = 20;

        ctx.fillStyle = 'rgba(255,255,255,0.9)';
        ctx.strokeStyle = '#cbd5e0';
        ctx.lineWidth = 1;
        this.roundRect(ctx, barX - 2, barY - 2, barWidth + 4, barHeight + 4, 5);
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = '#e2e8f0';
        this.roundRect(ctx, barX, barY, barWidth, barHeight, 4);
        ctx.fill();

        const gradient = ctx.createLinearGradient(barX, 0, barX + barWidth, 0);
        gradient.addColorStop(0, '#667eea');
        gradient.addColorStop(1, '#764ba2');
        ctx.fillStyle = gradient;
        this.roundRect(ctx, barX, barY, barWidth * progress / 100, barHeight, 4);
        ctx.fill();

        ctx.fillStyle = '#1a202c';
        ctx.font = 'bold 13px Arial';
        ctx.textAlign = 'center';
        ctx.fillText(`调度进度: ${progress}%`, this.canvas.width / 2, barY + 32);

        if (this.isPaused) {
            ctx.fillStyle = 'rgba(0,0,0,0.45)';
            ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
            ctx.fillStyle = '#fff';
            ctx.font = 'bold 30px Arial';
            ctx.textAlign = 'center';
            ctx.fillText('⏸ 已暂停', this.canvas.width / 2, this.canvas.height / 2);
            ctx.font = '16px Arial';
            ctx.fillText('点击"继续"按钮恢复调度', this.canvas.width / 2, this.canvas.height / 2 + 40);
        }
    }

    drawCoordinateDisplay() {
        if (!this.coordDisplay.visible) return;
        const ctx = this.ctx;
        const x = this.coordDisplay.screenX;
        const y = this.coordDisplay.screenY;

        const crossSize = 12;
        ctx.strokeStyle = '#667eea';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(x - crossSize, y); ctx.lineTo(x + crossSize, y);
        ctx.moveTo(x, y - crossSize); ctx.lineTo(x, y + crossSize);
        ctx.stroke();

        const labelX = x + 16;
        const labelY = y - 12;
        const labelText = `X: ${this.coordDisplay.x}  Y: ${this.coordDisplay.y}`;

        ctx.font = '12px Arial';
        const textWidth = ctx.measureText(labelText).width;
        ctx.fillStyle = 'rgba(102,126,234,0.95)';
        this.roundRect(ctx, labelX - 4, labelY - 12, textWidth + 16, 22, 4);
        ctx.fill();

        ctx.fillStyle = '#fff';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'middle';
        ctx.fillText(labelText, labelX + 4, labelY);
    }

    roundRect(ctx, x, y, w, h, r) {
        ctx.beginPath();
        ctx.moveTo(x + r, y);
        ctx.lineTo(x + w - r, y);
        ctx.quadraticCurveTo(x + w, y, x + w, y + r);
        ctx.lineTo(x + w, y + h - r);
        ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
        ctx.lineTo(x + r, y + h);
        ctx.quadraticCurveTo(x, y + h, x, y + h - r);
        ctx.lineTo(x, y + r);
        ctx.quadraticCurveTo(x, y, x + r, y);
        ctx.closePath();
    }

    easeInOutQuad(t) {
        return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
    }

    playSchedule(assignments, speed = 1) {
        this.assignments = assignments;
        this.currentTime = 0;
        this.isPlaying = true;
        this.isPaused = false;
        this.vehicleTrails = {};
        this.maxTime = Math.max(...assignments.map(a => a.unloading_end || 0), 1);
        this.speed = speed;
        this.animationDuration = Math.max(2000, this.maxTime * 15 / speed);
        this.playStartTime = Date.now();
    }

    pauseSchedule() {
        if (!this.isPlaying) return;
        this.isPaused = true;
        this.isPlaying = false;
        this.pauseTime = this.currentTime;
    }

    resumeSchedule() {
        if (!this.isPaused || this.assignments.length === 0) return;
        this.isPaused = false;
        this.isPlaying = true;
        this.currentTime = this.pauseTime;
        this.playStartTime = Date.now() - (this.pauseTime / this.maxTime) * this.animationDuration;
    }

    updatePlayback() {
        if (!this.isPlaying || this.isPaused || this.maxTime <= 0) return;
        const elapsed = Date.now() - this.playStartTime;
        this.currentTime = (elapsed / this.animationDuration) * this.maxTime;

        if (this.currentTime >= this.maxTime) {
            this.currentTime = this.maxTime;
            this.isPlaying = false;
        }

        if (this.onProgressUpdate) {
            const progress = Math.min(100, Math.round((this.currentTime / this.maxTime) * 100));
            this.onProgressUpdate(progress);
        }
    }

    stopSchedule() {
        this.isPlaying = false;
        this.isPaused = false;
        this.currentTime = this.maxTime;
        this.vehicleTrails = {};
    }

let dynamicMap = null;

function initMap() {
    dynamicMap = new DynamicMap('mapCanvas');
    setTimeout(() => {
        dynamicMap.resize();
        if (dynamicMap.nodes.length > 0) dynamicMap.fitToView();
    }, 100);
    setTimeout(() => {
        dynamicMap.resize();
        if (dynamicMap.nodes.length > 0) dynamicMap.fitToView();
    }, 500);
    window.addEventListener('load', () => {
        dynamicMap.resize();
        if (dynamicMap.nodes.length > 0) dynamicMap.fitToView();
    });
}
