#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import pandas as pd
from flask import Blueprint, request, jsonify
from datetime import datetime
import logging

from app.config import Config
from app.utils.file_utils import safe_read_csv
from app.utils.validation import validate_optimization_params
from app.services.blending_service import OptimizedSmartBlendingAlgorithm

logger = logging.getLogger(__name__)

# 创建优化计算蓝图
optimization_bp = Blueprint('optimization', __name__)

@optimization_bp.route('/optimization', methods=['POST'])
def run_optimization():
    """执行优化计算"""
    try:
        # 获取请求数据
        data = request.json
        if not data:
            return jsonify({'status': 'error', 'message': '请求数据为空'}), 400
        
        # 验证参数
        is_valid, errors = validate_optimization_params(data)
        if not is_valid:
            return jsonify({'status': 'error', 'message': '; '.join(errors)}), 400
        
        # 提取参数
        optimization_target = data.get('optimization_target', '最低成本')
        selected_coal_ids = data.get('selected_coal_ids', [])
        constraints = data.get('constraints', {})
        ga_params = data.get('ga_params', {})
        
        # 调试日志
        logger.info(f"收到优化请求:")
        logger.info(f"  优化目标: {optimization_target}")
        logger.info(f"  选中煤种ID: {selected_coal_ids}")
        logger.info(f"  约束条件: {constraints}")
        logger.info(f"  遗传算法参数: {ga_params}")
        
        # 读取煤种数据
        df = safe_read_csv(Config.COAL_DATA_PATH)
        
        # 筛选选中的煤种
        selected_coals = df[df['序号'].isin(selected_coal_ids)]
        if len(selected_coals) < 2:
            return jsonify({'status': 'error', 'message': '请至少选择两种煤进行混配'}), 400
        
        # 准备算法输入数据
        coal_names = selected_coals['煤种名称'].tolist()
        prices = selected_coals['价格(元/吨)'].values
        heat_values = selected_coals['热值(kcal/kg)'].values
        ash_contents = selected_coals['灰分(%)'].values
        volatile_matters = selected_coals['挥发分(%)'].values
        fixed_carbons = selected_coals['固定碳(%)'].values
        sulfur_contents = selected_coals['全硫(%)'].values
        
        # 处理配比约束
        ratio_constraints_data = constraints.get('ratio_constraints', {})
        ratio_min_list = []
        ratio_max_list = []
        
        # 从前端配比约束数据中提取每种煤的配比限制
        for coal_id in selected_coal_ids:
            if str(coal_id) in ratio_constraints_data:
                coal_constraint = ratio_constraints_data[str(coal_id)]
                ratio_min_list.append(coal_constraint.get('min', 5) / 100.0)  # 转换为小数
                ratio_max_list.append(coal_constraint.get('max', 80) / 100.0)  # 转换为小数
            else:
                # 使用默认值
                ratio_min_list.append(0.05)  # 5%
                ratio_max_list.append(0.80)  # 80%
        
        # 准备约束条件
        params = {
            'heat_value': constraints.get('heat_target', 6000),
            'heat_min': constraints.get('heat_min', 5800),
            'heat_max': constraints.get('heat_max', 6500),
            'ash_limit': constraints.get('ash_max', 18.0),
            'ash_min': constraints.get('ash_min', 8.0),
            'volatile_min': constraints.get('volatile_min', 15.0),
            'volatile_max': constraints.get('volatile_max', 35.0),
            'fixed_carbon_min': constraints.get('fixed_carbon_min', 55.0),
            'fixed_carbon_max': constraints.get('fixed_carbon_max', 75.0),
            'sulfur_limit': constraints.get('sulfur_max', 0.8),
            'sulfur_min': constraints.get('sulfur_min', 0.4),
            'price_limit': constraints.get('price_max', 800),
            'price_min': constraints.get('price_min', 450),
            'ratio_constraints': {
                'min': ratio_min_list,
                'max': ratio_max_list
            }
        }
        
        # 准备遗传算法参数
        ga_config = {
            'population_size': ga_params.get('population_size', 500),
            'max_generations': ga_params.get('max_generations', 3000),
            'mutation_rate': ga_params.get('mutation_rate', 0.2),
            'crossover_rate': ga_params.get('crossover_rate', 0.85),
            'tournament_size': ga_params.get('tournament_size', 7),
            'elite_ratio': ga_params.get('elite_ratio', 0.1),
            'early_stopping_patience': ga_params.get('early_stopping_patience', 200),
            'constraint_penalty_factor': ga_params.get('constraint_penalty_factor', 1500),
            'parallel_workers': ga_params.get('parallel_workers', 4),
            'adaptive_mutation': ga_params.get('adaptive_mutation', True),
            'diversity_factor': ga_params.get('diversity_factor', 0.1)
        }
        
        # 创建并运行遗传算法
        start_time = datetime.now()
        algorithm = OptimizedSmartBlendingAlgorithm()
        
        # 设置算法配置
        algorithm.set_optimizer_config(ga_config)
        
        # 准备煤种数据
        coals = []
        for i in range(len(coal_names)):
            coal = {
                'name': coal_names[i],
                'price': float(prices[i]),
                'calorific_value': float(heat_values[i]),
                'ash_content': float(ash_contents[i]),
                'volatile_matter': float(volatile_matters[i]),
                'fixed_carbon': float(fixed_carbons[i]),
                'total_sulfur': float(sulfur_contents[i])
            }
            coals.append(coal)
        
        # 运行优化算法
        logger.info(f"开始运行优化算法")
        logger.info(f"煤种数据: {coals}")
        logger.info(f"参数: {params}")
        
        result = algorithm.calculate(
            coals=coals,
            params=params,
            optimization_target=optimization_target
        )
        end_time = datetime.now()
        
        logger.info(f"算法执行完成，结果: {result}")
        
        # 计算耗时
        time_taken = (end_time - start_time).total_seconds()
        
        # 从算法结果中提取数据
        summary = result['summary']
        coal_results = result['coal_results']
        
        # 提取最优配比（按照煤种顺序）
        optimal_ratios = []
        actual_coal_names = []
        
        # 创建煤种名称到配比的映射
        ratio_map = {}
        for coal_result in coal_results:
            ratio_map[coal_result['name']] = coal_result['ratio'] / 100.0  # 转换为小数
        
        # 按照输入顺序提取配比
        for coal_name in coal_names:
            ratio = ratio_map.get(coal_name, 0.0)
            optimal_ratios.append(ratio)
            actual_coal_names.append(coal_name)
        
        # 准备返回结果
        optimization_result = {
            'status': 'success',
            'message': '优化计算完成',
            'result': {
                'coal_names': actual_coal_names,
                'optimal_ratios': optimal_ratios,
                'blending_ratio': {name: ratio for name, ratio in zip(actual_coal_names, optimal_ratios)},
                'total_price': float(summary['total_price']),
                'total_heat': float(summary['total_heat']),
                'total_ash': float(summary['total_ash']),
                'total_volatile': float(summary['total_volatile']),
                'total_fixed_carbon': float(summary['total_fixed_carbon']),
                'total_sulfur': float(summary['total_sulfur']),
                'performance_price_ratio': float(summary['performance_price_ratio']),
                'iterations': int(summary['generations_used']),
                'time_taken': time_taken,
                'fitness_value': float(summary['fitness_score']),
                'constraints_satisfied': len(summary.get('constraint_violations', [])) == 0
            }
        }
        
        # 保存结果到历史记录
        history_file = os.path.join(Config.HISTORY_DIR, f"optimization_{datetime.now().strftime('%Y%m%d%H%M%S')}.json")
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(optimization_result, f, ensure_ascii=False, indent=2)
        
        return jsonify(optimization_result)
    except Exception as e:
        logger.error(f"优化计算失败: {str(e)}")
        return jsonify({'status': 'error', 'message': f'优化计算失败: {str(e)}'}), 500

@optimization_bp.route('/optimization/history', methods=['GET'])
def get_optimization_history():
    """获取优化历史记录"""
    try:
        history_files = [f for f in os.listdir(Config.HISTORY_DIR) if f.endswith('.json')]
        history_files.sort(reverse=True)  # 按文件名倒序排列（最新的在前）
        
        history_list = []
        for file in history_files:
            file_path = os.path.join(Config.HISTORY_DIR, file)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    history_data = json.load(f)
                    # 提取关键信息
                    timestamp = file.replace('optimization_', '').replace('.json', '')
                    date_obj = datetime.strptime(timestamp, '%Y%m%d%H%M%S')
                    formatted_date = date_obj.strftime('%Y-%m-%d %H:%M:%S')
                    
                    history_item = {
                        'id': timestamp,
                        'date': formatted_date,
                        'coal_names': history_data['result']['coal_names'],
                        'optimal_ratios': history_data['result']['optimal_ratios'],
                        'total_price': history_data['result']['total_price'],
                        'total_heat': history_data['result']['total_heat'],
                        'performance_price_ratio': history_data['result']['performance_price_ratio']
                    }
                    history_list.append(history_item)
            except Exception as e:
                logger.error(f"读取历史记录文件 {file} 失败: {str(e)}")
        
        return jsonify({'status': 'success', 'data': history_list})
    except Exception as e:
        logger.error(f"获取优化历史记录失败: {str(e)}")
        return jsonify({'status': 'error', 'message': f'获取优化历史记录失败: {str(e)}'}), 500

@optimization_bp.route('/optimization/history/<history_id>', methods=['GET'])
def get_optimization_history_detail(history_id):
    """获取特定的优化历史记录详情"""
    try:
        history_file = os.path.join(Config.HISTORY_DIR, f"optimization_{history_id}.json")
        
        if not os.path.exists(history_file):
            return jsonify({'status': 'error', 'message': '历史记录不存在'}), 404
        
        with open(history_file, 'r', encoding='utf-8') as f:
            history_data = json.load(f)
        
        return jsonify({'status': 'success', 'data': history_data})
    except Exception as e:
        logger.error(f"获取优化历史记录详情失败: {str(e)}")
        return jsonify({'status': 'error', 'message': f'获取优化历史记录详情失败: {str(e)}'}), 500 
