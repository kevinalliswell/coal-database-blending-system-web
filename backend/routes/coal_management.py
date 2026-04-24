#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pandas as pd
from flask import Blueprint, request, jsonify, send_file
from datetime import datetime
import logging

from app.config import Config
from app.utils.file_utils import (
    save_uploaded_file, read_uploaded_file, validate_coal_data_format, 
    merge_coal_data, safe_read_csv
)
from app.utils.validation import safe_float, safe_int, validate_coal_data
from app.utils.excel_utils import create_coal_template

logger = logging.getLogger(__name__)

# 创建煤种管理蓝图
coal_bp = Blueprint('coal_management', __name__)


def _serialize_coal_row(row):
    """将 CSV 行转换为前端所需的煤种字典。"""
    return {
        'id': safe_int(row.get('序号', 0)),
        'name': str(row.get('煤种名称', '')),
        'type': str(row.get('煤种类型', '')),
        'supplier': str(row.get('供应商/产地', '')),
        'price': safe_float(row.get('价格(元/吨)', 0)),
        'calorific_value': safe_float(row.get('热值(kcal/kg)', 0)),
        'ash_content': safe_float(row.get('灰分(%)', 0)),
        'volatile_matter': safe_float(row.get('挥发分(%)', 0)),
        'fixed_carbon': safe_float(row.get('固定碳(%)', 0)),
        'total_sulfur': safe_float(row.get('全硫(%)', 0)),
        'moisture': safe_float(row.get('全水分(%)', 0)),
        'mad': safe_float(row.get('空干基水分(%)', 0))
        if '空干基水分(%)' in row and pd.notna(row.get('空干基水分(%)')) and row.get('空干基水分(%)') != ''
        else None,
        'hgi': safe_float(row.get('可磨性HGI', 0))
        if '可磨性HGI' in row and pd.notna(row.get('可磨性HGI')) and row.get('可磨性HGI') != ''
        else None,
        'burnout_rate': safe_float(row.get('燃尽率(%)', 0))
        if '燃尽率(%)' in row and pd.notna(row.get('燃尽率(%)')) and row.get('燃尽率(%)') != ''
        else None,
        'carbon_content': safe_float(row.get('含碳量C(%)', 0))
        if '含碳量C(%)' in row and pd.notna(row.get('含碳量C(%)')) and row.get('含碳量C(%)') != ''
        else None,
        'hydrogen_content': safe_float(row.get('含氢量H(%)', 0))
        if '含氢量H(%)' in row and pd.notna(row.get('含氢量H(%)')) and row.get('含氢量H(%)') != ''
        else None,
        'nitrogen_content': safe_float(row.get('含氮量N(%)', 0))
        if '含氮量N(%)' in row and pd.notna(row.get('含氮量N(%)')) and row.get('含氮量N(%)') != ''
        else None,
    }

@coal_bp.route('/coals', methods=['GET'])
def get_coals():
    """获取所有煤种数据（支持分页和搜索）"""
    try:
        # 获取查询参数
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 10))
        search = request.args.get('search', '').strip()
        coal_type = request.args.get('type', '').strip()
        
        # 从CSV文件读取煤种数据
        try:
            df = safe_read_csv(Config.COAL_DATA_PATH)
        except FileNotFoundError:
            # 如果文件不存在，返回空结果
            return jsonify({
                'status': 'success', 
                'data': [],
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total': 0,
                    'total_pages': 0
                }
            })
        
        # 搜索过滤
        if search:
            mask = df['煤种名称'].str.contains(search, case=False, na=False) | \
                   df['煤种类型'].str.contains(search, case=False, na=False)
            df = df[mask]
        
        # 类型过滤
        if coal_type:
            df = df[df['煤种类型'] == coal_type]
        
        # 计算总数
        total = len(df)
        
        # 分页
        if page_size > 0:
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            df = df.iloc[start_idx:end_idx]
        
        # 转换为JSON格式
        coals = [_serialize_coal_row(row) for _, row in df.iterrows()]
        
        return jsonify({
            'status': 'success', 
            'data': coals,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total': total,
                'total_pages': (total + page_size - 1) // page_size if page_size > 0 else 1
            }
        })
    except Exception as e:
        logger.error(f"获取煤种数据失败: {str(e)}")
        return jsonify({'status': 'error', 'message': f'获取煤种数据失败: {str(e)}'}), 500


@coal_bp.route('/coals/<int:coal_id>', methods=['GET'])
def get_coal(coal_id):
    """获取单个煤种详情，兼容前端编辑弹窗请求。"""
    try:
        df = safe_read_csv(Config.COAL_DATA_PATH)
        coal_rows = df[df['序号'] == coal_id]

        if coal_rows.empty:
            return jsonify({'status': 'error', 'message': '煤种不存在'}), 404

        coal = _serialize_coal_row(coal_rows.iloc[0])
        return jsonify({'status': 'success', 'data': coal})
    except FileNotFoundError:
        return jsonify({'status': 'error', 'message': '煤种数据文件不存在'}), 404
    except Exception as e:
        logger.error(f"获取煤种详情失败: {str(e)}")
        return jsonify({'status': 'error', 'message': f'获取煤种详情失败: {str(e)}'}), 500

@coal_bp.route('/coals/upload', methods=['POST'])
def upload_coal_data():
    """上传煤种数据文件"""
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': '没有文件部分'}), 400
    
    file = request.files['file']
    
    try:
        # 保存上传的文件
        file_path, saved_filename = save_uploaded_file(file, Config.UPLOAD_FOLDER)
        
        # 读取上传的文件
        df = read_uploaded_file(file_path)
        
        # 验证文件格式
        validate_coal_data_format(df)
        
        # 读取现有数据并合并
        try:
            existing_df = safe_read_csv(Config.COAL_DATA_PATH)
        except FileNotFoundError:
            existing_df = pd.DataFrame()
        
        # 合并数据
        combined_df = merge_coal_data(df, existing_df)
        
        # 保存合并后的数据
        combined_df.to_csv(Config.COAL_DATA_PATH, index=False, encoding='utf-8')
        
        return jsonify({
            'status': 'success', 
            'message': '文件上传成功',
            'filename': saved_filename,
            'coal_count': len(df)
        })
        
    except ValueError as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
    except Exception as e:
        logger.error(f"处理上传文件失败: {str(e)}")
        return jsonify({'status': 'error', 'message': f'处理文件失败: {str(e)}'}), 500

@coal_bp.route('/coals', methods=['POST'])
def add_coal():
    """添加煤种"""
    try:
        data = request.json
        if not data:
            return jsonify({'status': 'error', 'message': '请求数据为空'}), 400
        
        # 验证数据
        is_valid, errors = validate_coal_data(data)
        if not is_valid:
            return jsonify({'status': 'error', 'message': '; '.join(errors)}), 400
        
        # 读取现有数据
        try:
            df = safe_read_csv(Config.COAL_DATA_PATH)
        except FileNotFoundError:
            # 如果文件不存在，创建新的DataFrame
            df = pd.DataFrame()
        
        # 生成新的序号
        if len(df) > 0 and '序号' in df.columns:
            new_id = int(df['序号'].max()) + 1
        else:
            new_id = 1
        
        # 创建新记录
        new_row = {
            '序号': new_id,
            '煤种名称': data['name'],
            '煤种类型': data['type'],
            '供应商/产地': data.get('supplier', ''),
            '价格(元/吨)': float(data['price']),
            '热值(kcal/kg)': float(data['calorific_value']),
            '灰分(%)': float(data['ash_content']),
            '挥发分(%)': float(data['volatile_matter']),
            '固定碳(%)': float(data['fixed_carbon']),
            '全硫(%)': float(data['total_sulfur']),
            '全水分(%)': float(data.get('moisture', 0)),
            '空干基水分(%)': float(data['mad']) if data.get('mad') else None,
            '可磨性HGI': float(data['hgi']) if data.get('hgi') else None,
            '燃尽率(%)': float(data['burnout_rate']) if data.get('burnout_rate') else None,
            '含碳量C(%)': float(data['carbon_content']) if data.get('carbon_content') else None,
            '含氢量H(%)': float(data['hydrogen_content']) if data.get('hydrogen_content') else None,
            '含氮量N(%)': float(data['nitrogen_content']) if data.get('nitrogen_content') else None
        }
        
        # 添加到DataFrame
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        
        # 保存到文件
        df.to_csv(Config.COAL_DATA_PATH, index=False, encoding='utf-8')
        
        return jsonify({'status': 'success', 'message': '煤种添加成功', 'coal_id': new_id})
        
    except Exception as e:
        logger.error(f"添加煤种失败: {str(e)}")
        return jsonify({'status': 'error', 'message': f'添加煤种失败: {str(e)}'}), 500

@coal_bp.route('/coals/<int:coal_id>', methods=['PUT'])
def update_coal(coal_id):
    """更新煤种"""
    try:
        data = request.json
        if not data:
            return jsonify({'status': 'error', 'message': '请求数据为空'}), 400
        
        # 读取现有数据
        df = safe_read_csv(Config.COAL_DATA_PATH)
        
        # 查找要更新的记录
        coal_index = df[df['序号'] == coal_id].index
        if len(coal_index) == 0:
            return jsonify({'status': 'error', 'message': '煤种不存在'}), 404
        
        coal_index = coal_index[0]
        
        # 更新字段
        if 'name' in data:
            df.at[coal_index, '煤种名称'] = data['name']
        if 'type' in data:
            df.at[coal_index, '煤种类型'] = data['type']
        if 'supplier' in data:
            df.at[coal_index, '供应商/产地'] = data['supplier']
        if 'price' in data:
            df.at[coal_index, '价格(元/吨)'] = float(data['price'])
        if 'calorific_value' in data:
            df.at[coal_index, '热值(kcal/kg)'] = float(data['calorific_value'])
        if 'ash_content' in data:
            df.at[coal_index, '灰分(%)'] = float(data['ash_content'])
        if 'volatile_matter' in data:
            df.at[coal_index, '挥发分(%)'] = float(data['volatile_matter'])
        if 'fixed_carbon' in data:
            df.at[coal_index, '固定碳(%)'] = float(data['fixed_carbon'])
        if 'total_sulfur' in data:
            df.at[coal_index, '全硫(%)'] = float(data['total_sulfur'])
        if 'moisture' in data:
            df.at[coal_index, '全水分(%)'] = float(data['moisture'])
        if 'mad' in data and data['mad']:
            df.at[coal_index, '空干基水分(%)'] = float(data['mad'])
        if 'hgi' in data and data['hgi']:
            df.at[coal_index, '可磨性HGI'] = float(data['hgi'])
        if 'burnout_rate' in data and data['burnout_rate']:
            df.at[coal_index, '燃尽率(%)'] = float(data['burnout_rate'])
        if 'carbon_content' in data and data['carbon_content']:
            df.at[coal_index, '含碳量C(%)'] = float(data['carbon_content'])
        if 'hydrogen_content' in data and data['hydrogen_content']:
            df.at[coal_index, '含氢量H(%)'] = float(data['hydrogen_content'])
        if 'nitrogen_content' in data and data['nitrogen_content']:
            df.at[coal_index, '含氮量N(%)'] = float(data['nitrogen_content'])
        
        # 保存到文件
        df.to_csv(Config.COAL_DATA_PATH, index=False, encoding='utf-8')
        
        return jsonify({'status': 'success', 'message': '煤种更新成功'})
        
    except Exception as e:
        logger.error(f"更新煤种失败: {str(e)}")
        return jsonify({'status': 'error', 'message': f'更新煤种失败: {str(e)}'}), 500

@coal_bp.route('/coals/<int:coal_id>', methods=['DELETE'])
def delete_coal(coal_id):
    """删除煤种"""
    try:
        # 读取现有数据
        df = safe_read_csv(Config.COAL_DATA_PATH)
        
        # 查找要删除的记录
        coal_index = df[df['序号'] == coal_id].index
        if len(coal_index) == 0:
            return jsonify({'status': 'error', 'message': '煤种不存在'}), 404
        
        # 删除记录
        df = df.drop(coal_index)
        
        # 保存到文件
        df.to_csv(Config.COAL_DATA_PATH, index=False, encoding='utf-8')
        
        return jsonify({'status': 'success', 'message': '煤种删除成功'})
        
    except Exception as e:
        logger.error(f"删除煤种失败: {str(e)}")
        return jsonify({'status': 'error', 'message': f'删除煤种失败: {str(e)}'}), 500

@coal_bp.route('/coals/batch_delete', methods=['POST'])
def batch_delete_coals():
    """批量删除煤种"""
    try:
        data = request.json
        coal_ids = data.get('coal_ids', [])
        
        if not coal_ids:
            return jsonify({'status': 'error', 'message': '请选择要删除的煤种'}), 400
        
        # 读取现有数据
        df = safe_read_csv(Config.COAL_DATA_PATH)
        
        # 删除指定的记录
        df = df[~df['序号'].isin(coal_ids)]
        
        # 保存到文件
        df.to_csv(Config.COAL_DATA_PATH, index=False, encoding='utf-8')
        
        return jsonify({'status': 'success', 'message': f'成功删除 {len(coal_ids)} 条煤种记录'})
        
    except Exception as e:
        logger.error(f"批量删除煤种失败: {str(e)}")
        return jsonify({'status': 'error', 'message': f'批量删除煤种失败: {str(e)}'}), 500

@coal_bp.route('/coals/export', methods=['POST'])
def export_coals():
    """导出煤种数据"""
    try:
        data = request.json
        coal_ids = data.get('coal_ids', [])
        export_all = data.get('export_all', False)
        
        # 读取数据
        df = safe_read_csv(Config.COAL_DATA_PATH)
        
        # 筛选要导出的数据
        if not export_all and coal_ids:
            df = df[df['序号'].isin(coal_ids)]
        
        if len(df) == 0:
            return jsonify({'status': 'error', 'message': '没有要导出的数据'}), 400
        
        # 创建Excel文件
        from io import BytesIO
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='煤种数据', index=False)
        
        output.seek(0)
        
        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'煤种数据导出_{timestamp}.xlsx'
        
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        logger.error(f"导出煤种数据失败: {str(e)}")
        return jsonify({'status': 'error', 'message': f'导出失败: {str(e)}'}), 500

@coal_bp.route('/coals/template', methods=['GET'])
def download_coal_template():
    """下载导入模板"""
    try:
        output = create_coal_template()
        
        return send_file(
            output,
            as_attachment=True,
            download_name='煤种数据导入模板.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        logger.error(f"下载模板失败: {str(e)}")
        return jsonify({'status': 'error', 'message': f'下载模板失败: {str(e)}'}), 500 
