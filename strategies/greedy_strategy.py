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
        # 找出 bound locomotive（热启动任务占用的机车，不参与调度）
        assigned_tasks = {}  # {task_id: info}
        bound_loco_ids = set()
        for t in self.tasks:
            if t.get("bound_locomotive") and t["status"] == "running":
                bound_loco_ids.add(t["bound_locomotive"])
                loco = next((l for l in self.locomotives if l["id"] == t["bound_locomotive"]), None)
                if loco:
                    import math
                    travel_time = int(math.ceil(
                        self.precomputed_paths[loco["id"]][t["start_node"]][t["end_node"]]["time"]
                        / self.hyper_params["travel_time_precision"]
                    ) * self.hyper_params["travel_time_precision"])
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
            if l.get("is_powered_on", True) and l.get("is_schedulable", True)
            and l["id"] not in bound_loco_ids  # 排除 bound locomotive
        ]

        active_tasks = [
            t for t in self.tasks
            if t["status"] in ["pending", "running", "paused"]
            and t["id"] not in assigned_tasks  # 排除已分配的任务
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
        task_end_times = {}  # 修复: 追踪任务实际完成时间
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
                    completed_tasks.add(tid)
                    task_end_times[tid] = unloading_end  # 记录实际完成时间
                    made_progress = True

            if not made_progress:
                break

        # 合并 assigned_tasks（bound 任务）到 assignments
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

        # makespan 取所有任务（包含 assigned_tasks）和调度任务的最大完成时间
        all_end_times = [a["unloading_end"] for a in assignments]
        makespan = max(all_end_times) if all_end_times else 0

        return {
            "solve_status": "feasible",
            "makespan": makespan,
            "assignments": assignments,
            "num_tasks": len(assignments),
            "num_locomotives": len(schedulable_locomotives) + len(assigned_tasks),
            "algorithm": "greedy"
        }
