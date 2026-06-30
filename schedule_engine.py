"""
任务优先级调度与让道机制模块
包含：热启动支持、上下行方向调度、优先级让道、紧急任务处理
"""
import json
import os
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict


class PriorityScheduler:
    def __init__(self, map_config, hyper_params):
        self.map_config = map_config
        self.hyper_params = hyper_params
        self.nodes = {n["id"]: n for n in map_config["nodes"]}
        self.edges = map_config["edges"]
        self.direction_lock = {"up": False, "down": False}
        self.active_tasks_by_direction = {"up": [], "down": []}

    def determine_direction(self, start_node: str, end_node: str) -> str:
        start = self.nodes.get(start_node, {})
        end = self.nodes.get(end_node, {})

        start_y = start.get("y", 0)
        end_y = end.get("y", 0)

        if end_y > start_y:
            return "up"
        elif end_y < start_y:
            return "down"
        else:
            start_x = start.get("x", 0)
            end_x = end.get("x", 0)
            return "up" if end_x > start_x else "down"

    def check_direction_available(self, direction: str) -> bool:
        return not self.direction_lock[direction]

    def lock_direction(self, direction: str):
        self.direction_lock[direction] = True

    def unlock_direction(self, direction: str):
        self.direction_lock[direction] = False
        self.active_tasks_by_direction[direction] = [
            t for t in self.active_tasks_by_direction[direction]
            if t.get("status") not in ["completed"]
        ]

    def get_opposite_direction(self, direction: str) -> str:
        return "down" if direction == "up" else "up"


class GiveWayManager:
    def __init__(self, map_config, hyper_params):
        self.map_config = map_config
        self.hyper_params = hyper_params
        self.nodes = {n["id"]: n for n in map_config["nodes"]}
        self.edges = map_config["edges"]
        self.adjacency = self._build_adjacency()

    def _build_adjacency(self) -> Dict[str, List[str]]:
        adj = defaultdict(list)
        for edge in self.edges:
            adj[edge["from"]].append(edge["to"])
            adj[edge["to"]].append(edge["from"])
        return adj

    def find_nearest_wait_node(self, current_path: List[str], current_position: int) -> Optional[str]:
        if current_position >= len(current_path):
            return None
        return current_path[current_position]

    def check_give_way_needed(self, high_prio_task: Dict[str, Any],
                               low_prio_task: Dict[str, Any]) -> bool:
        high_prio = high_prio_task.get("priority", 99)
        low_prio = low_prio_task.get("priority", 99)

        high_speed = high_prio_task.get("speed", 0)
        low_speed = low_prio_task.get("speed", 0)

        if high_prio < low_prio and high_speed > low_speed:
            high_path = set(high_prio_task.get("path", []))
            low_path = set(low_prio_task.get("path", []))
            if high_path & low_path:
                return True
        return False

    def calculate_give_way(self, low_prio_task: Dict[str, Any],
                            high_prio_task: Dict[str, Any]) -> Dict[str, Any]:
        low_path = low_prio_task.get("path", [])
        high_path = high_prio_task.get("path", [])

        common_nodes = set(low_path) & set(high_path)
        if not common_nodes:
            return {"needs_give_way": False}

        low_current_idx = low_prio_task.get("current_path_index", 0)

        wait_node = None
        for i in range(low_current_idx, len(low_path)):
            if low_path[i] in common_nodes:
                if i > 0:
                    wait_node = low_path[i - 1]
                else:
                    wait_node = low_path[0]
                break

        if wait_node is None and low_path:
            wait_node = low_path[min(low_current_idx, len(low_path) - 1)]

        return {
            "needs_give_way": True,
            "wait_node": wait_node,
            "wait_until_high_priority_passes": True,
            "high_priority_task_id": high_prio_task.get("task_id"),
            "resume_from": wait_node
        }


class HotStartManager:
    def __init__(self, config_dir: str = "data"):
        self.config_dir = config_dir
        self.hot_start_state = None

    def load_hot_start_state(self, filename: str = "hot_start_state.json") -> Optional[Dict[str, Any]]:
        path = os.path.join(self.config_dir, filename)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                self.hot_start_state = json.load(f)
            return self.hot_start_state
        return None

    def save_hot_start_state(self, state: Dict[str, Any],
                              filename: str = "hot_start_state.json"):
        path = os.path.join(self.config_dir, filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        self.hot_start_state = state

    def get_busy_locomotives(self, locomotives_config: Dict[str, Any]) -> List[str]:
        busy_locomotives = []
        for loco in locomotives_config.get("locomotives", []):
            if loco.get("current_task") is not None or loco.get("task_phase") is not None:
                busy_locomotives.append(loco["id"])
        return busy_locomotives

    def apply_hot_start(self, tasks_config: Dict[str, Any],
                         locomotives_config: Dict[str, Any]) -> Tuple[Dict, Dict]:
        busy_locomotives = self.get_busy_locomotives(locomotives_config)

        updated_locomotives = []
        for loco in locomotives_config["locomotives"]:
            loco_copy = loco.copy()
            if loco["id"] in busy_locomotives:
                loco_copy["is_schedulable"] = False
            updated_locomotives.append(loco_copy)

        return tasks_config, {"locomotives": updated_locomotives}

    def get_running_tasks(self, tasks_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [t for t in tasks_config.get("tasks", [])
                if t.get("status") in ["running", "paused"]]


class EmergencyTaskManager:
    def __init__(self):
        self.paused_tasks = []
        self.active_emergency_tasks = []
        self.emergency_history = []

    def trigger_emergency_task(self, emergency_task: Dict[str, Any],
                                current_tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        non_emergency = [t for t in current_tasks
                        if t.get("task_type") != "emergency" and t.get("status") == "running"]

        for task in non_emergency:
            task["status"] = "paused"
            self.paused_tasks.append(task["id"])

        emergency_task["priority"] = 1
        emergency_task["task_type"] = "emergency"
        emergency_task["status"] = "pending"
        emergency_task["trigger_time"] = len(self.emergency_history)

        self.active_emergency_tasks.append(emergency_task["id"])
        self.emergency_history.append(emergency_task)

        return {
            "paused_tasks": self.paused_tasks.copy(),
            "emergency_task": emergency_task,
            "active_emergency_tasks": self.active_emergency_tasks.copy()
        }

    def complete_emergency_task(self, task_id: str) -> Dict[str, Any]:
        if task_id in self.active_emergency_tasks:
            self.active_emergency_tasks.remove(task_id)

        return {
            "completed_task": task_id,
            "remaining_emergency": len(self.active_emergency_tasks),
            "can_resume": len(self.active_emergency_tasks) == 0
        }

    def resume_paused_tasks(self, current_tasks: List[Dict[str, Any]]) -> List[str]:
        if self.active_emergency_tasks:
            return []

        resumed = []
        for task in current_tasks:
            if task["id"] in self.paused_tasks and task["status"] == "paused":
                task["status"] = "running"
                resumed.append(task["id"])

        self.paused_tasks = []
        return resumed

    def boost_task_priority(self, task_id: str, tasks: List[Dict[str, Any]],
                             boost_amount: int = 10) -> Optional[Dict[str, Any]]:
        for task in tasks:
            if task["id"] == task_id:
                old_priority = task["priority"]
                new_priority = max(1, old_priority - boost_amount)
                task["priority"] = new_priority
                return {
                    "task_id": task_id,
                    "old_priority": old_priority,
                    "new_priority": new_priority
                }
        return None


class OutputGenerator:
    def __init__(self, output_dir: str = "data"):
        self.output_dir = output_dir

    def generate_schedule_output(self, result: Dict[str, Any],
                                  map_config: Dict[str, Any],
                                  tasks_config: Dict[str, Any],
                                  locomotives_config: Dict[str, Any],
                                  hyper_params: Dict[str, Any],
                                  batch_id: str) -> Dict[str, Any]:
        output = {
            "batch_id": batch_id,
            "solve_status": result["solve_status"],
            "makespan": result["makespan"],
            "strategy_name": result.get("strategy_name", "unknown"),
            "strategy_display_name": result.get("strategy_display_name", "未知策略"),
            "solve_time": result.get("solve_time", 0),
            "num_tasks": result.get("num_tasks", 0),
            "num_locomotives": result.get("num_locomotives", 0),
            "assignments": [],
            "map_config": map_config,
            "hyper_params": hyper_params,
            "locomotives": locomotives_config.get("locomotives", []),
            "tasks": tasks_config.get("tasks", [])
        }

        for assignment in result.get("assignments", []):
            task_info = next((t for t in tasks_config["tasks"]
                            if t["id"] == assignment["task_id"]), None)
            loco_info = next((l for l in locomotives_config["locomotives"]
                            if l["id"] == assignment["locomotive_id"]), None)

            output["assignments"].append({
                "task_id": assignment["task_id"],
                "task_name": task_info.get("name", assignment["task_id"]) if task_info else assignment["task_id"],
                "task_type": task_info.get("task_type", "normal") if task_info else "normal",
                "priority": task_info.get("priority", 50) if task_info else 50,
                "locomotive_id": assignment["locomotive_id"],
                "locomotive_type": loco_info.get("traction_type", "unknown") if loco_info else "unknown",
                "start_time": assignment["start_time"],
                "loading_end": assignment["loading_end"],
                "transport_end": assignment["transport_end"],
                "unloading_end": assignment["unloading_end"],
                "path": assignment.get("path", []),
                "segments": assignment.get("segments", []),
                "material_weight": task_info.get("material_weight", 0) if task_info else 0,
                "start_node": task_info.get("start_node", "") if task_info else "",
                "end_node": task_info.get("end_node", "") if task_info else ""
            })

        return output

    def save_output(self, output: Dict[str, Any], filename: str):
        path = os.path.join(self.output_dir, filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        return path

    def generate_comparison_report(self, comparison: Dict[str, Any],
                                    batch_id: str) -> Dict[str, Any]:
        report = {
            "batch_id": batch_id,
            "comparison_time": comparison.get("comparison_time", 0),
            "best_strategy": comparison.get("best_strategy"),
            "best_makespan": comparison.get("best_makespan"),
            "fastest_strategy": comparison.get("fastest_strategy"),
            "fastest_time": comparison.get("fastest_time"),
            "strategies": comparison.get("strategies", []),
            "analysis": self._generate_analysis(comparison)
        }
        return report

    def _generate_analysis(self, comparison: Dict[str, Any]) -> Dict[str, Any]:
        strategies = comparison.get("strategies", [])
        if not strategies:
            return {}

        best_makespan = min((s["makespan"] for s in strategies if s.get("makespan", -1) >= 0), default=None)
        base_strategy = next((s for s in strategies if s["name"] == "cpsat"), None)

        analysis = {
            "benchmark": "cpsat",
            "benchmark_makespan": base_strategy.get("makespan") if base_strategy else None,
            "benchmark_time": base_strategy.get("solve_time") if base_strategy else None,
            "improvements": [],
            "dimensions": []
        }

        for strategy in strategies:
            if strategy["name"] == "cpsat":
                continue
            if strategy.get("makespan", -1) >= 0 and base_strategy and base_strategy.get("makespan", 0) > 0:
                makespan_ratio = strategy["makespan"] / base_strategy["makespan"]
                time_ratio = base_strategy.get("solve_time", 1) / max(strategy.get("solve_time", 0.001), 0.001)

                improvement = {
                    "strategy": strategy["name"],
                    "display_name": strategy.get("display_name", strategy["name"]),
                    "makespan_ratio": round(makespan_ratio, 4),
                    "speedup_ratio": round(time_ratio, 2),
                    "makespan_diff": strategy["makespan"] - base_strategy["makespan"],
                    "time_diff": base_strategy.get("solve_time", 0) - strategy.get("solve_time", 0)
                }
                analysis["improvements"].append(improvement)

        return analysis
