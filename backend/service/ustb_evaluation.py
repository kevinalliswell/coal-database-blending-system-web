
def calculate_oxygen_content(Cad, Had, Nad, Sad, Aad, Mad):
    """
    计算煤粉中的含氧量。
    算法说明：差减法计算煤粉中的含氧量，参考国标：GB-T+31391-2015煤的元素分析
        煤粉中的含氧量 = 100 - 空气干燥基碳含量 - 空气干燥基氢含量 - 空气干燥基氮含量 - 空气干燥基全硫含量 - 空气干燥基煤的灰分产率 - 空气干燥基水分含量

    参数:
        Cad (float): 空气干燥基碳含量（质量分数）
        Had (float): 空气干燥基氢含量（质量分数）
        Nad (float): 空气干燥基氮含量（质量分数）
        Sad (float): 空气干燥基全硫含量（质量分数）
        Aad (float): 空气干燥基煤的灰分产率（质量分数）
        Mad (float): 空气干燥基水分含量（质量分数）

    返回:
        float: 煤粉中的含氧量（质量分数）
    """
    return round(100 - Cad - Had - Nad - Sad - Aad - Mad, 2)


def effective_calorific_value(Cad, Had, Oad, Sad, Aad, Mad, combustion_efficiency=100):
    """
    计算有效发热值，考虑燃烧效率和多种因素。

    参数:
        Cad (float): 碳的百分比。
        Had (float): 氢的百分比。
        Oad (float): 氧的百分比。
        Sad (float): 硫的百分比。
        Aad (float): 灰分的百分比。
        Mad (float): 水分的百分比。
        combustion_efficiency (float): 燃烧效率，默认为 100。

    返回:
        float: 考虑燃烧率的有效发热值。
    """
    # print(f"\n燃烧率: {combustion_efficiency}%")

    # 计算碳不完全燃烧放热量
    incomplete_combustion = round((10 * Cad / 12) * 125.4 * (combustion_efficiency / 100), 2)

    # 计算低位发热值
    low_heat_value = round(339 * Cad + 1031 * Had - 109 * (Oad - Sad) - 25.1 * Mad, 4)

    # 计算碳氢化合物分解耗热
    hydrocarbon_heat_decomposition = round(
        (10 * Cad / 12 - 10 * Oad / 16) * 408.8 + (10 * Oad / 16) * 283.4 + 5 * Had * 242 - low_heat_value, 2
    )

    # 计算灰分带出热量
    ash_heat_loss_value = round(Aad * 2 * 420 * 4.18 / 100, 2)

    # 计算脱硫耗热
    desulfurization_heat_value = round(Sad * 4600 / 100, 2)

    # 计算水分解耗热
    water_heat_loss = round((10 * Mad / 18) * 124.5, 2)

    # 计算有效发热值
    effective_value = (
            incomplete_combustion
            - hydrocarbon_heat_decomposition
            - ash_heat_loss_value
            - desulfurization_heat_value
            - water_heat_loss
    )

    return round(effective_value, 2)


def calculate_dry_basis_price(inlet_price, moisture_content):
    """
    计算干基到厂含税价。
    
    参数:
        inlet_price (float): 采购价/入厂价格（元/吨）
        moisture_content (float): 水分含量（小数形式，如0.1895表示18.95%）
    
    返回:
        float: 干基价格（元/吨）
    """

    return round(inlet_price / ((100 - moisture_content)/100), 2)


def calculate_milling_price(HGI, standard_electricity_consumption=21.12, unit_electricity_price=0.55,
                            standard_HGI=80):
    """
    计算制粉价格。
    算法说明：制粉价格=（标准可磨性指数-可磨性指数）×标准煤电耗×单位电价/标准可磨性指数+标准煤电耗×单位电价；
    参数:
        HGI (float): 煤粉的Hardgrove可磨性指数。
        standard_electricity_consumption (float): 标准用电量（默认值为21.12 kW·h/t）。
        unit_electricity_price (float): 单位电价（默认值为0.55元/kW·h）。
        standard_HGI (float): 标准Hardgrove可磨性指数（默认值为80）。

    返回:
        float: 计算得到的制粉价格。
    """
    return round(((
                          standard_HGI - HGI) * standard_electricity_consumption * unit_electricity_price / standard_HGI) + (
                         standard_electricity_consumption * unit_electricity_price), 2)


def calculate_performance_price_ratio(calorific_value, dry_basis_price, milling_price):
    """
    计算性价比系数K。

    参数:
        calorific_value (float): 煤粉的有效发热值 (kJ/kg)
        dry_basis_price (float): 干基价格 (元/吨)
        milling_price (float): 制粉价格 (元/吨)

    返回:
        float: 性价比系数K (kJ/kg·元)
    """

    # 确保价格为正值
    dry_basis_price = abs(dry_basis_price)
    milling_price = abs(milling_price)

    total_cost = dry_basis_price + milling_price    # 喷吹成本=干基价格+制粉价格

    # 防止除以0
    if total_cost <= 0:
        total_cost = 1

    result = round(calorific_value / total_cost, 2)

    return result
