import numpy as np
import random
import time
from typing import List, Dict, Tuple, Optional
import logging
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import os
from functools import lru_cache


class ImprovedGeneticOptimizer:
    """改进的遗传算法优化器"""
    
    def __init__(self, config: Dict = None):
        """初始化遗传算法参数"""
        default_config = {
            'population_size': 300,
            'max_generations': 2000,
            'mutation_rate': 0.15,
            'crossover_rate': 0.85,
            'tournament_size': 7,
            'elite_ratio': 0.1,
            'early_stopping_patience': 150,
            'convergence_threshold': 1e-8,
            'parallel_workers': min(4, os.cpu_count()),
            'adaptive_mutation': True,
            'constraint_penalty_factor': 1000.0,
            'diversity_factor': 0.1  # 新增：多样性保持因子
        }
        
        self.config = {**default_config, **(config or {})}
        self._ensure_config_types()
        
        self.fitness_history = []
        self.best_fitness = float('inf')
        self.stagnation_count = 0
        self.generation_count = 0
        self.logger = logging.getLogger(__name__)
    
    def _ensure_config_types(self):
        """确保配置参数的数据类型正确"""
        try:
            for key in ['population_size', 'max_generations', 'tournament_size', 
                       'early_stopping_patience', 'parallel_workers']:
                self.config[key] = int(self.config[key])
            
            for key in ['mutation_rate', 'crossover_rate', 'elite_ratio', 
                       'convergence_threshold', 'constraint_penalty_factor', 'diversity_factor']:
                self.config[key] = float(self.config[key])
                
            if isinstance(self.config.get('adaptive_mutation'), str):
                self.config['adaptive_mutation'] = self.config['adaptive_mutation'].lower() in ('true', '1', 'yes')
                
        except (ValueError, TypeError, KeyError) as e:
            self.logger.warning(f"配置类型转换失败: {e}，使用默认值")
    
    def create_individual(self, n_coals: int, ratio_limits: Dict = None) -> List[float]:
        """创建一个有效的个体（支持上下限约束）"""
        max_attempts = 100
        
        # 处理配比约束
        min_limits = ratio_limits.get('min', [0.0] * n_coals) if ratio_limits else [0.0] * n_coals
        max_limits = ratio_limits.get('max', [1.0] * n_coals) if ratio_limits else [1.0] * n_coals
        
        for attempt in range(max_attempts):
            # 生成满足下限的初始配比
            individual = []
            for i in range(n_coals):
                min_val = min_limits[i]
                max_val = max_limits[i]
                if min_val > max_val:
                    min_val, max_val = max_val, min_val
                individual.append(random.uniform(min_val, max_val))
            
            # 归一化到满足约束
            individual = self.normalize_with_constraints(individual, ratio_limits)
            
            # 验证约束
            if self._validate_constraints(individual, ratio_limits):
                return individual
        
        # 如果无法生成有效个体，使用安全策略
        return self._create_safe_individual(n_coals, ratio_limits)
    
    def _create_safe_individual(self, n_coals: int, ratio_limits: Dict = None) -> List[float]:
        """创建一个安全的个体（确保满足所有约束）"""
        min_limits = ratio_limits.get('min', [0.0] * n_coals) if ratio_limits else [0.0] * n_coals
        max_limits = ratio_limits.get('max', [1.0] * n_coals) if ratio_limits else [1.0] * n_coals
        
        # 检查约束的可行性
        total_min = sum(min_limits)
        total_max = sum(max_limits)
        
        if total_min > 1.0:
            # 下限总和超过1，按比例缩放
            scale_factor = 0.95 / total_min
            individual = [limit * scale_factor for limit in min_limits]
        elif total_max < 1.0:
            # 上限总和小于1，使用上限值并归一化
            individual = max_limits.copy()
        else:
            # 使用下限作为基础，分配剩余部分
            remaining = 1.0 - total_min
            available_capacity = [max_limits[i] - min_limits[i] for i in range(n_coals)]
            total_capacity = sum(available_capacity)
            
            individual = min_limits.copy()
            if total_capacity > 0:
                for i in range(n_coals):
                    additional = remaining * (available_capacity[i] / total_capacity)
                    individual[i] += additional
        
        return self.normalize_with_constraints(individual, ratio_limits)
    
    def _validate_constraints(self, individual: List[float], ratio_limits: Dict = None) -> bool:
        """验证个体是否满足所有约束"""
        if not ratio_limits:
            return abs(sum(individual) - 1.0) < 1e-6
        
        min_limits = ratio_limits.get('min', [0.0] * len(individual))
        max_limits = ratio_limits.get('max', [1.0] * len(individual))
        
        for i, value in enumerate(individual):
            if value < min_limits[i] - 1e-6 or value > max_limits[i] + 1e-6:
                return False
        
        return abs(sum(individual) - 1.0) < 1e-6
    
    def normalize_with_constraints(self, individual: List[float], ratio_limits: Dict = None) -> List[float]:
        """改进的约束归一化方法（支持上下限）"""
        if not ratio_limits:
            total = sum(individual)
            return [x / total for x in individual] if total > 0 else [1.0/len(individual)] * len(individual)
        
        min_limits = ratio_limits.get('min', [0.0] * len(individual))
        max_limits = ratio_limits.get('max', [1.0] * len(individual))
        
        # 确保在约束范围内
        for i in range(len(individual)):
            individual[i] = max(min_limits[i], min(individual[i], max_limits[i]))
        
        # 多轮迭代调整
        for iteration in range(10):  # 最多10轮调整
            current_sum = sum(individual)
            target_sum = 1.0
            
            if abs(current_sum - target_sum) < 1e-6:
                break
            
            if current_sum < target_sum:
                # 需要增加配比
                shortage = target_sum - current_sum
                available_indices = [i for i in range(len(individual)) 
                                   if individual[i] < max_limits[i]]
                
                if available_indices:
                    available_capacity = sum(max_limits[i] - individual[i] for i in available_indices)
                    if available_capacity > 0:
                        for i in available_indices:
                            capacity = max_limits[i] - individual[i]
                            addition = shortage * (capacity / available_capacity)
                            individual[i] += min(addition, capacity)
            else:
                # 需要减少配比
                excess = current_sum - target_sum
                reducible_indices = [i for i in range(len(individual)) 
                                   if individual[i] > min_limits[i]]
                
                if reducible_indices:
                    reducible_capacity = sum(individual[i] - min_limits[i] for i in reducible_indices)
                    if reducible_capacity > 0:
                        for i in reducible_indices:
                            capacity = individual[i] - min_limits[i]
                            reduction = excess * (capacity / reducible_capacity)
                            individual[i] -= min(reduction, capacity)
        
        # 最终归一化
        final_sum = sum(individual)
        if final_sum > 0:
            individual = [x / final_sum for x in individual]
        
        return individual
    
    def crossover(self, parent1: List[float], parent2: List[float], 
                  ratio_limits: Dict = None) -> Tuple[List[float], List[float]]:
        """改进的交叉操作"""
        n = len(parent1)
        
        # 多种交叉策略
        crossover_type = random.choice(['multi_point', 'uniform', 'arithmetic'])
        
        if crossover_type == 'multi_point':
            # 多点交叉
            num_points = min(3, n-1)
            if num_points > 0:
                crossover_points = sorted(random.sample(range(1, n), num_points))
                child1, child2 = parent1.copy(), parent2.copy()
                
                for i in range(len(crossover_points)):
                    start = crossover_points[i-1] if i > 0 else 0
                    end = crossover_points[i]
                    
                    if i % 2 == 1:
                        child1[start:end], child2[start:end] = child2[start:end], child1[start:end]
            else:
                child1, child2 = parent1.copy(), parent2.copy()
                
        elif crossover_type == 'uniform':
            # 均匀交叉
            child1, child2 = [], []
            for i in range(n):
                if random.random() < 0.5:
                    child1.append(parent1[i])
                    child2.append(parent2[i])
                else:
                    child1.append(parent2[i])
                    child2.append(parent1[i])
                    
        else:  # arithmetic
            # 算术交叉
            alpha = random.random()
            child1 = [alpha * p1 + (1 - alpha) * p2 for p1, p2 in zip(parent1, parent2)]
            child2 = [(1 - alpha) * p1 + alpha * p2 for p1, p2 in zip(parent1, parent2)]
        
        # 归一化并应用约束
        child1 = self.normalize_with_constraints(child1, ratio_limits)
        child2 = self.normalize_with_constraints(child2, ratio_limits)
        
        return child1, child2
    
    def mutate(self, individual: List[float], ratio_limits: Dict = None) -> List[float]:
        """改进的变异操作"""
        result = individual.copy()
        n = len(result)
        
        # 自适应变异率
        if self.config['adaptive_mutation']:
            base_rate = self.config['mutation_rate']
            if self.stagnation_count > 50:
                current_mutation_rate = min(base_rate * 2.0, 0.5)
            elif self.stagnation_count > 20:
                current_mutation_rate = base_rate * 1.5
            else:
                current_mutation_rate = base_rate
        else:
            current_mutation_rate = self.config['mutation_rate']
        
        # 多种变异策略
        mutation_strategies = ['gaussian', 'uniform', 'swap', 'boundary']
        strategy = random.choice(mutation_strategies)
        
        min_limits = ratio_limits.get('min', [0.0] * n) if ratio_limits else [0.0] * n
        max_limits = ratio_limits.get('max', [1.0] * n) if ratio_limits else [1.0] * n
        
        if strategy == 'gaussian':
            # 高斯变异
            sigma = 0.1 * (1 - self.generation_count / self.config['max_generations'])
            for i in range(n):
                if random.random() < current_mutation_rate:
                    noise = random.gauss(0, sigma)
                    result[i] = max(min_limits[i], min(result[i] + noise, max_limits[i]))
                    
        elif strategy == 'uniform':
            # 均匀变异
            for i in range(n):
                if random.random() < current_mutation_rate:
                    result[i] = random.uniform(min_limits[i], max_limits[i])
                    
        elif strategy == 'swap' and n > 1:
            # 交换变异
            if random.random() < current_mutation_rate:
                i, j = random.sample(range(n), 2)
                # 检查交换后是否仍满足约束
                temp_i, temp_j = result[j], result[i]
                if (min_limits[i] <= temp_i <= max_limits[i] and 
                    min_limits[j] <= temp_j <= max_limits[j]):
                    result[i], result[j] = temp_i, temp_j
                    
        else:  # boundary
            # 边界变异
            for i in range(n):
                if random.random() < current_mutation_rate:
                    if random.random() < 0.5:
                        result[i] = min_limits[i]
                    else:
                        result[i] = max_limits[i]
        
        return self.normalize_with_constraints(result, ratio_limits)
    
    def optimize(self, fitness_func, n_coals: int, ratio_limits: Dict = None,
                progress_callback=None, log_callback=None) -> Tuple[List[float], float]:
        """主优化函数"""
        self.fitness_history = []
        self.best_fitness = float('inf')
        self.stagnation_count = 0
        
        # 初始化种群
        population = [self.create_individual(n_coals, ratio_limits) 
                     for _ in range(self.config['population_size'])]
        
        best_individual = None
        
        for generation in range(self.config['max_generations']):
            self.generation_count = generation
            
            # 评估适应度
            fitness_scores = self.evaluate_population_parallel(population, fitness_func)
            
            # 更新最佳解
            gen_best_idx = np.argmin(fitness_scores)
            gen_best_fitness = fitness_scores[gen_best_idx]
            
            if gen_best_fitness < self.best_fitness:
                self.best_fitness = gen_best_fitness
                best_individual = population[gen_best_idx].copy()
                self.stagnation_count = 0
            else:
                self.stagnation_count += 1
            
            self.fitness_history.append(self.best_fitness)
            
            # 日志输出
            if log_callback and generation % 50 == 0:
                log_callback(f"第 {generation} 代: 最佳适应度 = {self.best_fitness:.6f}")
            
            # 进度更新
            if progress_callback:
                progress_callback(int((generation + 1) / self.config['max_generations'] * 100))
            
            # 早停检查
            if self.check_early_stopping():
                if log_callback:
                    log_callback(f"第 {generation} 代达到收敛条件，提前停止")
                break
            
            # 创建新一代
            new_population = []
            
            # 精英保留
            elite_size = int(self.config['elite_ratio'] * self.config['population_size'])
            elite_indices = np.argsort(fitness_scores)[:elite_size]
            for idx in elite_indices:
                new_population.append(population[idx].copy())
            
            # 生成剩余个体
            while len(new_population) < self.config['population_size']:
                # 选择父代
                parent1 = self.tournament_selection(population, fitness_scores)
                parent2 = self.tournament_selection(population, fitness_scores)
                
                # 交叉
                if random.random() < self.config['crossover_rate']:
                    child1, child2 = self.crossover(parent1, parent2, ratio_limits)
                else:
                    child1, child2 = parent1.copy(), parent2.copy()
                
                # 变异
                child1 = self.mutate(child1, ratio_limits)
                child2 = self.mutate(child2, ratio_limits)
                
                new_population.extend([child1, child2])
            
            # 截断到指定大小
            population = new_population[:self.config['population_size']]
        
        if log_callback:
            log_callback(f"优化完成，最终适应度: {self.best_fitness:.6f}")
        
        return best_individual, self.best_fitness
    
    def tournament_selection(self, population: List[List[float]], 
                           fitness_scores: List[float]) -> List[float]:
        """锦标赛选择"""
        tournament_size = min(self.config['tournament_size'], len(population))
        tournament_indices = random.sample(range(len(population)), tournament_size)
        
        best_idx = min(tournament_indices, key=lambda i: fitness_scores[i])
        return population[best_idx].copy()
    
    def evaluate_population_parallel(self, population: List[List[float]], 
                                   fitness_func) -> List[float]:
        """并行评估种群适应度"""
        parallel_workers = int(self.config.get('parallel_workers', 1))
        
        if parallel_workers <= 1 or len(population) < 10:
            return [fitness_func(individual) for individual in population]
        
        try:
            max_workers = min(parallel_workers, len(population), 4)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                fitness_scores = list(executor.map(fitness_func, population))
            return fitness_scores
        except Exception as e:
            self.logger.warning(f"并行计算失败，转为串行计算: {e}")
            return [fitness_func(individual) for individual in population]
    
    def check_early_stopping(self) -> bool:
        """检查早停条件"""
        patience = int(self.config.get('early_stopping_patience', 150))
        threshold = float(self.config.get('convergence_threshold', 1e-8))
        
        if len(self.fitness_history) < patience:
            return False
        
        recent_history = self.fitness_history[-patience:]
        improvement = abs(float(recent_history[0]) - float(recent_history[-1]))
        
        return improvement < threshold


class OptimizedSmartBlendingAlgorithm:
    """优化的智能混煤算法类"""
    
    def __init__(self):
        """初始化算法"""
        self.optimizer = ImprovedGeneticOptimizer()
        self.logger = logging.getLogger(__name__)
    
    def calculate(self, coals, params, optimization_target="最低成本"):
        """计算最优混煤配比
        
        参数:
            coals: 煤种数据列表，每个煤种包含：
                - name: 煤种名称
                - price: 价格 (元/吨)
                - calorific_value: 热值 (kcal/kg)
                - ash_content: 灰分 (%)
                - volatile_matter: 挥发分 (%)
                - fixed_carbon: 固定碳 (%)
                - total_sulfur: 硫含量 (%)
                
            params: 混煤参数字典，包含：
                - heat_value: 目标热值
                - heat_min, heat_max: 热值上下限
                - ash_limit: 灰分上限
                - ash_min: 灰分下限
                - volatile_min, volatile_max: 挥发分范围
                - fixed_carbon_min, fixed_carbon_max: 固定碳范围
                - sulfur_limit: 硫含量上限
                - sulfur_min: 硫含量下限
                - price_limit: 价格上限
                - price_min: 价格下限
                - ratio_constraints: 配比约束
                  - min: 下限列表
                  - max: 上限列表
                
            optimization_target: 优化目标
            
        返回:
            dict: 计算结果
        """
        # 检查输入
        if not coals or len(coals) < 2:
            raise ValueError("至少需要2种煤进行混合")
        
        if not params:
            raise ValueError("请提供混煤参数")
        
        # 验证煤种数据完整性
        required_fields = ['name', 'price', 'calorific_value', 'ash_content', 
                          'volatile_matter', 'fixed_carbon', 'total_sulfur']
        for i, coal in enumerate(coals):
            for field in required_fields:
                if field not in coal:
                    raise ValueError(f"煤种 {i+1} 缺少必需字段: {field}")
        
        # 提取关键参数
        n_coals = len(coals)
        
        # 提取煤种属性（移除氮含量）
        prices = np.array([coal.get('price', 0) for coal in coals])
        heat_values = np.array([coal.get('calorific_value', 0) for coal in coals])
        ash_contents = np.array([coal.get('ash_content', 0) for coal in coals])
        volatile_matters = np.array([coal.get('volatile_matter', 0) for coal in coals])
        fixed_carbons = np.array([coal.get('fixed_carbon', 0) for coal in coals])
        sulfur_contents = np.array([coal.get('total_sulfur', 0) for coal in coals])
        
        # 配比约束处理（支持上下限）
        ratio_limits = None
        if 'ratio_constraints' in params:
            ratio_limits = params['ratio_constraints']
        elif params.get('use_ratio_constraint', False):
            max_ratio = params.get('max_single_ratio', 60) / 100
            min_ratio = params.get('min_single_ratio', 5) / 100
            ratio_limits = {
                'min': [min_ratio] * n_coals,
                'max': [max_ratio] * n_coals
            }
        
        # 定义适应度函数
        def fitness_function(individual):
            return self._calculate_fitness(
                individual, prices, heat_values, ash_contents, volatile_matters,
                fixed_carbons, sulfur_contents, params, optimization_target
            )
        
        # 执行遗传算法优化
        try:
            optimal_ratios, best_fitness = self.optimizer.optimize(
                fitness_function, n_coals, ratio_limits
            )
            
            # 计算混煤属性（移除氮含量）
            total_price = np.sum(optimal_ratios * prices)
            total_heat = np.sum(optimal_ratios * heat_values)
            total_ash = np.sum(optimal_ratios * ash_contents)
            total_volatile = np.sum(optimal_ratios * volatile_matters)
            total_fixed_carbon = np.sum(optimal_ratios * fixed_carbons)
            total_sulfur = np.sum(optimal_ratios * sulfur_contents)
            
            # 计算性价比
            performance_price_ratio = total_heat / (total_price * (1 + total_ash/100)) if total_price > 0 else 0
            
            # 构建返回结果（移除氮含量）
            coal_results = []
            for i, coal in enumerate(coals):
                ratio = optimal_ratios[i] * 100  # 转为百分比
                if ratio < 0.1:  # 忽略微小比例
                    continue
                    
                coal_result = {
                    'name': coal.get('name', f'煤种{i+1}'),
                    'ratio': ratio,
                    'price_contribution': optimal_ratios[i] * prices[i],
                    'heat_contribution': optimal_ratios[i] * heat_values[i],
                    'ash_contribution': optimal_ratios[i] * ash_contents[i],
                    'volatile_contribution': optimal_ratios[i] * volatile_matters[i],
                    'fixed_carbon_contribution': optimal_ratios[i] * fixed_carbons[i],
                    'sulfur_contribution': optimal_ratios[i] * sulfur_contents[i]
                }
                coal_results.append(coal_result)
            
            # 排序结果（按比例降序）
            coal_results.sort(key=lambda x: x['ratio'], reverse=True)
            
            # 汇总信息（移除氮含量）
            summary = {
                'total_price': total_price,
                'total_heat': total_heat,
                'total_ash': total_ash,
                'total_volatile': total_volatile,
                'total_fixed_carbon': total_fixed_carbon,
                'total_sulfur': total_sulfur,
                'performance_price_ratio': performance_price_ratio,
                'optimization_target': optimization_target,
                'fitness_score': best_fitness,
                'generations_used': len(self.optimizer.fitness_history),
                'constraint_violations': self._check_constraint_violations(
                    total_price, total_heat, total_ash, total_volatile, 
                    total_fixed_carbon, total_sulfur, params
                )
            }
            
            return {'coal_results': coal_results, 'summary': summary}
            
        except Exception as e:
            self.logger.exception("遗传算法优化失败")
            raise ValueError(f"优化计算失败: {str(e)}")
    
    def _calculate_fitness(self, individual, prices, heat_values, ash_contents,
                          volatile_matters, fixed_carbons, sulfur_contents, 
                          params, optimization_target):
        """计算个体适应度（完全移除氮含量）"""
        # 计算实际值（移除氮含量）
        actual_price = np.sum(individual * prices)
        actual_heat = np.sum(individual * heat_values)
        actual_ash = np.sum(individual * ash_contents)
        actual_volatile = np.sum(individual * volatile_matters)
        actual_fixed_carbon = np.sum(individual * fixed_carbons)
        actual_sulfur = np.sum(individual * sulfur_contents)
        
        # 约束惩罚
        penalty = 0
        penalty_factor = self.optimizer.config['constraint_penalty_factor']
        
        # 热值约束
        if 'heat_value' in params:
            target_heat = params['heat_value']
            heat_deviation = abs(actual_heat - target_heat) / target_heat
            penalty += penalty_factor * heat_deviation
        
        if 'heat_min' in params and actual_heat < params['heat_min']:
            penalty += penalty_factor * (params['heat_min'] - actual_heat) / params['heat_min']
        
        if 'heat_max' in params and actual_heat > params['heat_max']:
            penalty += penalty_factor * (actual_heat - params['heat_max']) / params['heat_max']
        
        # 灰分约束
        if 'ash_limit' in params and actual_ash > params['ash_limit']:
            penalty += penalty_factor * (actual_ash - params['ash_limit']) / params['ash_limit']
        
        if 'ash_min' in params and actual_ash < params['ash_min']:
            penalty += penalty_factor * (params['ash_min'] - actual_ash) / params['ash_min']
        
        # 挥发分约束
        if 'volatile_min' in params and actual_volatile < params['volatile_min']:
            penalty += penalty_factor * (params['volatile_min'] - actual_volatile) / params['volatile_min']
        
        if 'volatile_max' in params and actual_volatile > params['volatile_max']:
            penalty += penalty_factor * (actual_volatile - params['volatile_max']) / params['volatile_max']
        
        # 固定碳约束
        if 'fixed_carbon_min' in params and actual_fixed_carbon < params['fixed_carbon_min']:
            penalty += penalty_factor * (params['fixed_carbon_min'] - actual_fixed_carbon) / params['fixed_carbon_min']
        
        if 'fixed_carbon_max' in params and actual_fixed_carbon > params['fixed_carbon_max']:
            penalty += penalty_factor * (actual_fixed_carbon - params['fixed_carbon_max']) / params['fixed_carbon_max']
        
        # 硫分约束
        if 'sulfur_limit' in params and actual_sulfur > params['sulfur_limit']:
            penalty += penalty_factor * (actual_sulfur - params['sulfur_limit']) / params['sulfur_limit']
        
        if 'sulfur_min' in params and actual_sulfur < params['sulfur_min']:
            penalty += penalty_factor * (params['sulfur_min'] - actual_sulfur) / params['sulfur_min']
        
        # 价格约束
        if 'price_limit' in params and actual_price > params['price_limit']:
            penalty += penalty_factor * (actual_price - params['price_limit']) / params['price_limit']
        
        if 'price_min' in params and actual_price < params['price_min']:
            penalty += penalty_factor * (params['price_min'] - actual_price) / params['price_min']
        
        # 基础目标函数
        if optimization_target == "最低成本":
            base_fitness = actual_price / 1000  # 归一化
        elif optimization_target == "最高性价比":
            if actual_price > 0:
                performance_ratio = actual_heat / (actual_price * (1 + actual_ash/100))
                base_fitness = -performance_ratio / 10  # 负号表示最大化
            else:
                base_fitness = float('inf')
        elif optimization_target == "最佳性能":
            # 综合性能指标（移除氮含量评分）
            heat_score = -actual_heat / 8000  # 热值越高越好
            ash_score = actual_ash / 15       # 灰分越低越好
            fixed_carbon_score = -actual_fixed_carbon / 80  # 固定碳越高越好
            sulfur_score = actual_sulfur / 1.5  # 硫分越低越好
            
            base_fitness = heat_score + ash_score + fixed_carbon_score + sulfur_score
        else:
            raise ValueError(f"不支持的优化目标: {optimization_target}")
        
        return base_fitness + penalty
    
    def _check_constraint_violations(self, price, heat, ash, volatile, fixed_carbon, 
                                   sulfur, params):
        """检查约束违反情况（完全移除氮含量）"""
        violations = []
        
        # 检查所有约束（不包括氮含量）
        constraints = [
            ('heat_min', heat, '热值下限'),
            ('heat_max', heat, '热值上限'),
            ('ash_limit', ash, '灰分上限'),
            ('ash_min', ash, '灰分下限'),
            ('volatile_min', volatile, '挥发分下限'),
            ('volatile_max', volatile, '挥发分上限'),
            ('fixed_carbon_min', fixed_carbon, '固定碳下限'),
            ('fixed_carbon_max', fixed_carbon, '固定碳上限'),
            ('sulfur_limit', sulfur, '硫含量上限'),
            ('sulfur_min', sulfur, '硫含量下限'),
            ('price_limit', price, '价格上限'),
            ('price_min', price, '价格下限')
        ]
        
        for param_name, actual_value, constraint_name in constraints:
            if param_name in params:
                limit_value = params[param_name]
                if 'min' in param_name and actual_value < limit_value:
                    violations.append(f"{constraint_name}: {actual_value:.2f} < {limit_value:.2f}")
                elif ('limit' in param_name or 'max' in param_name) and actual_value > limit_value:
                    violations.append(f"{constraint_name}: {actual_value:.2f} > {limit_value:.2f}")
        
        return violations
    
    def set_optimizer_config(self, config: Dict):
        """设置优化器配置"""
        self.optimizer = ImprovedGeneticOptimizer(config) 