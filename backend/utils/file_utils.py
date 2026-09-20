#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import pandas as pd
from uuid import uuid4
import logging

logger = logging.getLogger(__name__)

def allowed_file(filename, allowed_extensions=None):
    """检查文件扩展名是否合法"""
    if allowed_extensions is None:
        allowed_extensions = {'csv', 'xlsx', 'xls'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def safe_read_csv(file_path):
    """安全读取CSV文件，自动处理编码问题"""
    try:
        return pd.read_csv(file_path, encoding='utf-8', keep_default_na=False)
    except UnicodeDecodeError:
        return pd.read_csv(file_path, encoding='gbk', keep_default_na=False)

def safe_read_excel(file_path):
    """安全读取Excel文件，尝试多种引擎"""
    try:
        return pd.read_excel(file_path, engine='openpyxl', keep_default_na=False)
    except Exception:
        try:
            return pd.read_excel(file_path, engine='xlrd', keep_default_na=False)
        except Exception:
            return pd.read_excel(file_path, keep_default_na=False)

def save_uploaded_file(file, upload_folder):
    """保存上传的文件，返回保存路径"""
    if not file or file.filename == '':
        raise ValueError('没有选择文件')
    
    if not allowed_file(file.filename):
        raise ValueError('不允许的文件类型')
    
    # A non-ASCII basename can be erased by secure_filename, including the dot.
    # Keep only the already-allowlisted extension and generate our own basename.
    extension = file.filename.rsplit('.', 1)[1].lower()
    saved_filename = f'{uuid4().hex}.{extension}'
    file_path = os.path.join(upload_folder, saved_filename)
    file.save(file_path)
    
    return file_path, saved_filename

def read_uploaded_file(file_path):
    """读取上传的文件（CSV或Excel）"""
    filename = os.path.basename(file_path)
    
    if filename.lower().endswith('.csv'):
        return safe_read_csv(file_path)
    else:  # Excel文件
        return safe_read_excel(file_path)

def validate_coal_data_format(df):
    """验证煤种数据文件格式"""
    required_columns = [
        '煤种名称', '煤种类型', '价格(元/吨)', '热值(kcal/kg)', 
        '灰分(%)', '挥发分(%)', '固定碳(%)', '全硫(%)'
    ]
    
    # 可选字段（不强制要求）
    optional_columns = [
        '供应商/产地', '全水分(%)', '空干基水分(%)', '可磨性HGI', 
        '燃尽率(%)', '含碳量C(%)', '含氢量H(%)', '含氮量N(%)'
    ]
    
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f'文件格式不正确，缺少以下必需列: {", ".join(missing_columns)}')
    
    # 检查数据类型和有效性
    for index, row in df.iterrows():
        # 检查必需字段是否为空
        for col in required_columns:
            if pd.isna(row[col]) or str(row[col]).strip() == '':
                raise ValueError(f'第{index+1}行的{col}字段不能为空')
        
        # 检查数值字段的有效性
        numeric_fields = ['价格(元/吨)', '热值(kcal/kg)', '灰分(%)', '挥发分(%)', '固定碳(%)', '全硫(%)']
        for field in numeric_fields:
            if field in df.columns:
                try:
                    value = float(row[field])
                    if value < 0:
                        raise ValueError(f'第{index+1}行的{field}不能为负数')
                except (ValueError, TypeError):
                    raise ValueError(f'第{index+1}行的{field}必须是有效数字')
    
    return True

def merge_coal_data(new_df, existing_df):
    """合并新的煤种数据到现有数据中"""
    if len(existing_df) > 0:
        # 生成新的序号
        max_id = existing_df['序号'].max() if '序号' in existing_df.columns else 0
        if '序号' not in new_df.columns:
            new_df['序号'] = range(max_id + 1, max_id + 1 + len(new_df))
        else:
            new_df['序号'] = range(max_id + 1, max_id + 1 + len(new_df))
        
        # 合并数据
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
    else:
        # 如果没有现有数据，生成序号
        if '序号' not in new_df.columns:
            new_df['序号'] = range(1, len(new_df) + 1)
        combined_df = new_df
    
    return combined_df
