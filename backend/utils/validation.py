#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging

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
    """验证煤种数据的完整性和合理性。"""
    errors = []

    required_fields = [
        'name',
        'type',
        'price',
        'calorific_value',
        'ash_content',
        'volatile_matter',
        'fixed_carbon',
        'total_sulfur',
    ]
    for field in required_fields:
        if field not in data or data[field] in (None, ''):
            errors.append(f'缺少必需字段: {field}')

    if errors:
        return False, errors

    try:
        price = float(data['price'])
        if price <= 0:
            errors.append('价格必须大于0')
        elif price > 2000:
            errors.append('价格过高，请检查数据')

        calorific_value = float(data['calorific_value'])
        if calorific_value < 3000 or calorific_value > 8000:
            errors.append('热值范围应在3000-8000 kcal/kg之间')

        ash_content = float(data['ash_content'])
        if ash_content < 0 or ash_content > 50:
            errors.append('灰分含量应在0-50%之间')

        volatile_matter = float(data['volatile_matter'])
        if volatile_matter < 0 or volatile_matter > 50:
            errors.append('挥发分含量应在0-50%之间')

        fixed_carbon = float(data['fixed_carbon'])
        if fixed_carbon < 0 or fixed_carbon > 100:
            errors.append('固定碳含量应在0-100%之间')

        total_sulfur = float(data['total_sulfur'])
        if total_sulfur < 0 or total_sulfur > 5:
            errors.append('全硫含量应在0-5%之间')

        total_components = ash_content + volatile_matter + fixed_carbon
        if total_components < 90 or total_components > 110:
            errors.append('灰分、挥发分、固定碳总和应接近100%')

    except ValueError:
        errors.append('数值格式错误')

    return len(errors) == 0, errors


def validate_optimization_params(data):
    """兼容校验接口；路由使用同一规范化函数的已验证结果。"""
    from backend.utils.optimization_validation import normalize_optimization_request

    try:
        normalize_optimization_request(data)
    except ValueError as exc:
        return False, [str(exc)]
    return True, []


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
