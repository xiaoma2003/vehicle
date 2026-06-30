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

    def _ceil_to_precision(self, minutes: float) -> int:
        return int(math.ceil(minutes / self.precision) * self.precision)

    def solve(self) -> Dict[str, Any]:
        model = cp_model.CpModel()

        schedulable_locomotives = [
            l for l in self.locomotives
            if l.get("is_powered_on", True) and l.get("is_schedulable", True)
        ]

        active_tasks = [
            t for t in self.tasks
            if t["status"] in ["pending", "running", "paused"]
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

        task_vars = {}
        for task in active_tasks:
            tid = task["id"]
            task_vars[tid] = {
                "assigned_loco": model.NewIntVar(0, len(schedulable_locomotives) - 1, f"loco_{tid}"),
                "start_time": model.NewIntVar(0, self.BigM, f"start_{tid}"),
                "loading_end": model.NewIntVar(0, self.BigM, f"load_end_{tid}"),
                "transport_end": model.NewIntVar(0, self.BigM, f"trans_end_{tid}"),
                "unloading_end": model.NewIntVar(0, self.BigM, f"unload_end_{tid}"),
                "is_assigned": model.NewBoolVar(f"assigned_{tid}")
            }

        makespan = model.NewIntVar(0, self.BigM, "makespan")

        for i, loco in enumerate(schedulable_locomotives):
            loco_id = loco["id"]
            loco_tasks = [t for t in active_tasks]
            for idx, task in enumerate(loco_tasks):
                tid = task["id"]
                tv = task_vars[tid]
                is_this_loco = model.NewBoolVar(f"loco_{loco_id}_task_{tid}")
                model.Add(tv["assigned_loco"] == i).OnlyEnforceIf(is_this_loco)
                model.Add(tv["assigned_loco"] != i).OnlyEnforceIf(is_this_loco.Not())

                path_info = self.precomputed_paths[loco_id][task["start_node"]][task["end_node"]]
                empty_path_info = self.precomputed_paths[loco_id][loco["initial_node"]][task["start_node"]]

                travel_time = self._ceil_to_precision(path_info["time"])
                empty_travel_time = self._ceil_to_precision(empty_path_info["time"])
                loading_time = self.hyper_params["loading_time"]
                unloading_time = self.hyper_params["unloading_time"]

                model.Add(tv["loading_end"] == tv["start_time"] + loading_time).OnlyEnforceIf(is_this_loco)
                model.Add(tv["transport_end"] == tv["loading_end"] + travel_time).OnlyEnforceIf(is_this_loco)
                model.Add(tv["unloading_end"] == tv["transport_end"] + unloading_time).OnlyEnforceIf(is_this_loco)

                model.Add(tv["start_time"] >= 0).OnlyEnforceIf(is_this_loco)

        for task in active_tasks:
            tid = task["id"]
            tv = task_vars[tid]
            model.Add(tv["is_assigned"] == 1)
            model.Add(tv["unloading_end"] <= makespan)

        for task in active_tasks:
            tid = task["id"]
            tv = task_vars[tid]
            for dep_id in task.get("depends_on", []):
                if dep_id in task_vars:
                    dep_tv = task_vars[dep_id]
                    model.Add(tv["start_time"] >= dep_tv["unloading_end"])

        for i, loco in enumerate(schedulable_locomotives):
            loco_id = loco["id"]
            loco_task_vars = [(t["id"], task_vars[t["id"]]) for t in active_tasks]
            for idx1, (tid1, tv1) in enumerate(loco_task_vars):
                for idx2, (tid2, tv2) in enumerate(loco_task_vars):
                    if idx1 >= idx2:
                        continue
                    same_loco = model.NewBoolVar(f"same_loco_{tid1}_{tid2}")
                    both_assigned = model.NewBoolVar(f"both_assigned_{tid1}_{tid2}")
                    model.AddBoolAnd([tv1["is_assigned"], tv2["is_assigned"]]).OnlyEnforceIf(both_assigned)
                    model.AddBoolOr([tv1["is_assigned"].Not(), tv2["is_assigned"].Not()]).OnlyEnforceIf(both_assigned.Not())

                    same_loco_1 = model.NewBoolVar(f"sl1_{tid1}_{tid2}")
                    same_loco_2 = model.NewBoolVar(f"sl2_{tid1}_{tid2}")
                    model.Add(tv1["assigned_loco"] == i).OnlyEnforceIf(same_loco_1)
                    model.Add(tv1["assigned_loco"] != i).OnlyEnforceIf(same_loco_1.Not())
                    model.Add(tv2["assigned_loco"] == i).OnlyEnforceIf(same_loco_2)
                    model.Add(tv2["assigned_loco"] != i).OnlyEnforceIf(same_loco_2.Not())
                    model.AddBoolAnd([same_loco_1, same_loco_2]).OnlyEnforceIf(same_loco)
                    model.AddBoolOr([same_loco_1.Not(), same_loco_2.Not()]).OnlyEnforceIf(same_loco.Not())

                    order = model.NewBoolVar(f"order_{tid1}_{tid2}")
                    condition = model.NewBoolVar(f"cond_{tid1}_{tid2}")
                    model.AddBoolAnd([both_assigned, same_loco]).OnlyEnforceIf(condition)
                    model.AddBoolOr([both_assigned.Not(), same_loco.Not()]).OnlyEnforceIf(condition.Not())

                    model.Add(tv1["unloading_end"] <= tv2["start_time"]).OnlyEnforceIf([condition, order])
                    model.Add(tv2["unloading_end"] <= tv1["start_time"]).OnlyEnforceIf([condition, order.Not()])

        for task in active_tasks:
            tid = task["id"]
            tv = task_vars[tid]
            for i, loco in enumerate(schedulable_locomotives):
                is_loco = model.NewBoolVar(f"check_cap_{tid}_{loco['id']}")
                model.Add(tv["assigned_loco"] == i).OnlyEnforceIf(is_loco)
                model.Add(tv["assigned_loco"] != i).OnlyEnforceIf(is_loco.Not())
                if task["material_weight"] > loco["Q"]:
                    model.Add(tv["is_assigned"] == 0).OnlyEnforceIf(is_loco)

        model.Minimize(makespan)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 300.0
        solver.parameters.num_search_workers = 8

        status = solver.Solve(model)

        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            assignments = []
            for task in active_tasks:
                tid = task["id"]
                tv = task_vars[tid]
                if solver.Value(tv["is_assigned"]):
                    loco_idx = solver.Value(tv["assigned_loco"])
                    loco = schedulable_locomotives[loco_idx]
                    path_info = self.precomputed_paths[loco["id"]][task["start_node"]][task["end_node"]]
                    assignments.append({
                        "task_id": tid,
                        "locomotive_id": loco["id"],
                        "start_time": solver.Value(tv["start_time"]),
                        "loading_end": solver.Value(tv["loading_end"]),
                        "transport_end": solver.Value(tv["transport_end"]),
                        "unloading_end": solver.Value(tv["unloading_end"]),
                        "path": path_info["path"],
                        "segments": path_info["segments"]
                    })

            return {
                "solve_status": "optimal" if status == cp_model.OPTIMAL else "feasible",
                "makespan": solver.Value(makespan),
                "assignments": assignments,
                "num_tasks": len(assignments),
                "num_locomotives": len(schedulable_locomotives)
            }
        else:
            return {
                "solve_status": "infeasible",
                "makespan": -1,
                "assignments": [],
                "message": "无法找到可行解，请检查约束条件"
            }
