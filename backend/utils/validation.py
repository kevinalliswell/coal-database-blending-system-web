#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import math

import pandas as pd

from backend.utils.coal_basis import CLOSURE_TOLERANCE, validate_assay_basis

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
    if all(value is not None for value in proximate) and sum(proximate) > 100 + (CLOSURE_TOLERANCE if data.get("analysis_basis") in ("ad", "ar", "d") else 1e-6):
        errors.append('灰分、挥发分、固定碳总和不能超过100%')
    if not errors:
        errors.extend(validate_assay_basis(data))
    return not errors, errors


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
