"""
候选策略2：遗传算法（Genetic Algorithm）
通过进化算法搜索最优调度方案
"""
import random
import copy
import math
from typing import Dict, List, Any, Tuple


class GeneticAlgorithmScheduler:
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

    def _create_individual(self) -> List[int]:
        task_order = list(range(len(self.active_tasks)))
        random.shuffle(task_order)
        return task_order

    def _decode_chromosome(self, chromosome: List[int]) -> Tuple[List[Dict[str, Any]], int]:
        if not self.active_tasks or not self.schedulable_locomotives:
            return [], 0

        loco_available_time = {l["id"]: 0 for l in self.schedulable_locomotives}
        loco_current_node = {l["id"]: l["initial_node"] for l in self.schedulable_locomotives}

        completed_tasks = set()
        task_end_times = {}  # 记录任务实际完成时间
        assignments = []

        scheduled = set()
        max_iterations = len(chromosome) * 2
        iter_count = 0

        while len(scheduled) < len(chromosome) and iter_count < max_iterations:
            iter_count += 1
            made_progress = False

            for gene_idx in chromosome:
                if gene_idx in scheduled:
                    continue
                task = self.active_tasks[gene_idx]
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

                if task["material_weight"] <= 0:
                    scheduled.add(gene_idx)
                    continue

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
                    scheduled.add(gene_idx)
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

    def _fitness(self, chromosome: List[int]) -> float:
        _, makespan = self._decode_chromosome(chromosome)
        if makespan == 0:
            return float('inf')
        return 1.0 / makespan

    def _crossover(self, parent1: List[int], parent2: List[int]) -> List[int]:
        if len(parent1) <= 1:
            return parent1.copy()

        point = random.randint(1, len(parent1) - 1)
        child = parent1[:point]
        for gene in parent2:
            if gene not in child:
                child.append(gene)
        return child

    def _mutate(self, chromosome: List[int], mutation_rate: float = 0.1) -> List[int]:
        if len(chromosome) <= 1:
            return chromosome

        mutated = chromosome.copy()
        if random.random() < mutation_rate:
            i, j = random.sample(range(len(mutated)), 2)
            mutated[i], mutated[j] = mutated[j], mutated[i]
        return mutated

    def solve(self, population_size: int = 50, generations: int = 100,
              mutation_rate: float = 0.1, elitism: int = 5) -> Dict[str, Any]:
        if not self.active_tasks or not self.schedulable_locomotives:
            return {
                "solve_status": "optimal",
                "makespan": 0,
                "assignments": [],
                "algorithm": "genetic_algorithm",
                "generations": 0,
                "population_size": population_size
            }

        population = [self._create_individual() for _ in range(population_size)]

        best_fitness = -1
        best_chromosome = None
        best_assignments = None
        best_makespan = float('inf')

        for gen in range(generations):
            fitness_scores = [self._fitness(ind) for ind in population]

            elite_indices = sorted(range(len(population)), key=lambda i: fitness_scores[i], reverse=True)[:elitism]
            elite = [population[i] for i in elite_indices]

            if fitness_scores[elite_indices[0]] > best_fitness:
                best_fitness = fitness_scores[elite_indices[0]]
                best_chromosome = population[elite_indices[0]]
                best_assignments, best_makespan = self._decode_chromosome(best_chromosome)

            new_population = elite.copy()

            total_fitness = sum(fitness_scores)
            if total_fitness == 0:
                probabilities = [1.0 / len(population)] * len(population)
            else:
                probabilities = [f / total_fitness for f in fitness_scores]

            while len(new_population) < population_size:
                parent1_idx = random.choices(range(len(population)), weights=probabilities, k=1)[0]
                parent2_idx = random.choices(range(len(population)), weights=probabilities, k=1)[0]
                child = self._crossover(population[parent1_idx], population[parent2_idx])
                child = self._mutate(child, mutation_rate)
                new_population.append(child)

            population = new_population

        return {
            "solve_status": "feasible",
            "makespan": best_makespan,
            "assignments": best_assignments,
            "num_tasks": len(best_assignments),
            "num_locomotives": len(self.schedulable_locomotives) + len(self.assigned_tasks),
            "algorithm": "genetic_algorithm",
            "generations": generations,
            "population_size": population_size,
            "final_fitness": best_fitness
        }
