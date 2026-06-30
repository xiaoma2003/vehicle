# 车辆调度AI算法评测系统

基于《AI项目综合训练》任务书设计的车辆调度AI算法评测系统，支持多种调度算法对比、动态地图展示、热启动、优先级让道等功能。

## 功能特性

### 🗺️ 动态地图展示
- Canvas动态渲染地图节点和边
- 支持缩放、拖拽交互
- 节点类型：车站、加油站、充电站、物料站、道岔
- 边方向：双向、正向(上行)、反向(下行)
- 车辆运行实时动画展示

### 🚃 车辆管理
- 支持油车（柴油机车）和电车（电动机车）两种类型
- 动态添加车辆功能
- 车辆实时状态展示（能源、位置、任务状态）
- 能源管理（电量/油量监控与报警）

### 📋 任务调度
- 三种任务类型：普通任务、临时任务、紧急任务
- 任务优先级（1-99级，1级最高）
- 任务依赖链管理
- 热启动支持：已绑定任务的车辆不再分配新任务

### ⚙️ 调度算法（4种）
1. **CP-SAT基准策略** - Dijkstra + Google OR-Tools CP-SAT约束规划
2. **贪心算法** - 基于优先级和最短路径的贪心调度
3. **遗传算法** - 进化算法搜索最优调度方案
4. **模拟退火** - 基于模拟退火的调度优化

### 🚦 让道机制
- 优先级低的车辆为优先级高且速度快的车辆让道
- 让道措施：在最近节点停下让道
- 让完后继续完成车辆调度
- 上下行方向调度：同一方向无任务时才能换方向

### 📊 多策略对比
- 多算法同时对比评测
- 工期、求解时间等多维度对比
- 自动识别最优策略和最快策略
- 与基准策略的对比分析

### 💾 数据持久化
- SQLite数据库存储（7张表）
- 历史回放功能
- 多维度组合查询
- 分页与导出支持
- JSON配置文件驱动

### 📝 系统日志
- 完整的操作日志记录
- 日志级别：INFO/WARN/ERROR
- 日志查询与过滤

## 项目结构

```
vehicle-scheduling-system/
├── app.py                    # Flask后端服务入口
├── config_loader.py          # 配置加载与验证模块
├── schedule_engine.py        # 调度引擎核心模块
├── schedule_api.py           # ScheduleAPI接口类
├── schedule_database.py      # SQLite数据库模块
├── strategy_manager.py       # 策略管理器
├── test_system.py            # 集成测试脚本
├── requirements.txt          # Python依赖
├── strategies/               # 调度策略目录
│   ├── __init__.py
│   ├── base_cpsat.py         # CP-SAT基准策略（含Dijkstra）
│   ├── greedy_strategy.py    # 贪心算法
│   ├── genetic_algorithm.py  # 遗传算法
│   └── simulated_annealing.py # 模拟退火算法
├── templates/                # 前端模板
│   └── index.html            # 主页面
├── static/                   # 静态资源
│   ├── css/style.css         # 样式文件
│   └── js/
│       ├── map.js            # 地图渲染模块
│       └── app.js            # 前端主应用
└── data/                     # 数据目录
    ├── map_config.json       # 地图配置
    ├── tasks_config.json     # 任务配置
    ├── locomotives_config.json # 机车配置
    └── hyper_params.json     # 超参数配置
```

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行系统

```bash
python app.py
```

访问 http://localhost:5000 打开系统界面

### 运行测试

```bash
python test_system.py
```

## API接口

### 配置管理
- `GET /api/config/map` - 获取地图配置
- `POST /api/config/map` - 保存地图配置
- `GET /api/config/tasks` - 获取任务配置
- `POST /api/config/tasks` - 保存任务配置
- `GET /api/config/locomotives` - 获取机车配置
- `POST /api/config/locomotives` - 保存机车配置
- `GET /api/config/hyper-params` - 获取超参数
- `POST /api/config/hyper-params` - 保存超参数

### 调度控制
- `POST /api/schedule/run` - 执行调度
- `POST /api/schedule/compare` - 多策略对比
- `GET /api/strategies` - 获取可用策略列表

### 动态添加
- `POST /api/locomotives/add` - 添加机车
- `POST /api/tasks/add` - 添加任务
- `POST /api/nodes/add` - 添加节点
- `POST /api/edges/add` - 添加边

### 任务管理
- `POST /api/tasks/boost-priority` - 提升任务优先级
- `POST /api/emergency/trigger` - 触发紧急任务

### 查询接口
- `GET /api/query/runs` - 查询调度运行记录
- `GET /api/query/tasks` - 查询任务
- `GET /api/query/locomotives` - 查询机车
- `GET /api/query/logs` - 查询系统日志
- `GET /api/runs/<id>` - 获取运行详情
- `GET /api/batches/<id>` - 获取批次历史
- `GET /api/statistics` - 获取统计信息
- `GET /api/batch-ids` - 获取所有批次ID

### 其他
- `POST /api/give-way/analyze` - 让道分析
- `GET /api/direction/check` - 检查方向锁
- `GET /api/export/<batch_id>` - 导出批次数据

## 核心约束（CP-SAT基准策略）

1. 每台机车同时只能执行一个任务
2. 每个任务只能分配给一台机车
3. 任务必须在指定时间窗内完成
4. 机车载重能力约束
5. 任务依赖约束（前置任务完成后才能开始）
6. 机车必须开机且可调度才能分配任务
7. 能源消耗约束（电量/油量限制）
8. 上下行方向约束（同一方向无任务才能换向）
9. 道岔通过时间约束
10. 坡度对速度的影响（上坡减速、下坡加速）
11. 装货/卸货时间约束
12. 优先级约束（高优先级任务优先分配）
13. 热启动约束（已有任务的车辆不再分配）

## 技术栈

- **后端**: Python + Flask + OR-Tools
- **前端**: 原生JavaScript + Canvas
- **数据库**: SQLite
- **算法**: CP-SAT、贪心算法、遗传算法、模拟退火

## 性能指标

| 指标 | 支持规模 | 固定基准 |
|------|---------|---------|
| 车辆数 | ≤100台 | 10台 |
| 任务数 | ≤500个 | 50个 |
| 节点数 | ≤200个 | - |
| 求解时间 | ≤300秒 | - |

## 许可证

Apache 2.0
