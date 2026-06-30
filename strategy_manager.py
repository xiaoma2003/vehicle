"""
策略管理器 - 统一管理所有调度策略
"""
import time
import math
from typing import Dict, List, Any

from strategies.base_cpsat import DijkstraPathCalculator, CPSATScheduler
from strategies.greedy_strategy import GreedyScheduler
from strategies.genetic_algorithm import GeneticAlgorithmScheduler
from strategies.simulated_annealing import SimulatedAnnealingScheduler


class StrategyManager:
    def __init__(self):
        self.strategies = {
            "cpsat": {"name": "CP-SAT基准策略", "class": None, "is_baseline": True, "description": "Dijkstra + Google OR-Tools CP-SAT约束规划"},
            "greedy": {"name": "贪心算法", "class": GreedyScheduler, "is_baseline": False, "description": "基于优先级和最短路径的贪心调度"},
            "genetic": {"name": "遗传算法", "class": GeneticAlgorithmScheduler, "is_baseline": False, "description": "进化算法搜索最优调度方案"},
            "simulated_annealing": {"name": "模拟退火", "class": SimulatedAnnealingScheduler, "is_baseline": False, "description": "基于模拟退火的调度优化"}
        }

    def get_available_strategies(self) -> Dict[str, Dict]:
        return self.strategies

    def run_strategy(self, strategy_name: str, map_config, tasks_config,
                     locomotives_config, hyper_params) -> Dict[str, Any]:
        path_calculator = DijkstraPathCalculator(map_config, hyper_params)
        precomputed_paths = path_calculator.precompute_all_paths(
            locomotives_config["locomotives"]
        )

        start_time = time.time()

        if strategy_name == "cpsat":
            scheduler = CPSATScheduler(
                map_config, tasks_config, locomotives_config,
                hyper_params, precomputed_paths
            )
        elif strategy_name in self.strategies and self.strategies[strategy_name]["class"]:
            scheduler_class = self.strategies[strategy_name]["class"]
            scheduler = scheduler_class(
                map_config, tasks_config, locomotives_config,
                hyper_params, precomputed_paths
            )
        else:
            raise ValueError(f"未知策略: {strategy_name}")

        result = scheduler.solve()
        end_time = time.time()
        result["solve_time"] = round(end_time - start_time, 4)
        result["strategy_name"] = strategy_name
        result["strategy_display_name"] = self.strategies[strategy_name]["name"]
        result["energy_consumption"] = self._calculate_energy_consumption(result, locomotives_config)
        result["dynamic_adaptability"] = self._calculate_dynamic_adaptability(result)

        return result

    def _calculate_energy_consumption(self, result: Dict, locomotives_config: Dict) -> float:
        """计算总能耗（kWh/L）"""
        assignments = result.get("assignments", [])
        if not assignments:
            return 0.0

        total_energy = 0.0
        loco_map = {l["id"]: l for l in locomotives_config.get("locomotives", [])}

        for a in assignments:
            loco = loco_map.get(a["locomotive_id"], {})
            is_electric = loco.get("traction_type") == "electric"
            # 运输距离 = 运输时间 * 速度
            transport_time = (a.get("transport_end", 0) - a.get("loading_end", 0))
            speed = loco.get("max_speed", 800)
            # 粗略估算: 能耗 = 运输时间 * 消耗率 * 载重系数
            rate = 0.5 if is_electric else 0.8  # 电车kWh, 油车L per minute
            weight = loco.get("Q", 50)
            total_energy += transport_time * rate * (weight / 50)

        return round(total_energy, 2)

    def _calculate_dynamic_adaptability(self, result: Dict) -> float:
        """计算动态适应性（重调度响应时间，基于求解时间）"""
        solve_time = result.get("solve_time", 0)
        # 响应时间越短适应性越好，用 1/(1+solve_time) 归一化
        return round(1.0 / (1.0 + solve_time), 4)

    def compare_strategies(self, strategy_names: List[str], map_config, tasks_config,
                           locomotives_config, hyper_params) -> Dict[str, Any]:
        results = {}
        comparison = {
            "strategies": [],
            "best_makespan": float('inf'),
            "best_strategy": None,
            "fastest_strategy": None,
            "fastest_time": float('inf'),
            "baseline": None
        }

        for strategy_name in strategy_names:
            try:
                result = self.run_strategy(
                    strategy_name, map_config, tasks_config,
                    locomotives_config, hyper_params
                )
                results[strategy_name] = result

                energy = self._calculate_energy_consumption(result, locomotives_config)
                adaptability = self._calculate_dynamic_adaptability(result)
                is_baseline = self.strategies[strategy_name].get("is_baseline", False)

                if result["makespan"] >= 0 and result["makespan"] < comparison["best_makespan"]:
                    comparison["best_makespan"] = result["makespan"]
                    comparison["best_strategy"] = strategy_name

                if result.get("solve_time", 0) < comparison["fastest_time"]:
                    comparison["fastest_time"] = result["solve_time"]
                    comparison["fastest_strategy"] = strategy_name

                strategy_info = {
                    "name": strategy_name,
                    "display_name": result["strategy_display_name"],
                    "makespan": result["makespan"],
                    "solve_time": result.get("solve_time", 0),
                    "num_tasks": result.get("num_tasks", 0),
                    "solve_status": result["solve_status"],
                    "energy_consumption": energy,
                    "dynamic_adaptability": adaptability,
                    "is_baseline": is_baseline
                }
                comparison["strategies"].append(strategy_info)

                if is_baseline:
                    comparison["baseline"] = strategy_info

            except Exception as e:
                results[strategy_name] = {
                    "solve_status": "error",
                    "error": str(e),
                    "strategy_name": strategy_name
                }
                comparison["strategies"].append({
                    "name": strategy_name,
                    "display_name": self.strategies[strategy_name]["name"],
                    "error": str(e),
                    "solve_status": "error",
                    "is_baseline": self.strategies[strategy_name].get("is_baseline", False)
                })

        comparison["results"] = results
        return comparison
