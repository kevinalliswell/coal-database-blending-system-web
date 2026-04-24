#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app

from backend.database import CoalDataManager, OptimizationHistoryManager
from backend.blending_algorithm_optimized import OptimizedSmartBlendingAlgorithm

logger = logging.getLogger(__name__)

# 创建优化计算蓝图（数据库版本）
optimization_db_bp = Blueprint('optimization_db', __name__)

@optimization_db_bp.route('/optimize', methods=['POST'])
def optimize_blending():
    """执行智能混煤优化计算（数据库版本）"""
    try:
        data = request.json
        if not data:
            return jsonify({'status': 'error', 'message': '请求数据为空'}), 400
        
        # 获取选中的煤种名称
        selected_coal_names = data.get('selected_coals', [])
        if not selected_coal_names or len(selected_coal_names) < 2:
            return jsonify({'status': 'error', 'message': '请至少选择2种煤进行优化'}), 400
        
        # 从数据库获取煤种数据
        coal_manager = CoalDataManager(current_app.db_manager)
        coals_data = coal_manager.get_coals_by_names(selected_coal_names)
        
        if not coals_data or len(coals_data) != len(selected_coal_names):
            return jsonify({'status': 'error', 'message': '部分煤种数据未找到'}), 400
        
        # 转换数据格式以兼容算法
        coal_list = []
        for coal in coals_data:
            coal_item = {
                'name': coal['name'],
                'price': float(coal['price']),
                'calorific_value': float(coal['calorific_value']),
                'ash_content': float(coal['ash_content']),
                'volatile_matter': float(coal['volatile_matter']),
                'fixed_carbon': float(coal['fixed_carbon']),
                'total_sulfur': float(coal['total_sulfur'])
            }
            coal_list.append(coal_item)
        
        # 获取约束条件
        constraints = data.get('constraints', {})
        
        # 获取配比约束
        ratio_constraints = data.get('ratio_constraints', {})
        
        # 获取算法参数
        algorithm_params = data.get('algorithm_params', {})
        
        # 获取优化目标
        optimization_target = data.get('optimization_target', 'lowest_cost')
        
        # 执行优化算法
        algorithm = OptimizedSmartBlendingAlgorithm(
            coal_data=coal_list,
            constraints=constraints,
            ratio_constraints=ratio_constraints,
            optimization_target=optimization_target,
            **algorithm_params
        )
        
        # 运行优化
        result = algorithm.optimize()
        
        if result['status'] == 'success':
            # 保存优化结果到数据库
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            
            history_data = {
                'timestamp': timestamp,
                'coal_names': selected_coal_names,
                'optimal_ratios': result['result']['optimal_ratios'],
                'constraints': constraints,
                'total_price': result['result']['total_price'],
                'total_heat': result['result']['total_heat'],
                'total_ash': result['result']['total_ash'],
                'total_volatile': result['result']['total_volatile'],
                'total_fixed_carbon': result['result']['total_fixed_carbon'],
                'total_sulfur': result['result']['total_sulfur'],
                'performance_price_ratio': result['result']['performance_price_ratio'],
                'iterations': result['result']['iterations'],
                'time_taken': result['result']['time_taken'],
                'fitness_value': result['result']['fitness_value'],
                'constraints_satisfied': result['result']['constraints_satisfied']
            }
            
            # 保存到数据库
            history_manager = OptimizationHistoryManager(current_app.db_manager)
            history_id = history_manager.save_optimization_result(history_data)
            
            # 在结果中添加历史记录ID
            result['result']['history_id'] = history_id
            result['result']['timestamp'] = timestamp
            
            logger.info(f"优化计算完成，历史记录ID: {history_id}")
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"优化计算失败: {str(e)}")
        return jsonify({
            'status': 'error', 
            'message': f'优化计算失败: {str(e)}'
        }), 500

@optimization_db_bp.route('/history', methods=['GET'])
def get_optimization_history():
    """获取优化历史记录（数据库版本）"""
    try:
        # 获取查询参数
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 10))
        
        # 从数据库获取历史记录
        history_manager = OptimizationHistoryManager(current_app.db_manager)
        result = history_manager.get_optimization_history(page, page_size)
        
        return jsonify({
            'status': 'success',
            'data': result['data'],
            'pagination': result['pagination']
        })
        
    except Exception as e:
        logger.error(f"获取历史记录失败: {str(e)}")
        return jsonify({
            'status': 'error', 
            'message': f'获取历史记录失败: {str(e)}'
        }), 500

@optimization_db_bp.route('/history/<int:history_id>', methods=['GET'])
def get_optimization_detail(history_id):
    """获取优化历史详情（数据库版本）"""
    try:
        # 从数据库获取详细记录
        history_manager = OptimizationHistoryManager(current_app.db_manager)
        record = history_manager.get_optimization_by_id(history_id)
        
        if not record:
            return jsonify({
                'status': 'error', 
                'message': '历史记录不存在'
            }), 404
        
        return jsonify({
            'status': 'success',
            'data': record
        })
        
    except Exception as e:
        logger.error(f"获取历史详情失败: {str(e)}")
        return jsonify({
            'status': 'error', 
            'message': f'获取历史详情失败: {str(e)}'
        }), 500

@optimization_db_bp.route('/history/<int:history_id>', methods=['DELETE'])
def delete_optimization_history(history_id):
    """删除优化历史记录（数据库版本）"""
    try:
        with current_app.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM optimization_history WHERE id = ?", (history_id,))
            
            if cursor.rowcount == 0:
                return jsonify({
                    'status': 'error', 
                    'message': '历史记录不存在'
                }), 404
            
            conn.commit()
        
        return jsonify({
            'status': 'success',
            'message': '历史记录删除成功'
        })
        
    except Exception as e:
        logger.error(f"删除历史记录失败: {str(e)}")
        return jsonify({
            'status': 'error', 
            'message': f'删除历史记录失败: {str(e)}'
        }), 500

@optimization_db_bp.route('/history/batch_delete', methods=['POST'])
def batch_delete_optimization_history():
    """批量删除优化历史记录（数据库版本）"""
    try:
        data = request.json
        history_ids = data.get('history_ids', [])
        
        if not history_ids:
            return jsonify({'status': 'error', 'message': '请选择要删除的历史记录'}), 400
        
        with current_app.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            placeholders = ','.join(['?'] * len(history_ids))
            sql = f"DELETE FROM optimization_history WHERE id IN ({placeholders})"
            
            cursor.execute(sql, history_ids)
            deleted_count = cursor.rowcount
            conn.commit()
        
        return jsonify({
            'status': 'success',
            'message': f'成功删除 {deleted_count} 条历史记录'
        })
        
    except Exception as e:
        logger.error(f"批量删除历史记录失败: {str(e)}")
        return jsonify({
            'status': 'error', 
            'message': f'批量删除历史记录失败: {str(e)}'
        }), 500

@optimization_db_bp.route('/statistics', methods=['GET'])
def get_optimization_statistics():
    """获取优化统计信息（数据库版本）"""
    try:
        with current_app.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # 总的优化次数
            cursor.execute("SELECT COUNT(*) FROM optimization_history")
            total_optimizations = cursor.fetchone()[0]
            
            # 成功的优化次数
            cursor.execute("SELECT COUNT(*) FROM optimization_history WHERE constraints_satisfied = 1")
            successful_optimizations = cursor.fetchone()[0]
            
            # 平均优化时间
            cursor.execute("SELECT AVG(time_taken) FROM optimization_history WHERE time_taken IS NOT NULL")
            avg_time = cursor.fetchone()[0] or 0
            
            # 最常用的煤种组合
            cursor.execute("""
                SELECT coal_names, COUNT(*) as count 
                FROM optimization_history 
                GROUP BY coal_names 
                ORDER BY count DESC 
                LIMIT 5
            """)
            popular_combinations = []
            for row in cursor.fetchall():
                try:
                    coal_names = json.loads(row[0])
                    popular_combinations.append({
                        'coal_names': coal_names,
                        'count': row[1]
                    })
                except:
                    continue
            
            # 最近30天的优化趋势
            cursor.execute("""
                SELECT DATE(created_at) as date, COUNT(*) as count
                FROM optimization_history 
                WHERE created_at >= DATE('now', '-30 days')
                GROUP BY DATE(created_at)
                ORDER BY date
            """)
            
            recent_trend = [{'date': row[0], 'count': row[1]} for row in cursor.fetchall()]
        
        statistics = {
            'total_optimizations': total_optimizations,
            'successful_optimizations': successful_optimizations,
            'success_rate': (successful_optimizations / total_optimizations * 100) if total_optimizations > 0 else 0,
            'average_time': round(avg_time, 2),
            'popular_combinations': popular_combinations,
            'recent_trend': recent_trend
        }
        
        return jsonify({
            'status': 'success',
            'data': statistics
        })
        
    except Exception as e:
        logger.error(f"获取统计信息失败: {str(e)}")
        return jsonify({
            'status': 'error', 
            'message': f'获取统计信息失败: {str(e)}'
        }), 500 