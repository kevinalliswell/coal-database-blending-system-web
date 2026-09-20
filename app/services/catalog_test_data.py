"""Synthetic, optional teaching data. Nothing here writes to a database."""


def test_coal_records():
    """Three anthracites and three bituminous coals with explicit report metadata."""
    records = []
    for index in range(6):
        anthracite = index < 3
        coal_type = '无烟煤' if anthracite else '烟煤'
        ash = [9, 10.5, 12, 8, 10, 11.5][index]
        volatile_daf = [7, 9, 11, 28, 33, 37][index]
        values = {
            'total_moisture': ([7, 8, 9, 9, 10, 11][index], '%', 'ar'),
            'air_dry_moisture': ([1.2, 1.4, 1.6, 2, 2.2, 2.4][index], '%', 'ad'),
            'ash_content': (ash, '%', 'd'),
            'volatile_matter': (volatile_daf, '%', 'daf'),
            'fixed_carbon': (round(100 - ash - volatile_daf * (100 - ash) / 100, 6), '%', 'd'),
            'total_sulfur': (round(.45 + .04 * index, 2), '%', 'd'),
            'calorific_value': ([28.8, 28.1, 27.3, 27.7, 26.8, 26][index], 'MJ/kg', 'ar'),
            'price': ([1100, 980, 900, 930, 850, 780][index], 'CNY/t', 'ar'),
            'carbon_content': ([82, 80, 78, 78, 76, 74][index], '%', 'd'),
            'hydrogen_content': ([2.5, 2.8, 3, 4.2, 4.5, 4.8][index], '%', 'd'),
            'nitrogen_content': (1.2, '%', 'd'),
            'sio2_content': ([52, 50, 48, 54, 51, 49][index], '%', 'ash'),
            'hgi': ([68, 65, 62, 58, 55, 53][index], 'index', 'unknown'),
            'burnout_rate': ([88, 89, 90, 94, 95, 96][index], '%', 'unknown'),
        }
        raw = {metric: dict(value=value, unit=unit, basis=basis)
               for metric, (value, unit, basis) in values.items()}
        raw['calorific_value']['heat_type'] = 'net_v'
        raw['hydrogen_content']['hydrogen_includes_moisture'] = False
        records.append({'coal_name': f'测试{coal_type}-{index % 3 + 1:02}', 'type': coal_type,
                        'batch_code': 'TEST-001', 'supplier': '合成教学数据',
                        'report_number': f'TEST-ASSAY-{index + 1:02}',
                        'notes': '合成测试数据，非生产化验；仅供练习导入与计算，不代表实测煤质。', 'raw': raw})
    return records
