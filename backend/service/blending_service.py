#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
import random
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.optimize import linprog


class ImprovedGeneticOptimizer:
    """用于受约束混煤搜索的遗传算法优化器。"""

    def __init__(self, config: Optional[Dict] = None):
        default_config = {
            'population_size': 300,
            'max_generations': 2000,
            'mutation_rate': 0.15,
            'crossover_rate': 0.85,
            'tournament_size': 7,
            'elite_ratio': 0.1,
            'early_stopping_patience': 150,
            'convergence_threshold': 1e-6,
            'parallel_workers': min(4, os.cpu_count() or 1),
            'parallel_computing': True,
            'adaptive_mutation': True,
            'constraint_penalty_factor': 1000.0,
            'diversity_factor': 0.1,
        }
        self.config = {**default_config, **(config or {})}
        self.logger = logging.getLogger(__name__)
        self._ensure_config_types()

        self.fitness_history: List[float] = []
        self.best_fitness = float('inf')
        self.stagnation_count = 0
        self.generation_count = 0

    def _ensure_config_types(self):
        """统一配置类型。"""
        for key in [
            'population_size',
            'max_generations',
            'tournament_size',
            'early_stopping_patience',
            'parallel_workers',
        ]:
            self.config[key] = int(self.config[key])

        for key in [
            'mutation_rate',
            'crossover_rate',
            'elite_ratio',
            'convergence_threshold',
            'constraint_penalty_factor',
            'diversity_factor',
        ]:
            self.config[key] = float(self.config[key])

        self.config['adaptive_mutation'] = self._coerce_bool(
            self.config.get('adaptive_mutation', True)
        )
        self.config['parallel_computing'] = self._coerce_bool(
            self.config.get('parallel_computing', True)
        )

        if not self.config['parallel_computing']:
            self.config['parallel_workers'] = 1

    @staticmethod
    def _coerce_bool(value) -> bool:
        if isinstance(value, str):
            return value.lower() in {'true', '1', 'yes', 'on'}
        return bool(value)

    def repair_individual(
        self,
        individual: List[float],
        ratio_limits: Optional[Dict] = None,
        weights: Optional[List[float]] = None,
    ) -> Optional[List[float]]:
        """修复个体，使其满足单煤种边界和总和为1。"""
        values = np.asarray(individual, dtype=float)
        n_coals = len(values)

        if n_coals == 0:
            return None

        if ratio_limits is None:
            total = float(values.sum())
            if total <= 0:
                return [1.0 / n_coals] * n_coals
            return (values / total).tolist()

        min_limits = np.asarray(ratio_limits.get('min', [0.0] * n_coals), dtype=float)
        max_limits = np.asarray(ratio_limits.get('max', [1.0] * n_coals), dtype=float)

        if len(min_limits) != n_coals or len(max_limits) != n_coals:
            raise ValueError('配比约束维度与煤种数量不一致')
        if np.any(min_limits > max_limits):
            raise ValueError('存在煤种配比下限大于上限')

        total_min = float(min_limits.sum())
        total_max = float(max_limits.sum())
        if total_min > 1.0 + 1e-9 or total_max < 1.0 - 1e-9:
            return None

        result = np.clip(values, min_limits, max_limits)
        preference = np.asarray(weights if weights is not None else result, dtype=float)
        if preference.shape != result.shape:
            preference = result.copy()

        for _ in range(30):
            diff = 1.0 - float(result.sum())
            if abs(diff) <= 1e-9:
                return result.tolist()

            if diff > 0:
                slack = np.maximum(max_limits - result, 0.0)
                eligible = slack > 1e-12
                if not np.any(eligible):
                    break

                basis = np.maximum(preference[eligible], 0.0) + 1e-9
                basis = basis * np.maximum(slack[eligible], 1e-9)
                basis_sum = float(basis.sum())
                if basis_sum <= 0:
                    basis = slack[eligible]
                    basis_sum = float(basis.sum())
                allocation = diff * (basis / basis_sum)
                result[eligible] += np.minimum(allocation, slack[eligible])
            else:
                reducible = np.maximum(result - min_limits, 0.0)
                eligible = reducible > 1e-12
                if not np.any(eligible):
                    break

                basis = np.maximum(result[eligible], 0.0) + 1e-9
                basis = basis * np.maximum(reducible[eligible], 1e-9)
                basis_sum = float(basis.sum())
                if basis_sum <= 0:
                    basis = reducible[eligible]
                    basis_sum = float(basis.sum())
                reduction = (-diff) * (basis / basis_sum)
                result[eligible] -= np.minimum(reduction, reducible[eligible])

        residual = 1.0 - float(result.sum())
        if abs(residual) <= 1e-6:
            return result.tolist()

        if residual > 0:
            slack = np.maximum(max_limits - result, 0.0)
            if float(slack.sum()) >= residual - 1e-9:
                index = int(np.argmax(slack))
                result[index] += residual
        else:
            reducible = np.maximum(result - min_limits, 0.0)
            if float(reducible.sum()) >= (-residual) - 1e-9:
                index = int(np.argmax(reducible))
                result[index] += residual

        if abs(float(result.sum()) - 1.0) > 1e-6:
            return None
        if np.any(result < min_limits - 1e-6) or np.any(result > max_limits + 1e-6):
            return None

        return result.tolist()

    def create_individual(
        self,
        n_coals: int,
        ratio_limits: Optional[Dict] = None,
        seed_individual: Optional[List[float]] = None,
    ) -> List[float]:
        """创建满足配比约束的个体。"""
        max_attempts = 100

        for _ in range(max_attempts):
            if ratio_limits is None:
                candidate = np.random.dirichlet(np.ones(n_coals)).tolist()
            else:
                min_limits = np.asarray(ratio_limits.get('min', [0.0] * n_coals), dtype=float)
                max_limits = np.asarray(ratio_limits.get('max', [1.0] * n_coals), dtype=float)
                remaining = 1.0 - float(min_limits.sum())
                slack = np.maximum(max_limits - min_limits, 0.0)

                if remaining < -1e-9 or float(max_limits.sum()) < 1.0 - 1e-9:
                    break

                if seed_individual is not None:
                    seed = np.asarray(seed_individual, dtype=float)
                    noise = np.random.normal(0.0, 0.03, n_coals)
                    weights = np.maximum(seed + noise, 0.0)
                    weights = np.minimum(weights, slack + 1e-9)
                else:
                    weights = np.random.random(n_coals) * np.maximum(slack, 1e-9)

                if float(weights.sum()) <= 0:
                    weights = np.maximum(slack, 1e-9)

                extra = np.zeros(n_coals)
                if remaining > 0:
                    extra = remaining * (weights / float(weights.sum()))

                candidate = (min_limits + extra).tolist()

            repaired = self.repair_individual(candidate, ratio_limits, candidate)
            if repaired is not None:
                return repaired

        safe = self._create_safe_individual(n_coals, ratio_limits, seed_individual)
        if safe is None:
            raise ValueError('无法生成满足配比约束的初始个体')
        return safe

    def _create_safe_individual(
        self,
        n_coals: int,
        ratio_limits: Optional[Dict] = None,
        seed_individual: Optional[List[float]] = None,
    ) -> Optional[List[float]]:
        if seed_individual is not None:
            repaired = self.repair_individual(seed_individual, ratio_limits, seed_individual)
            if repaired is not None:
                return repaired

        if ratio_limits is None:
            return [1.0 / n_coals] * n_coals

        min_limits = np.asarray(ratio_limits.get('min', [0.0] * n_coals), dtype=float)
        max_limits = np.asarray(ratio_limits.get('max', [1.0] * n_coals), dtype=float)
        remaining = 1.0 - float(min_limits.sum())
        slack = np.maximum(max_limits - min_limits, 0.0)
        if remaining < -1e-9 or float(max_limits.sum()) < 1.0 - 1e-9:
            return None

        if remaining <= 1e-12:
            return min_limits.tolist()

        weights = np.maximum(slack, 1e-9)
        candidate = min_limits + remaining * (weights / float(weights.sum()))
        return self.repair_individual(candidate.tolist(), ratio_limits, candidate.tolist())

    def crossover(
        self,
        parent1: List[float],
        parent2: List[float],
        ratio_limits: Optional[Dict] = None,
    ) -> Tuple[List[float], List[float]]:
        """交叉产生新个体。"""
        n = len(parent1)
        alpha = random.random()

        if random.random() < 0.5:
            child1 = [alpha * p1 + (1 - alpha) * p2 for p1, p2 in zip(parent1, parent2)]
            child2 = [(1 - alpha) * p1 + alpha * p2 for p1, p2 in zip(parent1, parent2)]
        else:
            mask = [random.random() < 0.5 for _ in range(n)]
            child1 = [parent1[i] if mask[i] else parent2[i] for i in range(n)]
            child2 = [parent2[i] if mask[i] else parent1[i] for i in range(n)]

        repaired_child1 = self.repair_individual(child1, ratio_limits, parent1)
        repaired_child2 = self.repair_individual(child2, ratio_limits, parent2)

        if repaired_child1 is None:
            repaired_child1 = self.create_individual(n, ratio_limits, parent1)
        if repaired_child2 is None:
            repaired_child2 = self.create_individual(n, ratio_limits, parent2)

        return repaired_child1, repaired_child2

    def mutate(self, individual: List[float], ratio_limits: Optional[Dict] = None) -> List[float]:
        """基于扰动和修复的变异操作。"""
        result = np.asarray(individual, dtype=float).copy()
        n_coals = len(result)

        mutation_rate = self.config['mutation_rate']
        if self.config['adaptive_mutation']:
            if self.stagnation_count > 50:
                mutation_rate = min(mutation_rate * 2.0, 0.5)
            elif self.stagnation_count > 20:
                mutation_rate = min(mutation_rate * 1.5, 0.5)

        sigma = max(0.005, 0.08 * (1 - self.generation_count / max(self.config['max_generations'], 1)))

        for index in range(n_coals):
            if random.random() < mutation_rate:
                result[index] += random.gauss(0.0, sigma)

        if n_coals > 1 and random.random() < mutation_rate:
            i, j = random.sample(range(n_coals), 2)
            transfer = min(abs(random.gauss(0.0, sigma)), result[i])
            result[i] -= transfer
            result[j] += transfer

        repaired = self.repair_individual(result.tolist(), ratio_limits, individual)
        if repaired is None:
            return self.create_individual(n_coals, ratio_limits, individual)
        return repaired

    def optimize(
        self,
        fitness_func,
        n_coals: int,
        ratio_limits: Optional[Dict] = None,
        seed_individual: Optional[List[float]] = None,
        progress_callback=None,
        log_callback=None,
    ) -> Tuple[Optional[List[float]], float]:
        """执行遗传算法优化。"""
        self.fitness_history = []
        self.best_fitness = float('inf')
        self.stagnation_count = 0
        self.generation_count = 0

        population = []
        if seed_individual is not None:
            repaired_seed = self.repair_individual(seed_individual, ratio_limits, seed_individual)
            if repaired_seed is not None:
                population.append(repaired_seed)

        while len(population) < self.config['population_size']:
            use_seed = seed_individual if seed_individual is not None and len(population) < self.config['population_size'] // 2 else None
            population.append(self.create_individual(n_coals, ratio_limits, use_seed))

        best_individual = None

        for generation in range(self.config['max_generations']):
            self.generation_count = generation
            fitness_scores = self.evaluate_population_parallel(population, fitness_func)

            gen_best_idx = int(np.argmin(fitness_scores))
            gen_best_fitness = float(fitness_scores[gen_best_idx])
            gen_best_individual = population[gen_best_idx].copy()

            if gen_best_fitness + 1e-12 < self.best_fitness:
                self.best_fitness = gen_best_fitness
                best_individual = gen_best_individual
                self.stagnation_count = 0
            else:
                self.stagnation_count += 1

            self.fitness_history.append(self.best_fitness)

            if log_callback and generation % 50 == 0:
                log_callback(f'第 {generation} 代，当前最优适应度 = {self.best_fitness:.6f}')

            if progress_callback:
                progress_callback(int((generation + 1) / self.config['max_generations'] * 100))

            if self.check_early_stopping():
                if log_callback:
                    log_callback(f'第 {generation} 代达到早停条件，提前结束')
                break

            elite_size = max(1, int(self.config['elite_ratio'] * self.config['population_size']))
            elite_indices = np.argsort(fitness_scores)[:elite_size]
            new_population = [population[index].copy() for index in elite_indices]

            diversity_factor = float(self.config.get('diversity_factor', 0.0))
            if diversity_factor > 0 and self.stagnation_count > 0:
                patience = max(1, int(self.config.get('early_stopping_patience', 1)))
                immigrant_scale = min(1.0, self.stagnation_count / patience)
                immigrant_count = int(self.config['population_size'] * diversity_factor * immigrant_scale)
                for _ in range(immigrant_count):
                    new_population.append(self.create_individual(n_coals, ratio_limits, seed_individual))

            while len(new_population) < self.config['population_size']:
                parent1 = self.tournament_selection(population, fitness_scores)
                parent2 = self.tournament_selection(population, fitness_scores)

                if random.random() < self.config['crossover_rate']:
                    child1, child2 = self.crossover(parent1, parent2, ratio_limits)
                else:
                    child1, child2 = parent1.copy(), parent2.copy()

                child1 = self.mutate(child1, ratio_limits)
                child2 = self.mutate(child2, ratio_limits)
                new_population.extend([child1, child2])

            population = new_population[:self.config['population_size']]

        if log_callback:
            log_callback(f'优化完成，最终最优适应度 = {self.best_fitness:.6f}')

        return best_individual, self.best_fitness

    def tournament_selection(self, population: List[List[float]], fitness_scores: List[float]) -> List[float]:
        tournament_size = min(self.config['tournament_size'], len(population))
        tournament_indices = random.sample(range(len(population)), tournament_size)
        best_index = min(tournament_indices, key=lambda index: fitness_scores[index])
        return population[best_index].copy()

    def evaluate_population_parallel(self, population: List[List[float]], fitness_func) -> List[float]:
        parallel_workers = int(self.config.get('parallel_workers', 1))
        parallel_enabled = bool(self.config.get('parallel_computing', True))

        if not parallel_enabled or parallel_workers <= 1 or len(population) < 10:
            return [fitness_func(individual) for individual in population]

        worker_cap = os.cpu_count() or parallel_workers
        max_workers = min(parallel_workers, len(population), worker_cap)
        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                return list(executor.map(fitness_func, population))
        except Exception as exc:
            self.logger.warning(f'并行评估失败，改用串行模式: {exc}')
            return [fitness_func(individual) for individual in population]

    def check_early_stopping(self) -> bool:
        patience = int(self.config.get('early_stopping_patience', 150))
        threshold = float(self.config.get('convergence_threshold', 1e-6))

        if len(self.fitness_history) < patience:
            return False

        recent_history = self.fitness_history[-patience:]
        improvement = abs(float(recent_history[0]) - float(recent_history[-1]))
        return improvement < threshold


class NSGA2BlendingOptimizer:
    """NSGA-II optimizer for constrained multi-objective coal blending."""

    def __init__(self, base_optimizer: ImprovedGeneticOptimizer):
        self.base_optimizer = base_optimizer
        self.config = base_optimizer.config
        self.generations_used = 0
        self.logger = logging.getLogger(__name__)

    def optimize(
        self,
        objective_func,
        n_coals: int,
        ratio_limits: Dict,
        seed_individual: Optional[List[float]] = None,
    ) -> List[Dict]:
        random_seed = self.config.get('random_seed')
        if random_seed is not None:
            random.seed(int(random_seed))
            np.random.seed(int(random_seed))

        population_size = int(self.config.get('population_size', 300))
        max_generations = int(self.config.get('max_generations', 2000))
        patience = int(self.config.get('early_stopping_patience', 150))
        threshold = float(self.config.get('convergence_threshold', 1e-6))
        population = self._create_initial_population(n_coals, ratio_limits, seed_individual)

        best_cost = float('inf')
        best_heat = float('-inf')
        best_quality = float('inf')
        stagnation_count = 0

        evaluated = []
        for generation in range(max_generations):
            self.base_optimizer.generation_count = generation

            evaluated = self._evaluate_population(population, objective_func)
            fronts = self.fast_non_dominated_sort(evaluated)
            for front in fronts:
                self.assign_crowding_distance(front, evaluated)

            feasible = [item for item in evaluated if item['is_feasible']]
            if feasible:
                gen_best_cost = min(item['total_price'] for item in feasible)
                gen_best_heat = max(item['total_heat'] for item in feasible)
                gen_best_quality = min(item['quality_penalty'] for item in feasible)
                improved = (
                    gen_best_cost < best_cost - threshold
                    or gen_best_heat > best_heat + threshold
                    or gen_best_quality < best_quality - threshold
                )
                best_cost = min(best_cost, gen_best_cost)
                best_heat = max(best_heat, gen_best_heat)
                best_quality = min(best_quality, gen_best_quality)
                stagnation_count = 0 if improved else stagnation_count + 1
            else:
                stagnation_count += 1

            self.base_optimizer.stagnation_count = stagnation_count
            self.generations_used = generation + 1

            if generation + 1 >= patience and stagnation_count >= patience:
                break

            offspring = []
            while len(offspring) < population_size:
                parent1 = self._select_parent(evaluated)
                parent2 = self._select_parent(evaluated)
                if random.random() < float(self.config.get('crossover_rate', 0.85)):
                    child1, child2 = self.base_optimizer.crossover(
                        parent1['ratios'],
                        parent2['ratios'],
                        ratio_limits,
                    )
                else:
                    child1 = parent1['ratios'].copy()
                    child2 = parent2['ratios'].copy()

                offspring.append(self.base_optimizer.mutate(child1, ratio_limits))
                if len(offspring) < population_size:
                    offspring.append(self.base_optimizer.mutate(child2, ratio_limits))

            combined = evaluated + self._evaluate_population(offspring, objective_func)
            population = self._next_generation(combined, population_size)

        if not evaluated:
            evaluated = self._evaluate_population(population, objective_func)
        fronts = self.fast_non_dominated_sort(evaluated)
        if not fronts:
            return []
        first_front = fronts[0]
        self.assign_crowding_distance(first_front, evaluated)
        return [evaluated[index] for index in first_front if evaluated[index]['is_feasible']]

    def _create_initial_population(
        self,
        n_coals: int,
        ratio_limits: Dict,
        seed_individual: Optional[List[float]],
    ) -> List[List[float]]:
        population = []
        if seed_individual is not None:
            repaired_seed = self.base_optimizer.repair_individual(seed_individual, ratio_limits, seed_individual)
            if repaired_seed is not None:
                population.append(repaired_seed)

        while len(population) < int(self.config.get('population_size', 300)):
            use_seed = seed_individual if seed_individual is not None and len(population) < int(self.config.get('population_size', 300)) // 2 else None
            population.append(self.base_optimizer.create_individual(n_coals, ratio_limits, use_seed))

        return population

    def _evaluate_population(self, population: List[List[float]], objective_func) -> List[Dict]:
        evaluated = []
        seen = set()
        for ratios in population:
            key = tuple(round(value, 8) for value in ratios)
            if key in seen:
                continue
            seen.add(key)
            item = objective_func(ratios)
            item['ratios'] = list(ratios)
            item['rank'] = 0
            item['crowding_distance'] = 0.0
            evaluated.append(item)
        return evaluated

    def _select_parent(self, evaluated: List[Dict]) -> Dict:
        tournament_size = min(int(self.config.get('tournament_size', 7)), len(evaluated))
        candidates = random.sample(evaluated, tournament_size)
        return min(
            candidates,
            key=lambda item: (
                item.get('rank', float('inf')),
                -item.get('crowding_distance', 0.0),
                item.get('violation_score', 0.0),
            ),
        )

    def _next_generation(self, evaluated: List[Dict], population_size: int) -> List[List[float]]:
        fronts = self.fast_non_dominated_sort(evaluated)
        next_items = []
        for front in fronts:
            self.assign_crowding_distance(front, evaluated)
            front_items = [evaluated[index] for index in front]
            if len(next_items) + len(front_items) <= population_size:
                next_items.extend(front_items)
                continue

            remaining = population_size - len(next_items)
            front_items.sort(key=lambda item: item.get('crowding_distance', 0.0), reverse=True)
            next_items.extend(front_items[:remaining])
            break

        return [item['ratios'].copy() for item in next_items]

    def fast_non_dominated_sort(self, evaluated: List[Dict]) -> List[List[int]]:
        dominates_map = {index: [] for index in range(len(evaluated))}
        dominated_counts = {index: 0 for index in range(len(evaluated))}
        fronts = [[]]

        for left_index, left in enumerate(evaluated):
            for right_index, right in enumerate(evaluated):
                if left_index == right_index:
                    continue
                if self.dominates(left, right):
                    dominates_map[left_index].append(right_index)
                elif self.dominates(right, left):
                    dominated_counts[left_index] += 1

            if dominated_counts[left_index] == 0:
                evaluated[left_index]['rank'] = 1
                fronts[0].append(left_index)

        current = 0
        while current < len(fronts) and fronts[current]:
            next_front = []
            for left_index in fronts[current]:
                for right_index in dominates_map[left_index]:
                    dominated_counts[right_index] -= 1
                    if dominated_counts[right_index] == 0:
                        evaluated[right_index]['rank'] = current + 2
                        next_front.append(right_index)
            current += 1
            if next_front:
                fronts.append(next_front)

        return fronts

    @staticmethod
    def dominates(left: Dict, right: Dict) -> bool:
        if left['is_feasible'] and not right['is_feasible']:
            return True
        if not left['is_feasible'] and right['is_feasible']:
            return False
        if not left['is_feasible'] and not right['is_feasible']:
            return left['violation_score'] < right['violation_score'] - 1e-12

        left_values = left['objective_tuple']
        right_values = right['objective_tuple']
        return all(left_value <= right_value + 1e-12 for left_value, right_value in zip(left_values, right_values)) and any(
            left_value < right_value - 1e-12 for left_value, right_value in zip(left_values, right_values)
        )

    @staticmethod
    def assign_crowding_distance(front: List[int], evaluated: List[Dict]):
        if not front:
            return
        for index in front:
            evaluated[index]['crowding_distance'] = 0.0

        objective_count = len(evaluated[front[0]]['objective_tuple'])
        if len(front) <= 2:
            for index in front:
                evaluated[index]['crowding_distance'] = float('inf')
            return

        for objective_index in range(objective_count):
            sorted_front = sorted(front, key=lambda index: evaluated[index]['objective_tuple'][objective_index])
            evaluated[sorted_front[0]]['crowding_distance'] = float('inf')
            evaluated[sorted_front[-1]]['crowding_distance'] = float('inf')
            min_value = evaluated[sorted_front[0]]['objective_tuple'][objective_index]
            max_value = evaluated[sorted_front[-1]]['objective_tuple'][objective_index]
            if abs(max_value - min_value) <= 1e-12:
                continue

            for position in range(1, len(sorted_front) - 1):
                previous_value = evaluated[sorted_front[position - 1]]['objective_tuple'][objective_index]
                next_value = evaluated[sorted_front[position + 1]]['objective_tuple'][objective_index]
                evaluated[sorted_front[position]]['crowding_distance'] += (next_value - previous_value) / (max_value - min_value)


class OptimizedSmartBlendingAlgorithm:
    """喷煤工艺导向的混煤优化算法。"""

    OBJECTIVE_TYPE = 'pci_pareto_nsga2_v1'
    OBJECTIVE_ALIASES = {
        '喷煤性价比最优': '多目标Pareto最优',
        '最低成本': '多目标Pareto最优',
        '最高性价比': '多目标Pareto最优',
        '多目标Pareto最优': '多目标Pareto最优',
    }

    def __init__(self):
        self.optimizer = ImprovedGeneticOptimizer()
        self.logger = logging.getLogger(__name__)

    def normalize_optimization_target(self, optimization_target: Optional[str]) -> str:
        target = optimization_target or '喷煤性价比最优'
        if target == '最佳性能':
            raise ValueError('当前版本仅支持多目标Pareto最优')
        if target not in self.OBJECTIVE_ALIASES:
            raise ValueError(f'不支持的优化目标: {target}')
        return self.OBJECTIVE_ALIASES[target]

    def calculate(self, coals, params, optimization_target='喷煤性价比最优'):
        """计算喷煤工艺下的最优混煤配比。"""
        if not coals or len(coals) < 2:
            raise ValueError('至少需要2种煤进行混合')
        if not params:
            raise ValueError('请提供混煤参数')

        canonical_target = self.normalize_optimization_target(optimization_target)

        required_fields = [
            'name',
            'price',
            'calorific_value',
            'ash_content',
            'volatile_matter',
            'fixed_carbon',
            'total_sulfur',
        ]
        for index, coal in enumerate(coals):
            for field in required_fields:
                if field not in coal:
                    raise ValueError(f'煤种 {index + 1} 缺少必需字段: {field}')

        n_coals = len(coals)
        coal_names = [coal.get('name', f'煤种{index + 1}') for index, coal in enumerate(coals)]

        prices = np.asarray([coal.get('price', 0.0) for coal in coals], dtype=float)
        heat_values = np.asarray([coal.get('calorific_value', 0.0) for coal in coals], dtype=float)
        ash_contents = np.asarray([coal.get('ash_content', 0.0) for coal in coals], dtype=float)
        volatile_matters = np.asarray([coal.get('volatile_matter', 0.0) for coal in coals], dtype=float)
        fixed_carbons = np.asarray([coal.get('fixed_carbon', 0.0) for coal in coals], dtype=float)
        sulfur_contents = np.asarray([coal.get('total_sulfur', 0.0) for coal in coals], dtype=float)

        ratio_limits = self._build_ratio_limits(params, n_coals)

        metric_vectors = {
            'heat': heat_values,
            'ash': ash_contents,
            'volatile': volatile_matters,
            'fixed_carbon': fixed_carbons,
            'sulfur': sulfur_contents,
            'price': prices,
        }

        feasible_seed = self._solve_min_cost_feasible_seed(
            prices=prices,
            metric_vectors=metric_vectors,
            params=params,
            ratio_limits=ratio_limits,
        )
        if not feasible_seed['success']:
            return {
                'status': 'no_feasible_solution',
                'message': feasible_seed['message'],
                'coal_results': [],
                'summary': {
                    'objective_type': self.OBJECTIVE_TYPE,
                    'optimization_target': canonical_target,
                    'fitness_score': float('inf'),
                    'generations_used': 0,
                    'is_feasible': False,
                    'violation_score': None,
                    'constraint_violations': feasible_seed['constraint_violations'],
                    'active_constraints': [],
                    'diagnosis': feasible_seed['diagnosis'],
                },
            }

        seed_ratios = feasible_seed['ratios']

        def objective_function(individual):
            evaluation = self._evaluate_solution(
                ratios=individual,
                coal_names=coal_names,
                prices=prices,
                heat_values=heat_values,
                ash_contents=ash_contents,
                volatile_matters=volatile_matters,
                fixed_carbons=fixed_carbons,
                sulfur_contents=sulfur_contents,
                params=params,
            )
            quality_penalty = self._calculate_quality_penalty(evaluation, params)
            evaluation['quality_penalty'] = quality_penalty
            evaluation['objective_values'] = {
                'cost': evaluation['total_price'],
                'heat': evaluation['total_heat'],
                'quality_penalty': quality_penalty,
            }
            evaluation['objective_tuple'] = (
                evaluation['total_price'],
                -evaluation['total_heat'],
                quality_penalty,
            )
            evaluation['fitness'] = quality_penalty if evaluation['is_feasible'] else evaluation['fitness']
            return evaluation

        nsga_optimizer = NSGA2BlendingOptimizer(self.optimizer)
        pareto_items = nsga_optimizer.optimize(
            objective_function,
            n_coals=n_coals,
            ratio_limits=ratio_limits,
            seed_individual=seed_ratios,
        )

        if not pareto_items:
            return {
                'status': 'search_failed',
                'message': '可行域存在，但NSGA-II未能生成Pareto可行解',
                'coal_results': [],
                'summary': {
                    'objective_type': self.OBJECTIVE_TYPE,
                    'optimization_target': canonical_target,
                    'fitness_score': float('inf'),
                    'generations_used': nsga_optimizer.generations_used,
                    'is_feasible': False,
                    'violation_score': None,
                    'constraint_violations': [],
                    'active_constraints': [],
                    'diagnosis': ['NSGA-II未返回任何可行候选解'],
                },
            }

        pareto_solutions = self._build_pareto_solutions(
            pareto_items=pareto_items,
            coal_names=coal_names,
        )
        if not pareto_solutions:
            return {
                'status': 'search_failed',
                'message': '可行域存在，但Pareto前沿中没有满足约束的候选方案',
                'coal_results': [],
                'summary': {
                    'objective_type': self.OBJECTIVE_TYPE,
                    'optimization_target': canonical_target,
                    'fitness_score': float('inf'),
                    'generations_used': nsga_optimizer.generations_used,
                    'is_feasible': False,
                    'violation_score': None,
                    'constraint_violations': [],
                    'active_constraints': [],
                    'diagnosis': ['请放宽约束或增加候选煤种后重试'],
                },
            }

        recommended_solution = self._choose_recommended_solution(pareto_solutions)
        final_ratios = recommended_solution['optimal_ratios']
        final_evaluation = next(
            item for item in pareto_items
            if tuple(round(value, 8) for value in item['ratios']) == tuple(round(value, 8) for value in final_ratios)
        )

        coal_results = self._build_coal_results(coals, final_ratios, prices, heat_values, ash_contents, volatile_matters, fixed_carbons, sulfur_contents)

        summary = {
            'objective_type': self.OBJECTIVE_TYPE,
            'optimization_target': canonical_target,
            'total_price': final_evaluation['total_price'],
            'total_heat': final_evaluation['total_heat'],
            'total_ash': final_evaluation['total_ash'],
            'total_volatile': final_evaluation['total_volatile'],
            'total_fixed_carbon': final_evaluation['total_fixed_carbon'],
            'total_sulfur': final_evaluation['total_sulfur'],
            'performance_price_ratio': final_evaluation['performance_price_ratio'],
            'fitness_score': recommended_solution['quality_penalty'],
            'generations_used': nsga_optimizer.generations_used,
            'is_feasible': True,
            'violation_score': 0.0,
            'constraint_violations': [],
            'active_constraints': final_evaluation['active_constraints'],
            'diagnosis': feasible_seed['diagnosis'] + ['NSGA-II已生成多目标Pareto候选方案'],
            'quality_penalty': recommended_solution['quality_penalty'],
            'objective_values': recommended_solution['objective_values'],
            'recommended_solution': recommended_solution,
            'pareto_solutions': pareto_solutions,
        }

        return {
            'status': 'success',
            'message': '多目标Pareto优化完成',
            'coal_results': coal_results,
            'summary': summary,
        }

    def _build_pareto_solutions(self, pareto_items: List[Dict], coal_names: List[str]) -> List[Dict]:
        sorted_items = sorted(
            [item for item in pareto_items if item.get('is_feasible')],
            key=lambda item: (
                item['total_price'],
                -item['total_heat'],
                item['quality_penalty'],
            ),
        )
        max_solutions = int(self.optimizer.config.get('pareto_solution_limit', 20))
        solutions = []
        for index, item in enumerate(sorted_items[:max_solutions], start=1):
            ratios = [float(value) for value in item['ratios']]
            solutions.append({
                'solution_id': f'pareto_{index:03d}',
                'rank': int(item.get('rank', 1)),
                'crowding_distance': self._safe_float(item.get('crowding_distance', 0.0)),
                'coal_names': coal_names,
                'optimal_ratios': ratios,
                'blending_ratio': {
                    coal_name: ratios[coal_index]
                    for coal_index, coal_name in enumerate(coal_names)
                },
                'total_price': item['total_price'],
                'total_heat': item['total_heat'],
                'total_ash': item['total_ash'],
                'total_volatile': item['total_volatile'],
                'total_fixed_carbon': item['total_fixed_carbon'],
                'total_sulfur': item['total_sulfur'],
                'performance_price_ratio': item['performance_price_ratio'],
                'quality_penalty': item['quality_penalty'],
                'objective_values': item['objective_values'],
                'is_feasible': True,
                'violation_score': 0.0,
                'constraint_violations': [],
                'active_constraints': item.get('active_constraints', []),
            })
        return solutions

    def _build_coal_results(
        self,
        coals,
        ratios,
        prices,
        heat_values,
        ash_contents,
        volatile_matters,
        fixed_carbons,
        sulfur_contents,
    ) -> List[Dict]:
        coal_results = []
        for index, coal in enumerate(coals):
            ratio_percent = ratios[index] * 100.0
            if ratio_percent < 0.1:
                continue

            coal_results.append({
                'name': coal.get('name', f'煤种{index + 1}'),
                'ratio': ratio_percent,
                'price_contribution': float(ratios[index] * prices[index]),
                'heat_contribution': float(ratios[index] * heat_values[index]),
                'ash_contribution': float(ratios[index] * ash_contents[index]),
                'volatile_contribution': float(ratios[index] * volatile_matters[index]),
                'fixed_carbon_contribution': float(ratios[index] * fixed_carbons[index]),
                'sulfur_contribution': float(ratios[index] * sulfur_contents[index]),
            })

        coal_results.sort(key=lambda item: item['ratio'], reverse=True)
        return coal_results

    def _choose_recommended_solution(self, pareto_solutions: List[Dict]) -> Dict:
        if len(pareto_solutions) == 1:
            return pareto_solutions[0]

        cost_values = [solution['objective_values']['cost'] for solution in pareto_solutions]
        heat_values = [solution['objective_values']['heat'] for solution in pareto_solutions]
        quality_values = [solution['objective_values']['quality_penalty'] for solution in pareto_solutions]
        cost_min, cost_max = min(cost_values), max(cost_values)
        heat_min, heat_max = min(heat_values), max(heat_values)
        quality_min, quality_max = min(quality_values), max(quality_values)

        def normalize_min(value, min_value, max_value):
            return 0.0 if abs(max_value - min_value) <= 1e-12 else (value - min_value) / (max_value - min_value)

        def normalize_max(value, min_value, max_value):
            return 0.0 if abs(max_value - min_value) <= 1e-12 else (max_value - value) / (max_value - min_value)

        def ideal_distance(solution):
            cost_distance = normalize_min(solution['objective_values']['cost'], cost_min, cost_max)
            heat_distance = normalize_max(solution['objective_values']['heat'], heat_min, heat_max)
            quality_distance = normalize_min(solution['objective_values']['quality_penalty'], quality_min, quality_max)
            return (cost_distance ** 2 + heat_distance ** 2 + quality_distance ** 2) ** 0.5

        return min(pareto_solutions, key=lambda solution: (ideal_distance(solution), solution['total_price']))

    def _calculate_quality_penalty(self, evaluation: Dict, params: Dict) -> float:
        ash_penalty = self._normalize_low_is_better(evaluation['total_ash'], params.get('ash_min'), params.get('ash_limit'))
        sulfur_penalty = self._normalize_low_is_better(evaluation['total_sulfur'], params.get('sulfur_min'), params.get('sulfur_limit'))
        volatile_penalty = self._normalize_midpoint_deviation(
            evaluation['total_volatile'],
            params.get('volatile_min'),
            params.get('volatile_max'),
        )
        fixed_carbon_penalty = self._normalize_midpoint_deviation(
            evaluation['total_fixed_carbon'],
            params.get('fixed_carbon_min'),
            params.get('fixed_carbon_max'),
        )
        return float((ash_penalty + sulfur_penalty + volatile_penalty + fixed_carbon_penalty) / 4.0)

    @staticmethod
    def _normalize_low_is_better(value, min_value, max_value) -> float:
        if min_value is None or max_value is None:
            return 0.0
        min_value = float(min_value)
        max_value = float(max_value)
        span = max(max_value - min_value, 1e-9)
        return float(max(0.0, min(1.0, (float(value) - min_value) / span)))

    @staticmethod
    def _normalize_midpoint_deviation(value, min_value, max_value) -> float:
        if min_value is None or max_value is None:
            return 0.0
        min_value = float(min_value)
        max_value = float(max_value)
        midpoint = (min_value + max_value) / 2.0
        half_span = max((max_value - min_value) / 2.0, 1e-9)
        return float(max(0.0, min(1.0, abs(float(value) - midpoint) / half_span)))

    @staticmethod
    def _safe_float(value) -> float:
        value = float(value)
        if np.isfinite(value):
            return value
        return 1e9

    def _build_ratio_limits(self, params: Dict, n_coals: int) -> Dict:
        if 'ratio_constraints' in params:
            ratio_constraints = params['ratio_constraints']
            min_limits = ratio_constraints.get('min', [0.0] * n_coals)
            max_limits = ratio_constraints.get('max', [1.0] * n_coals)
        elif params.get('use_ratio_constraint', False):
            min_ratio = params.get('min_single_ratio', 5) / 100.0
            max_ratio = params.get('max_single_ratio', 60) / 100.0
            min_limits = [min_ratio] * n_coals
            max_limits = [max_ratio] * n_coals
        else:
            min_limits = [0.0] * n_coals
            max_limits = [1.0] * n_coals

        ratio_limits = {
            'min': [float(value) for value in min_limits],
            'max': [float(value) for value in max_limits],
        }

        if len(ratio_limits['min']) != n_coals or len(ratio_limits['max']) != n_coals:
            raise ValueError('配比约束数量与选中煤种数量不一致')

        total_min = sum(ratio_limits['min'])
        total_max = sum(ratio_limits['max'])
        if total_min > 1.0 + 1e-9 or total_max < 1.0 - 1e-9:
            raise ValueError('配比上下限无法组成100%的混煤方案')

        return ratio_limits

    def _solve_min_cost_feasible_seed(
        self,
        prices: np.ndarray,
        metric_vectors: Dict[str, np.ndarray],
        params: Dict,
        ratio_limits: Dict,
    ) -> Dict:
        bounds = list(zip(ratio_limits['min'], ratio_limits['max']))
        A_ub, b_ub, constraint_specs = self._build_linear_constraints(metric_vectors, params)
        A_eq = [np.ones(len(prices))]
        b_eq = [1.0]

        result = linprog(
            c=prices,
            A_ub=A_ub if A_ub else None,
            b_ub=b_ub if b_ub else None,
            A_eq=A_eq,
            b_eq=b_eq,
            bounds=bounds,
            method='highs',
        )

        if result.success and result.x is not None:
            repaired = self.optimizer.repair_individual(result.x.tolist(), ratio_limits, result.x.tolist())
            if repaired is not None:
                return {
                    'success': True,
                    'ratios': repaired,
                    'message': '已找到满足约束的可行解',
                    'constraint_violations': [],
                    'diagnosis': ['线性可行性预检查通过，并生成了最低成本可行 seed'],
                }

        diagnosis = self._diagnose_infeasibility(metric_vectors, params, ratio_limits)
        return {
            'success': False,
            'ratios': None,
            'message': '当前约束与所选煤种组合下不存在可行混煤方案',
            'constraint_violations': diagnosis['violations'],
            'diagnosis': diagnosis['messages'],
        }

    def _build_linear_constraints(self, metric_vectors: Dict[str, np.ndarray], params: Dict):
        specs = [
            ('heat_min', 'heat', '>='),
            ('heat_max', 'heat', '<='),
            ('ash_min', 'ash', '>='),
            ('ash_limit', 'ash', '<='),
            ('volatile_min', 'volatile', '>='),
            ('volatile_max', 'volatile', '<='),
            ('fixed_carbon_min', 'fixed_carbon', '>='),
            ('fixed_carbon_max', 'fixed_carbon', '<='),
            ('sulfur_min', 'sulfur', '>='),
            ('sulfur_limit', 'sulfur', '<='),
            ('price_min', 'price', '>='),
            ('price_limit', 'price', '<='),
        ]

        A_ub = []
        b_ub = []
        used_specs = []

        for param_key, metric_key, operator in specs:
            if param_key not in params or params[param_key] is None:
                continue

            limit_value = float(params[param_key])
            coefficients = np.asarray(metric_vectors[metric_key], dtype=float)
            if operator == '>=':
                A_ub.append((-coefficients).tolist())
                b_ub.append(-limit_value)
            else:
                A_ub.append(coefficients.tolist())
                b_ub.append(limit_value)
            used_specs.append((param_key, metric_key, operator, limit_value))

        return A_ub, b_ub, used_specs

    def _diagnose_infeasibility(self, metric_vectors: Dict[str, np.ndarray], params: Dict, ratio_limits: Dict) -> Dict:
        messages = []
        violations = []

        total_min = sum(ratio_limits['min'])
        total_max = sum(ratio_limits['max'])
        if total_min > 1.0 + 1e-9:
            messages.append('单煤种配比下限总和超过100%，无法满足总配比约束')
            violations.append({'label': '总配比下限', 'detail': f'下限总和为 {total_min * 100:.2f}%'})
        if total_max < 1.0 - 1e-9:
            messages.append('单煤种配比上限总和不足100%，无法满足总配比约束')
            violations.append({'label': '总配比上限', 'detail': f'上限总和为 {total_max * 100:.2f}%'})

        grouped_specs = {
            'heat': [('heat_min', 'heat', '>='), ('heat_max', 'heat', '<=')],
            'ash': [('ash_min', 'ash', '>='), ('ash_limit', 'ash', '<=')],
            'volatile': [('volatile_min', 'volatile', '>='), ('volatile_max', 'volatile', '<=')],
            'fixed_carbon': [('fixed_carbon_min', 'fixed_carbon', '>='), ('fixed_carbon_max', 'fixed_carbon', '<=')],
            'sulfur': [('sulfur_min', 'sulfur', '>='), ('sulfur_limit', 'sulfur', '<=')],
            'price': [('price_min', 'price', '>='), ('price_limit', 'price', '<=')],
        }

        for label, specs in grouped_specs.items():
            reduced_params = params.copy()
            removed_any = False
            for param_key, _, _ in specs:
                if param_key in reduced_params:
                    removed_any = True
                    reduced_params.pop(param_key, None)
            if not removed_any:
                continue

            A_ub, b_ub, _ = self._build_linear_constraints(metric_vectors, reduced_params)
            result = linprog(
                c=np.zeros(len(metric_vectors['price'])),
                A_ub=A_ub if A_ub else None,
                b_ub=b_ub if b_ub else None,
                A_eq=[np.ones(len(metric_vectors['price']))],
                b_eq=[1.0],
                bounds=list(zip(ratio_limits['min'], ratio_limits['max'])),
                method='highs',
            )
            if result.success:
                messages.append(f'{label}约束与当前煤种集合或其他约束存在冲突')
                violations.append({'label': f'{label}约束', 'detail': '移除此类约束后可恢复可行域'})

        if not messages:
            messages.append('当前煤种集合在既定质量约束和配比约束下不存在可行解')

        return {'messages': messages, 'violations': violations}

    def _evaluate_solution(
        self,
        ratios,
        coal_names,
        prices,
        heat_values,
        ash_contents,
        volatile_matters,
        fixed_carbons,
        sulfur_contents,
        params,
    ) -> Dict:
        ratios_array = np.asarray(ratios, dtype=float)

        total_price = float(np.sum(ratios_array * prices))
        total_heat = float(np.sum(ratios_array * heat_values))
        total_ash = float(np.sum(ratios_array * ash_contents))
        total_volatile = float(np.sum(ratios_array * volatile_matters))
        total_fixed_carbon = float(np.sum(ratios_array * fixed_carbons))
        total_sulfur = float(np.sum(ratios_array * sulfur_contents))
        performance_price_ratio = (
            total_heat / (total_price * (1 + total_ash / 100.0))
            if total_price > 0
            else 0.0
        )

        constraint_checks = []
        self._append_range_constraint(constraint_checks, '热值下限', total_heat, params.get('heat_min'), '>=')
        self._append_range_constraint(constraint_checks, '热值上限', total_heat, params.get('heat_max'), '<=')
        self._append_range_constraint(constraint_checks, '灰分下限', total_ash, params.get('ash_min'), '>=')
        self._append_range_constraint(constraint_checks, '灰分上限', total_ash, params.get('ash_limit'), '<=')
        self._append_range_constraint(constraint_checks, '挥发分下限', total_volatile, params.get('volatile_min'), '>=')
        self._append_range_constraint(constraint_checks, '挥发分上限', total_volatile, params.get('volatile_max'), '<=')
        self._append_range_constraint(constraint_checks, '固定碳下限', total_fixed_carbon, params.get('fixed_carbon_min'), '>=')
        self._append_range_constraint(constraint_checks, '固定碳上限', total_fixed_carbon, params.get('fixed_carbon_max'), '<=')
        self._append_range_constraint(constraint_checks, '全硫下限', total_sulfur, params.get('sulfur_min'), '>=')
        self._append_range_constraint(constraint_checks, '全硫上限', total_sulfur, params.get('sulfur_limit'), '<=')
        self._append_range_constraint(constraint_checks, '成本下限', total_price, params.get('price_min'), '>=')
        self._append_range_constraint(constraint_checks, '成本上限', total_price, params.get('price_limit'), '<=')

        ratio_limits = params.get('ratio_constraints', {})
        min_limits = ratio_limits.get('min', [0.0] * len(ratios_array))
        max_limits = ratio_limits.get('max', [1.0] * len(ratios_array))
        for index, coal_name in enumerate(coal_names):
            self._append_range_constraint(
                constraint_checks,
                f'{coal_name}配比下限',
                float(ratios_array[index]),
                min_limits[index] if index < len(min_limits) else 0.0,
                '>=',
                percentage=True,
            )
            self._append_range_constraint(
                constraint_checks,
                f'{coal_name}配比上限',
                float(ratios_array[index]),
                max_limits[index] if index < len(max_limits) else 1.0,
                '<=',
                percentage=True,
            )

        self._append_range_constraint(
            constraint_checks,
            '总配比',
            float(ratios_array.sum()),
            1.0,
            '==',
            percentage=True,
        )

        violations = [item for item in constraint_checks if not item['satisfied']]
        active_constraints = [item['label'] for item in constraint_checks if item['satisfied'] and item['active']]
        violation_score = float(sum(item['relative_gap'] for item in violations))
        is_feasible = len(violations) == 0

        if is_feasible:
            fitness = total_price
        else:
            infeasible_base = 1_000_000.0
            penalty_factor = float(self.optimizer.config.get('constraint_penalty_factor', 1000.0))
            fitness = infeasible_base + penalty_factor * violation_score

        return {
            'fitness': float(fitness),
            'is_feasible': is_feasible,
            'violation_score': violation_score,
            'constraint_violations': violations,
            'active_constraints': active_constraints,
            'total_price': total_price,
            'total_heat': total_heat,
            'total_ash': total_ash,
            'total_volatile': total_volatile,
            'total_fixed_carbon': total_fixed_carbon,
            'total_sulfur': total_sulfur,
            'performance_price_ratio': float(performance_price_ratio),
        }

    def _append_range_constraint(
        self,
        checks: List[Dict],
        label: str,
        actual: float,
        expected: Optional[float],
        operator: str,
        percentage: bool = False,
    ):
        if expected is None:
            return

        expected = float(expected)
        tolerance = max(1e-8, abs(expected) * 1e-6)

        if operator == '>=':
            gap = max(expected - actual, 0.0)
            satisfied = actual >= expected - tolerance
            active = expected > 0 and satisfied and abs(actual - expected) <= tolerance
        elif operator == '<=':
            gap = max(actual - expected, 0.0)
            satisfied = actual <= expected + tolerance
            active = satisfied and abs(actual - expected) <= tolerance
        else:
            gap = abs(actual - expected)
            satisfied = abs(actual - expected) <= tolerance
            active = satisfied

        scale = max(abs(expected), 1.0)
        relative_gap = gap / scale
        unit = '%' if percentage else ''

        checks.append({
            'label': label,
            'actual': actual,
            'expected': expected,
            'operator': operator,
            'unit': unit,
            'satisfied': satisfied,
            'active': active,
            'gap': gap,
            'relative_gap': relative_gap,
            'message': self._format_constraint_message(label, actual, expected, operator, unit),
        })

    @staticmethod
    def _format_constraint_message(label: str, actual: float, expected: float, operator: str, unit: str) -> str:
        if operator == '>=':
            return f'{label}: {actual:.4f}{unit} < {expected:.4f}{unit}'
        if operator == '<=':
            return f'{label}: {actual:.4f}{unit} > {expected:.4f}{unit}'
        return f'{label}: {actual:.4f}{unit} != {expected:.4f}{unit}'

    def set_optimizer_config(self, config: Dict):
        """设置优化器配置。"""
        self.optimizer = ImprovedGeneticOptimizer(config)
