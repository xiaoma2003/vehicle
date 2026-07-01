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
        this.directionLock = { up: false, down: false };

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
        this.canvas.addEventListener('wheel', (e) => this.onWheel(e));

        this.animate();
    }

    resize() {
        const rect = this.canvas.parentElement.getBoundingClientRect();
        this.canvas.width = rect.width;
        this.canvas.height = 650;
    }

    setData(nodes, edges) {
        this.nodes = nodes;
        this.edges = edges;
        this.fitToView();
    }

    setVehicles(vehicles) {
        this.vehicles = vehicles;
    }

    setAssignments(assignments) {
        this.assignments = assignments;
    }

    setDirectionLock(up, down) {
        this.directionLock = { up, down };
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
        this.offsetX = padding - minX * this.scale;
        this.offsetY = padding - minY * this.scale;
    }

    worldToScreen(x, y) {
        return {
            x: x * this.scale + this.offsetX,
            y: y * this.scale + this.offsetY
        };
    }

    screenToWorld(x, y) {
        return {
            x: (x - this.offsetX) / this.scale,
            y: (y - this.offsetY) / this.scale
        };
    }

    onMouseDown(e) {
        const rect = this.canvas.getBoundingClientRect();
        this.isDragging = true;
        this.lastMouseX = e.clientX - rect.left;
        this.lastMouseY = e.clientY - rect.top;
        this.canvas.style.cursor = 'grabbing';
    }

    onMouseMove(e) {
        if (!this.isDragging) return;
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

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
        this.scale = Math.max(0.1, Math.min(5, this.scale * zoomFactor));

        const worldAfter = this.screenToWorld(mouseX, mouseY);

        this.offsetX += (worldAfter.x - worldBefore.x) * this.scale;
        this.offsetY += (worldAfter.y - worldBefore.y) * this.scale;
    }

    animate() {
        this.draw();
        this.animationFrame = requestAnimationFrame(() => this.animate());
    }

    draw() {
        const ctx = this.ctx;
        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        this.drawGrid();
        this.drawEdges();
        this.drawNodes();
        this.drawAssignments();
        this.drawVehicles();
    }

    drawGrid() {
        const ctx = this.ctx;
        ctx.strokeStyle = '#e8e8e8';
        ctx.lineWidth = 0.5;

        const gridSize = 50 * this.scale;
        const startX = this.offsetX % gridSize;
        const startY = this.offsetY % gridSize;

        for (let x = startX; x < this.canvas.width; x += gridSize) {
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, this.canvas.height);
            ctx.stroke();
        }

        for (let y = startY; y < this.canvas.height; y += gridSize) {
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(this.canvas.width, y);
            ctx.stroke();
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
            let color = '#aaa';

            if (direction === 'forward') {
                color = this.directionLock.up ? '#f44336' : '#666';
            } else if (direction === 'backward') {
                color = this.directionLock.down ? '#2196f3' : '#666';
            }

            ctx.strokeStyle = color;
            ctx.lineWidth = 2;
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
            ctx.fillStyle = '#666';
            ctx.font = '9px Arial';
            ctx.textAlign = 'center';
            ctx.fillText(`${(edge.length || 0).toFixed(0)}m`, midX, midY - 6);
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

            ctx.font = '12px Arial';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(icon, pos.x, pos.y);

            ctx.fillStyle = '#333';
            ctx.font = 'bold 10px Arial';
            ctx.fillText(node.id || '', pos.x, pos.y + radius + 10);

            if (node.name) {
                ctx.fillStyle = '#666';
                ctx.font = '9px Arial';
                ctx.fillText(node.name, pos.x, pos.y + radius + 20);
            }
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

            const segCount = path.length - 1;
            const segProgress = progress * segCount;
            const currentSeg = Math.min(segCount - 1, Math.floor(segProgress));
            const segFraction = segProgress - currentSeg;

            const fromNode = this.nodes.find(n => n.id === path[currentSeg]);
            const toNode = this.nodes.find(n => n.id === path[currentSeg + 1]);

            if (!fromNode || !toNode) return;

            const from = this.worldToScreen(fromNode.x || 0, fromNode.y || 0);
            const to = this.worldToScreen(toNode.x || 0, toNode.y || 0);

            const vehicleX = from.x + (to.x - from.x) * segFraction;
            const vehicleY = from.y + (to.y - from.y) * segFraction;

            const isElectric = assignment.locomotive_type === 'electric';
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
            ctx.fillText('🚃', vehicleX, vehicleY);

            ctx.fillStyle = '#333';
            ctx.font = 'bold 9px Arial';
            ctx.fillText(assignment.task_id || '', vehicleX, vehicleY - 16);
        });
    }

    drawVehicles() {
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
        });
    }

    playSchedule(assignments) {
        this.assignments = assignments;
        this.currentTime = 0;
        this.isPlaying = true;

        const maxTime = Math.max(...assignments.map(a => a.unloading_end || 0));
        const duration = Math.max(5000, maxTime * 10);
        const startTime = Date.now();

        const animate = () => {
            if (!this.isPlaying) return;

            const elapsed = Date.now() - startTime;
            this.currentTime = (elapsed / duration) * maxTime;

            if (elapsed < duration) {
                requestAnimationFrame(animate);
            } else {
                this.currentTime = maxTime;
                this.isPlaying = false;
            }
        };

        animate();
    }

    pauseSchedule() {
        this.isPlaying = false;
    }

    resumeSchedule() {
        if (this.assignments.length > 0) {
            this.isPlaying = true;
        }
    }
}

let dynamicMap = null;

function initMap() {
    dynamicMap = new DynamicMap('mapCanvas');
}
