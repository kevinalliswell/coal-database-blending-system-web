#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import math
from copy import deepcopy
from datetime import datetime

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import OptimizationHistory
from app.services.blending_service import OptimizedSmartBlendingAlgorithm
from app.services.coal_basis_service import validate_blending_basis
from app.services.coal_data_service import coal_to_algorithm_dict, get_coals_by_ids
from backend.utils.optimization_validation import normalize_optimization_request

logger = logging.getLogger(__name__)

optimization_bp = Blueprint('optimization', __name__)


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


def _build_algorithm_params(constraints, selected_coal_ids):
    ratio_constraints_data = constraints.get('ratio_constraints', {})
    ratio_min_list = []
    ratio_max_list = []

    for coal_id in selected_coal_ids:
        coal_constraint = ratio_constraints_data.get(str(coal_id), {})
        ratio_min_list.append(float(coal_constraint.get('min', 0)) / 100.0)
        ratio_max_list.append(float(coal_constraint.get('max', 100)) / 100.0)

    return {
        'heat_min': constraints.get('heat_min', 6000),
        'heat_max': constraints.get('heat_max', 7800),
        'ash_limit': constraints.get('ash_max', 20.0),
        'ash_min': constraints.get('ash_min', 0.0),
        'volatile_min': constraints.get('volatile_min', 8.0),
        'volatile_max': constraints.get('volatile_max', 40.0),
        'fixed_carbon_min': constraints.get('fixed_carbon_min', 50.0),
        'fixed_carbon_max': constraints.get('fixed_carbon_max', 85.0),
        'sulfur_limit': constraints.get('sulfur_max', 1.2),
        'sulfur_min': constraints.get('sulfur_min', 0.0),
        'price_limit': constraints.get('price_max', 1500),
        'price_min': constraints.get('price_min', 0),
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
        'early_stopping_patience': ga_params.get('early_stopping_patience', 200),
        'adaptive_mutation': ga_params.get('adaptive_mutation', True),
        # NSGA-II uses NumPy kernels, not the legacy single-objective thread pool.
        'parallel_computing': False,
        'parallel_workers': 1,
        'random_seed': ga_params.get('random_seed'),
        'convergence_threshold': ga_params.get('convergence_threshold', 1e-6),
        'pareto_solution_limit': ga_params.get('pareto_solution_limit', 20),
    }


def _build_parameter_warnings(data):
    deprecated = {'elite_ratio', 'constraint_penalty_factor', 'parallel_workers',
                  'parallel_computing', 'diversity_factor'}
    ignored = sorted(deprecated.intersection(data.get('ga_params', {})))
    warnings = []
    if ignored:
        warnings.append('NSGA-II不使用以下已弃用参数: ' + ', '.join(ignored))
    if 'heat_target' in data.get('constraints', {}):
        warnings.append('heat_target已弃用，不参与优化；热值采用heat_min/heat_max约束')
    return warnings


def _build_input_snapshot(selected_coals, coals, params, ga_config):
    """Capture effective inputs before optimization or later coal edits can change them."""
    constraint_keys = {
        'heat_value': 'heat_target', 'ash_limit': 'ash_max',
        'sulfur_limit': 'sulfur_max', 'price_limit': 'price_max',
    }
    constraints = {
        constraint_keys.get(key, key): value
        for key, value in params.items() if key != 'ratio_constraints'
    }
    constraints['ratio_constraints'] = {
        str(coal.id): {'min': lower * 100, 'max': upper * 100}
        for coal, lower, upper in zip(selected_coals, params['ratio_constraints']['min'], params['ratio_constraints']['max'])
    }
    return deepcopy({
        'schema_version': 1,
        'coals': [coal.to_dict() for coal in selected_coals],
        'algorithm_coals': coals,
        'algorithm_params': params,
        'ga_config': ga_config,
        'constraints': constraints,
    })


def _build_api_result(coal_names, algorithm_result, time_taken, input_snapshot=None):
    summary = algorithm_result.get('summary', {})
    coal_results = algorithm_result.get('coal_results', [])
    ratio_map = {item['name']: item['ratio'] / 100.0 for item in coal_results}

    recommended_solution = summary.get('recommended_solution')
    pareto_solutions = summary.get('pareto_solutions', [])
    if recommended_solution and isinstance(recommended_solution.get('optimal_ratios'), list):
        optimal_ratios = recommended_solution['optimal_ratios']
    else:
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
        'quality_penalty': summary.get('quality_penalty'),
        'objective_values': summary.get('objective_values'),
        'recommended_solution': recommended_solution,
        'pareto_solutions': pareto_solutions,
        'timestamp': timestamp,
    }

    payload = {
        'status': algorithm_result.get('status', 'success'),
        'message': algorithm_result.get('message', '优化计算完成'),
        'result': result_payload,
    }
    if input_snapshot is not None:
        payload['input_snapshot'] = input_snapshot
        payload['constraints'] = input_snapshot['constraints']
    return _sanitize_json_value(payload)


def _save_optimization_history(request_data, response_payload):
    result = response_payload.get('result') or {}

    history = OptimizationHistory(
        timestamp=result.get('timestamp', datetime.now().isoformat()),
        coal_names=_dump_json(result.get('coal_names', [])),
        optimal_ratios=_dump_json(result.get('optimal_ratios', [])),
        constraints=_dump_json(response_payload.get('constraints', request_data.get('constraints', {}))),
        total_price=result.get('total_price'),
        total_heat=result.get('total_heat'),
        total_ash=result.get('total_ash'),
        total_volatile=result.get('total_volatile'),
        total_fixed_carbon=result.get('total_fixed_carbon'),
        total_sulfur=result.get('total_sulfur'),
        performance_price_ratio=result.get('performance_price_ratio'),
        iterations=result.get('iterations'),
        time_taken=result.get('time_taken'),
        fitness_value=result.get('fitness_value'),
        constraints_satisfied=result.get('constraints_satisfied'),
        request_payload=_dump_json(request_data),
        result_payload=_dump_json(response_payload),
    )
    db.session.add(history)
    db.session.commit()


@optimization_bp.route('/optimization', methods=['POST'])
def run_optimization():
    """执行喷煤工艺混煤优化。"""
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'status': 'error', 'message': '请求数据为空'}), 400

        data = normalize_optimization_request(data)

        optimization_target = data.get('optimization_target', '喷煤性价比最优')
        selected_coal_ids = data.get('selected_coal_ids', [])
        constraints = data.get('constraints', {})
        ga_params = data.get('ga_params', {})

        logger.info('收到优化请求')
        logger.info('  优化目标: %s', optimization_target)
        logger.info('  选中煤种ID: %s', selected_coal_ids)
        logger.info('  约束条件: %s', constraints)
        logger.info('  遗传算法参数: %s', ga_params)

        selected_coals = get_coals_by_ids(selected_coal_ids)
        if len(selected_coals) < 2:
            return jsonify({'status': 'error', 'message': '请至少选择两种煤进行混配'}), 400

        selected_ids_found = {coal.id for coal in selected_coals}
        missing_ids = [coal_id for coal_id in selected_coal_ids if int(coal_id) not in selected_ids_found]
        if missing_ids:
            return jsonify({'status': 'error', 'message': f'煤种不存在: {missing_ids}'}), 404

        data_validation = validate_blending_basis(
            selected_coals, data.get("calculation_mode", "verified"), data.get("ratio_basis", "unknown")
        )
        coal_names = [coal.name for coal in selected_coals]
        coals = [coal_to_algorithm_dict(coal) for coal in selected_coals]

        params = _build_algorithm_params(constraints, selected_coal_ids)
        ga_config = _build_ga_config(ga_params)

        algorithm = OptimizedSmartBlendingAlgorithm()
        algorithm.set_optimizer_config(ga_config)
        input_snapshot = _build_input_snapshot(selected_coals, coals, params, algorithm.optimizer.config)
        input_snapshot.update({
            'calculation_mode': data.get('calculation_mode', 'verified'),
            'ratio_basis': data_validation['ratio_basis'],
            'data_validation': deepcopy(data_validation),
        })

        start_time = datetime.now()
        algorithm_result = algorithm.calculate(
            coals=coals,
            params=params,
            optimization_target=optimization_target,
        )
        end_time = datetime.now()

        time_taken = (end_time - start_time).total_seconds()
        payload = _build_api_result(coal_names, algorithm_result, time_taken, input_snapshot)
        payload['result']['data_validation'] = data_validation
        parameter_warnings = _build_parameter_warnings(data)
        if parameter_warnings:
            payload['parameter_warnings'] = parameter_warnings
            payload['warning'] = '; '.join(parameter_warnings)

        if payload['status'] == 'success':
            try:
                _save_optimization_history(data, payload)
                payload['history_saved'] = True
            except SQLAlchemyError as exc:
                db.session.rollback()
                logger.warning('优化结果已生成，但保存历史记录失败: %s', exc)
                payload['history_saved'] = False
                payload['warning'] = '; '.join(parameter_warnings + [
                    '优化结果已生成，但历史记录保存失败，请初始化或迁移数据库后再试。'
                ])

        return jsonify(_sanitize_json_value(payload))

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
        history_list = [
            item.to_summary_dict()
            for item in OptimizationHistory.query.order_by(OptimizationHistory.created_at.desc()).all()
        ]
        return jsonify(_sanitize_json_value({'status': 'success', 'data': history_list}))
    except Exception as exc:
        logger.error('获取优化历史记录失败: %s', exc)
        return jsonify({'status': 'error', 'message': f'获取优化历史记录失败: {exc}'}), 500


@optimization_bp.route('/optimization/history/<int:history_id>', methods=['GET'])
def get_optimization_history_detail(history_id):
    """获取特定优化历史记录详情。"""
    try:
        history = db.session.get(OptimizationHistory, history_id)
        if history is None:
            return jsonify({'status': 'error', 'message': '历史记录不存在'}), 404

        return jsonify(_sanitize_json_value({'status': 'success', 'data': history.to_detail_dict()}))
    except Exception as exc:
        logger.error('获取优化历史记录详情失败: %s', exc)
        return jsonify({'status': 'error', 'message': f'获取优化历史记录详情失败: {exc}'}), 500
