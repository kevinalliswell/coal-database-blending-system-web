#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import os
from datetime import datetime

from flask import Blueprint, jsonify, request

from app.config import Config
from app.services.blending_service import OptimizedSmartBlendingAlgorithm
from app.utils.file_utils import safe_read_csv
from app.utils.validation import validate_optimization_params

logger = logging.getLogger(__name__)

optimization_bp = Blueprint('optimization', __name__)


def _build_algorithm_params(constraints, selected_coal_ids):
    ratio_constraints_data = constraints.get('ratio_constraints', {})
    ratio_min_list = []
    ratio_max_list = []

    for coal_id in selected_coal_ids:
        coal_constraint = ratio_constraints_data.get(str(coal_id), {})
        ratio_min_list.append(float(coal_constraint.get('min', 5)) / 100.0)
        ratio_max_list.append(float(coal_constraint.get('max', 80)) / 100.0)

    return {
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
            'max': ratio_max_list,
        },
    }


def _build_ga_config(ga_params):
    return {
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
        'parallel_computing': ga_params.get('parallel_computing', True),
        'diversity_factor': ga_params.get('diversity_factor', 0.1),
    }


def _build_api_result(coal_names, algorithm_result, time_taken):
    summary = algorithm_result.get('summary', {})
    coal_results = algorithm_result.get('coal_results', [])
    ratio_map = {item['name']: item['ratio'] / 100.0 for item in coal_results}

    optimal_ratios = [ratio_map.get(coal_name, 0.0) for coal_name in coal_names]
    timestamp = datetime.now().isoformat()

    result_payload = {
        'objective_type': summary.get('objective_type', OptimizedSmartBlendingAlgorithm.OBJECTIVE_TYPE),
        'optimization_target': summary.get('optimization_target', '喷煤性价比最优'),
        'coal_names': coal_names,
        'optimal_ratios': optimal_ratios,
        'blending_ratio': {name: ratio for name, ratio in zip(coal_names, optimal_ratios)},
        'total_price': summary.get('total_price'),
        'total_heat': summary.get('total_heat'),
        'total_ash': summary.get('total_ash'),
        'total_volatile': summary.get('total_volatile'),
        'total_fixed_carbon': summary.get('total_fixed_carbon'),
        'total_sulfur': summary.get('total_sulfur'),
        'performance_price_ratio': summary.get('performance_price_ratio', 0.0),
        'iterations': int(summary.get('generations_used', 0)),
        'time_taken': float(time_taken),
        'fitness_value': summary.get('fitness_score'),
        'is_feasible': bool(summary.get('is_feasible', False)),
        'constraints_satisfied': bool(summary.get('is_feasible', False)),
        'constraint_violations': summary.get('constraint_violations', []),
        'violation_score': summary.get('violation_score'),
        'active_constraints': summary.get('active_constraints', []),
        'diagnosis': summary.get('diagnosis', []),
        'timestamp': timestamp,
    }

    return {
        'status': algorithm_result.get('status', 'success'),
        'message': algorithm_result.get('message', '优化计算完成'),
        'result': result_payload,
    }


@optimization_bp.route('/optimization', methods=['POST'])
def run_optimization():
    """执行喷煤工艺混煤优化。"""
    try:
        data = request.json
        if not data:
            return jsonify({'status': 'error', 'message': '请求数据为空'}), 400

        is_valid, errors = validate_optimization_params(data)
        if not is_valid:
            return jsonify({'status': 'error', 'message': '; '.join(errors)}), 400

        optimization_target = data.get('optimization_target', '喷煤性价比最优')
        selected_coal_ids = data.get('selected_coal_ids', [])
        constraints = data.get('constraints', {})
        ga_params = data.get('ga_params', {})

        logger.info('收到优化请求')
        logger.info('  优化目标: %s', optimization_target)
        logger.info('  选中煤种ID: %s', selected_coal_ids)
        logger.info('  约束条件: %s', constraints)
        logger.info('  遗传算法参数: %s', ga_params)

        df = safe_read_csv(Config.COAL_DATA_PATH)
        selected_coals = df[df['序号'].isin(selected_coal_ids)]
        if len(selected_coals) < 2:
            return jsonify({'status': 'error', 'message': '请至少选择两种煤进行混配'}), 400

        coal_names = selected_coals['煤种名称'].tolist()
        coals = []
        for _, row in selected_coals.iterrows():
            coals.append({
                'name': row['煤种名称'],
                'price': float(row['价格(元/吨)']),
                'calorific_value': float(row['热值(kcal/kg)']),
                'ash_content': float(row['灰分(%)']),
                'volatile_matter': float(row['挥发分(%)']),
                'fixed_carbon': float(row['固定碳(%)']),
                'total_sulfur': float(row['全硫(%)']),
            })

        params = _build_algorithm_params(constraints, selected_coal_ids)
        ga_config = _build_ga_config(ga_params)

        algorithm = OptimizedSmartBlendingAlgorithm()
        algorithm.set_optimizer_config(ga_config)

        start_time = datetime.now()
        algorithm_result = algorithm.calculate(
            coals=coals,
            params=params,
            optimization_target=optimization_target,
        )
        end_time = datetime.now()

        time_taken = (end_time - start_time).total_seconds()
        payload = _build_api_result(coal_names, algorithm_result, time_taken)

        if payload['status'] == 'success':
            history_file = os.path.join(
                Config.HISTORY_DIR,
                f"optimization_{datetime.now().strftime('%Y%m%d%H%M%S')}.json",
            )
            with open(history_file, 'w', encoding='utf-8') as file:
                json.dump(payload, file, ensure_ascii=False, indent=2)

        return jsonify(payload)

    except ValueError as exc:
        logger.error('优化计算参数错误: %s', exc)
        return jsonify({'status': 'error', 'message': str(exc)}), 400
    except Exception as exc:
        logger.exception('优化计算失败')
        return jsonify({'status': 'error', 'message': f'优化计算失败: {exc}'}), 500


@optimization_bp.route('/optimization/history', methods=['GET'])
def get_optimization_history():
    """获取优化历史记录。"""
    try:
        history_files = [name for name in os.listdir(Config.HISTORY_DIR) if name.endswith('.json')]
        history_files.sort(reverse=True)

        history_list = []
        for filename in history_files:
            file_path = os.path.join(Config.HISTORY_DIR, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    history_data = json.load(file)

                result = history_data.get('result', {})
                timestamp = filename.replace('optimization_', '').replace('.json', '')
                date_obj = datetime.strptime(timestamp, '%Y%m%d%H%M%S')
                formatted_date = date_obj.strftime('%Y-%m-%d %H:%M:%S')

                history_list.append({
                    'id': timestamp,
                    'date': formatted_date,
                    'coal_names': result.get('coal_names', []),
                    'optimal_ratios': result.get('optimal_ratios', []),
                    'total_price': result.get('total_price'),
                    'total_heat': result.get('total_heat'),
                    'objective_type': result.get('objective_type'),
                    'is_feasible': result.get(
                        'is_feasible',
                        result.get('constraints_satisfied', False),
                    ),
                })
            except Exception as exc:
                logger.error('读取历史记录文件 %s 失败: %s', filename, exc)

        return jsonify({'status': 'success', 'data': history_list})
    except Exception as exc:
        logger.error('获取优化历史记录失败: %s', exc)
        return jsonify({'status': 'error', 'message': f'获取优化历史记录失败: {exc}'}), 500


@optimization_bp.route('/optimization/history/<history_id>', methods=['GET'])
def get_optimization_history_detail(history_id):
    """获取特定优化历史记录详情。"""
    try:
        history_file = os.path.join(Config.HISTORY_DIR, f'optimization_{history_id}.json')
        if not os.path.exists(history_file):
            return jsonify({'status': 'error', 'message': '历史记录不存在'}), 404

        with open(history_file, 'r', encoding='utf-8') as file:
            history_data = json.load(file)

        return jsonify({'status': 'success', 'data': history_data})
    except Exception as exc:
        logger.error('获取优化历史记录详情失败: %s', exc)
        return jsonify({'status': 'error', 'message': f'获取优化历史记录详情失败: {exc}'}), 500
