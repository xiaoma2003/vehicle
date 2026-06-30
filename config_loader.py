"""
车辆调度AI算法评测系统 - 配置加载与验证模块
负责加载和验证四类JSON配置文件
"""
import json
import os
from typing import Dict, List, Any, Optional


class ConfigLoader:
    def __init__(self, config_dir: str = "data"):
        self.config_dir = config_dir
        self.map_config = None
        self.tasks_config = None
        self.locomotives_config = None
        self.hyper_params = None

    def load_all_configs(self) -> Dict[str, Any]:
        self.map_config = self.load_map_config()
        self.tasks_config = self.load_tasks_config()
        self.locomotives_config = self.load_locomotives_config()
        self.hyper_params = self.load_hyper_params()
        return {
            "map": self.map_config,
            "tasks": self.tasks_config,
            "locomotives": self.locomotives_config,
            "hyper_params": self.hyper_params
        }

    def load_map_config(self, filename: str = "map_config.json") -> Dict[str, Any]:
        path = os.path.join(self.config_dir, filename)
        with open(path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        self._validate_map_config(config)
        return config

    def load_tasks_config(self, filename: str = "tasks_config.json") -> Dict[str, Any]:
        path = os.path.join(self.config_dir, filename)
        with open(path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        self._validate_tasks_config(config)
        return config

    def load_locomotives_config(self, filename: str = "locomotives_config.json") -> Dict[str, Any]:
        path = os.path.join(self.config_dir, filename)
        with open(path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        self._validate_locomotives_config(config)
        return config

    def load_hyper_params(self, filename: str = "hyper_params.json") -> Dict[str, Any]:
        path = os.path.join(self.config_dir, filename)
        with open(path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        self._validate_hyper_params(config)
        return config

    def save_config(self, config: Dict[str, Any], filename: str):
        path = os.path.join(self.config_dir, filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def _validate_map_config(self, config: Dict[str, Any]):
        if "nodes" not in config:
            raise ValueError("地图配置缺少nodes字段")
        if "edges" not in config:
            raise ValueError("地图配置缺少edges字段")
        node_ids = set()
        for node in config["nodes"]:
            if "id" not in node:
                raise ValueError("节点缺少id字段")
            if node["id"] in node_ids:
                raise ValueError(f"节点ID重复: {node['id']}")
            node_ids.add(node["id"])
            if "type" not in node:
                raise ValueError(f"节点{node['id']}缺少type字段")
            if node["type"] not in ["station", "fuel_station", "charge_station", "material_station", "switch"]:
                raise ValueError(f"节点{node['id']}类型无效: {node['type']}")
        for edge in config["edges"]:
            if "from" not in edge or "to" not in edge:
                raise ValueError("边缺少from或to字段")
            if edge["from"] not in node_ids:
                raise ValueError(f"边的起点不存在: {edge['from']}")
            if edge["to"] not in node_ids:
                raise ValueError(f"边的终点不存在: {edge['to']}")
            if "length" not in edge or edge["length"] <= 0:
                raise ValueError(f"边{edge['from']}->{edge['to']}长度无效")
            if "speed_limit" not in edge:
                edge["speed_limit"] = 600
            if "slope" not in edge:
                edge["slope"] = 0.0
            if "direction" not in edge:
                edge["direction"] = "bidirectional"

    def _validate_tasks_config(self, config: Dict[str, Any]):
        if "tasks" not in config:
            raise ValueError("任务配置缺少tasks字段")
        task_ids = set()
        for task in config["tasks"]:
            if "id" not in task:
                raise ValueError("任务缺少id字段")
            if task["id"] in task_ids:
                raise ValueError(f"任务ID重复: {task['id']}")
            task_ids.add(task["id"])
            if "priority" not in task or not isinstance(task["priority"], int) or task["priority"] < 1 or task["priority"] > 99:
                raise ValueError(f"任务{task['id']}优先级必须为1-99的整数")
            if "task_type" not in task or task["task_type"] not in ["normal", "temporary", "emergency"]:
                raise ValueError(f"任务{task['id']}类型无效: {task.get('task_type')}")
            if "status" not in task or task["status"] not in ["pending", "running", "paused", "completed"]:
                raise ValueError(f"任务{task['id']}状态无效: {task.get('status')}")
            if "depends_on" in task:
                for dep_id in task["depends_on"]:
                    if dep_id not in task_ids:
                        raise ValueError(f"任务{task['id']}依赖不存在的任务: {dep_id}")
            if "start_node" not in task:
                raise ValueError(f"任务{task['id']}缺少start_node")
            if "end_node" not in task:
                raise ValueError(f"任务{task['id']}缺少end_node")
            if "material_weight" not in task or task["material_weight"] <= 0:
                raise ValueError(f"任务{task['id']}物料重量无效")
        self._check_circular_dependency(config["tasks"])

    def _check_circular_dependency(self, tasks: List[Dict[str, Any]]):
        task_map = {t["id"]: t for t in tasks}
        visited = set()
        rec_stack = set()

        def dfs(task_id: str) -> bool:
            visited.add(task_id)
            rec_stack.add(task_id)
            for dep_id in task_map[task_id].get("depends_on", []):
                if dep_id not in visited:
                    if dfs(dep_id):
                        return True
                elif dep_id in rec_stack:
                    return True
            rec_stack.remove(task_id)
            return False

        for task in tasks:
            if task["id"] not in visited:
                if dfs(task["id"]):
                    raise ValueError(f"任务存在循环依赖")

    def _validate_locomotives_config(self, config: Dict[str, Any]):
        if "locomotives" not in config:
            raise ValueError("机车配置缺少locomotives字段")
        loco_ids = set()
        for loco in config["locomotives"]:
            if "id" not in loco:
                raise ValueError("机车缺少id字段")
            if loco["id"] in loco_ids:
                raise ValueError(f"机车ID重复: {loco['id']}")
            loco_ids.add(loco["id"])
            if "traction_type" not in loco or loco["traction_type"] not in ["electric", "diesel"]:
                raise ValueError(f"机车{loco['id']}牵引类型无效")
            if loco["traction_type"] == "electric":
                if "battery" not in loco or loco["battery"] < 0:
                    raise ValueError(f"电动机车{loco['id']}电池容量无效")
            else:
                if "fuel_tank" not in loco or loco["fuel_tank"] < 0:
                    raise ValueError(f"柴油机车{loco['id']}油箱容量无效")
            if "Q" not in loco or loco["Q"] <= 0:
                raise ValueError(f"机车{loco['id']}载重能力无效")
            if "max_speed" not in loco or loco["max_speed"] <= 0:
                raise ValueError(f"机车{loco['id']}最大速度无效")
            if "initial_node" not in loco:
                raise ValueError(f"机车{loco['id']}缺少初始位置")
            if "is_powered_on" not in loco:
                loco["is_powered_on"] = True
            if "is_schedulable" not in loco:
                loco["is_schedulable"] = True
            if "task_phase" not in loco:
                loco["task_phase"] = None
            if "current_task" not in loco:
                loco["current_task"] = None

    def _validate_hyper_params(self, config: Dict[str, Any]):
        required = [
            "travel_time_precision", "default_priority", "BigM",
            "slope_factor_uphill", "slope_factor_downhill",
            "switch_pass_time", "loading_time", "unloading_time",
            "battery_low_threshold", "fuel_low_threshold",
            "energy_consumption_rate"
        ]
        for key in required:
            if key not in config:
                raise ValueError(f"超参数缺少{key}字段")
        if config["travel_time_precision"] < 2:
            raise ValueError("travel_time_precision必须≥2")
