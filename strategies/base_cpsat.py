"""
车辆调度AI算法评测系统 - 基准策略：Dijkstra + CP-SAT
"""
import math
import heapq
from typing import Dict, List, Any, Tuple, Optional
from collections import defaultdict
from ortools.sat.python import cp_model


class DijkstraPathCalculator:
    def __init__(self, map_config: Dict[str, Any], hyper_params: Dict[str, Any]):
        self.nodes = {n["id"]: n for n in map_config["nodes"]}
        self.edges = map_config["edges"]
        self.hyper_params = hyper_params
        self.adjacency = self._build_adjacency()
        self.segment_speeds = {}

    def _build_adjacency(self) -> Dict[str, List[Dict[str, Any]]]:
        adj = defaultdict(list)
        for edge in self.edges:
            from_node = edge["from"]
            to_node = edge["to"]
            length = edge["length"]
            speed_limit = edge.get("speed_limit", 600)
            slope = edge.get("slope", 0.0)
            direction = edge.get("direction", "bidirectional")

            if direction in ["forward", "bidirectional"]:
                adj[from_node].append({
                    "to": to_node,
                    "length": length,
                    "speed_limit": speed_limit,
                    "slope": slope,
                    "is_switch": self.nodes[to_node].get("type") == "switch"
                })
            if direction in ["backward", "bidirectional"]:
                adj[to_node].append({
                    "to": from_node,
                    "length": length,
                    "speed_limit": speed_limit,
                    "slope": -slope,
                    "is_switch": self.nodes[from_node].get("type") == "switch"
                })
        return adj

    def calculate_segment_speed(self, max_speed: float, speed_limit: float, slope: float) -> float:
        speed = min(max_speed, speed_limit)
        if slope > 0:
            speed *= (1 - self.hyper_params["slope_factor_uphill"] * slope)
        elif slope < 0:
            speed *= (1 + self.hyper_params["slope_factor_downhill"] * abs(slope))
        return max(speed, 10.0)

    def shortest_path(self, start: str, end: str, loco_max_speed: float, loco_id: str) -> Tuple[List[str], float, List[Dict[str, Any]]]:
        if start == end:
            return [start], 0.0, []

        distances = {node: float('inf') for node in self.nodes}
        distances[start] = 0
        previous = {node: None for node in self.nodes}
        pq = [(0, start)]
        visited = set()

        while pq:
            current_dist, current = heapq.heappop(pq)
            if current in visited:
                continue
            visited.add(current)
            if current == end:
                break

            for neighbor in self.adjacency[current]:
                next_node = neighbor["to"]
                if next_node in visited:
                    continue

                seg_speed = self.calculate_segment_speed(
                    loco_max_speed,
                    neighbor["speed_limit"],
                    neighbor["slope"]
                )
                travel_time = neighbor["length"] / seg_speed

                if neighbor["is_switch"]:
                    travel_time += self.hyper_params["switch_pass_time"]

                new_dist = current_dist + travel_time
                if new_dist < distances[next_node]:
                    distances[next_node] = new_dist
                    previous[next_node] = current
                    heapq.heappush(pq, (new_dist, next_node))

        if distances[end] == float('inf'):
            raise ValueError(f"无法找到从{start}到{end}的路径")

        path = []
        current = end
        while current is not None:
            path.append(current)
            current = previous[current]
        path.reverse()

        segments = []
        for i in range(len(path) - 1):
            from_node = path[i]
            to_node = path[i + 1]
            seg_info = None
            for neighbor in self.adjacency[from_node]:
                if neighbor["to"] == to_node:
                    seg_info = neighbor
                    break
            if seg_info:
                seg_speed = self.calculate_segment_speed(
                    loco_max_speed,
                    seg_info["speed_limit"],
                    seg_info["slope"]
                )
                segments.append({
                    "from": from_node,
                    "to": to_node,
                    "length": seg_info["length"],
                    "speed": seg_speed,
                    "time": seg_info["length"] / seg_speed
                })

        self.segment_speeds[loco_id] = segments
        return path, distances[end], segments

    def precompute_all_paths(self, locomotives: List[Dict[str, Any]]) -> Dict[str, Any]:
        all_paths = {}
        for loco in locomotives:
            loco_id = loco["id"]
            max_speed = loco["max_speed"]
            all_paths[loco_id] = {}
            for start_node in self.nodes:
                all_paths[loco_id][start_node] = {}
                for end_node in self.nodes:
                    path, time, segments = self.shortest_path(start_node, end_node, max_speed, loco_id)
                    all_paths[loco_id][start_node][end_node] = {
                        "path": path,
                        "time": time,
                        "segments": segments
                    }
        return all_paths


class CPSATScheduler:
    def __init__(self, map_config, tasks_config, locomotives_config, hyper_params, precomputed_paths):
        self.map_config = map_config
        self.tasks = tasks_config["tasks"]
        self.locomotives = locomotives_config["locomotives"]
        self.hyper_params = hyper_params
        self.precomputed_paths = precomputed_paths
        self.BigM = hyper_params["BigM"]
        self.precision = hyper_params["travel_time_precision"]

    def _ceil(self, minutes: float) -> int:
        return int(math.ceil(minutes / self.precision) * self.precision)

    def solve(self) -> Dict[str, Any]:
        model = cp_model.CpModel()

        # ===== 预处理：排除已绑定任务的机车 =====

        # 已分配的任务（热启动，不参与调度）
        assigned_tasks = {}
        bound_loco_ids = set()
        for t in self.tasks:
            if t.get("bound_locomotive") and t["status"] == "running":
                bound_loco_ids.add(t["bound_locomotive"])
                loco = next((l for l in self.locomotives if l["id"] == t["bound_locomotive"]), None)
                if loco:
                    travel_time = self._ceil(
                        self.precomputed_paths[loco["id"]][t["start_node"]][t["end_node"]]["time"]
                    )
                    loading = self.hyper_params["loading_time"]
                    unloading = self.hyper_params["unloading_time"]
                    assigned_tasks[t["id"]] = {
                        "task": t,
                        "locomotive": loco,
                        "start_time": 0,
                        "loading_end": loading,
                        "transport_end": loading + travel_time,
                        "unloading_end": loading + travel_time + unloading
                    }

        schedulable_locomotives = [
            l for l in self.locomotives
            if l.get("is_powered_on", True)
            and l.get("is_schedulable", True)
            and l["id"] not in bound_loco_ids
        ]

        active_tasks = [
            t for t in self.tasks
            if t["status"] in ["pending", "running", "paused"]
            and t["id"] not in assigned_tasks
        ]

        if not active_tasks:
            return {
                "solve_status": "optimal",
                "makespan": 0,
                "assignments": [],
                "message": "没有待调度的任务"
            }

        if not schedulable_locomotives:
            return {
                "solve_status": "infeasible",
                "makespan": -1,
                "assignments": [],
                "message": "没有可调度的机车"
            }

        num_locos = len(schedulable_locomotives)
        loco_index = {l["id"]: i for i, l in enumerate(schedulable_locomotives)}

        # ===== 决策变量 =====
        # task -> locomotive index (0..num_locos-1)
        loco_assign = {}
        # 任务执行时间窗口 [start, end]
        task_start = {}
        task_end = {}

        for tid in [t["id"] for t in active_tasks]:
            loco_assign[tid] = model.NewIntVar(0, num_locos - 1, f"assign_{tid}")
            task_start[tid] = model.NewIntVar(0, self.BigM, f"start_{tid}")
            task_end[tid] = model.NewIntVar(0, self.BigM, f"end_{tid}")

        makespan = model.NewIntVar(0, self.BigM, "makespan")

        # ===== 预计算时间常数 =====
        # loco -> task: 空驶时间、作业时间
        empty_times = {}   # loco_id, tid -> 空驶时间（初始位置->任务起点）
        job_times = {}     # loco_id, tid -> 有载作业时间（起点->终点）
        seq_empty = {}     # loco_id, tid1, tid2 -> tid1结束后到tid2起点的空驶时间

        loading = self.hyper_params["loading_time"]
        unloading = self.hyper_params["unloading_time"]

        for loco in schedulable_locomotives:
            lid = loco["id"]
            empty_times[lid] = {}
            job_times[lid] = {}
            seq_empty[lid] = {}

            for task in active_tasks:
                tid = task["id"]
                empty_times[lid][tid] = self._ceil(
                    self.precomputed_paths[lid][loco["initial_node"]][task["start_node"]]["time"]
                )
                job_times[lid][tid] = self._ceil(
                    self.precomputed_paths[lid][task["start_node"]][task["end_node"]]["time"]
                )

            for t1 in active_tasks:
                t1id = t1["id"]
                seq_empty[lid][t1id] = {}
                for t2 in active_tasks:
                    t2id = t2["id"]
                    seq_empty[lid][t1id][t2id] = self._ceil(
                        self.precomputed_paths[lid][t1["end_node"]][t2["start_node"]]["time"]
                    )

        # ===== 约束1+5: 时间链 + 载重约束（合并，用 OnlyEnforceIf 统一表达）=====
        # 对于能承载该任务的机车: 添加时间链约束
        # 对于不能承载的机车: 禁止赋值
        for task in active_tasks:
            tid = task["id"]
            weight = task["material_weight"]
            for i, loco in enumerate(schedulable_locomotives):
                lid = loco["id"]
                can_carry = (weight <= loco["Q"])
                b = model.NewBoolVar(f"b_{tid}_{lid}")
                # 建立 b 与 loco_assign 的等价关系
                model.Add(loco_assign[tid] == i).OnlyEnforceIf(b)
                model.Add(loco_assign[tid] != i).OnlyEnforceIf(b.Not())

                if can_carry:
                    # 能承载: 添加时间链约束
                    model.Add(
                        task_end[tid] ==
                        task_start[tid] + empty_times[lid][tid]
                        + loading + job_times[lid][tid] + unloading
                    ).OnlyEnforceIf(b)
                else:
                    # 不能承载: 强制 b = False（即 loco_assign != i）
                    model.Add(b == 0)  # 禁止此分配

        # ===== 约束2: makespan = max(task_end) =====

        for tid in [t["id"] for t in active_tasks]:
            model.Add(task_end[tid] <= makespan)
        for tid, info in assigned_tasks.items():
            model.Add(info["unloading_end"] <= makespan)

        # ===== 约束3: 任务依赖 =====
        for task in active_tasks:
            for dep_id in task.get("depends_on", []):
                if dep_id in task_end:
                    model.Add(task_start[task["id"]] >= task_end[dep_id])

        # ===== 约束4: 同机车任务不重叠（使用顺序变量选择方向）=====
        # 若两个任务被分配到同一台机车，必须有执行顺序
        for i, loco in enumerate(schedulable_locomotives):
            lid = loco["id"]
            tids = [t["id"] for t in active_tasks]
            for idx1, tid1 in enumerate(tids):
                for idx2, tid2 in enumerate(tids):
                    if idx1 >= idx2:
                        continue

                    # b1 = (loco_assign[tid1] == i)
                    b1 = model.NewBoolVar(f"b1_{lid}_{tid1}")
                    model.Add(loco_assign[tid1] == i).OnlyEnforceIf(b1)
                    model.Add(loco_assign[tid1] != i).OnlyEnforceIf(b1.Not())
                    # b2 = (loco_assign[tid2] == i)
                    b2 = model.NewBoolVar(f"b2_{lid}_{tid2}")
                    model.Add(loco_assign[tid2] == i).OnlyEnforceIf(b2)
                    model.Add(loco_assign[tid2] != i).OnlyEnforceIf(b2.Not())

                    # both = b1 AND b2：两个任务都在同一台机车上
                    both = model.NewBoolVar(f"both_{lid}_{tid1}_{tid2}")
                    model.AddBoolAnd([b1, b2]).OnlyEnforceIf(both)
                    model.AddBoolOr([b1.Not(), b2.Not()]).OnlyEnforceIf(both.Not())

                    # o = 顺序变量：o=True 表示 tid1 先执行，o=False 表示 tid2 先执行
                    o = model.NewBoolVar(f"o_{lid}_{tid1}_{tid2}")
                    
                    t1_to_t2 = seq_empty[lid][tid1][tid2]
                    t2_to_t1 = seq_empty[lid][tid2][tid1]

                    # 若 both=True 且 o=True：tid1 先执行，tid2.start >= tid1.end + t1_to_t2
                    model.Add(
                        task_start[tid2] >= task_end[tid1] + t1_to_t2
                    ).OnlyEnforceIf(both, o)
                    # 若 both=True 且 o=False：tid2 先执行，tid1.start >= tid2.end + t2_to_t1
                    model.Add(
                        task_start[tid1] >= task_end[tid2] + t2_to_t1
                    ).OnlyEnforceIf(both, o.Not())

        model.Minimize(makespan)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.hyper_params.get("solve_time_limit", 300.0)
        solver.parameters.num_search_workers = 8

        status = solver.Solve(model)

        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            assignments = []
            for task in active_tasks:
                tid = task["id"]
                loco_idx = solver.Value(loco_assign[tid])
                loco = schedulable_locomotives[loco_idx]
                start = solver.Value(task_start[tid])
                end = solver.Value(task_end[tid])

                path_info = self.precomputed_paths[loco["id"]][task["start_node"]][task["end_node"]]
                loading_end = start + empty_times[loco["id"]][tid] + loading
                transport_end = loading_end + job_times[loco["id"]][tid]

                assignments.append({
                    "task_id": tid,
                    "locomotive_id": loco["id"],
                    "start_time": start,
                    "loading_end": loading_end,
                    "transport_end": transport_end,
                    "unloading_end": end,
                    "path": path_info["path"],
                    "segments": path_info["segments"]
                })

            # 加上热启动（已分配）的任务
            for tid, info in assigned_tasks.items():
                loco = info["locomotive"]
                path_info = self.precomputed_paths[loco["id"]][info["task"]["start_node"]][info["task"]["end_node"]]
                assignments.append({
                    "task_id": tid,
                    "locomotive_id": loco["id"],
                    "start_time": info["start_time"],
                    "loading_end": info["loading_end"],
                    "transport_end": info["transport_end"],
                    "unloading_end": info["unloading_end"],
                    "path": path_info["path"],
                    "segments": path_info["segments"]
                })

            return {
                "solve_status": "optimal" if status == cp_model.OPTIMAL else "feasible",
                "makespan": max(solver.Value(makespan),
                               max((info["unloading_end"] for info in assigned_tasks.values()), default=0)),
                "assignments": assignments,
                "num_tasks": len(assignments),
                "num_locomotives": len(schedulable_locomotives) + len(assigned_tasks),
                "solve_time": round(solver.WallTime(), 2),
                "config": {
                    "solve_time_limit": self.hyper_params.get("solve_time_limit", 300),
                    "num_search_workers": 8
                }
            }
        else:
            return {
                "solve_status": "infeasible",
                "makespan": -1,
                "assignments": [],
                "message": "无法找到可行解，请检查约束条件"
            }
