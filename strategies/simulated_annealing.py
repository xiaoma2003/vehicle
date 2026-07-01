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

        self.schedulable_locomotives = [
            l for l in self.locomotives
            if l.get("is_powered_on", True) and l.get("is_schedulable", True)
        ]
        self.active_tasks = [
            t for t in self.tasks
            if t["status"] in ["pending", "running", "paused"]
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

                deps_met = all(
                    any(self.active_tasks[s]["id"] == dep_id for s in scheduled)
                    for dep_id in task.get("depends_on", [])
                )
                if not deps_met:
                    continue

                best_loco = None
                best_end_time = float('inf')
                best_path_info = None

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

                    start_time = loco_available_time[loco_id]
                    total_time = empty_travel_time + loading_time + travel_time + unloading_time
                    end_time = start_time + total_time

                    if end_time < best_end_time:
                        best_end_time = end_time
                        best_loco = loco
                        best_path_info = path_info

                if best_loco:
                    loco_id = best_loco["id"]
                    start_time = loco_available_time[loco_id]
                    loading_end = start_time + self.hyper_params["loading_time"]
                    transport_end = loading_end + best_path_info["time"]
                    unloading_end = transport_end + self.hyper_params["unloading_time"]

                    assignments.append({
                        "task_id": tid,
                        "locomotive_id": loco_id,
                        "start_time": int(start_time),
                        "loading_end": int(loading_end),
                        "transport_end": int(transport_end),
                        "unloading_end": int(unloading_end),
                        "path": best_path_info["path"],
                        "segments": best_path_info["segments"]
                    })

                    loco_available_time[loco_id] = unloading_end
                    loco_current_node[loco_id] = task["end_node"]
                    scheduled.add(idx)
                    made_progress = True

            if not made_progress:
                break

        makespan = max((a["unloading_end"] for a in assignments), default=0)
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
            "num_locomotives": len(self.schedulable_locomotives),
            "algorithm": "simulated_annealing",
            "initial_temp": initial_temp,
            "final_temp": temp,
            "cooling_rate": cooling_rate,
            "iterations": total_iterations
        }
