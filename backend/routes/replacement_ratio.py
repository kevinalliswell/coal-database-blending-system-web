#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import math

from flask import Blueprint, request, jsonify

from app.extensions import db
from app.models import ReplacementRatioHistory
from backend.utils.replacement_validation import normalize_theory_request
from app.services.replacement_ratio_service import (
    ReplacementRatioCalculator,
    ActualReplacementRatioCalculator,
    CoalParameters,
    CokeParameters,
    BlastFurnaceParameters,
    ProductionData
)

logger = logging.getLogger(__name__)

# 创建置换比计算蓝图
replacement_ratio_bp = Blueprint('replacement_ratio', __name__)


def _sanitize_json_value(value):
    if isinstance(value, dict):
        return {key: _sanitize_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_json_value(item) for item in value]
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def _dump_json(payload):
    return json.dumps(_sanitize_json_value(payload), ensure_ascii=False, allow_nan=False)


def _safe_float(value, default=0.0):
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _format_percent_from_fraction(value):
    return f'{_safe_float(value) * 100:.2f}%'


def _build_theory_parameter_summary(data):
    coal_params = data.get('coal_params') or {}
    coke_params = data.get('coke_params') or {}
    blast_furnace_params = data.get('blast_furnace_params') or {}

    return (
        f"煤粉含碳 {_format_percent_from_fraction(coal_params.get('carbon_content'))}，"
        f"焦炭含碳 {_format_percent_from_fraction(coke_params.get('carbon_content'))}，"
        f"煤气利用率 {_safe_float(blast_furnace_params.get('eta_co')):.4f}"
    )


def _build_actual_parameter_summary(data, calculation_mode):
    production_data = data.get('production_data') or {}
    initial_coke = _safe_float(production_data.get('initial_coke_ratio'))
    final_coke = _safe_float(production_data.get('final_coke_ratio'))
    initial_coal = _safe_float(production_data.get('initial_coal_ratio'))
    final_coal = _safe_float(production_data.get('final_coal_ratio'))
    return (
        f"焦比 {initial_coke:.1f}->{final_coke:.1f} kg/t，"
        f"煤比 {initial_coal:.1f}->{final_coal:.1f} kg/t，"
        f"模式 {'高级实际' if calculation_mode == 'advanced' else '基础实际'}"
    )


def _save_replacement_ratio_history(request_data, response_payload, calculation_type, calculation_mode):
    parameter_summary = (
        _build_theory_parameter_summary(request_data)
        if calculation_type == 'theory'
        else _build_actual_parameter_summary(request_data, calculation_mode)
    )

    history = ReplacementRatioHistory(
        calculation_type=calculation_type,
        calculation_mode=calculation_mode,
        ratio_value=response_payload.get('ratio'),
        parameter_summary=parameter_summary,
        request_payload=_dump_json(request_data),
        result_payload=_dump_json(response_payload),
    )
    db.session.add(history)
    db.session.commit()

@replacement_ratio_bp.route('/calculate_theory_ratio', methods=['POST'])
def calculate_theory_ratio():
    """理论置换比计算API"""
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'status': 'error', 'message': '请求数据为空'}), 400
        
        # 验证参数
        data = normalize_theory_request(data)
        
        # 提取参数
        coal_params_data = data.get('coal_params', {})
        coke_params_data = data.get('coke_params', {})
        blast_furnace_params_data = data.get('blast_furnace_params', {})
        
        # 创建参数对象
        coal_params = CoalParameters(
            carbon_content=coal_params_data.get('carbon_content', 0.78),
            hydrogen_content=coal_params_data.get('hydrogen_content', 0.035),
            ash_content=coal_params_data.get('ash_content', 0.12),
            sio2_content=coal_params_data.get('sio2_content', 0.48),
            decomposition_heat=coal_params_data.get('decomposition_heat', 220.0),
            physical_heat=coal_params_data.get('physical_heat', 450.0)
        )
        
        coke_params = CokeParameters(
            carbon_content=coke_params_data.get('carbon_content', 0.86),
            ash_content=coke_params_data.get('ash_content', 0.11),
            sio2_content=coke_params_data.get('sio2_content', 0.52)
        )
        
        blast_furnace_params = BlastFurnaceParameters(
            eta_co=blast_furnace_params_data.get('eta_co', 0.4444),
            slag_basicity=blast_furnace_params_data.get('slag_basicity', 1.15),
            slag_enthalpy=blast_furnace_params_data.get('slag_enthalpy', 1800.0),
            wind_temperature=blast_furnace_params_data.get('wind_temperature', 1180.0),
            hot_blast_enthalpy=blast_furnace_params_data.get('hot_blast_enthalpy')
        )
        
        # 创建计算器并执行计算
        calculator = ReplacementRatioCalculator(coal_params, coke_params, blast_furnace_params)
        ratio, details = calculator.calculate_displacement_ratio()
        
        # 获取额外的热量平衡数据
        carbon_burning_heat = calculator.calculate_carbon_burning_heat()
        hydrogen_saving_carbon = calculator.calculate_hydrogen_saving_carbon_percentage()
        
        # 格式化结果
        result = {
            'status': 'success',
            'ratio': ratio,
            'details': details,
            'carbon_burning_heat': carbon_burning_heat,
            'hydrogen_saving_carbon': hydrogen_saving_carbon,
            'decomposition_heat_consumption': coal_params.decomposition_heat,  # kcal/kg
            'physical_heat_consumption': coal_params.physical_heat,
            'total_heat_consumption': coal_params.decomposition_heat + coal_params.physical_heat,
            'effective_hot_blast_enthalpy': calculator.effective_hot_blast_enthalpy(),  # kJ/m³
            'hot_blast_enthalpy_source': 'temperature_estimate' if blast_furnace_params.hot_blast_enthalpy is None else 'provided',
            'hydrogen_replacement_heat': 62222  # kJ/kg，氢气参加直接还原替代的热量
        }
        
        _save_replacement_ratio_history(data, result, 'theory', 'theory')
        logger.info(f"理论置换比计算成功: {ratio:.6f}")
        return jsonify(_sanitize_json_value(result))
        
    except ValueError as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
    except Exception as e:
        logger.error(f"理论置换比计算失败: {str(e)}")
        return jsonify({'status': 'error', 'message': f'计算失败: {str(e)}'}), 500

@replacement_ratio_bp.route('/calculate_actual_ratio', methods=['POST'])
def calculate_actual_ratio():
    """实际置换比计算API"""
    try:
        data = request.json
        if not data:
            return jsonify({'status': 'error', 'message': '请求数据为空'}), 400
        
        # 提取参数
        production_data_params = data.get('production_data', {})
        enable_advanced = data.get('enable_advanced', False)
        
        # 创建生产数据对象
        production_data = ProductionData(
            initial_coke_ratio=production_data_params.get('initial_coke_ratio', 400.0),
            final_coke_ratio=production_data_params.get('final_coke_ratio', 370.0),
            initial_coal_ratio=production_data_params.get('initial_coal_ratio', 150.0),
            final_coal_ratio=production_data_params.get('final_coal_ratio', 180.0),
            adjustment_factor=production_data_params.get('adjustment_factor', 2.5),
            iron_output_change=production_data_params.get('iron_output_change', 0.0),
            slag_ratio_change=production_data_params.get('slag_ratio_change', 0.0),
            carbon_efficiency_change=production_data_params.get('carbon_efficiency_change', 0.0)
        )
        
        # 创建计算器并执行计算
        calculator = ActualReplacementRatioCalculator()
        
        if enable_advanced:
            ratio, details = calculator.calculate_with_production_factors(production_data)
        else:
            ratio, details = calculator.calculate_basic_ratio(production_data)
        
        # 格式化结果
        result = {
            'status': 'success',
            'ratio': ratio,
            'details': details,
            'calculation_type': 'advanced' if enable_advanced else 'basic'
        }
        
        calculation_mode = 'advanced' if enable_advanced else 'basic'
        _save_replacement_ratio_history(data, result, 'actual', calculation_mode)
        logger.info(f"实际置换比计算成功: {ratio:.6f} ({'高级' if enable_advanced else '基本'}模式)")
        return jsonify(_sanitize_json_value(result))
        
    except Exception as e:
        logger.error(f"实际置换比计算失败: {str(e)}")
        return jsonify({'status': 'error', 'message': f'计算失败: {str(e)}'}), 500

@replacement_ratio_bp.route('/replacement_ratio/history', methods=['GET'])
def get_replacement_ratio_history():
    """获取置换比计算历史记录API"""
    try:
        history = [
            item.to_summary_dict()
            for item in ReplacementRatioHistory.query.order_by(ReplacementRatioHistory.created_at.desc()).all()
        ]
        return jsonify({'status': 'success', 'data': history})
    except Exception as e:
        logger.error(f"获取置换比计算历史失败: {str(e)}")
        return jsonify({'status': 'error', 'message': f'获取历史记录失败: {str(e)}'}), 500


@replacement_ratio_bp.route('/replacement_ratio/history/<int:history_id>', methods=['GET'])
def get_replacement_ratio_history_detail(history_id):
    """获取置换比计算历史详情API"""
    try:
        history = db.session.get(ReplacementRatioHistory, history_id)
        if history is None:
            return jsonify({'status': 'error', 'message': '历史记录不存在'}), 404

        return jsonify({'status': 'success', 'data': _sanitize_json_value(history.to_detail_dict())})
    except Exception as e:
        logger.error(f"获取置换比计算历史详情失败: {str(e)}")
        return jsonify({'status': 'error', 'message': f'获取历史详情失败: {str(e)}'}), 500
