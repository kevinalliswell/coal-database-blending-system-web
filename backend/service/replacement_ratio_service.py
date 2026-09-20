#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
理论置换比计算模块

本模块提供计算理论置换比的功能，基于冶金理论中的置换比算法。
置换比计算公式为:
B = (C煤 + C_H - C煤灰 - C分) / (C焦 - C焦灰)
其中:
C煤: 煤粉含碳量(包括挥发份的碳)
C_H: 煤粉中氢参加还原而节约的碳量
C煤灰: 煤粉中灰分造渣所消耗的碳
C分: 煤粉分解热和加热至1500°C物理热所消耗的碳
C焦: 焦炭含碳量
C焦灰: 焦炭中灰分造渣所消耗的碳

同时提供实际置换比计算功能，基于高炉生产实践数据计算。
"""

from typing import Dict, Tuple, Optional, Union, Any, List
import logging
import math
from dataclasses import dataclass

# 设置日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class CoalParameters:
    """煤粉相关参数数据类"""
    carbon_content: float  # 煤粉含碳量
    hydrogen_content: float  # 煤粉中氢含量
    ash_content: float  # 煤粉中灰分含量
    sio2_content: float  # 灰分中SiO₂含量
    decomposition_heat: float = 240.0  # 内核热耗统一 kcal_IT/kg 干煤；API不使用此默认值
    physical_heat: float = 480.0  # 加热至1500°C物理热，kcal_IT/kg 干煤；API须显式提供


@dataclass
class CokeParameters:
    """焦炭相关参数数据类"""
    carbon_content: float  # 焦炭含碳量
    ash_content: float  # 焦炭中灰分含量
    sio2_content: float  # 灰分中SiO₂含量


@dataclass
class BlastFurnaceParameters:
    """高炉工艺相关参数数据类"""
    eta_co: float # 煤气利用率, gas utilization rate
    slag_basicity: float  # 炉渣碱度
    slag_enthalpy: float  # 炉渣热焓
    wind_temperature: float = 1200.0  # 风温，默认为1200°C
    hot_blast_enthalpy: Optional[float] = None  # 实测鼓风热焓 kJ/m³；None 时按风温估算
    carbon_incomplete_combustion_heat: float = 9794.0  # 碳不完全燃烧热，默认为9794kJ/kg
    carbon_heating_heat: float = 2758.0  # 焦炭里的1kg炭加热至1500°C的热量，默认为2758kJ/kg


class ReplacementRatioCalculator:
    """理论置换比计算器类"""

    def __init__(
            self,
            coal_params: CoalParameters,
            coke_params: CokeParameters,
            blast_furnace_params: BlastFurnaceParameters
    ):
        """
        初始化置换比计算器

        参数:
            coal_params: 煤粉相关参数
            coke_params: 焦炭相关参数
            blast_furnace_params: 高炉工艺相关参数
        """
        self.coal = coal_params
        self.coke = coke_params
        self.blast_furnace = blast_furnace_params
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def effective_hot_blast_enthalpy(self) -> float:
        """Return supplied kJ/m³, or the existing 1.3*T engineering estimate."""
        supplied = self.blast_furnace.hot_blast_enthalpy
        value = self.blast_furnace.wind_temperature if supplied is None else supplied
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError('风温或实测鼓风热焓必须为非负有限数值')
        return 1.3 * value if supplied is None else value

    def calculate_carbon_burning_heat(self, air_volume: float = 1.2) -> float:
        """
        计算1kg碳在风口前燃烧产生的**净有效热量**, 单位: kJ/kg

        计算原理:
        有效热 = (鼓风带入热 + 碳不完全燃烧放热) - 碳自身加热耗热

        参数:
            air_volume: 1kg碳在风口燃烧所需的风量，默认为1.2m³/kg

        返回:
            1kg碳在风口前燃烧产生的净有效热量，单位: kJ/kg
        """
        # 修正计算方法：
        # 1. 鼓风带入热量 = 风量 × 鼓风焓值 (kJ/m³ × m³/kg = kJ/kg)
        # 2. 碳燃烧可用热 = 鼓风带入热量 + 碳不完全燃烧热 - 碳加热至反应温度所需热量
        
        # 计算鼓风焓值 (基于温度的焓值计算)
        # 鼓风焓值 ≈ 1.3 × 温度 (kJ/m³·°C)，这是空气的平均比热容
        blast_enthalpy_per_m3 = self.effective_hot_blast_enthalpy()  # kJ/m³
        
        # 鼓风带入的热量
        blast_heat = air_volume * blast_enthalpy_per_m3
        
        # 总燃烧热 (修正: 碳加热热应为能量消耗，因此是减项)
        heat = (
            blast_heat +  # 鼓风带入热量
            self.blast_furnace.carbon_incomplete_combustion_heat -  # 碳不完全燃烧放热
            self.blast_furnace.carbon_heating_heat  # 碳加热消耗热
        )
        
        self.logger.debug(f"计算的1kg碳在风口前燃烧产生的净有效热量: {heat} kJ/kg")
        self.logger.debug(f"计算过程: 鼓风热={blast_heat}, 不完全燃烧热={self.blast_furnace.carbon_incomplete_combustion_heat}, 碳加热消耗热={self.blast_furnace.carbon_heating_heat}")
        return heat

    def calculate_hydrogen_saving_carbon_percentage(self) -> float:
        """
        计算煤粉中氢参加还原而节约的碳量，单位: %
        
        公式: CH = HL * ȠH * (xC/xH2 + QH2(d)/QC)
        其中:
            HL: 煤粉中氢的含量，单位: %
            ȠH: 氢气利用率
            xC_xH2: 6－氢参加直接还原代替的碳量(=12/2)
            QH2(d): 氢气参加直接还原替代的热量，一般取62222kJ/kg
            QC: 1kg碳在风口前燃烧产生的热量，单位: kJ/kg

        返回:
            煤粉中氢参加还原而节约的碳量，单位: %
        """
        # 计算煤气利用率 (CO2/(CO2+CO)) is now directly provided
        eta_co = self.blast_furnace.eta_co
        
        # 计算氢气利用率 - 修正经验公式，增加边界检查
        # 原公式：eta_h = 1.41 * eta_co - 1.07 * eta_co^2
        # 修正：增加物理意义检查和边界限制
        eta_h_raw = 1.41 * eta_co - 1.07 * eta_co ** 2
        
        # 氢气利用率不能超过1.0，也不能小于0
        eta_h = max(0.0, min(1.0, eta_h_raw))
        
        # 如果计算值超出合理范围，给出警告
        if eta_h_raw != eta_h:
            self.logger.warning(f"氢气利用率计算值 {eta_h_raw:.4f} 超出合理范围，已修正为 {eta_h:.4f}")
        
        # 氢参加直接还原代替的碳量 (原子量比: C:12, H2:2)
        xc_xh2 = 12 / 2  # = 6
        
        # 氢气参加直接还原替代的热量，一般取62222kJ/kg
        qh2_d = 62222  # kJ/kg
        
        # 计算1kg碳在风口前燃烧产生的热量
        qc = self.calculate_carbon_burning_heat()
        
        # 验证计算参数的合理性
        if qc <= 0:
            self.logger.error("碳燃烧热计算结果异常，无法计算氢节约碳量")
            raise ValueError("碳燃烧热计算结果异常")
        
        # 计算煤粉中氢参加还原而节约的碳量
        ch = self.coal.hydrogen_content * eta_h * (xc_xh2 + qh2_d / qc)
        
        self.logger.debug(f"煤粉中氢参加还原而节约的碳量CH: {ch:.6f}%")
        self.logger.debug(f"计算过程: HL={self.coal.hydrogen_content:.4f}, ȠCO={eta_co:.4f}, ȠH={eta_h:.4f}, xC_xH2={xc_xh2}, QH2_d={qh2_d}, QC={qc:.2f}")
        
        return ch

    def calculate_carbon_consumed_by_slag(self, ash_content: float, sio2_content: float) -> float:
        """
        计算灰分造渣所消耗的碳

        计算原理：
        1. 灰分造渣需要消耗热量来熔化和形成炉渣
        2. 炉渣碱度影响造渣过程的热需求
        3. SiO₂含量高的灰分需要更多的热量来调节碱度
        4. 所消耗的热量需要转换为等效的碳消耗量

        公式: C_slag = Ash × (1 + SiO₂ × R) × H_slag / Q_C
        其中:
        Ash: 灰分含量 (%)
        SiO₂: 灰分中SiO₂含量 (%)
        R: 炉渣碱度
        H_slag: 炉渣热焓 (kJ/kg)
        Q_C: 1kg碳燃烧产生的热量 (kJ/kg)

        参数:
            ash_content: 灰分含量 (%)
            sio2_content: 灰分中SiO₂含量 (%)

        返回:
            灰分造渣所消耗的碳，单位: %
        """
        # 参数验证
        if ash_content < 0 or ash_content > 1:
            self.logger.warning(f"灰分含量 {ash_content} 超出合理范围 [0, 1]")
        
        if sio2_content < 0 or sio2_content > 1:
            self.logger.warning(f"SiO₂含量 {sio2_content} 超出合理范围 [0, 1]")
        
        if self.blast_furnace.slag_basicity <= 0:
            self.logger.error("炉渣碱度必须大于0")
            raise ValueError("炉渣碱度必须大于0")
        
        # 计算1kg碳在风口前燃烧产生的热量
        carbon_burning_heat = self.calculate_carbon_burning_heat()
        
        if carbon_burning_heat <= 0:
            self.logger.error("碳燃烧热计算结果异常")
            raise ValueError("碳燃烧热计算结果异常")
        
        # 计算造渣系数：考虑SiO₂含量和炉渣碱度的影响
        slag_factor = 1 + sio2_content * self.blast_furnace.slag_basicity
        
        # 计算灰分造渣所消耗的碳
        carbon_consumed = (
            ash_content * 
            slag_factor * 
            self.blast_furnace.slag_enthalpy / 
            carbon_burning_heat
        )
        
        self.logger.debug(f"灰分造渣所消耗的碳: {carbon_consumed:.6f}%")
        self.logger.debug(f"计算过程: 灰分={ash_content:.4f}, SiO₂={sio2_content:.4f}, 造渣系数={slag_factor:.4f}, 渣焓={self.blast_furnace.slag_enthalpy}, 碳燃烧热={carbon_burning_heat:.2f}")
        
        return carbon_consumed

    def calculate_carbon_consumed_by_decomposition(self) -> float:
        """
        计算煤粉分解热和加热至1500°C物理热所消耗的碳

        计算原理：
        1. 煤粉注入高炉后需要分解（热解）消耗热量
        2. 煤粉从常温加热至1500°C需要物理热
        3. 这些热量需要由燃烧的碳来提供
        4. 转换为等效的碳消耗量

        公式: C_decomp = (H_decomp + H_physical) / Q_C
        其中:
        H_decomp: 煤粉分解热 (kJ/kg)
        H_physical: 加热至1500°C的物理热 (kJ/kg)
        Q_C: 1kg碳燃烧产生的热量 (kJ/kg)

        返回:
            煤粉分解热和加热至1500°C物理热所消耗的碳，单位: %
        """
        # 计算1kg碳在风口前燃烧产生的热量
        carbon_burning_heat = self.calculate_carbon_burning_heat()
        
        if carbon_burning_heat <= 0:
            self.logger.error("碳燃烧热计算结果异常，无法计算分解热消耗碳量")
            raise ValueError("碳燃烧热计算结果异常")
        
        # 与煤热值统一使用国际蒸汽表卡；API热耗为kJ/kg，进入内核前除以此系数。
        # 不将热化学卡(4.184)与燃料报告常用的kcal_IT混用。
        kcal_to_kj = 4.1868
        
        # 计算煤粉分解热（kJ/kg）
        decomposition_heat_kj = self.coal.decomposition_heat * kcal_to_kj
        
        # 计算加热至1500°C的物理热（kJ/kg）
        physical_heat_kj = self.coal.physical_heat * kcal_to_kj
        
        # 总热量需求
        total_heat_demand = decomposition_heat_kj + physical_heat_kj
        
        # 计算煤粉分解热和加热至1500°C物理热所消耗的碳
        carbon_consumed = total_heat_demand / carbon_burning_heat
        
        self.logger.debug(f"煤粉分解热和加热至1500°C物理热所消耗的碳: {carbon_consumed:.6f}%")
        self.logger.debug(f"计算过程:")
        self.logger.debug(f"  分解热: {self.coal.decomposition_heat} kcal/kg = {decomposition_heat_kj:.2f} kJ/kg")
        self.logger.debug(f"  物理热: {self.coal.physical_heat} kcal/kg = {physical_heat_kj:.2f} kJ/kg")
        self.logger.debug(f"  总热需求: {total_heat_demand:.2f} kJ/kg")
        self.logger.debug(f"  碳燃烧热: {carbon_burning_heat:.2f} kJ/kg")
        
        return carbon_consumed

    def calculate_displacement_ratio(self) -> Tuple[float, Dict[str, float]]:
        """
        计算理论置换比并返回详细的计算过程

        返回:
            理论置换比及计算过程中各个参数的值
        """
        # 煤粉含碳量
        carbon_in_coal = self.coal.carbon_content
        
        # 煤粉中氢参加还原而节约的碳量
        carbon_saved_by_hydrogen = self.calculate_hydrogen_saving_carbon_percentage()
        
        # 煤粉中灰分造渣所消耗的碳
        carbon_consumed_by_slag_in_coal = self.calculate_carbon_consumed_by_slag(
            self.coal.ash_content, 
            self.coal.sio2_content
        )
        
        # 煤粉分解热和加热至1500°C物理热所消耗的碳
        carbon_consumed_by_decomposition = self.calculate_carbon_consumed_by_decomposition()
        
        # 焦炭含碳量
        carbon_in_coke = self.coke.carbon_content
        
        # 焦炭中灰分造渣所消耗的碳
        carbon_consumed_by_slag_in_coke = self.calculate_carbon_consumed_by_slag(
            self.coke.ash_content, 
            self.coke.sio2_content
        )
        
        # 计算置换比分子
        numerator = (
            carbon_in_coal + 
            carbon_saved_by_hydrogen - 
            carbon_consumed_by_slag_in_coal - 
            carbon_consumed_by_decomposition
        )
        
        # 计算置换比分母
        denominator = carbon_in_coke - carbon_consumed_by_slag_in_coke
        
        # 计算置换比
        if denominator <= 0 or not math.isfinite(denominator):
            raise ValueError("置换比计算错误: 焦炭有效碳量必须大于零")
        
        displacement_ratio = numerator / denominator
        
        # 记录详细计算过程
        calculation_details = {
            "煤粉含碳量": carbon_in_coal,
            "煤粉中氢参加还原而节约的碳量": carbon_saved_by_hydrogen,
            "煤粉中灰分造渣所消耗的碳": carbon_consumed_by_slag_in_coal,
            "煤粉分解热和加热至1500°C物理热所消耗的碳": carbon_consumed_by_decomposition,
            "焦炭含碳量": carbon_in_coke,
            "焦炭中灰分造渣所消耗的碳": carbon_consumed_by_slag_in_coke,
            "置换比分子": numerator,
            "置换比分母": denominator,
            "理论置换比": displacement_ratio
        }
        
        self.logger.info(f"理论置换比计算结果: {displacement_ratio}")
        
        return displacement_ratio, calculation_details


@dataclass
class ProductionData:
    """高炉生产数据数据类"""
    initial_coke_ratio: float  # 调整前焦比，单位：kg/t
    final_coke_ratio: float  # 调整后焦比，单位：kg/t
    initial_coal_ratio: float  # 调整前煤比，单位：kg/t
    final_coal_ratio: float  # 调整后煤比，单位：kg/t
    adjustment_factor: float = 0.0  # 修正系数，单位：kg/t
    iron_output_change: float = 0.0  # 铁水产量变化，单位：吨/天
    slag_ratio_change: float = 0.0  # 渣比变化，单位：kg/t
    carbon_efficiency_change: float = 0.0  # 碳利用效率变化，单位：%


class ActualReplacementRatioCalculator:
    """实际置换比计算器类"""
    
    def __init__(self):
        """初始化实际置换比计算器"""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def calculate_basic_ratio(self, data: ProductionData) -> Tuple[float, Dict[str, float]]:
        """
        计算基本实际置换比（基于焦比和煤比变化）
        
        实际置换比计算公式:
        R = (ΔC + K) / ΔP
        其中:
        ΔC: 焦比减少量(kg/t)
        ΔP: 煤比增加量(kg/t)
        K: 修正系数(kg/t)
        
        参数:
            data: 高炉生产数据
            
        返回:
            实际置换比及相关计算参数
        """
        # 计算焦比变化量
        delta_coke = data.initial_coke_ratio - data.final_coke_ratio
        
        # 计算煤比变化量
        delta_coal = data.final_coal_ratio - data.initial_coal_ratio
        
        # 检查分母是否为零
        if delta_coal == 0:
            self.logger.error("实际置换比计算错误: 分母为零 (煤比变化量为0)")
            raise ValueError("实际置换比计算错误: 分母为零 (煤比变化量为0)")
        
        # 计算实际置换比
        replacement_ratio = (delta_coke + data.adjustment_factor) / delta_coal
        
        # 记录计算详情
        calculation_details = {
            "调整前焦比(kg/t)": data.initial_coke_ratio,
            "调整后焦比(kg/t)": data.final_coke_ratio,
            "调整前煤比(kg/t)": data.initial_coal_ratio,
            "调整后煤比(kg/t)": data.final_coal_ratio,
            "焦比减少量(kg/t)": delta_coke,
            "煤比增加量(kg/t)": delta_coal,
            "修正系数(kg/t)": data.adjustment_factor,
            "实际置换比": replacement_ratio
        }
        
        self.logger.info(f"实际置换比计算结果: {replacement_ratio}")
        
        return replacement_ratio, calculation_details
    
    def calculate_with_production_factors(self, data: ProductionData) -> Tuple[float, Dict[str, float]]:
        """
        计算考虑生产因素的实际置换比（带高炉状态修正）
        
        考虑生产因素的实际置换比计算公式:
        R = (ΔC + K + αΔQ + βΔS + γΔη) / ΔP
        其中:
        ΔC: 焦比减少量(kg/t)
        ΔP: 煤比增加量(kg/t)
        K: 基础修正系数(kg/t)
        ΔQ: 铁水产量变化(t/d)
        ΔS: 渣比变化(kg/t)
        Δη: 碳利用效率变化(%)
        α,β,γ: 影响因子权重
        
        参数:
            data: 高炉生产数据
            
        返回:
            考虑生产因素的实际置换比及相关计算参数
        """
        # 计算基本置换比
        basic_ratio, basic_details = self.calculate_basic_ratio(data)
        
        # 定义影响因子权重
        alpha = 0.05  # 铁水产量影响权重
        beta = 0.02   # 渣比影响权重
        gamma = 0.1   # 碳利用效率影响权重
        
        # 计算高炉状态修正项
        output_correction = alpha * data.iron_output_change
        slag_correction = beta * data.slag_ratio_change
        efficiency_correction = gamma * data.carbon_efficiency_change
        
        # 总修正量
        total_correction = data.adjustment_factor + output_correction + slag_correction + efficiency_correction
        
        # 计算考虑生产因素的实际置换比
        delta_coke = data.initial_coke_ratio - data.final_coke_ratio
        delta_coal = data.final_coal_ratio - data.initial_coal_ratio
        
        # 检查分母是否为零
        if delta_coal == 0:
            self.logger.error("实际置换比计算错误: 分母为零 (煤比变化量为0)")
            raise ValueError("实际置换比计算错误: 分母为零 (煤比变化量为0)")
        
        # 计算修正后的实际置换比
        corrected_ratio = (delta_coke + total_correction) / delta_coal
        
        # 记录计算详情
        calculation_details = {
            **basic_details,
            "铁水产量变化(t/d)": data.iron_output_change,
            "铁水产量修正项": output_correction,
            "渣比变化(kg/t)": data.slag_ratio_change,
            "渣比修正项": slag_correction,
            "碳利用效率变化(%)": data.carbon_efficiency_change,
            "碳效率修正项": efficiency_correction,
            "总修正量": total_correction,
            "修正后实际置换比": corrected_ratio
        }
        
        self.logger.info(f"考虑生产因素的实际置换比计算结果: {corrected_ratio}")
        
        return corrected_ratio, calculation_details
    
    def calculate_historical_average(self, historical_data: List[ProductionData]) -> Tuple[float, Dict]:
        """
        计算历史平均置换比
        
        参数:
            historical_data: 历史生产数据列表
            
        返回:
            历史平均置换比及统计信息
        """
        if not historical_data:
            self.logger.error("无法计算历史平均置换比: 数据为空")
            raise ValueError("无法计算历史平均置换比: 数据为空")
        
        # 计算每组数据的置换比
        ratios = []
        details = []
        
        for i, data in enumerate(historical_data):
            try:
                ratio, detail = self.calculate_basic_ratio(data)
                ratios.append(ratio)
                details.append(detail)
                self.logger.debug(f"历史数据 #{i+1} 置换比: {ratio}")
            except ValueError as e:
                self.logger.warning(f"跳过历史数据 #{i+1}: {str(e)}")
        
        if not ratios:
            self.logger.error("无法计算历史平均置换比: 所有数据均无效")
            raise ValueError("无法计算历史平均置换比: 所有数据均无效")
        
        # 计算统计值
        avg_ratio = sum(ratios) / len(ratios)
        max_ratio = max(ratios)
        min_ratio = min(ratios)
        
        # 计算标准差
        variance = sum((r - avg_ratio) ** 2 for r in ratios) / len(ratios)
        std_dev = variance ** 0.5
        
        # 统计信息
        statistics = {
            "样本数量": len(ratios),
            "平均置换比": avg_ratio,
            "最大置换比": max_ratio,
            "最小置换比": min_ratio,
            "置换比标准差": std_dev,
            "置换比波动范围": max_ratio - min_ratio,
            "各样本置换比": ratios,
            "各样本详情": details
        }
        
        self.logger.info(f"历史平均置换比计算结果: {avg_ratio} (样本数: {len(ratios)})")
        
        return avg_ratio, statistics


# 测试示例
if __name__ == "__main__":
    # 定义煤粉参数 (与README.md中"典型参数示例"保持一致)
    coal_params = CoalParameters(
        carbon_content=0.78,        # 含碳量 78%
        hydrogen_content=0.035,     # 氢含量 3.5%
        ash_content=0.12,           # 灰分 12%
        sio2_content=0.48,          # SiO₂含量 48%
        decomposition_heat=220,     # 分解热 220 kcal/kg
        physical_heat=450           # 物理热 450 kcal/kg
    )
    
    # 定义焦炭参数 (与README.md中"典型参数示例"保持一致)
    coke_params = CokeParameters(
        carbon_content=0.86,        # 含碳量 86%
        ash_content=0.11,           # 灰分 11%
        sio2_content=0.52           # SiO₂含量 52%
    )
    
    # 定义高炉工艺参数 (与README.md中"典型参数示例"保持一致)
    blast_furnace_params = BlastFurnaceParameters(
        eta_co=0.4444,           # 煤气利用率 (原CO2:CO = 0.8 -> 0.8/(1+0.8) = 0.4444)
        slag_basicity=1.15,         # 碱度 1.15
        slag_enthalpy=1800,         # 渣焓 1800 kJ/kg
        wind_temperature=1180,      # 风温 1180°C
        hot_blast_enthalpy=1.5
    )
    
    # 创建理论置换比计算器实例
    theory_calculator = ReplacementRatioCalculator(coal_params, coke_params, blast_furnace_params)
    
    # 计算理论置换比
    theory_ratio, theory_details = theory_calculator.calculate_displacement_ratio()
    
    # 打印理论计算结果
    print("\n===== 理论置换比计算 =====")
    for key, value in theory_details.items():
        print(f"{key}: {value:.6f}")
    print(f"\n最终理论置换比: {theory_ratio:.6f}")
    
    # 创建实际置换比计算器实例
    actual_calculator = ActualReplacementRatioCalculator()
    
    # 定义高炉生产数据
    production_data = ProductionData(
        initial_coke_ratio=400,      # 调整前焦比
        final_coke_ratio=370,        # 调整后焦比
        initial_coal_ratio=150,      # 调整前煤比
        final_coal_ratio=180,        # 调整后煤比
        adjustment_factor=2.5,       # 修正系数
        iron_output_change=50,       # 铁水产量变化
        slag_ratio_change=-10,       # 渣比变化
        carbon_efficiency_change=2.0 # 碳利用效率变化
    )
    
    # 计算基本实际置换比
    actual_ratio, actual_details = actual_calculator.calculate_basic_ratio(production_data)
    
    # 打印基本实际置换比计算结果
    print("\n===== 基本实际置换比计算 =====")
    for key, value in actual_details.items():
        if isinstance(value, float):
            print(f"{key}: {value:.2f}")
        else:
            print(f"{key}: {value}")
    
    # 计算考虑生产因素的实际置换比
    corrected_ratio, corrected_details = actual_calculator.calculate_with_production_factors(production_data)
    
    # 打印修正后的实际置换比计算结果
    print("\n===== 考虑生产因素的实际置换比计算 =====")
    for key, value in corrected_details.items():
        if isinstance(value, float):
            print(f"{key}: {value:.2f}")
        else:
            print(f"{key}: {value}")
    
    # 定义历史生产数据
    historical_data = [
        ProductionData(initial_coke_ratio=400, final_coke_ratio=375, initial_coal_ratio=140, final_coal_ratio=165),
        ProductionData(initial_coke_ratio=390, final_coke_ratio=370, initial_coal_ratio=150, final_coal_ratio=170),
        ProductionData(initial_coke_ratio=380, final_coke_ratio=360, initial_coal_ratio=155, final_coal_ratio=175),
        ProductionData(initial_coke_ratio=410, final_coke_ratio=385, initial_coal_ratio=160, final_coal_ratio=185)
    ]
    
    # 计算历史平均置换比
    avg_ratio, statistics = actual_calculator.calculate_historical_average(historical_data)
    
    # 打印历史平均置换比计算结果
    print("\n===== 历史平均置换比计算 =====")
    print(f"样本数量: {statistics['样本数量']}")
    print(f"平均置换比: {statistics['平均置换比']:.4f}")
    print(f"最大置换比: {statistics['最大置换比']:.4f}")
    print(f"最小置换比: {statistics['最小置换比']:.4f}")
    print(f"置换比标准差: {statistics['置换比标准差']:.4f}")
    print(f"置换比波动范围: {statistics['置换比波动范围']:.4f}")


