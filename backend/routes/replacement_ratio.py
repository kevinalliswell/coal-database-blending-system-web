#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Blueprint, request, jsonify
import logging

from app.utils.validation import validate_replacement_ratio_params
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

@replacement_ratio_bp.route('/calculate_theory_ratio', methods=['POST'])
def calculate_theory_ratio():
    """理论置换比计算API"""
    try:
        data = request.json
        if not data:
            return jsonify({'status': 'error', 'message': '请求数据为空'}), 400
        
        # 验证参数
        is_valid, errors = validate_replacement_ratio_params(data)
        if not is_valid:
            return jsonify({'status': 'error', 'message': '; '.join(errors)}), 400
        
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
            hot_blast_enthalpy=blast_furnace_params_data.get('hot_blast_enthalpy', 1.5)
        )
        
        # 创建计算器并执行计算
        calculator = ReplacementRatioCalculator(coal_params, coke_params, blast_furnace_params)
        ratio, details = calculator.calculate_displacement_ratio()
        
        # 获取额外的热量平衡数据
        carbon_burning_heat = calculator.calculate_carbon_burning_heat()
        hydrogen_saving_carbon = calculator.calculate_hydrogen_saving_carbon_percentage()
        decomposition_consumption = calculator.calculate_carbon_consumed_by_decomposition()
        
        # 格式化结果
        result = {
            'status': 'success',
            'ratio': ratio,
            'details': details,
            'carbon_burning_heat': carbon_burning_heat,
            'hydrogen_saving_carbon': hydrogen_saving_carbon,
            'decomposition_heat_consumption': decomposition_consumption * carbon_burning_heat / 4.184,  # 转换为kcal/kg
            'physical_heat_consumption': coal_params.physical_heat,
            'hydrogen_replacement_heat': 62222  # kJ/kg，氢气参加直接还原替代的热量
        }
        
        logger.info(f"理论置换比计算成功: {ratio:.6f}")
        return jsonify(result)
        
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
        
        logger.info(f"实际置换比计算成功: {ratio:.6f} ({'高级' if enable_advanced else '基本'}模式)")
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"实际置换比计算失败: {str(e)}")
        return jsonify({'status': 'error', 'message': f'计算失败: {str(e)}'}), 500

@replacement_ratio_bp.route('/replacement_ratio/history', methods=['GET'])
def get_replacement_ratio_history():
    """获取置换比计算历史记录API"""
    try:
        # 这里可以从数据库或文件中读取历史记录
        # 目前返回空列表，实际应用中可以实现持久化存储
        history = []
        return jsonify({'status': 'success', 'data': history})
    except Exception as e:
        logger.error(f"获取置换比计算历史失败: {str(e)}")
        return jsonify({'status': 'error', 'message': f'获取历史记录失败: {str(e)}'}), 500 
