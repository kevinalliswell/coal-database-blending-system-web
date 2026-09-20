#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import math
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, g

from app.extensions import db
from app.models import ReplacementRatioHistory
from app.models.catalog import AssayRevision
from app.services.access_service import AccessError, get_settings
from app.services.catalog_service import serialize_assay
from app.services.assay_conversion import KJ_PER_KCAL
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
    # Summaries may use effective values, but request_payload preserves user input
    # exactly; notably kJ/kg inputs must not be overwritten by internal kcal_IT.
    summary_data = request_data
    if calculation_type == 'theory':
        normalized_coal = (response_payload.get('input_snapshot') or {}).get('normalized', {}).get('coal_params')
        if normalized_coal:
            summary_data = {**request_data, 'coal_params': normalized_coal}
    parameter_summary = (
        _build_theory_parameter_summary(summary_data)
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


def _object(value, allowed, label):
    if not isinstance(value, dict):
        raise ValueError(f'{label}必须为对象')
    extra = set(value) - set(allowed)
    if extra:
        raise ValueError(f'{label}含不支持的字段: {", ".join(sorted(extra))}')
    return value


def _number(data, field, *, minimum=0, maximum=None):
    value = data.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'缺少或无效的数值: {field}')
    try:
        value = float(value)
    except OverflowError:
        raise ValueError(f'{field}数值超出范围') from None
    if not math.isfinite(value) or (minimum is not None and value < minimum) or (maximum is not None and value > maximum):
        raise ValueError(f'{field}必须为允许范围内的有限数值')
    return value


def _text(data, field, *, required=True):
    value = data.get(field, '')
    if not isinstance(value, str) or len(value.strip()) > 500 or (required and not value.strip()):
        raise ValueError(f'{field}须为明确的来源/期间文字，最长500字')
    return value.strip()


def _settings(data):
    settings = get_settings()
    if type(data.get('settings_version')) is not int:
        raise ValueError('必须提供整数 settings_version，请刷新系统设置')
    if data['settings_version'] != settings['version']:
        raise AccessError('系统设置已改变，请刷新后重新计算', 409, 'settings_conflict')
    return settings


def _snapshot(data, normalized, settings, *, assay=None):
    user = g.current_user
    return {
        'schema_version': 2, 'created_at': datetime.now(timezone.utc).isoformat(),
        'actor': {'id': user.id, 'username': user.username, 'display_name': user.display_name, 'role': user.role},
        'request': deepcopy(data), 'settings': deepcopy(settings),
        'assay': deepcopy(assay),
        'raw': deepcopy(assay['raw'] if assay else data['production_data']),
        'normalized': deepcopy(normalized),
        'conversion_trace': deepcopy(assay['eligibility']['theory']['trace'] if assay else []),
    }


def _check_result(ratio, details):
    if not math.isfinite(ratio) or any(not math.isfinite(value) for value in details.values()):
        raise ValueError('计算结果超出有限数值范围，请检查输入')


def _theory_inputs(data):
    _object(data, {'assay_revision_id', 'settings_version', 'coal_params', 'coke_params',
                   'blast_furnace_params', 'allow_hot_blast_estimate', 'parameter_source'}, '请求')
    settings = _settings(data)
    revision_id = data.get('assay_revision_id')
    if type(revision_id) is not int or revision_id <= 0:
        raise ValueError('必须选择 assay_revision_id 化验修订，不能直接填写煤粉成分')
    record = db.session.get(AssayRevision, revision_id)
    if record is None:
        raise AccessError('化验修订不存在', 404, 'not_found')
    assay = serialize_assay(record, settings)
    eligibility = assay['eligibility']['theory']
    if not eligibility['eligible']:
        raise ValueError('化验不能用于理论置换比: ' + '；'.join(issue['message'] for issue in eligibility['issues']))
    coal_data = _object(data.get('coal_params'), {'decomposition_heat', 'physical_heat', 'heat_unit'}, '煤粉热耗参数')
    if coal_data.get('heat_unit') != 'kJ/kg':
        raise ValueError('煤粉分解热和物理热必须显式使用 heat_unit=kJ/kg（每kg干煤）')
    coal = {field: eligibility['values'][field] / 100 for field in
            ('carbon_content', 'hydrogen_content', 'ash_content', 'sio2_content')}
    coal.update({field: _number(coal_data, field) / KJ_PER_KCAL for field in ('decomposition_heat', 'physical_heat')})
    coke_data = _object(data.get('coke_params'), {'analysis_basis', 'carbon_content', 'ash_content', 'sio2_content'}, '焦炭参数')
    if coke_data.get('analysis_basis') != 'd':
        raise ValueError('焦炭 C/A 必须明确为干基 d，SiO₂ 为灰基')
    coke = {field: _number(coke_data, field, maximum=1) for field in ('carbon_content', 'ash_content', 'sio2_content')}
    if coke['carbon_content'] <= 0 or coke['carbon_content'] + coke['ash_content'] > 1.005:
        raise ValueError('焦炭碳须大于零，且干基 C+A 不能超过100%加输入质控容差')
    furnace_data = _object(data.get('blast_furnace_params'),
                           {'eta_co', 'slag_basicity', 'slag_enthalpy', 'wind_temperature', 'hot_blast_enthalpy'}, '炉况参数')
    furnace = {'eta_co': _number(furnace_data, 'eta_co', maximum=1),
               'slag_basicity': _number(furnace_data, 'slag_basicity'),
               'slag_enthalpy': _number(furnace_data, 'slag_enthalpy')}
    if furnace['slag_basicity'] <= 0:
        raise ValueError('炉渣碱度必须大于零')
    allow_estimate = data.get('allow_hot_blast_estimate', False)
    if type(allow_estimate) is not bool:
        raise ValueError('allow_hot_blast_estimate 必须为布尔值')
    measured = furnace_data.get('hot_blast_enthalpy') is not None
    if measured and allow_estimate:
        raise ValueError('鼓风热焓只能选择提供数值或风温估算其中一种来源')
    if measured:
        furnace['hot_blast_enthalpy'] = _number(furnace_data, 'hot_blast_enthalpy')
        furnace['wind_temperature'] = (_number(furnace_data, 'wind_temperature')
                                        if furnace_data.get('wind_temperature') is not None else None)
    elif allow_estimate:
        furnace['wind_temperature'] = _number(furnace_data, 'wind_temperature')
        furnace['hot_blast_enthalpy'] = None
    else:
        raise ValueError('缺少鼓风热焓；使用风温估算须显式启用 allow_hot_blast_estimate')
    _text(data, 'parameter_source', required=False)
    return settings, assay, coal, coke, furnace

@replacement_ratio_bp.route('/calculate_theory_ratio', methods=['POST'])
def calculate_theory_ratio():
    """理论置换比计算API"""
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'status': 'error', 'message': '请求数据为空'}), 400
        
        settings, assay, coal_values, coke_values, furnace_values = _theory_inputs(data)
        coal_params = CoalParameters(**coal_values)
        coke_params = CokeParameters(**coke_values)
        blast_furnace_params = BlastFurnaceParameters(**furnace_values)
        
        # 创建计算器并执行计算
        calculator = ReplacementRatioCalculator(coal_params, coke_params, blast_furnace_params)
        ratio, details = calculator.calculate_displacement_ratio()
        _check_result(ratio, details)
        
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
            'decomposition_heat_consumption': coal_params.decomposition_heat * KJ_PER_KCAL,
            'physical_heat_consumption': coal_params.physical_heat * KJ_PER_KCAL,
            'total_heat_consumption': (coal_params.decomposition_heat + coal_params.physical_heat) * KJ_PER_KCAL,
            'heat_consumption_unit': 'kJ/kg',
            'effective_hot_blast_enthalpy': calculator.effective_hot_blast_enthalpy(),  # kJ/m³
            'hot_blast_enthalpy_source': 'temperature_estimate' if blast_furnace_params.hot_blast_enthalpy is None else 'provided',
            'hydrogen_replacement_heat': 62222,  # kJ/kg，模型常数
            'input_snapshot': _snapshot(data, {
                'coal_params': asdict(coal_params), 'coke_params': asdict(coke_params),
                'blast_furnace_params': asdict(blast_furnace_params),
                'analysis_basis': 'd', 'composition_unit': 'mass_fraction',
                'coal_thermal_input_unit': 'kJ/kg_dry_coal',
                'coal_thermal_model_unit': 'kcal_IT/kg_dry_coal',
                'model': 'carbon-hydrogen-heat-balance-v1',
                'model_constants': {'air_volume_m3_per_kg_carbon': 1.2, 'hydrogen_replacement_heat_kj_kg': 62222,
                                    'kj_per_kcal_IT': KJ_PER_KCAL},
            }, settings, assay=assay),
        }
        
        _save_replacement_ratio_history(data, result, 'theory', 'theory')
        logger.info(f"理论置换比计算成功: {ratio:.6f}")
        return jsonify(_sanitize_json_value(result))
        
    except AccessError as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e), 'code': e.code}), e.status
    except (ValueError, OverflowError) as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"理论置换比计算失败: {str(e)}")
        return jsonify({'status': 'error', 'message': '理论计算失败，请检查服务日志'}), 500

@replacement_ratio_bp.route('/calculate_actual_ratio', methods=['POST'])
def calculate_actual_ratio():
    """实际置换比计算API"""
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'status': 'error', 'message': '请求数据为空'}), 400
        
        _object(data, {'settings_version', 'production_data', 'mass_basis', 'furnace_id',
                       'period_before', 'period_after', 'correction_mode', 'correction_source'}, '请求')
        settings = _settings(data)
        if data.get('mass_basis') not in ('ar', 'd'):
            raise ValueError('必须明确煤与焦炭耗量的共同质量基准 mass_basis: ar 或 d')
        for field in ('furnace_id', 'period_before', 'period_after'):
            _text(data, field)
        if data['period_before'].strip() == data['period_after'].strip():
            raise ValueError('调整前后的统计期间必须明确且不同')
        basic_fields = ('initial_coke_ratio', 'final_coke_ratio', 'initial_coal_ratio', 'final_coal_ratio')
        raw_production = _object(data.get('production_data'), {*basic_fields, 'adjustment_factor'}, '生产数据')
        production_values = {field: _number(raw_production, field) for field in basic_fields}
        correction_mode = data.get('correction_mode', 'none')
        if correction_mode not in ('none', 'provided'):
            raise ValueError('只支持未修正 none 或显式提供修正项 provided；不启用未校准的高级经验修正')
        if correction_mode == 'provided':
            production_values['adjustment_factor'] = _number(raw_production, 'adjustment_factor', minimum=None)
            _text(data, 'correction_source')
        else:
            if 'adjustment_factor' in raw_production or data.get('correction_source'):
                raise ValueError('提供修正项必须显式选择 correction_mode=provided')
            # This is the definition of the uncorrected formula, not imputed data.
            production_values['adjustment_factor'] = 0.0
        production_data = ProductionData(**production_values)
        
        # 创建计算器并执行计算
        calculator = ActualReplacementRatioCalculator()
        
        ratio, details = calculator.calculate_basic_ratio(production_data)
        _check_result(ratio, details)
        
        # 格式化结果
        result = {
            'status': 'success',
            'ratio': ratio,
            'details': details,
            'calculation_type': 'advanced' if correction_mode == 'provided' else 'basic',
            'correction_mode': correction_mode,
            'mass_basis': data['mass_basis'],
            'input_snapshot': _snapshot(data, {'production_data': production_values,
                'mass_basis': data['mass_basis'], 'unit': 'kg/t_hot_metal',
                'formula': '(coke_before − coke_after + correction)/(coal_after − coal_before)',
                'correction_mode': correction_mode}, settings),
        }
        
        calculation_mode = result['calculation_type']
        _save_replacement_ratio_history(data, result, 'actual', calculation_mode)
        logger.info(f"实际置换比计算成功: {ratio:.6f} ({correction_mode})")
        return jsonify(_sanitize_json_value(result))
        
    except AccessError as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e), 'code': e.code}), e.status
    except (ValueError, OverflowError) as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"实际置换比计算失败: {str(e)}")
        return jsonify({'status': 'error', 'message': '实际计算失败，请检查服务日志'}), 500

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
