"""
车辆调度AI算法评测系统 - API接口模块
ScheduleAPI类，封装16个核心接口方法
"""
import uuid
import time
import json
import os
from typing import Dict, List, Any, Optional

from config_loader import ConfigLoader
from strategy_manager import StrategyManager
from schedule_engine import (
    PriorityScheduler, GiveWayManager, HotStartManager,
    EmergencyTaskManager, OutputGenerator
)
from schedule_database import ScheduleDatabase


class ScheduleAPI:
    def __init__(self, config_dir: str = "data", db_path: str = "data/schedule_history.db"):
        self.config_dir = config_dir
        self.config_loader = ConfigLoader(config_dir)
        self.strategy_manager = StrategyManager()
        self.db = ScheduleDatabase(db_path)
        self.output_generator = OutputGenerator(config_dir)

        self.map_config = None
        self.tasks_config = None
        self.locomotives_config = None
        self.hyper_params = None

        self._load_configs_safe()

    def _load_configs_safe(self):
        try:
            self.config_loader.load_all_configs()
            self.map_config = self.config_loader.map_config
            self.tasks_config = self.config_loader.tasks_config
            self.locomotives_config = self.config_loader.locomotives_config
            self.hyper_params = self.config_loader.hyper_params
        except Exception:
            pass

    def _ensure_configs(self):
        if not all([self.map_config, self.tasks_config,
                    self.locomotives_config, self.hyper_params]):
            self._load_configs_safe()
        return all([self.map_config, self.tasks_config,
                    self.locomotives_config, self.hyper_params])

    def _generate_batch_id(self) -> str:
        return f"batch_{int(time.time())}_{uuid.uuid4().hex[:8]}"

    def load_map_config(self, filename: str = "map_config.json") -> Dict[str, Any]:
        self.map_config = self.config_loader.load_map_config(filename)
        return {"success": True, "data": self.map_config}

    def load_tasks_config(self, filename: str = "tasks_config.json") -> Dict[str, Any]:
        self.tasks_config = self.config_loader.load_tasks_config(filename)
        return {"success": True, "data": self.tasks_config}

    def load_locomotives_config(self, filename: str = "locomotives_config.json") -> Dict[str, Any]:
        self.locomotives_config = self.config_loader.load_locomotives_config(filename)
        return {"success": True, "data": self.locomotives_config}

    def load_hyper_params(self, filename: str = "hyper_params.json") -> Dict[str, Any]:
        self.hyper_params = self.config_loader.load_hyper_params(filename)
        return {"success": True, "data": self.hyper_params}

    def save_map_config(self, config: Dict[str, Any],
                         filename: str = "map_config.json") -> Dict[str, Any]:
        self.config_loader._validate_map_config(config)
        self.config_loader.save_config(config, filename)
        self.map_config = config
        return {"success": True, "message": "地图配置已保存"}

    def save_tasks_config(self, config: Dict[str, Any],
                           filename: str = "tasks_config.json") -> Dict[str, Any]:
        self.config_loader._validate_tasks_config(config)
        self.config_loader.save_config(config, filename)
        self.tasks_config = config
        return {"success": True, "message": "任务配置已保存"}

    def save_locomotives_config(self, config: Dict[str, Any],
                                 filename: str = "locomotives_config.json") -> Dict[str, Any]:
        self.config_loader._validate_locomotives_config(config)
        self.config_loader.save_config(config, filename)
        self.locomotives_config = config
        return {"success": True, "message": "机车配置已保存"}

    def save_hyper_params(self, params: Dict[str, Any],
                           filename: str = "hyper_params.json") -> Dict[str, Any]:
        self.config_loader._validate_hyper_params(params)
        self.config_loader.save_config(params, filename)
        self.hyper_params = params
        return {"success": True, "message": "超参数配置已保存"}

    def run_schedule(self, strategy_name: str = "cpsat",
                     use_hot_start: bool = False) -> Dict[str, Any]:
        if not self._ensure_configs():
            return {"success": False, "error": "配置文件未加载"}

        try:
            batch_id = self._generate_batch_id()

            tasks_to_use = self.tasks_config
            locos_to_use = self.locomotives_config

            if use_hot_start:
                hot_start = HotStartManager(self.config_dir)
                tasks_to_use, locos_to_use = hot_start.apply_hot_start(
                    self.tasks_config, self.locomotives_config
                )

            self.db.save_config_batch(
                batch_id, self.map_config, tasks_to_use,
                locos_to_use, self.hyper_params
            )

            result = self.strategy_manager.run_strategy(
                strategy_name, self.map_config, tasks_to_use,
                locos_to_use, self.hyper_params
            )

            result["batch_id"] = batch_id

            self.db.save_scheduler_run(
                batch_id, strategy_name,
                result.get("strategy_display_name", strategy_name),
                result
            )

            output = self.output_generator.generate_schedule_output(
                result, self.map_config, tasks_to_use,
                locos_to_use, self.hyper_params, batch_id
            )
            self.output_generator.save_output(
                output, f"schedule_output_{batch_id}.json"
            )

            self.db.add_log(batch_id, "INFO", "scheduling",
                          f"调度完成: {strategy_name}, makespan={result['makespan']}")

            return {"success": True, "data": result}
        except Exception as e:
            self.db.add_log(None, "ERROR", "scheduling", f"调度失败: {str(e)}")
            return {"success": False, "error": str(e)}

    def compare_strategies(self, strategy_names: List[str]) -> Dict[str, Any]:
        if not self._ensure_configs():
            return {"success": False, "error": "配置文件未加载"}

        try:
            batch_id = self._generate_batch_id()

            self.db.save_config_batch(
                batch_id, self.map_config, self.tasks_config,
                self.locomotives_config, self.hyper_params
            )

            comparison = self.strategy_manager.compare_strategies(
                strategy_names, self.map_config, self.tasks_config,
                self.locomotives_config, self.hyper_params
            )
            comparison["batch_id"] = batch_id
            comparison["comparison_time"] = time.time()

            for strategy_name, result in comparison.get("results", {}).items():
                if result.get("solve_status") != "error":
                    self.db.save_scheduler_run(
                        batch_id, strategy_name,
                        result.get("strategy_display_name", strategy_name),
                        result
                    )

            report = self.output_generator.generate_comparison_report(
                comparison, batch_id
            )
            self.output_generator.save_output(
                report, f"comparison_report_{batch_id}.json"
            )

            self.db.add_log(batch_id, "INFO", "comparison",
                          f"多策略对比完成: {len(strategy_names)}种策略")

            return {"success": True, "data": comparison}
        except Exception as e:
            self.db.add_log(None, "ERROR", "comparison", f"对比失败: {str(e)}")
            return {"success": False, "error": str(e)}

    def add_locomotive(self, locomotive: Dict[str, Any]) -> Dict[str, Any]:
        if not self.locomotives_config:
            self.locomotives_config = {"locomotives": []}

        loco_list = self.locomotives_config["locomotives"]
        if any(l["id"] == locomotive["id"] for l in loco_list):
            return {"success": False, "error": f"机车ID已存在: {locomotive['id']}"}

        temp_config = {"locomotives": loco_list + [locomotive]}
        self.config_loader._validate_locomotives_config(temp_config)

        loco_list.append(locomotive)
        self.config_loader.save_config(self.locomotives_config, "locomotives_config.json")

        self.db.add_log(None, "INFO", "locomotive", f"添加机车: {locomotive['id']} ({locomotive['traction_type']})")

        return {"success": True, "data": locomotive, "message": "机车添加成功"}

    def update_locomotive(self, locomotive: Dict[str, Any]) -> Dict[str, Any]:
        if not self.locomotives_config:
            return {"success": False, "error": "机车配置未加载"}

        loco_list = self.locomotives_config["locomotives"]
        loco_id = locomotive.get("id")
        if not loco_id:
            return {"success": False, "error": "缺少机车ID"}

        existing = None
        for i, l in enumerate(loco_list):
            if l["id"] == loco_id:
                existing = l
                break

        if existing is None:
            return {"success": False, "error": f"机车不存在: {loco_id}"}

        # 更新允许的字段
        allowed_fields = [
            "traction_type", "Q", "max_speed", "initial_node",
            "battery", "fuel_tank", "is_powered_on", "is_schedulable",
            "current_task", "task_phase"
        ]
        for field in allowed_fields:
            if field in locomotive:
                existing[field] = locomotive[field]

        self.config_loader._validate_locomotives_config(self.locomotives_config)
        self.config_loader.save_config(self.locomotives_config, "locomotives_config.json")

        self.db.add_log(None, "INFO", "locomotive", f"更新机车: {loco_id}")

        return {"success": True, "data": existing, "message": "机车更新成功"}

    def add_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        if not self.tasks_config:
            self.tasks_config = {"tasks": []}

        task_list = self.tasks_config["tasks"]
        if any(t["id"] == task["id"] for t in task_list):
            return {"success": False, "error": f"任务ID已存在: {task['id']}"}

        temp_config = {"tasks": task_list + [task]}
        self.config_loader._validate_tasks_config(temp_config)

        task_list.append(task)
        self.config_loader.save_config(self.tasks_config, "tasks_config.json")

        self.db.add_log(None, "INFO", "task", f"添加任务: {task['id']}")

        return {"success": True, "data": task, "message": "任务添加成功"}

    def add_node(self, node: Dict[str, Any]) -> Dict[str, Any]:
        if not self.map_config:
            self.map_config = {"nodes": [], "edges": []}

        node_list = self.map_config["nodes"]
        if any(n["id"] == node["id"] for n in node_list):
            return {"success": False, "error": f"节点ID已存在: {node['id']}"}

        node_list.append(node)
        self.config_loader._validate_map_config(self.map_config)
        self.config_loader.save_config(self.map_config, "map_config.json")

        self.db.add_log(None, "INFO", "map", f"添加节点: {node['id']} ({node['type']})")

        return {"success": True, "data": node, "message": "节点添加成功"}

    def add_edge(self, edge: Dict[str, Any]) -> Dict[str, Any]:
        if not self.map_config:
            return {"success": False, "error": "地图配置未加载"}

        self.map_config["edges"].append(edge)
        self.config_loader._validate_map_config(self.map_config)
        self.config_loader.save_config(self.map_config, "map_config.json")

        self.db.add_log(None, "INFO", "map",
                      f"添加边: {edge['from']} -> {edge['to']}")

        return {"success": True, "data": edge, "message": "边添加成功"}

    def delete_node(self, node_id: str) -> Dict[str, Any]:
        if not self.map_config:
            return {"success": False, "error": "地图配置未加载"}

        node_list = self.map_config["nodes"]
        node = next((n for n in node_list if n["id"] == node_id), None)
        if not node:
            return {"success": False, "error": f"节点不存在: {node_id}"}

        self.map_config["nodes"] = [n for n in node_list if n["id"] != node_id]
        self.map_config["edges"] = [
            e for e in self.map_config["edges"]
            if e["from"] != node_id and e["to"] != node_id
        ]

        self.config_loader._validate_map_config(self.map_config)
        self.config_loader.save_config(self.map_config, "map_config.json")

        self.db.add_log(None, "INFO", "map", f"删除节点: {node_id} ({node['type']})")

        return {"success": True, "data": node, "message": f"节点 {node_id} 已删除"}

    def boost_task_priority(self, task_id: str, boost_amount: int = 10) -> Dict[str, Any]:
        if not self.tasks_config:
            return {"success": False, "error": "任务配置未加载"}

        emergency_mgr = EmergencyTaskManager()
        result = emergency_mgr.boost_task_priority(
            task_id, self.tasks_config["tasks"], boost_amount
        )

        if result:
            self.config_loader.save_config(self.tasks_config, "tasks_config.json")
            self.db.add_log(None, "INFO", "priority",
                          f"任务优先级提升: {task_id}, {result['old_priority']} -> {result['new_priority']}")
            return {"success": True, "data": result}
        else:
            return {"success": False, "error": f"任务不存在: {task_id}"}

    def trigger_emergency_task(self, emergency_task: Dict[str, Any]) -> Dict[str, Any]:
        if not self.tasks_config:
            return {"success": False, "error": "任务配置未加载"}

        emergency_mgr = EmergencyTaskManager()
        result = emergency_mgr.trigger_emergency_task(
            emergency_task, self.tasks_config["tasks"]
        )

        self.tasks_config["tasks"].append(emergency_task)
        self.config_loader.save_config(self.tasks_config, "tasks_config.json")

        self.db.add_log(None, "WARN", "emergency",
                      f"紧急任务触发: {emergency_task['id']}, 暂停{len(result['paused_tasks'])}个任务")

        return {"success": True, "data": result}

    def query_runs(self, batch_id: Optional[str] = None,
                    strategy_name: Optional[str] = None,
                    page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        result = self.db.query_runs(batch_id, strategy_name, None, page, page_size)
        return {"success": True, "data": result}

    def query_tasks(self, batch_id: Optional[str] = None,
                     task_type: Optional[str] = None,
                     page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        result = self.db.query_tasks(batch_id, task_type, None, page, page_size)
        return {"success": True, "data": result}

    def query_locomotives(self, batch_id: Optional[str] = None,
                           traction_type: Optional[str] = None,
                           page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        result = self.db.query_locomotives(batch_id, traction_type, page, page_size)
        return {"success": True, "data": result}

    def query_logs(self, batch_id: Optional[str] = None,
                   log_level: Optional[str] = None,
                   page: int = 1, page_size: int = 50) -> Dict[str, Any]:
        result = self.db.query_logs(batch_id, log_level, None, page, page_size)
        return {"success": True, "data": result}

    def get_run_detail(self, run_id: int) -> Dict[str, Any]:
        result = self.db.get_run_detail(run_id)
        if result:
            return {"success": True, "data": result}
        return {"success": False, "error": "运行记录不存在"}

    def get_batch_history(self, batch_id: str) -> Dict[str, Any]:
        result = self.db.get_batch_history(batch_id)
        if result:
            return {"success": True, "data": result}
        return {"success": False, "error": "批次不存在"}

    def get_statistics(self) -> Dict[str, Any]:
        stats = self.db.get_statistics()
        return {"success": True, "data": stats}

    def get_available_strategies(self) -> Dict[str, Any]:
        strategies = self.strategy_manager.get_available_strategies()
        result = {}
        for name, info in strategies.items():
            result[name] = {
                "name": info["name"],
                "description": info.get("description", "")
            }
        return {"success": True, "data": result}

    def get_all_batch_ids(self) -> Dict[str, Any]:
        batch_ids = self.db.get_all_batch_ids()
        return {"success": True, "data": batch_ids}

    def get_give_way_analysis(self, high_prio_task_id: str,
                               low_prio_task_id: str) -> Dict[str, Any]:
        if not self._ensure_configs():
            return {"success": False, "error": "配置文件未加载"}

        if not self.map_config:
            return {"success": False, "error": "地图配置未加载"}

        give_way_mgr = GiveWayManager(self.map_config, self.hyper_params or {})

        high_task = next((t for t in self.tasks_config["tasks"]
                         if t["id"] == high_prio_task_id), None)
        low_task = next((t for t in self.tasks_config["tasks"]
                        if t["id"] == low_prio_task_id), None)

        if not high_task or not low_task:
            return {"success": False, "error": "任务不存在"}

        result = give_way_mgr.calculate_give_way(
            {"task_id": low_prio_task_id, "path": low_task.get("path", []),
             "priority": low_task.get("priority", 99)},
            {"task_id": high_prio_task_id, "path": high_task.get("path", []),
             "priority": high_task.get("priority", 99), "speed": 100}
        )

        return {"success": True, "data": result}

    def check_direction_lock(self, direction: str) -> Dict[str, Any]:
        if not self.map_config:
            return {"success": False, "error": "地图配置未加载"}

        priority_scheduler = PriorityScheduler(self.map_config, self.hyper_params or {})
        is_available = priority_scheduler.check_direction_available(direction)

        return {
            "success": True,
            "data": {
                "direction": direction,
                "is_available": is_available,
                "lock_status": priority_scheduler.direction_lock
            }
        }
