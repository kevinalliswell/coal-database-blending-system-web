#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def generate_blending_report_filename(data: dict) -> str:
    """
    根据优化结果数据生成统一格式的报告文件名。

    文件名格式: 智能混煤方案_{配比方案}_{时间戳}.xlsx
    示例: 智能混煤方案_山西45_昊华35_神华20_2024-05-21-143000.xlsx

    Args:
        data (dict): 包含优化结果的字典。
                     需要包含 'blending_ratio' 和 'timestamp' 等键。

    Returns:
        str: 生成的文件名。
    """
    try:
        # 1. 提取配比方案
        # 兼容历史数据和当前数据
        ratio_info = data.get('blending_ratio', {})
        if not ratio_info and 'result' in data:
            ratio_info = data.get('result', {}).get('blending_ratio', {})

        if ratio_info:
            # 格式: 煤种名+配比(整数)
            scheme_parts = [f"{name}-{ratio * 100:.2f}%" for name, ratio in ratio_info.items() if ratio > 0]
            scheme_str = "_".join(scheme_parts)
        else:
            scheme_str = "自定义方案"

    except Exception as e:
        logger.warning(f"从数据中提取配比方案失败，将使用默认名称: {e}")
        scheme_str = "通用方案"

    # 2. 提取并格式化时间戳
    try:
        # 优先从数据中获取时间戳，如果获取不到则使用当前时间
        ts_str = data.get('timestamp', datetime.now().isoformat())
        
        # 尝试解析两种可能的时间格式
        if '.' in ts_str:
            dt_obj = datetime.fromisoformat(ts_str.split('.')[0])
        else:
            dt_obj = datetime.fromisoformat(ts_str)
            
        timestamp = dt_obj.strftime('%Y-%m-%d-%H%M%S')
    except (ValueError, TypeError) as e:
        logger.warning(f"解析时间戳失败({ts_str})，将使用当前时间: {e}")
        timestamp = datetime.now().strftime('%Y-%m-%d-%H%M%S')

    # 3. 组合文件名
    return f"智能混煤方案_{scheme_str}_{timestamp}.xlsx" 