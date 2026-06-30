"""
候选策略3：模拟退火算法（Simulated Annealing）
基于模拟退火的调度优化算法
"""
import random
import math
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

    def solve(self, initial_temp: float = 1000.0, cooling_rate: float = 0.995,
              min_temp: float = 0.1, iterations_per_temp: int = 20) -> Dict[str, Any]:
        if not self.active_tasks or not self.schedulable_locomotives:
            return {
                "solve_status": "optimal",
                "makespan": 0,
                "assignments": [],
                "algorithm": "simulated_annealing",
                "iterations": 0,
                "final_temp": initial_temp
            }

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
            "initial_temp": initial_temp,
            "final_temp": temp,
            "cooling_rate": cooling_rate,
            "iterations": total_iterations
        }
