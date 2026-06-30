"""
策略管理器 - 统一管理所有调度策略
"""
import time
from typing import Dict, List, Any

from strategies.base_cpsat import DijkstraPathCalculator, CPSATScheduler
from strategies.greedy_strategy import GreedyScheduler
from strategies.genetic_algorithm import GeneticAlgorithmScheduler
from strategies.simulated_annealing import SimulatedAnnealingScheduler


class StrategyManager:
    def __init__(self):
        self.strategies = {
            "cpsat": {"name": "CP-SAT基准策略", "class": None, "description": "Dijkstra + Google OR-Tools CP-SAT约束规划"},
            "greedy": {"name": "贪心算法", "class": GreedyScheduler, "description": "基于优先级和最短路径的贪心调度"},
            "genetic": {"name": "遗传算法", "class": GeneticAlgorithmScheduler, "description": "进化算法搜索最优调度方案"},
            "simulated_annealing": {"name": "模拟退火", "class": SimulatedAnnealingScheduler, "description": "基于模拟退火的调度优化"}
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
        result["solve_time"] = round(end_time - start_time, 3)
        result["strategy_name"] = strategy_name
        result["strategy_display_name"] = self.strategies[strategy_name]["name"]

        return result

    def compare_strategies(self, strategy_names: List[str], map_config, tasks_config,
                           locomotives_config, hyper_params) -> Dict[str, Any]:
        results = {}
        comparison = {
            "strategies": [],
            "best_makespan": float('inf'),
            "best_strategy": None,
            "fastest_strategy": None,
            "fastest_time": float('inf')
        }

        for strategy_name in strategy_names:
            try:
                result = self.run_strategy(
                    strategy_name, map_config, tasks_config,
                    locomotives_config, hyper_params
                )
                results[strategy_name] = result

                if result["makespan"] >= 0 and result["makespan"] < comparison["best_makespan"]:
                    comparison["best_makespan"] = result["makespan"]
                    comparison["best_strategy"] = strategy_name

                if result.get("solve_time", 0) < comparison["fastest_time"]:
                    comparison["fastest_time"] = result["solve_time"]
                    comparison["fastest_strategy"] = strategy_name

                comparison["strategies"].append({
                    "name": strategy_name,
                    "display_name": result["strategy_display_name"],
                    "makespan": result["makespan"],
                    "solve_time": result.get("solve_time", 0),
                    "num_tasks": result.get("num_tasks", 0),
                    "solve_status": result["solve_status"]
                })

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
                    "solve_status": "error"
                })

        comparison["results"] = results
        return comparison
