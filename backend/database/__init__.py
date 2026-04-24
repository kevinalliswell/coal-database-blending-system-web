#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
import json

logger = logging.getLogger(__name__)

class DatabaseManager:
    """数据库管理器 - 负责数据库连接和表结构初始化"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            # 默认数据库路径
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.db_path = os.path.join(base_dir, 'data', 'coal_system.db')
        else:
            self.db_path = db_path
        
        # 确保数据库目录存在
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # 初始化数据库
        self.init_database()
    
    def get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 允许通过列名访问
        return conn
    
    def init_database(self):
        """初始化数据库表结构"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 创建煤种数据表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS coal_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(100) NOT NULL UNIQUE,
                    type VARCHAR(50) NOT NULL,
                    price DECIMAL(10,2) NOT NULL,
                    calorific_value DECIMAL(8,2) NOT NULL,
                    ash_content DECIMAL(5,2) NOT NULL,
                    volatile_matter DECIMAL(5,2) NOT NULL,
                    fixed_carbon DECIMAL(5,2) NOT NULL,
                    total_sulfur DECIMAL(5,2) NOT NULL,
                    total_moisture DECIMAL(5,2),
                    air_dry_moisture DECIMAL(5,2),
                    supplier VARCHAR(100),
                    hgi DECIMAL(5,2),
                    burnout_rate DECIMAL(5,2),
                    carbon_content DECIMAL(5,2),
                    hydrogen_content DECIMAL(5,2),
                    nitrogen_content DECIMAL(5,2),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建优化历史记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS optimization_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp VARCHAR(20) NOT NULL,
                    coal_names TEXT NOT NULL,
                    optimal_ratios TEXT NOT NULL,
                    constraints TEXT NOT NULL,
                    total_price DECIMAL(10,2),
                    total_heat DECIMAL(8,2),
                    total_ash DECIMAL(5,2),
                    total_volatile DECIMAL(5,2),
                    total_fixed_carbon DECIMAL(5,2),
                    total_sulfur DECIMAL(5,2),
                    performance_price_ratio DECIMAL(10,4),
                    iterations INTEGER,
                    time_taken DECIMAL(10,6),
                    fitness_value DECIMAL(15,8),
                    constraints_satisfied BOOLEAN,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建上传文件记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS upload_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_filename VARCHAR(255) NOT NULL,
                    saved_filename VARCHAR(255) NOT NULL,
                    file_path VARCHAR(500) NOT NULL,
                    file_size INTEGER,
                    upload_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    processed BOOLEAN DEFAULT FALSE
                )
            ''')
            
            conn.commit()
            logger.info("数据库初始化完成")

class CoalDataManager:
    """煤种数据管理器 - 负责煤种数据的增删改查操作"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    def add_coal(self, coal_data: Dict[str, Any]) -> int:
        """添加煤种数据"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            sql = '''
                INSERT INTO coal_data (
                    name, type, price, calorific_value, ash_content,
                    volatile_matter, fixed_carbon, total_sulfur, total_moisture,
                    air_dry_moisture, supplier, hgi, burnout_rate,
                    carbon_content, hydrogen_content, nitrogen_content
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            '''
            
            values = (
                coal_data.get('name'),
                coal_data.get('type'),
                coal_data.get('price'),
                coal_data.get('calorific_value'),
                coal_data.get('ash_content'),
                coal_data.get('volatile_matter'),
                coal_data.get('fixed_carbon'),
                coal_data.get('total_sulfur'),
                coal_data.get('total_moisture'),
                coal_data.get('air_dry_moisture'),
                coal_data.get('supplier'),
                coal_data.get('hgi'),
                coal_data.get('burnout_rate'),
                coal_data.get('carbon_content'),
                coal_data.get('hydrogen_content'),
                coal_data.get('nitrogen_content')
            )
            
            cursor.execute(sql, values)
            conn.commit()
            return cursor.lastrowid
    
    def get_coals(self, page: int = 1, page_size: int = 10, 
                  search: str = '', coal_type: str = '') -> Dict[str, Any]:
        """获取煤种数据（支持分页和搜索）"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # 构建WHERE条件
            where_conditions = []
            params = []
            
            if search:
                where_conditions.append("(name LIKE ? OR type LIKE ?)")
                params.extend([f'%{search}%', f'%{search}%'])
            
            if coal_type:
                where_conditions.append("type = ?")
                params.append(coal_type)
            
            where_clause = ""
            if where_conditions:
                where_clause = "WHERE " + " AND ".join(where_conditions)
            
            # 获取总数
            count_sql = f"SELECT COUNT(*) FROM coal_data {where_clause}"
            cursor.execute(count_sql, params)
            total = cursor.fetchone()[0]
            
            # 获取分页数据
            offset = (page - 1) * page_size
            data_sql = f'''
                SELECT * FROM coal_data {where_clause}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            '''
            cursor.execute(data_sql, params + [page_size, offset])
            
            rows = cursor.fetchall()
            coals = [dict(row) for row in rows]
            
            return {
                'data': coals,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total': total,
                    'total_pages': max(1, (total + page_size - 1) // page_size) if page_size > 0 else 1
                }
            }
    
    def get_coal_by_id(self, coal_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取煤种数据"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM coal_data WHERE id = ?", (coal_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_coal_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """根据名称获取煤种数据"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM coal_data WHERE name = ?", (name,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_coals_by_names(self, coal_names: List[str]) -> List[Dict[str, Any]]:
        """根据煤种名称获取数据（用于优化算法）"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            placeholders = ','.join(['?'] * len(coal_names))
            sql = f"SELECT * FROM coal_data WHERE name IN ({placeholders})"
            cursor.execute(sql, coal_names)
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def update_coal(self, coal_id: int, coal_data: Dict[str, Any]) -> bool:
        """更新煤种数据"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            sql = '''
                UPDATE coal_data SET
                    name = ?, type = ?, price = ?, calorific_value = ?,
                    ash_content = ?, volatile_matter = ?, fixed_carbon = ?,
                    total_sulfur = ?, total_moisture = ?, air_dry_moisture = ?,
                    supplier = ?, hgi = ?, burnout_rate = ?, carbon_content = ?,
                    hydrogen_content = ?, nitrogen_content = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            '''
            
            values = (
                coal_data.get('name'),
                coal_data.get('type'),
                coal_data.get('price'),
                coal_data.get('calorific_value'),
                coal_data.get('ash_content'),
                coal_data.get('volatile_matter'),
                coal_data.get('fixed_carbon'),
                coal_data.get('total_sulfur'),
                coal_data.get('total_moisture'),
                coal_data.get('air_dry_moisture'),
                coal_data.get('supplier'),
                coal_data.get('hgi'),
                coal_data.get('burnout_rate'),
                coal_data.get('carbon_content'),
                coal_data.get('hydrogen_content'),
                coal_data.get('nitrogen_content'),
                coal_id
            )
            
            cursor.execute(sql, values)
            conn.commit()
            return cursor.rowcount > 0
    
    def delete_coals(self, coal_ids: List[int]) -> int:
        """批量删除煤种"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            placeholders = ','.join(['?'] * len(coal_ids))
            sql = f"DELETE FROM coal_data WHERE id IN ({placeholders})"
            
            cursor.execute(sql, coal_ids)
            conn.commit()
            return cursor.rowcount

class OptimizationHistoryManager:
    """优化历史记录管理器 - 负责优化结果的存储和查询"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    def save_optimization_result(self, result_data: Dict[str, Any]) -> int:
        """保存优化结果"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            sql = '''
                INSERT INTO optimization_history (
                    timestamp, coal_names, optimal_ratios, constraints,
                    total_price, total_heat, total_ash, total_volatile,
                    total_fixed_carbon, total_sulfur, performance_price_ratio,
                    iterations, time_taken, fitness_value, constraints_satisfied
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            '''
            
            values = (
                result_data.get('timestamp', datetime.now().strftime('%Y%m%d%H%M%S')),
                json.dumps(result_data.get('coal_names', []), ensure_ascii=False),
                json.dumps(result_data.get('optimal_ratios', [])),
                json.dumps(result_data.get('constraints', {}), ensure_ascii=False),
                result_data.get('total_price'),
                result_data.get('total_heat'),
                result_data.get('total_ash'),
                result_data.get('total_volatile'),
                result_data.get('total_fixed_carbon'),
                result_data.get('total_sulfur'),
                result_data.get('performance_price_ratio'),
                result_data.get('iterations'),
                result_data.get('time_taken'),
                result_data.get('fitness_value'),
                result_data.get('constraints_satisfied')
            )
            
            cursor.execute(sql, values)
            conn.commit()
            return cursor.lastrowid
    
    def get_optimization_history(self, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """获取优化历史记录"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # 获取总数
            cursor.execute("SELECT COUNT(*) FROM optimization_history")
            total = cursor.fetchone()[0]
            
            # 获取分页数据
            offset = (page - 1) * page_size
            sql = '''
                SELECT * FROM optimization_history
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            '''
            cursor.execute(sql, [page_size, offset])
            
            rows = cursor.fetchall()
            
            history = []
            for row in rows:
                record = dict(row)
                # 解析JSON字段
                try:
                    record['coal_names'] = json.loads(record['coal_names'])
                    record['optimal_ratios'] = json.loads(record['optimal_ratios'])
                    record['constraints'] = json.loads(record['constraints'])
                except json.JSONDecodeError as e:
                    logger.warning(f"解析历史记录JSON失败: {e}")
                    record['coal_names'] = []
                    record['optimal_ratios'] = []
                    record['constraints'] = {}
                
                history.append(record)
            
            return {
                'data': history,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total': total,
                    'total_pages': max(1, (total + page_size - 1) // page_size) if page_size > 0 else 1
                }
            }
    
    def get_optimization_by_id(self, history_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取优化历史记录"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM optimization_history WHERE id = ?", (history_id,))
            row = cursor.fetchone()
            
            if row:
                record = dict(row)
                # 解析JSON字段
                try:
                    record['coal_names'] = json.loads(record['coal_names'])
                    record['optimal_ratios'] = json.loads(record['optimal_ratios'])
                    record['constraints'] = json.loads(record['constraints'])
                except json.JSONDecodeError:
                    record['coal_names'] = []
                    record['optimal_ratios'] = []
                    record['constraints'] = {}
                
                return record
            
            return None

class UploadFileManager:
    """上传文件管理器 - 负责文件上传记录的管理"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    def record_upload(self, original_filename: str, saved_filename: str, 
                     file_path: str, file_size: int) -> int:
        """记录文件上传信息"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            sql = '''
                INSERT INTO upload_files (
                    original_filename, saved_filename, file_path, file_size
                ) VALUES (?, ?, ?, ?)
            '''
            
            cursor.execute(sql, (original_filename, saved_filename, file_path, file_size))
            conn.commit()
            return cursor.lastrowid
    
    def mark_as_processed(self, upload_id: int) -> bool:
        """标记文件为已处理"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE upload_files SET processed = TRUE WHERE id = ?", (upload_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def get_upload_history(self, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """获取上传历史"""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # 获取总数
            cursor.execute("SELECT COUNT(*) FROM upload_files")
            total = cursor.fetchone()[0]
            
            # 获取分页数据
            offset = (page - 1) * page_size
            sql = '''
                SELECT * FROM upload_files
                ORDER BY upload_time DESC
                LIMIT ? OFFSET ?
            '''
            cursor.execute(sql, [page_size, offset])
            
            rows = cursor.fetchall()
            uploads = [dict(row) for row in rows]
            
            return {
                'data': uploads,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total': total,
                    'total_pages': max(1, (total + page_size - 1) // page_size) if page_size > 0 else 1
                }
            } 