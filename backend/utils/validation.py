#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import math

import pandas as pd

logger = logging.getLogger(__name__)


def safe_float(value, default=0):
    """安全转换为浮点数。"""
    try:
        if pd.isna(value) or value == '':
            return default
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value, default=0):
    """安全转换为整数。"""
    try:
        if pd.isna(value) or value == '':
            return default
        return int(value)
    except (ValueError, TypeError):
        return default


def validate_coal_data(data):
    """校验存储字段，不将缺少分析基准的数据视为已验证化验。"""
    if not isinstance(data, dict):
        return False, ['煤种数据必须为对象']
    errors = []
    for field in ('name', 'type'):
        if not isinstance(data.get(field), str) or not data[field].strip():
            errors.append(f'缺少必需字段: {field}')

    def number(field, label, lower, upper=None, required=False, positive=False):
        value = data.get(field)
        if value is None or value == '':
            if required:
                errors.append(f'缺少必需字段: {field}')
            return None
        try:
            if isinstance(value, bool):
                raise ValueError
            parsed = float(value)
            if not math.isfinite(parsed):
                raise ValueError
        except (ValueError, TypeError, OverflowError):
            errors.append(f'{label}必须为有限数值')
            return None
        if parsed < lower or (positive and parsed == lower) or (upper is not None and parsed > upper):
            errors.append(f'{label}超出允许范围')
        return parsed

    number('price', '价格', 0, 2000, required=True, positive=True)
    number('calorific_value', '热值', 3000, 8000, required=True)
    proximate = [
        number('ash_content', '灰分', 0, 50, required=True),
        number('volatile_matter', '挥发分', 0, 50, required=True),
        number('fixed_carbon', '固定碳', 0, 100, required=True),
    ]
    number('total_sulfur', '全硫', 0, 5, required=True)
    for field, label in (
        ('total_moisture', '全水分'), ('moisture', '全水分'),
        ('air_dry_moisture', '空干基水分'), ('mad', '空干基水分'),
        ('burnout_rate', '燃尽率'), ('carbon_content', '含碳量'),
        ('hydrogen_content', '含氢量'), ('nitrogen_content', '含氮量'),
    ):
        number(field, label, 0, 100)
    number('hgi', '可磨性 HGI', 0)

    # Unknown-basis records can be stored, but cannot certify moisture closure.
    # This upper bound prevents physically impossible solids totals without
    # assuming dry coal and rejecting valid as-received assays.
    if all(value is not None for value in proximate) and sum(proximate) > 100 + 1e-6:
        errors.append('灰分、挥发分、固定碳总和不能超过100%')
    return not errors, errors


def validate_optimization_params(data):
    """验证优化参数。"""
    errors = []
    supported_targets = {'喷煤性价比最优', '最低成本', '最高性价比', '多目标Pareto最优'}
    deprecated_targets = {'最佳性能'}

    def _validate_range(config, min_key, max_key, label):
        min_value = config.get(min_key)
        max_value = config.get(max_key)

        if min_value is None or max_value is None:
            return

        try:
            min_value = float(min_value)
            max_value = float(max_value)
        except (TypeError, ValueError):
            errors.append(f'{label}约束必须为数值')
            return

        if min_value >= max_value:
            errors.append(f'{label}最小值应小于最大值')

    selected_coal_ids = data.get('selected_coal_ids', [])
    if not selected_coal_ids:
        errors.append('请至少选择一种煤')
    elif len(selected_coal_ids) < 2:
        errors.append('请至少选择两种煤进行混配')

    optimization_target = data.get('optimization_target', '喷煤性价比最优')
    if optimization_target in deprecated_targets:
        errors.append('当前版本仅支持多目标Pareto最优，最佳性能模式已下线')
    elif optimization_target not in supported_targets:
        errors.append('不支持的优化目标，请使用多目标Pareto最优')

    constraints = data.get('constraints', {})
    _validate_range(constraints, 'heat_min', 'heat_max', '热值')
    _validate_range(constraints, 'ash_min', 'ash_max', '灰分')
    _validate_range(constraints, 'volatile_min', 'volatile_max', '挥发分')
    _validate_range(constraints, 'fixed_carbon_min', 'fixed_carbon_max', '固定碳')
    _validate_range(constraints, 'sulfur_min', 'sulfur_max', '全硫')
    _validate_range(constraints, 'price_min', 'price_max', '价格')

    heat_target = constraints.get('heat_target')
    heat_min = constraints.get('heat_min')
    heat_max = constraints.get('heat_max')
    if heat_target is not None and heat_min is not None and heat_max is not None:
        try:
            heat_target = float(heat_target)
            heat_min = float(heat_min)
            heat_max = float(heat_max)
            if not heat_min <= heat_target <= heat_max:
                errors.append('热值目标值应位于热值上下限之间')
        except (TypeError, ValueError):
            errors.append('热值目标值必须为数值')

    ratio_constraints = constraints.get('ratio_constraints', {})
    total_min_ratio = 0.0
    total_max_ratio = 0.0
    for coal_id, constraint in ratio_constraints.items():
        min_ratio = constraint.get('min', 5)
        max_ratio = constraint.get('max', 80)
        try:
            min_ratio = float(min_ratio)
            max_ratio = float(max_ratio)
        except (TypeError, ValueError):
            errors.append(f'煤种{coal_id}的配比约束必须为数值')
            continue

        if min_ratio >= max_ratio:
            errors.append(f'煤种{coal_id}的配比最小值应小于最大值')
        if min_ratio < 0 or max_ratio > 100:
            errors.append(f'煤种{coal_id}的配比应在0-100%之间')

        total_min_ratio += min_ratio
        total_max_ratio += max_ratio

    if ratio_constraints:
        if total_min_ratio > 100:
            errors.append('所选煤种配比下限总和不能超过100%')
        if total_max_ratio < 100:
            errors.append('所选煤种配比上限总和不能低于100%')

    ga_params = data.get('ga_params', {})
    if ga_params:
        numeric_rules = {
            'population_size': (1, None, '种群大小'),
            'max_generations': (1, None, '最大迭代次数'),
            'mutation_rate': (0, 1, '变异率'),
            'crossover_rate': (0, 1, '交叉率'),
            'tournament_size': (2, None, '锦标赛大小'),
            'elite_ratio': (0, 1, '精英比例'),
            'early_stopping_patience': (1, None, '早停耐心值'),
            'constraint_penalty_factor': (0, None, '约束惩罚因子'),
            'parallel_workers': (1, None, '并行工作线程'),
            'diversity_factor': (0, 1, '多样性因子'),
        }

        for key, (min_value, max_value, label) in numeric_rules.items():
            if key not in ga_params:
                continue

            try:
                value = float(ga_params[key])
            except (TypeError, ValueError):
                errors.append(f'{label}必须为数值')
                continue

            if min_value is not None and value < min_value:
                errors.append(f'{label}不能小于{min_value}')
            if max_value is not None and value > max_value:
                errors.append(f'{label}不能大于{max_value}')

        if 'tournament_size' in ga_params and 'population_size' in ga_params:
            try:
                tournament_size = int(ga_params['tournament_size'])
                population_size = int(ga_params['population_size'])
                if tournament_size > population_size:
                    errors.append('锦标赛大小不能大于种群大小')
            except (TypeError, ValueError):
                pass

    return len(errors) == 0, errors


def validate_replacement_ratio_params(data):
    """验证置换比计算参数。"""
    errors = []

    coal_params = data.get('coal_params', {})
    required_coal_params = ['carbon_content', 'hydrogen_content', 'ash_content']
    for param in required_coal_params:
        if param not in coal_params:
            errors.append(f'缺少煤参数: {param}')
        else:
            value = coal_params[param]
            if not isinstance(value, (int, float)) or value <= 0:
                errors.append(f'煤参数{param}必须是正数')

    coke_params = data.get('coke_params', {})
    required_coke_params = ['carbon_content', 'ash_content']
    for param in required_coke_params:
        if param not in coke_params:
            errors.append(f'缺少焦炭参数: {param}')
        else:
            value = coke_params[param]
            if not isinstance(value, (int, float)) or value <= 0:
                errors.append(f'焦炭参数{param}必须是正数')

    return len(errors) == 0, errors
