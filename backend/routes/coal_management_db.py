#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import pandas as pd
from flask import Blueprint, request, jsonify, current_app, send_file
from datetime import datetime
import logging

from backend.config import Config
from backend.database import CoalDataManager
from backend.utils.file_utils import (
    save_uploaded_file, read_uploaded_file, validate_coal_data_format
)
from backend.utils.validation import validate_coal_data

logger = logging.getLogger(__name__)

# 创建煤种管理蓝图（数据库版本）
coal_db_bp = Blueprint('coal_management_db', __name__)

@coal_db_bp.route('/coals', methods=['GET'])
def get_coals():
    """获取所有煤种数据（支持分页和搜索）"""
    try:
        # 获取查询参数
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 10))
        search = request.args.get('search', '').strip()
        coal_type = request.args.get('type', '').strip()
        
        # 验证分页参数
        if page < 1:
            page = 1
        if page_size <= 0:
            page_size = 10
        
        # 使用数据库管理器
        coal_manager = CoalDataManager(current_app.db_manager)
        result = coal_manager.get_coals(page, page_size, search, coal_type)
        
        # 转换数据格式以兼容前端
        coals = []
        for coal in result['data']:
            coal_item = {
                'id': coal['id'],
                'name': coal['name'],
                'type': coal['type'],
                'price': coal['price'],
                'calorific_value': coal['calorific_value'],
                'ash_content': coal['ash_content'],
                'volatile_matter': coal['volatile_matter'],
                'fixed_carbon': coal['fixed_carbon'],
                'total_sulfur': coal['total_sulfur'],
                'total_moisture': coal['total_moisture'],
                'air_dry_moisture': coal['air_dry_moisture'],
                'supplier': coal['supplier'],
                'hgi': coal['hgi'],
                'burnout_rate': coal['burnout_rate'],
                'carbon_content': coal['carbon_content'],
                'hydrogen_content': coal['hydrogen_content'],
                'nitrogen_content': coal['nitrogen_content'],
                'created_at': coal['created_at'],
                'updated_at': coal['updated_at']
            }
            coals.append(coal_item)
        
        return jsonify({
            'status': 'success',
            'data': coals,
            'pagination': result['pagination']
        })
        
    except Exception as e:
        logger.error(f"获取煤种数据失败: {str(e)}")
        return jsonify({'status': 'error', 'message': f'获取数据失败: {str(e)}'}), 500

@coal_db_bp.route('/coals/<int:coal_id>', methods=['GET'])
def get_coal(coal_id):
    """获取单个煤种详情"""
    try:
        coal_manager = CoalDataManager(current_app.db_manager)
        coal = coal_manager.get_coal_by_id(coal_id)
        
        if not coal:
            return jsonify({'status': 'error', 'message': '煤种不存在'}), 404
            
        # 转换数据格式以兼容前端
        coal_data = {
            'id': coal['id'],
            'name': coal['name'],
            'type': coal['type'],
            'price': coal['price'],
            'calorific_value': coal['calorific_value'],
            'ash_content': coal['ash_content'],
            'volatile_matter': coal['volatile_matter'],
            'fixed_carbon': coal['fixed_carbon'],
            'total_sulfur': coal['total_sulfur'],
            'total_moisture': coal['total_moisture'],
            'air_dry_moisture': coal['air_dry_moisture'],
            'supplier': coal['supplier'],
            'hgi': coal['hgi'],
            'burnout_rate': coal['burnout_rate'],
            'carbon_content': coal['carbon_content'],
            'hydrogen_content': coal['hydrogen_content'],
            'nitrogen_content': coal['nitrogen_content'],
            'created_at': coal['created_at'],
            'updated_at': coal['updated_at']
        }
        
        return jsonify({
            'status': 'success',
            'data': coal_data
        })
        
    except Exception as e:
        logger.error(f"获取煤种详情失败: {str(e)}")
        return jsonify({'status': 'error', 'message': f'获取详情失败: {str(e)}'}), 500

@coal_db_bp.route('/coals', methods=['POST'])
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
        
        # 构造数据库格式的数据
        coal_data = {
            'name': data.get('name'),
            'type': data.get('type'),
            'price': float(data.get('price', 0)),
            'calorific_value': float(data.get('calorific_value', 0)),
            'ash_content': float(data.get('ash_content', 0)),
            'volatile_matter': float(data.get('volatile_matter', 0)),
            'fixed_carbon': float(data.get('fixed_carbon', 0)),
            'total_sulfur': float(data.get('total_sulfur', 0)),
            'total_moisture': float(data.get('total_moisture', 0)) if data.get('total_moisture') else None,
            'air_dry_moisture': float(data.get('air_dry_moisture', 0)) if data.get('air_dry_moisture') else None,
            'supplier': data.get('supplier', ''),
            'hgi': float(data.get('hgi', 0)) if data.get('hgi') else None,
            'burnout_rate': float(data.get('burnout_rate', 0)) if data.get('burnout_rate') else None,
            'carbon_content': float(data.get('carbon_content', 0)) if data.get('carbon_content') else None,
            'hydrogen_content': float(data.get('hydrogen_content', 0)) if data.get('hydrogen_content') else None,
            'nitrogen_content': float(data.get('nitrogen_content', 0)) if data.get('nitrogen_content') else None
        }
        
        # 添加到数据库
        coal_manager = CoalDataManager(current_app.db_manager)
        coal_id = coal_manager.add_coal(coal_data)
        
        return jsonify({
            'status': 'success',
            'message': '煤种添加成功',
            'coal_id': coal_id
        })
        
    except Exception as e:
        logger.error(f"添加煤种失败: {str(e)}")
        return jsonify({'status': 'error', 'message': f'添加煤种失败: {str(e)}'}), 500

@coal_db_bp.route('/coals/<int:coal_id>', methods=['PUT'])
def update_coal(coal_id):
    """更新煤种"""
    try:
        data = request.json
        if not data:
            return jsonify({'status': 'error', 'message': '请求数据为空'}), 400
        
        # 验证数据
        is_valid, errors = validate_coal_data(data)
        if not is_valid:
            return jsonify({'status': 'error', 'message': '; '.join(errors)}), 400
        
        # 构造数据库格式的数据
        coal_data = {
            'name': data.get('name'),
            'type': data.get('type'),
            'price': float(data.get('price', 0)),
            'calorific_value': float(data.get('calorific_value', 0)),
            'ash_content': float(data.get('ash_content', 0)),
            'volatile_matter': float(data.get('volatile_matter', 0)),
            'fixed_carbon': float(data.get('fixed_carbon', 0)),
            'total_sulfur': float(data.get('total_sulfur', 0)),
            'total_moisture': float(data.get('total_moisture', 0)) if data.get('total_moisture') else None,
            'air_dry_moisture': float(data.get('air_dry_moisture', 0)) if data.get('air_dry_moisture') else None,
            'supplier': data.get('supplier', ''),
            'hgi': float(data.get('hgi', 0)) if data.get('hgi') else None,
            'burnout_rate': float(data.get('burnout_rate', 0)) if data.get('burnout_rate') else None,
            'carbon_content': float(data.get('carbon_content', 0)) if data.get('carbon_content') else None,
            'hydrogen_content': float(data.get('hydrogen_content', 0)) if data.get('hydrogen_content') else None,
            'nitrogen_content': float(data.get('nitrogen_content', 0)) if data.get('nitrogen_content') else None
        }
        
        # 更新数据库
        coal_manager = CoalDataManager(current_app.db_manager)
        success = coal_manager.update_coal(coal_id, coal_data)
        
        if success:
            return jsonify({'status': 'success', 'message': '煤种更新成功'})
        else:
            return jsonify({'status': 'error', 'message': '煤种不存在或更新失败'}), 404
            
    except Exception as e:
        logger.error(f"更新煤种失败: {str(e)}")
        return jsonify({'status': 'error', 'message': f'更新煤种失败: {str(e)}'}), 500

@coal_db_bp.route('/coals/batch_delete', methods=['POST'])
def batch_delete_coals():
    """批量删除煤种"""
    try:
        data = request.json
        coal_ids = data.get('coal_ids', [])
        
        if not coal_ids:
            return jsonify({'status': 'error', 'message': '请选择要删除的煤种'}), 400
        
        # 删除数据库记录
        coal_manager = CoalDataManager(current_app.db_manager)
        deleted_count = coal_manager.delete_coals(coal_ids)
        
        return jsonify({
            'status': 'success',
            'message': f'成功删除 {deleted_count} 条煤种记录'
        })
        
    except Exception as e:
        logger.error(f"批量删除煤种失败: {str(e)}")
        return jsonify({'status': 'error', 'message': f'批量删除煤种失败: {str(e)}'}), 500

@coal_db_bp.route('/coals/upload', methods=['POST'])
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
        
        # 批量添加到数据库
        coal_manager = CoalDataManager(current_app.db_manager)
        success_count = 0
        error_count = 0
        error_details = []
        
        for index, row in df.iterrows():
            try:
                # 检查煤种名称是否已存在
                existing_coal = coal_manager.get_coal_by_name(str(row.get('煤种名称', '')).strip())
                if existing_coal:
                    error_count += 1
                    error_details.append(f"第{index+1}行: 煤种名称'{row.get('煤种名称')}'已存在")
                    continue
                
                coal_data = {
                    'name': str(row.get('煤种名称', '')).strip(),
                    'type': str(row.get('煤种类型', '')).strip(),
                    'price': float(row.get('价格(元/吨)', 0)),
                    'calorific_value': float(row.get('热值(kcal/kg)', 0)),
                    'ash_content': float(row.get('灰分(%)', 0)),
                    'volatile_matter': float(row.get('挥发分(%)', 0)),
                    'fixed_carbon': float(row.get('固定碳(%)', 0)),
                    'total_sulfur': float(row.get('全硫(%)', 0)),
                    'total_moisture': float(row.get('全水分(%)', 0)) if pd.notna(row.get('全水分(%)')) and str(row.get('全水分(%)')).strip() != '' else None,
                    'air_dry_moisture': float(row.get('空干基水分(%)', 0)) if pd.notna(row.get('空干基水分(%)')) and str(row.get('空干基水分(%)')).strip() != '' else None,
                    'supplier': str(row.get('供应商/产地', '')).strip() if pd.notna(row.get('供应商/产地')) and str(row.get('供应商/产地')).strip() != '' else None,
                    'hgi': float(row.get('可磨性HGI', 0)) if pd.notna(row.get('可磨性HGI')) and str(row.get('可磨性HGI')).strip() != '' else None,
                    'burnout_rate': float(row.get('燃尽率(%)', 0)) if pd.notna(row.get('燃尽率(%)')) and str(row.get('燃尽率(%)')).strip() != '' else None,
                    'carbon_content': float(row.get('含碳量C(%)', 0)) if pd.notna(row.get('含碳量C(%)')) and str(row.get('含碳量C(%)')).strip() != '' else None,
                    'hydrogen_content': float(row.get('含氢量H(%)', 0)) if pd.notna(row.get('含氢量H(%)')) and str(row.get('含氢量H(%)')).strip() != '' else None,
                    'nitrogen_content': float(row.get('含氮量N(%)', 0)) if pd.notna(row.get('含氮量N(%)')) and str(row.get('含氮量N(%)')).strip() != '' else None
                }
                
                # 验证必需字段
                if not coal_data['name'] or not coal_data['type']:
                    error_count += 1
                    error_details.append(f"第{index+1}行: 煤种名称或类型不能为空")
                    continue
                
                coal_manager.add_coal(coal_data)
                success_count += 1
                
            except Exception as e:
                error_count += 1
                error_message = str(e)
                if "UNIQUE constraint failed" in error_message:
                    error_details.append(f"第{index+1}行: 煤种名称重复")
                else:
                    error_details.append(f"第{index+1}行: {error_message}")
                logger.warning(f"导入第{index+1}行数据失败: {str(e)}")
        
        # 构建返回消息
        message_parts = []
        if success_count > 0:
            message_parts.append(f"成功导入 {success_count} 条记录")
        if error_count > 0:
            message_parts.append(f"失败 {error_count} 条记录")
        
        message = "，".join(message_parts)
        
        # 如果有错误详情，添加到消息中
        if error_details and len(error_details) <= 10:  # 只显示前10个错误
            message += f"。错误详情：{'; '.join(error_details[:10])}"
        elif len(error_details) > 10:
            message += f"。错误详情：{'; '.join(error_details[:10])}...（还有{len(error_details)-10}个错误）"
        
        return jsonify({
            'status': 'success' if success_count > 0 else 'error',
            'message': f'文件上传完成。{message}',
            'filename': saved_filename,
            'success_count': success_count,
            'error_count': error_count
        })
        
    except ValueError as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
    except Exception as e:
        logger.error(f"处理上传文件失败: {str(e)}")
        return jsonify({'status': 'error', 'message': f'处理文件失败: {str(e)}'}), 500

@coal_db_bp.route('/coals/types', methods=['GET'])
def get_coal_types():
    """获取所有煤种类型"""
    try:
        with current_app.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT type FROM coal_data ORDER BY type")
            types = [row[0] for row in cursor.fetchall()]
        
        return jsonify({
            'status': 'success',
            'data': types
        })
        
    except Exception as e:
        logger.error(f"获取煤种类型失败: {str(e)}")
        return jsonify({'status': 'error', 'message': f'获取煤种类型失败: {str(e)}'}), 500

@coal_db_bp.route('/coals/template', methods=['GET'])
def download_coal_template():
    """下载导入模板"""
    try:
        from utils.excel_utils import create_coal_template_with_mad
        output = create_coal_template_with_mad()
        
        return send_file(
            output,
            as_attachment=True,
            download_name='煤种数据导入模板.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        logger.error(f"下载模板失败: {str(e)}")
        return jsonify({'status': 'error', 'message': f'下载模板失败: {str(e)}'}), 500

@coal_db_bp.route('/coals/export', methods=['POST'])
def export_coals():
    """导出煤种数据"""
    try:
        data = request.json
        coal_ids = data.get('coal_ids', [])
        export_all = data.get('export_all', False)
        
        coal_manager = CoalDataManager(current_app.db_manager)
        
        # 获取要导出的数据
        if export_all:
            coals = coal_manager.get_all_coals()
        else:
            if not coal_ids:
                return jsonify({'status': 'error', 'message': '没有选择要导出的数据'}), 400
            coals = []
            for coal_id in coal_ids:
                coal = coal_manager.get_coal_by_id(coal_id)
                if coal:
                    coals.append(coal)
        
        if not coals:
            return jsonify({'status': 'error', 'message': '没有要导出的数据'}), 400
        
        # 转换为DataFrame
        df_data = []
        for coal in coals:
            df_data.append({
                '序号': coal['id'],
                '煤种名称': coal['name'],
                '煤种类型': coal['type'],
                '供应商/产地': coal.get('supplier', ''),
                '价格(元/吨)': coal['price'],
                '热值(kcal/kg)': coal['calorific_value'],
                '灰分(%)': coal['ash_content'],
                '挥发分(%)': coal['volatile_matter'],
                '固定碳(%)': coal['fixed_carbon'],
                '全硫(%)': coal['total_sulfur'],
                '全水分(%)': coal.get('total_moisture', ''),
                '空干基水分(%)': coal.get('air_dry_moisture', ''),
                '可磨性HGI': coal.get('hgi', ''),
                '燃尽率(%)': coal.get('burnout_rate', ''),
                '含碳量C(%)': coal.get('carbon_content', ''),
                '含氢量H(%)': coal.get('hydrogen_content', ''),
                '含氮量N(%)': coal.get('nitrogen_content', '')
            })
        
        df = pd.DataFrame(df_data)
        
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