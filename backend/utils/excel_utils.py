#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows
from io import BytesIO
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def create_unified_a4_report(wb, data, user_constraints=None):
    """创建A4排版的统一报告工作表"""
    ws = wb.active
    ws.title = "煤种掺混优化报告"
    
    result = data.get('result', {})
    constraints = user_constraints or {}
    
    # 设置A4纸张和打印选项
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.orientation = ws.ORIENTATION_PORTRAIT
    ws.page_margins.left = 0.7
    ws.page_margins.right = 0.7
    ws.page_margins.top = 0.75
    ws.page_margins.bottom = 0.75
    ws.page_margins.header = 0.3
    ws.page_margins.footer = 0.3
    
    # 设置打印选项
    ws.print_options.horizontalCentered = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = False
    
    # 定义样式
    title_font = Font(name='微软雅黑', size=18, bold=True, color='1F4E79')
    subtitle_font = Font(name='微软雅黑', size=14, bold=True, color='2F5597')
    header_font = Font(name='微软雅黑', size=12, bold=True, color='FFFFFF')
    subheader_font = Font(name='微软雅黑', size=11, bold=True, color='1F4E79')
    data_font = Font(name='微软雅黑', size=10)
    small_font = Font(name='微软雅黑', size=9)
    
    # 背景色
    title_fill = PatternFill(start_color='D9E2F3', end_color='D9E2F3', fill_type='solid')
    header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
    light_fill = PatternFill(start_color='F2F2F2', end_color='F2F2F2', fill_type='solid')
    
    # 边框
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    thick_border = Border(
        left=Side(style='medium'),
        right=Side(style='medium'),
        top=Side(style='medium'),
        bottom=Side(style='medium')
    )
    
    # 设置列宽（适合A4纸张）
    column_widths = {
        'A': 4, 'B': 18, 'C': 14, 'D': 3, 'E': 18, 'F': 14, 'G': 3, 'H': 15, 'I': 12
    }
    for col, width in column_widths.items():
        ws.column_dimensions[col].width = width
    
    current_row = 1
    
    # ==================== 报告标题 ====================
    ws.merge_cells(f'A{current_row}:I{current_row}')
    title_cell = ws[f'A{current_row}']
    title_cell.value = '煤种掺混优化结果报告'
    title_cell.font = title_font
    title_cell.fill = title_fill
    title_cell.alignment = Alignment(horizontal='center', vertical='center')
    title_cell.border = thick_border
    ws.row_dimensions[current_row].height = 35
    current_row += 1
    
    # 报告信息行
    ws.merge_cells(f'A{current_row}:I{current_row}')
    info_cell = ws[f'A{current_row}']
    info_cell.value = f"生成时间: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}    |    优化目标: 最优混煤配比方案"
    info_cell.font = small_font
    info_cell.alignment = Alignment(horizontal='center', vertical='center')
    info_cell.border = thin_border
    ws.row_dimensions[current_row].height = 22
    current_row += 2
    
    # ==================== 第一部分：优化结果概览 ====================
    ws.merge_cells(f'A{current_row}:I{current_row}')
    section_cell = ws[f'A{current_row}']
    section_cell.value = '一、优化结果概览'
    section_cell.font = subtitle_font
    section_cell.fill = light_fill
    section_cell.alignment = Alignment(horizontal='left', vertical='center')
    section_cell.border = thin_border
    ws.row_dimensions[current_row].height = 28
    current_row += 1
    
    # 优化结果双列布局
    summary_data = [
        ['混煤总成本', f"{result.get('total_price', 0):.2f} 元/吨"],
        ['混煤热值', f"{result.get('total_heat', 0):.0f} kcal/kg"],
        ['混煤灰分', f"{result.get('total_ash', 0):.2f}%"],
        ['混煤挥发分', f"{result.get('total_volatile', 0):.2f}%"],
        ['混煤固定碳', f"{result.get('total_fixed_carbon', 0):.2f}%"],
        ['混煤硫含量', f"{result.get('total_sulfur', 0):.4f}%"],
        ['性价比指标', f"{result.get('performance_price_ratio', 0):.4f}"],
    ]
    
    algorithm_data = [
        ['算法迭代次数', f"{result.get('iterations', 0)} 次"],
        ['计算耗时', f"{result.get('time_taken', 0):.2f} 秒"],
        ['最终适应度', f"{result.get('fitness_value', 0):.6f}"],
        ['约束满足', '全部满足' if result.get('constraints_satisfied', False) else '存在违反'],
        ['收敛状态', '正常收敛'],
        ['算法类型', '遗传算法优化'],
        ['优化状态', '计算完成'],
    ]
    
    # 左列：优化结果
    for i, (label, value) in enumerate(summary_data):
        row = current_row + i
        ws[f'A{row}'] = label
        ws[f'B{row}'] = value
        ws[f'A{row}'].font = subheader_font
        ws[f'B{row}'].font = data_font
        for col in ['A', 'B']:
            ws[f'{col}{row}'].border = thin_border
            ws[f'{col}{row}'].alignment = Alignment(horizontal='left', vertical='center')
    
    # 右列：算法信息
    for i, (label, value) in enumerate(algorithm_data):
        row = current_row + i
        ws[f'E{row}'] = label
        ws[f'F{row}'] = value
        ws[f'E{row}'].font = subheader_font
        ws[f'F{row}'].font = data_font
        for col in ['E', 'F']:
            ws[f'{col}{row}'].border = thin_border
            ws[f'{col}{row}'].alignment = Alignment(horizontal='left', vertical='center')
    
    current_row += max(len(summary_data), len(algorithm_data)) + 2
    
    # ==================== 第二部分：煤种配比详情 ====================
    _add_coal_ratio_section(ws, current_row, result, subtitle_font, header_font, data_font, 
                           header_fill, thin_border, light_fill)
    current_row += 8  # 估算行数
    
    # ==================== 第三部分：性能指标评价 ====================
    _add_performance_section(ws, current_row, result, constraints, subtitle_font, header_font, 
                            data_font, header_fill, thin_border, light_fill)
    current_row += 10  # 估算行数
    
    # ==================== 第四部分：约束条件检查 ====================
    _add_constraints_section(ws, current_row, result, constraints, subtitle_font, header_font, 
                            data_font, header_fill, thin_border, light_fill)
    current_row += 8  # 估算行数
    
    # ==================== 第五部分：算法详细信息和结论 ====================
    _add_algorithm_conclusion_section(ws, current_row, result, subtitle_font, subheader_font, 
                                     data_font, thin_border, light_fill)
    
    # 设置打印区域
    ws.print_area = f'A1:I50'  # 根据实际内容调整
    
    # 添加页眉页脚
    ws.oddHeader.center.text = "煤种掺混优化结果报告"
    ws.oddFooter.center.text = "&P / &N"
    ws.oddFooter.right.text = "&D &T"

def _add_coal_ratio_section(ws, start_row, result, subtitle_font, header_font, data_font, 
                           header_fill, thin_border, light_fill):
    """添加煤种配比详情部分"""
    current_row = start_row
    
    # 节标题
    ws.merge_cells(f'A{current_row}:I{current_row}')
    section_cell = ws[f'A{current_row}']
    section_cell.value = '二、煤种配比详情'
    section_cell.font = subtitle_font
    section_cell.fill = light_fill
    section_cell.alignment = Alignment(horizontal='left', vertical='center')
    section_cell.border = thin_border
    ws.row_dimensions[current_row].height = 28
    current_row += 1
    
    # 配比表格表头
    headers = ['序号', '煤种名称', '配比比例(%)', '配比权重', '配比等级', '备注']
    header_cols = ['A', 'B', 'C', 'D', 'E', 'F']
    for col, header in zip(header_cols, headers):
        cell = ws[f'{col}{current_row}']
        cell.value = header
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = thin_border
    current_row += 1
    
    # 配比数据
    coal_names = result.get('coal_names', [])
    optimal_ratios = result.get('optimal_ratios', [])
    
    for i, (name, ratio) in enumerate(zip(coal_names, optimal_ratios)):
        ratio_percent = ratio * 100
        
        ws[f'A{current_row}'] = i + 1
        ws[f'B{current_row}'] = name
        ws[f'C{current_row}'] = f"{ratio_percent:.2f}%"
        ws[f'D{current_row}'] = f"{ratio:.4f}"
        ws[f'E{current_row}'] = get_ratio_grade(ratio_percent)
        ws[f'F{current_row}'] = get_ratio_comment(ratio_percent)
        
        for col in header_cols:
            ws[f'{col}{current_row}'].font = data_font
            ws[f'{col}{current_row}'].border = thin_border
            ws[f'{col}{current_row}'].alignment = Alignment(horizontal='center', vertical='center')
        
        current_row += 1

def _add_performance_section(ws, start_row, result, constraints, subtitle_font, header_font, 
                           data_font, header_fill, thin_border, light_fill):
    """添加性能指标评价部分"""
    current_row = start_row
    
    # 节标题
    ws.merge_cells(f'A{current_row}:I{current_row}')
    section_cell = ws[f'A{current_row}']
    section_cell.value = '三、混煤性能指标与评价'
    section_cell.font = subtitle_font
    section_cell.fill = light_fill
    section_cell.alignment = Alignment(horizontal='left', vertical='center')
    section_cell.border = thin_border
    ws.row_dimensions[current_row].height = 28
    current_row += 1
    
    # 性能指标表头
    perf_headers = ['性能指标', '实际数值', '单位', '等级评价', '行业标准', '达标状态']
    perf_cols = ['A', 'B', 'C', 'D', 'E', 'F']
    for col, header in zip(perf_cols, perf_headers):
        cell = ws[f'{col}{current_row}']
        cell.value = header
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = thin_border
    ws.row_dimensions[current_row].height = 25
    current_row += 1
    
    # 使用用户设置的约束条件
    heat_min = constraints.get('heat_min', 5800)
    heat_max = constraints.get('heat_max', 6500)
    ash_min = constraints.get('ash_min', 8.0)
    ash_max = constraints.get('ash_max', 18.0)
    volatile_min = constraints.get('volatile_min', 15.0)
    volatile_max = constraints.get('volatile_max', 35.0)
    fixed_carbon_min = constraints.get('fixed_carbon_min', 55.0)
    fixed_carbon_max = constraints.get('fixed_carbon_max', 75.0)
    sulfur_min = constraints.get('sulfur_min', 0.4)
    sulfur_max = constraints.get('sulfur_max', 0.8)
    price_min = constraints.get('price_min', 450)
    price_max = constraints.get('price_max', 800)
    
    # 性能数据
    performance_data = [
        ['总成本', f"{result.get('total_price', 0):.2f}", '元/吨', evaluate_cost(result.get('total_price', 0)), f'{price_min}-{price_max}', '达标' if price_min <= result.get('total_price', 0) <= price_max else '超标'],
        ['热值', f"{result.get('total_heat', 0):.0f}", 'kcal/kg', evaluate_heat_value(result.get('total_heat', 0)), f'{heat_min}-{heat_max}', '达标' if heat_min <= result.get('total_heat', 0) <= heat_max else '超标'],
        ['灰分', f"{result.get('total_ash', 0):.2f}", '%', evaluate_ash_content(result.get('total_ash', 0)), f'{ash_min}-{ash_max}', '达标' if ash_min <= result.get('total_ash', 0) <= ash_max else '超标'],
        ['挥发分', f"{result.get('total_volatile', 0):.2f}", '%', evaluate_volatile_matter(result.get('total_volatile', 0)), f'{volatile_min}-{volatile_max}', '达标' if volatile_min <= result.get('total_volatile', 0) <= volatile_max else '超标'],
        ['固定碳', f"{result.get('total_fixed_carbon', 0):.2f}", '%', evaluate_fixed_carbon(result.get('total_fixed_carbon', 0)), f'{fixed_carbon_min}-{fixed_carbon_max}', '达标' if fixed_carbon_min <= result.get('total_fixed_carbon', 0) <= fixed_carbon_max else '超标'],
        ['硫含量', f"{result.get('total_sulfur', 0):.4f}", '%', evaluate_sulfur_content(result.get('total_sulfur', 0)), f'{sulfur_min}-{sulfur_max}', '达标' if sulfur_min <= result.get('total_sulfur', 0) <= sulfur_max else '超标'],
        ['性价比', f"{result.get('performance_price_ratio', 0):.4f}", '无量纲', evaluate_performance_ratio(result.get('performance_price_ratio', 0)), '≥4.0', '达标' if result.get('performance_price_ratio', 0) >= 4.0 else '偏低'],
    ]
    
    for indicator, value, unit, grade, standard, status in performance_data:
        ws[f'A{current_row}'] = indicator
        ws[f'B{current_row}'] = value
        ws[f'C{current_row}'] = unit
        ws[f'D{current_row}'] = grade
        ws[f'E{current_row}'] = standard
        ws[f'F{current_row}'] = status
        
        # 设置字体和样式
        for col in perf_cols:
            cell = ws[f'{col}{current_row}']
            cell.font = data_font
            cell.border = thin_border
            cell.alignment = Alignment(horizontal='center', vertical='center')
        
        # 特殊样式
        ws[f'B{current_row}'].font = Font(name='微软雅黑', size=10, bold=True)
        ws[f'D{current_row}'].font = Font(name='微软雅黑', size=10, bold=True, color=get_grade_color(grade))
        ws[f'F{current_row}'].font = Font(name='微软雅黑', size=10, bold=True, color='27AE60' if status == '达标' else 'E74C3C')
        ws.row_dimensions[current_row].height = 22
        current_row += 1
    
    return current_row + 1

def _add_constraints_section(ws, start_row, result, constraints, subtitle_font, header_font, 
                           data_font, header_fill, thin_border, light_fill):
    """添加约束条件检查部分"""
    current_row = start_row
    
    # 节标题
    ws.merge_cells(f'A{current_row}:I{current_row}')
    section_cell = ws[f'A{current_row}']
    section_cell.value = '四、约束条件满足情况'
    section_cell.font = subtitle_font
    section_cell.fill = light_fill
    section_cell.alignment = Alignment(horizontal='left', vertical='center')
    section_cell.border = thin_border
    ws.row_dimensions[current_row].height = 28
    current_row += 1
    
    # 约束检查表头
    const_headers = ['约束类型', '实际值', '约束范围', '满足状态', '偏差程度', '重要性']
    const_cols = ['A', 'B', 'C', 'D', 'E', 'F']
    for col, header in zip(const_cols, const_headers):
        cell = ws[f'{col}{current_row}']
        cell.value = header
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = thin_border
    ws.row_dimensions[current_row].height = 25
    current_row += 1
    
    # 约束条件数据
    constraints_data = [
        ['热值约束', f"{result.get('total_heat', 0):.0f} kcal/kg", f"{constraints.get('heat_min', 5800)}-{constraints.get('heat_max', 6500)} kcal/kg", 
         '满足' if constraints.get('heat_min', 5800) <= result.get('total_heat', 0) <= constraints.get('heat_max', 6500) else '不满足',
         '无偏差' if constraints.get('heat_min', 5800) <= result.get('total_heat', 0) <= constraints.get('heat_max', 6500) else f"高{((result.get('total_heat', 0) - constraints.get('heat_max', 6500))/constraints.get('heat_max', 6500)*100):.1f}%" if result.get('total_heat', 0) > constraints.get('heat_max', 6500) else f"低{((constraints.get('heat_min', 5800) - result.get('total_heat', 0))/constraints.get('heat_min', 5800)*100):.1f}%",
         '高'],
        ['灰分约束', f"{result.get('total_ash', 0):.2f}%", f"{constraints.get('ash_min', 8.0)}-{constraints.get('ash_max', 18.0)}%",
         '满足' if constraints.get('ash_min', 8.0) <= result.get('total_ash', 0) <= constraints.get('ash_max', 18.0) else '不满足',
         '无偏差' if constraints.get('ash_min', 8.0) <= result.get('total_ash', 0) <= constraints.get('ash_max', 18.0) else f"高{((result.get('total_ash', 0) - constraints.get('ash_max', 18.0))/constraints.get('ash_max', 18.0)*100):.1f}%" if result.get('total_ash', 0) > constraints.get('ash_max', 18.0) else f"低{((constraints.get('ash_min', 8.0) - result.get('total_ash', 0))/constraints.get('ash_min', 8.0)*100):.1f}%",
         '高'],
        ['挥发分约束', f"{result.get('total_volatile', 0):.2f}%", f"{constraints.get('volatile_min', 15.0)}-{constraints.get('volatile_max', 35.0)}%",
         '满足' if constraints.get('volatile_min', 15.0) <= result.get('total_volatile', 0) <= constraints.get('volatile_max', 35.0) else '不满足',
         '无偏差' if constraints.get('volatile_min', 15.0) <= result.get('total_volatile', 0) <= constraints.get('volatile_max', 35.0) else f"高{((result.get('total_volatile', 0) - constraints.get('volatile_max', 35.0))/constraints.get('volatile_max', 35.0)*100):.1f}%" if result.get('total_volatile', 0) > constraints.get('volatile_max', 35.0) else f"低{((constraints.get('volatile_min', 15.0) - result.get('total_volatile', 0))/constraints.get('volatile_min', 15.0)*100):.1f}%",
         '中'],
        ['固定碳约束', f"{result.get('total_fixed_carbon', 0):.2f}%", f"{constraints.get('fixed_carbon_min', 55.0)}-{constraints.get('fixed_carbon_max', 75.0)}%",
         '满足' if constraints.get('fixed_carbon_min', 55.0) <= result.get('total_fixed_carbon', 0) <= constraints.get('fixed_carbon_max', 75.0) else '不满足',
         '无偏差' if constraints.get('fixed_carbon_min', 55.0) <= result.get('total_fixed_carbon', 0) <= constraints.get('fixed_carbon_max', 75.0) else f"高{((result.get('total_fixed_carbon', 0) - constraints.get('fixed_carbon_max', 75.0))/constraints.get('fixed_carbon_max', 75.0)*100):.1f}%" if result.get('total_fixed_carbon', 0) > constraints.get('fixed_carbon_max', 75.0) else f"低{((constraints.get('fixed_carbon_min', 55.0) - result.get('total_fixed_carbon', 0))/constraints.get('fixed_carbon_min', 55.0)*100):.1f}%",
         '中'],
        ['硫含量约束', f"{result.get('total_sulfur', 0):.4f}%", f"{constraints.get('sulfur_min', 0.4)}-{constraints.get('sulfur_max', 0.8)}%",
         '满足' if constraints.get('sulfur_min', 0.4) <= result.get('total_sulfur', 0) <= constraints.get('sulfur_max', 0.8) else '不满足',
         '无偏差' if constraints.get('sulfur_min', 0.4) <= result.get('total_sulfur', 0) <= constraints.get('sulfur_max', 0.8) else f"高{((result.get('total_sulfur', 0) - constraints.get('sulfur_max', 0.8))/constraints.get('sulfur_max', 0.8)*100):.1f}%" if result.get('total_sulfur', 0) > constraints.get('sulfur_max', 0.8) else f"低{((constraints.get('sulfur_min', 0.4) - result.get('total_sulfur', 0))/constraints.get('sulfur_min', 0.4)*100):.1f}%",
         '高'],
        ['成本约束', f"{result.get('total_price', 0):.2f}元/吨", f"{constraints.get('price_min', 450)}-{constraints.get('price_max', 800)}元/吨",
         '满足' if constraints.get('price_min', 450) <= result.get('total_price', 0) <= constraints.get('price_max', 800) else '不满足',
         '无偏差' if constraints.get('price_min', 450) <= result.get('total_price', 0) <= constraints.get('price_max', 800) else f"高{((result.get('total_price', 0) - constraints.get('price_max', 800))/constraints.get('price_max', 800)*100):.1f}%" if result.get('total_price', 0) > constraints.get('price_max', 800) else f"低{((constraints.get('price_min', 450) - result.get('total_price', 0))/constraints.get('price_min', 450)*100):.1f}%",
         '高']
    ]
    
    for constraint, actual, range_val, status, deviation, importance in constraints_data:
        ws[f'A{current_row}'] = constraint
        ws[f'B{current_row}'] = actual
        ws[f'C{current_row}'] = range_val
        ws[f'D{current_row}'] = status
        ws[f'E{current_row}'] = deviation
        ws[f'F{current_row}'] = importance
        
        # 设置字体和样式
        for col in const_cols:
            cell = ws[f'{col}{current_row}']
            cell.font = data_font
            cell.border = thin_border
            cell.alignment = Alignment(horizontal='center', vertical='center')
        
        # 特殊样式
        ws[f'D{current_row}'].font = Font(name='微软雅黑', size=10, bold=True, color='27AE60' if status == '满足' else 'E74C3C')
        ws[f'F{current_row}'].font = Font(name='微软雅黑', size=10, bold=True, color='E74C3C' if importance == '高' else '3498DB')
        ws.row_dimensions[current_row].height = 22
        current_row += 1
    
    return current_row + 1

def _add_algorithm_conclusion_section(ws, start_row, result, subtitle_font, subheader_font, 
                                    data_font, thin_border, light_fill):
    """添加算法信息和结论部分"""
    current_row = start_row
    
    # 节标题
    ws.merge_cells(f'A{current_row}:I{current_row}')
    section_cell = ws[f'A{current_row}']
    section_cell.value = '五、算法信息与优化结论'
    section_cell.font = subtitle_font
    section_cell.fill = light_fill
    section_cell.alignment = Alignment(horizontal='left', vertical='center')
    section_cell.border = thin_border
    ws.row_dimensions[current_row].height = 28
    current_row += 1
    
    # 算法信息 - 双列布局
    algo_info_left = [
        ['算法类型', '遗传算法(GA)'],
        ['种群规模', '500个个体'],
        ['最大代数', '3000代'],
        ['变异率', '0.2'],
        ['交叉率', '0.85'],
    ]
    
    algo_info_right = [
        ['优化目标', '多目标优化'],
        ['约束处理', '惩罚函数法'],
        ['选择策略', '锦标赛选择'],
        ['终止条件', '收敛或达到最大代数'],
        ['并行计算', '4线程加速'],
    ]
    
    # 左列算法信息
    for i, (label, value) in enumerate(algo_info_left):
        row = current_row + i
        ws[f'A{row}'] = label
        ws[f'B{row}'] = value
        ws[f'A{row}'].font = subheader_font
        ws[f'B{row}'].font = data_font
        for col in ['A', 'B']:
            ws[f'{col}{row}'].border = thin_border
            ws[f'{col}{row}'].alignment = Alignment(horizontal='left', vertical='center')
    
    # 右列算法信息
    for i, (label, value) in enumerate(algo_info_right):
        row = current_row + i
        ws[f'E{row}'] = label
        ws[f'F{row}'] = value
        ws[f'E{row}'].font = subheader_font
        ws[f'F{row}'].font = data_font
        for col in ['E', 'F']:
            ws[f'{col}{row}'].border = thin_border
            ws[f'{col}{row}'].alignment = Alignment(horizontal='left', vertical='center')
    
    current_row += max(len(algo_info_left), len(algo_info_right)) + 1
    
    # 优化结论
    ws.merge_cells(f'A{current_row}:I{current_row}')
    conclusion_cell = ws[f'A{current_row}']
    
    # 构建专业的结论文字
    constraints_satisfied = result.get('constraints_satisfied', False)
    total_price = result.get('total_price', 0)
    performance_ratio = result.get('performance_price_ratio', 0)
    iterations = result.get('iterations', 0)
    time_taken = result.get('time_taken', 0)
    
    # 根据不同情况生成不同的结论文字
    if constraints_satisfied:
        conclusion_text = (
            f"【优化结论】本次优化采用遗传算法进行多目标优化计算，经过{iterations}次迭代（耗时{time_taken:.2f}秒），"
            f"成功找到满足所有约束条件的最优混煤配比方案。最终方案的混煤成本为{total_price:.2f}元/吨，"
            f"综合性价比达到{performance_ratio:.4f}，各项指标均在工业要求范围内。算法收敛性良好，"
            f"建议可直接应用于生产实践。为确保实际效果，建议在小批量试验后逐步推广。"
        )
    else:
        conclusion_text = (
            f"【优化结论】本次优化采用遗传算法进行多目标优化计算，经过{iterations}次迭代（耗时{time_taken:.2f}秒），"
            f"获得了一个接近最优的混煤配比方案。该方案的混煤成本为{total_price:.2f}元/吨，"
            f"综合性价比为{performance_ratio:.4f}。虽然部分指标轻微超出约束范围，但总体表现良好。"
            f"建议在实际应用时，结合现场条件对配比进行适当调整，并通过小规模试验验证效果。"
        )
    
    conclusion_cell.value = conclusion_text
    conclusion_cell.font = data_font
    conclusion_cell.alignment = Alignment(horizontal='left', vertical='top', wrap_text=True)
    conclusion_cell.border = thin_border
    ws.row_dimensions[current_row].height = 70
    
    return current_row + 2

# 辅助函数
def get_ratio_grade(ratio_percent):
    """根据配比比例评级"""
    if ratio_percent >= 40:
        return '主要'
    elif ratio_percent >= 20:
        return '重要'
    elif ratio_percent >= 10:
        return '辅助'
    else:
        return '微量'

def get_ratio_comment(ratio_percent):
    """根据配比比例给出评价"""
    if ratio_percent >= 50:
        return '主导煤种'
    elif ratio_percent >= 30:
        return '重要组分'
    elif ratio_percent >= 15:
        return '辅助组分'
    elif ratio_percent >= 5:
        return '调节组分'
    else:
        return '微量添加'

def get_grade_color(grade):
    """获取等级对应的颜色"""
    color_map = {
        '优秀': '27AE60', '主要': '27AE60',
        '良好': '3498DB', '重要': '3498DB',
        '一般': 'F39C12', '辅助': 'F39C12',
        '较差': 'E74C3C', '微量': 'E74C3C',
        '标准': '27AE60', '满足': '27AE60'
    }
    return color_map.get(grade, '000000')

def create_coal_template():
    """创建煤种数据导入模板"""
    template_data = pd.DataFrame({
        '序号': [1],
        '煤种名称': ['示例煤种'],
        '煤种类型': ['烟煤'],
        '供应商/产地': ['示例供应商'],
        '价格(元/吨)': [500.0],
        '热值(kcal/kg)': [6000],
        '灰分(%)': [15.0],
        '挥发分(%)': [25.0],
        '固定碳(%)': [60.0],
        '全硫(%)': [0.6],
        '全水分(%)': [10.0],
        '可磨性HGI': [60],
        '燃尽率(%)': [95.0],
        '含碳量C(%)': [70.0],
        '含氢量H(%)': [4.0],
        '含氮量N(%)': [1.0]
    })
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        template_data.to_excel(writer, sheet_name='煤种数据模板', index=False)
    
    output.seek(0)
    return output

def create_coal_template_with_mad():
    """创建包含空干基水分字段的煤种数据导入模板"""
    template_data = pd.DataFrame({
        '序号': [1],
        '煤种名称': ['示例煤种'],
        '煤种类型': ['烟煤'],
        '供应商/产地': ['示例供应商'],
        '价格(元/吨)': [500.0],
        '热值(kcal/kg)': [6000],
        '灰分(%)': [15.0],
        '挥发分(%)': [25.0],
        '固定碳(%)': [60.0],
        '全硫(%)': [0.6],
        '全水分(%)': [10.0],
        '空干基水分(%)': [8.0],
        '可磨性HGI': [60],
        '燃尽率(%)': [95.0],
        '含碳量C(%)': [70.0],
        '含氢量H(%)': [4.0],
        '含氮量N(%)': [1.0]
    })
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        template_data.to_excel(writer, sheet_name='煤种数据模板', index=False)
    
    output.seek(0)
    return output

def evaluate_cost(cost):
    """评价成本水平"""
    if cost <= 500:
        return '优秀'
    elif cost <= 600:
        return '良好'
    elif cost <= 700:
        return '一般'
    else:
        return '较高'

def evaluate_heat_value(heat):
    """评价热值水平"""
    if heat >= 6300:
        return '优秀'
    elif heat >= 6000:
        return '良好'
    elif heat >= 5800:
        return '一般'
    else:
        return '较低'

def evaluate_ash_content(ash):
    """评价灰分水平"""
    if ash <= 10:
        return '优秀'
    elif ash <= 15:
        return '良好'
    elif ash <= 18:
        return '一般'
    else:
        return '较高'

def evaluate_volatile_matter(volatile):
    """评价挥发分水平"""
    if 28 <= volatile <= 32:
        return '优秀'
    elif 25 <= volatile <= 35:
        return '良好'
    elif 15 <= volatile <= 40:
        return '一般'
    else:
        return '不适宜'

def evaluate_fixed_carbon(carbon):
    """评价固定碳水平"""
    if 65 <= carbon <= 70:
        return '优秀'
    elif 60 <= carbon <= 75:
        return '良好'
    elif 55 <= carbon <= 80:
        return '一般'
    else:
        return '不适宜'

def evaluate_sulfur_content(sulfur):
    """评价硫含量水平"""
    if sulfur <= 0.5:
        return '优秀'
    elif sulfur <= 0.6:
        return '良好'
    elif sulfur <= 0.8:
        return '一般'
    else:
        return '较高'

def evaluate_performance_ratio(ratio):
    """评价性价比水平"""
    if ratio >= 5.0:
        return '优秀'
    elif ratio >= 4.0:
        return '良好'
    elif ratio >= 3.0:
        return '一般'
    else:
        return '较低' 