"""
候选策略2：遗传算法（Genetic Algorithm）
通过进化算法搜索最优调度方案
"""
import random
import copy
from typing import Dict, List, Any, Tuple


class GeneticAlgorithmScheduler:
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
        assignments = []
        task_map = {t["id"]: t for t in self.active_tasks}
        task_idx_map = {i: self.active_tasks[i]["id"] for i in range(len(self.active_tasks))}

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

                deps_met = all(dep_id in [self.active_tasks[g]["id"] for g in scheduled]
                              for dep_id in task.get("depends_on", []))
                if not deps_met:
                    continue

                if task["material_weight"] <= 0:
                    scheduled.add(gene_idx)
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
                    scheduled.add(gene_idx)
                    made_progress = True

            if not made_progress:
                break

        makespan = max((a["unloading_end"] for a in assignments), default=0)
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
            "num_locomotives": len(self.schedulable_locomotives),
            "algorithm": "genetic_algorithm",
            "generations": generations,
            "population_size": population_size,
            "final_fitness": best_fitness
        }
