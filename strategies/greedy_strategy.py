"""
候选策略1：贪心算法
基于优先级和最短路径的贪心调度策略
"""
import random
from typing import Dict, List, Any, Tuple


class GreedyScheduler:
    def __init__(self, map_config, tasks_config, locomotives_config, hyper_params, precomputed_paths):
        self.map_config = map_config
        self.tasks = tasks_config["tasks"]
        self.locomotives = locomotives_config["locomotives"]
        self.hyper_params = hyper_params
        self.precomputed_paths = precomputed_paths
        random.seed(42)

    def solve(self) -> Dict[str, Any]:
        schedulable_locomotives = [
            l for l in self.locomotives
            if l.get("is_powered_on", True) and l.get("is_schedulable", True)
        ]

        active_tasks = [
            t for t in self.tasks
            if t["status"] in ["pending", "running", "paused"]
        ]

        if not active_tasks or not schedulable_locomotives:
            return {
                "solve_status": "optimal",
                "makespan": 0,
                "assignments": [],
                "algorithm": "greedy",
                "message": "无待调度任务或无可调度机车" if not active_tasks else "无可调度机车"
            }

        sorted_tasks = sorted(
            active_tasks,
            key=lambda t: (t["priority"], -t["material_weight"])
        )

        loco_available_time = {l["id"]: 0 for l in schedulable_locomotives}
        loco_current_node = {l["id"]: l["initial_node"] for l in schedulable_locomotives}

        completed_tasks = set()
        assignments = []

        max_iterations = len(sorted_tasks) * 2
        iteration = 0

        while len(completed_tasks) < len(sorted_tasks) and iteration < max_iterations:
            iteration += 1
            made_progress = False

            for task in sorted_tasks:
                tid = task["id"]
                if tid in completed_tasks:
                    continue

                deps_met = all(dep_id in completed_tasks for dep_id in task.get("depends_on", []))
                if not deps_met:
                    continue

                best_loco = None
                best_end_time = float('inf')
                best_path_info = None

                for loco in schedulable_locomotives:
                    if task["material_weight"] > loco["Q"]:
                        continue

                    loco_id = loco["id"]
                    path_info = self.precomputed_paths[loco_id][task["start_node"]][task["end_node"]]
                    empty_path_info = self.precomputed_paths[loco_id][loco_current_node[loco_id]][task["start_node"]]

                    travel_time = path_info["time"]
                    empty_travel_time = empty_path_info["time"]
                    loading_time = self.hyper_params["loading_time"]
                    unloading_time = self.hyper_params["unloading_time"]

                    start_time = max(loco_available_time[loco_id], 0)
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
                    completed_tasks.add(tid)
                    made_progress = True

            if not made_progress:
                break

        makespan = max((a["unloading_end"] for a in assignments), default=0)

        return {
            "solve_status": "feasible",
            "makespan": makespan,
            "assignments": assignments,
            "num_tasks": len(assignments),
            "num_locomotives": len(schedulable_locomotives),
            "algorithm": "greedy"
        }
