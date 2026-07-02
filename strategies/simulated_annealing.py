"""
候选策略3：模拟退火算法（Simulated Annealing）
基于模拟退火的调度优化算法
"""
import random
import math
import time
from typing import Dict, List, Any, Tuple


class SimulatedAnnealingScheduler:
    def __init__(self, map_config, tasks_config, locomotives_config, hyper_params, precomputed_paths):
        self.map_config = map_config
        self.tasks = tasks_config["tasks"]
        self.locomotives = locomotives_config["locomotives"]
        self.hyper_params = hyper_params
        self.precomputed_paths = precomputed_paths
        random.seed(42)

        # 排除 bound locomotive（热启动任务占用的机车）
        self.bound_loco_ids = set()
        self.assigned_tasks = {}
        for t in self.tasks:
            if t.get("bound_locomotive") and t["status"] == "running":
                self.bound_loco_ids.add(t["bound_locomotive"])
                loco = next((l for l in self.locomotives if l["id"] == t["bound_locomotive"]), None)
                if loco:
                    travel_time = int(math.ceil(
                        self.precomputed_paths[loco["id"]][t["start_node"]][t["end_node"]]["time"]
                        / self.hyper_params["travel_time_precision"]
                    ) * self.hyper_params["travel_time_precision"])
                    loading = self.hyper_params["loading_time"]
                    unloading = self.hyper_params["unloading_time"]
                    self.assigned_tasks[t["id"]] = {
                        "task": t,
                        "locomotive": loco,
                        "start_time": 0,
                        "loading_end": loading,
                        "transport_end": loading + travel_time,
                        "unloading_end": loading + travel_time + unloading
                    }

        self.schedulable_locomotives = [
            l for l in self.locomotives
            if l.get("is_powered_on", True) and l.get("is_schedulable", True)
            and l["id"] not in self.bound_loco_ids
        ]
        self.active_tasks = [
            t for t in self.tasks
            if t["status"] in ["pending", "running", "paused"]
            and t["id"] not in self.assigned_tasks
        ]

    def _create_initial_solution(self) -> List[int]:
        tasks = list(range(len(self.active_tasks)))
        tasks.sort(key=lambda i: (self.active_tasks[i]["priority"],
                                   -self.active_tasks[i]["material_weight"]))
        return tasks

    def _decode_solution(self, solution: List[int]) -> Tuple[List[Dict[str, Any]], int]:
        if not self.active_tasks or not self.schedulable_locomotives:
            return [], 0

        loco_available_time = {l["id"]: 0 for l in self.schedulable_locomotives}
        loco_current_node = {l["id"]: l["initial_node"] for l in self.schedulable_locomotives}

        edge_occupancy = {}  # edge_key -> [(entry_time, exit_time, direction), ...]
        task_end_times = {}  # 记录任务实际完成时间
        assignments = []
        scheduled = set()
        max_iterations = len(solution) * 2
        iter_count = 0

        while len(scheduled) < len(solution) and iter_count < max_iterations:
            iter_count += 1
            made_progress = False

            for idx in solution:
                if idx in scheduled:
                    continue
                task = self.active_tasks[idx]
                tid = task["id"]

                # 修复: 依赖任务必须已完成（finish），而非仅被分配（assigned）
                deps_finished = all(
                    dep_id in task_end_times
                    for dep_id in task.get("depends_on", [])
                )
                if not deps_finished:
                    continue

                # 依赖任务的最早完成时间约束
                dep_ready_time = max(
                    (task_end_times[dep_id] for dep_id in task.get("depends_on", [])),
                    default=0
                )

                best_loco = None
                best_end_time = float('inf')
                best_path_info = None
                best_start_time = 0
                best_empty_time = 0

                for loco in self.schedulable_locomotives:
                    if task["material_weight"] > loco["Q"]:
                        continue

                    loco_id = loco["id"]
                    path_info = self.precomputed_paths[loco_id][task["start_node"]][task["end_node"]]
                    empty_path_info = self.precomputed_paths[loco_id][loco_current_node[loco_id]][task["start_node"]]

                    travel_time = path_info["time"]
                    empty_travel_time = empty_path_info["time"]
                    loading_time = self.hyper_params["loading_time"]
                    unloading_time = self.hyper_params["unloading_time"]

                    start_time = max(loco_available_time[loco_id], dep_ready_time)
                    # 边安全约束：调整开始时间以避免冲突
                    start_time = self._adjust_for_edge_safety(
                        start_time, empty_path_info, path_info, edge_occupancy
                    )
                    total_time = empty_travel_time + loading_time + travel_time + unloading_time
                    end_time = start_time + total_time

                    if end_time < best_end_time:
                        best_end_time = end_time
                        best_loco = loco
                        best_path_info = path_info
                        best_start_time = start_time
                        best_empty_time = empty_travel_time

                if best_loco:
                    loco_id = best_loco["id"]
                    # 获取最佳机车的空驶路径信息
                    empty_path_info = self.precomputed_paths[loco_id][loco_current_node[loco_id]][task["start_node"]]
                    loading_end = best_start_time + best_empty_time + self.hyper_params["loading_time"]
                    transport_end = loading_end + best_path_info["time"]
                    unloading_end = transport_end + self.hyper_params["unloading_time"]

                    assignments.append({
                        "task_id": tid,
                        "locomotive_id": loco_id,
                        "start_time": int(best_start_time),
                        "loading_end": int(loading_end),
                        "transport_end": int(transport_end),
                        "unloading_end": int(unloading_end),
                        "path": best_path_info["path"],
                        "segments": best_path_info["segments"]
                    })

                    loco_available_time[loco_id] = unloading_end
                    loco_current_node[loco_id] = task["end_node"]
                    # 记录边占用
                    self._add_edge_occupancy(
                        best_start_time, empty_path_info, best_path_info, edge_occupancy
                    )
                    scheduled.add(idx)
                    task_end_times[tid] = unloading_end  # 记录实际完成时间（用 task_id 作为 key）
                    made_progress = True

            if not made_progress:
                break

        # 加入热启动任务
        for tid, info in self.assigned_tasks.items():
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

        # makespan 取所有任务的最大完成时间
        all_end_times = [a["unloading_end"] for a in assignments]
        makespan = max(all_end_times) if all_end_times else 0
        return assignments, makespan

    def _get_neighbor(self, solution: List[int]) -> List[int]:
        neighbor = solution.copy()
        if len(neighbor) <= 1:
            return neighbor

        move_type = random.randint(0, 2)

        if move_type == 0:
            i, j = random.sample(range(len(neighbor)), 2)
            neighbor[i], neighbor[j] = neighbor[j], neighbor[i]
        elif move_type == 1:
            i = random.randint(0, len(neighbor) - 1)
            j = random.randint(0, len(neighbor) - 1)
            if i != j:
                task = neighbor.pop(i)
                neighbor.insert(j, task)
        else:
            if len(neighbor) >= 4:
                start = random.randint(0, len(neighbor) - 2)
                end = random.randint(start + 1, len(neighbor) - 1)
                neighbor[start:end+1] = reversed(neighbor[start:end+1])

        return neighbor

    def _adjust_for_edge_safety(self, start_time, empty_path_info, job_path_info, edge_occupancy):
        """调整开始时间以避免边安全冲突（同向保持间隔，反向不可重叠）"""
        safety_gap = self.hyper_params.get("safety_gap", 5)
        loading = self.hyper_params["loading_time"]

        max_iterations = 100  # 防止无限循环
        for _ in range(max_iterations):
            new_start = start_time

            # 检查空驶路径边
            cumulative = 0
            for seg in empty_path_info.get("segments", []):
                entry = start_time + cumulative
                exit_t = entry + seg["time"]
                delay = self._find_edge_delay(
                    seg["from"], seg["to"], entry, exit_t, cumulative, edge_occupancy, safety_gap
                )
                if delay is not None and delay > new_start:
                    new_start = delay
                cumulative += seg["time"]

            # 检查作业路径边
            cumulative = empty_path_info["time"] + loading
            for seg in job_path_info.get("segments", []):
                entry = start_time + cumulative
                exit_t = entry + seg["time"]
                delay = self._find_edge_delay(
                    seg["from"], seg["to"], entry, exit_t, cumulative, edge_occupancy, safety_gap
                )
                if delay is not None and delay > new_start:
                    new_start = delay
                cumulative += seg["time"]

            if new_start == start_time:
                break
            start_time = new_start

        return start_time

    def _find_edge_delay(self, from_n, to_n, entry, exit_t, offset, edge_occupancy, safety_gap):
        """检查单条边的冲突，返回需要延迟到的开始时间（无冲突返回 None）"""
        nodes = sorted([from_n, to_n])
        edge_key = f"{nodes[0]}-{nodes[1]}"

        if edge_key not in edge_occupancy:
            return None

        edge = next((e for e in self.map_config["edges"]
                    if (e["from"] == nodes[0] and e["to"] == nodes[1]) or
                       (e["from"] == nodes[1] and e["to"] == nodes[0])), None)
        if edge is None:
            return None

        if edge["from"] == from_n and edge["to"] == to_n:
            task_dir = "forward"
        else:
            task_dir = "backward"

        max_delay = None
        for occ_entry, occ_exit, occ_dir in edge_occupancy[edge_key]:
            if entry >= occ_exit or exit_t <= occ_entry:
                continue  # 不重叠，无冲突

            if task_dir != occ_dir:
                # 反向冲突：必须等到占用结束后才能进入
                delay = occ_exit - offset
            else:
                # 同向：需要安全间隔
                delay = occ_exit + safety_gap - offset

            if max_delay is None or delay > max_delay:
                max_delay = delay

        return max_delay

    def _add_edge_occupancy(self, start_time, empty_path_info, job_path_info, edge_occupancy):
        """记录任务的边占用信息"""
        safety_gap = self.hyper_params.get("safety_gap", 5)
        loading = self.hyper_params["loading_time"]

        cumulative = start_time
        for seg in empty_path_info.get("segments", []):
            self._mark_edge_occupied(
                seg["from"], seg["to"], cumulative, cumulative + seg["time"], edge_occupancy
            )
            cumulative += seg["time"]

        cumulative = start_time + empty_path_info["time"] + loading
        for seg in job_path_info.get("segments", []):
            self._mark_edge_occupied(
                seg["from"], seg["to"], cumulative, cumulative + seg["time"], edge_occupancy
            )
            cumulative += seg["time"]

    def _mark_edge_occupied(self, from_n, to_n, entry, exit_t, edge_occupancy):
        """标记一条边被占用"""
        nodes = sorted([from_n, to_n])
        edge_key = f"{nodes[0]}-{nodes[1]}"

        edge = next((e for e in self.map_config["edges"]
                    if (e["from"] == nodes[0] and e["to"] == nodes[1]) or
                       (e["from"] == nodes[1] and e["to"] == nodes[0])), None)
        if edge is None:
            return

        if edge["from"] == from_n and edge["to"] == to_n:
            task_dir = "forward"
        else:
            task_dir = "backward"

        if edge_key not in edge_occupancy:
            edge_occupancy[edge_key] = []
        edge_occupancy[edge_key].append((entry, exit_t, task_dir))

    def solve(self, initial_temp: float = 1000.0, cooling_rate: float = 0.995,
              min_temp: float = 0.1, iterations_per_temp: int = 20) -> Dict[str, Any]:
        if not self.active_tasks or not self.schedulable_locomotives:
            return {
                "solve_status": "optimal",
                "makespan": 0,
                "assignments": [],
                "algorithm": "simulated_annealing",
                "solve_time": 0,
                "iterations": 0,
                "final_temp": initial_temp
            }

        start_time = time.time()
        current_solution = self._create_initial_solution()
        current_assignments, current_makespan = self._decode_solution(current_solution)

        best_solution = current_solution.copy()
        best_assignments = current_assignments
        best_makespan = current_makespan

        temp = initial_temp
        total_iterations = 0

        while temp > min_temp:
            for _ in range(iterations_per_temp):
                total_iterations += 1
                neighbor = self._get_neighbor(current_solution)
                neighbor_assignments, neighbor_makespan = self._decode_solution(neighbor)

                delta = neighbor_makespan - current_makespan

                if delta < 0 or random.random() < math.exp(-delta / temp):
                    current_solution = neighbor
                    current_makespan = neighbor_makespan
                    current_assignments = neighbor_assignments

                    if current_makespan < best_makespan:
                        best_solution = current_solution.copy()
                        best_makespan = current_makespan
                        best_assignments = current_assignments

            temp *= cooling_rate

        return {
            "solve_status": "feasible",
            "makespan": best_makespan,
            "assignments": best_assignments,
            "num_tasks": len(best_assignments),
            "num_locomotives": len(self.schedulable_locomotives) + len(self.assigned_tasks),
            "algorithm": "simulated_annealing",
            "solve_time": round(time.time() - start_time, 2),
            "initial_temp": initial_temp,
            "final_temp": temp,
            "cooling_rate": cooling_rate,
            "iterations": total_iterations
        }
