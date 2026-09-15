"""Validate theory-model quantities before arithmetic and history persistence."""
import math


def normalize_theory_request(data):
    if not isinstance(data, dict):
        raise ValueError('请求体必须为对象')
    result = dict(data)
    fields = {
        'coal_params': ('carbon_content', 'hydrogen_content', 'ash_content', 'sio2_content',
                        'decomposition_heat', 'physical_heat'),
        'coke_params': ('carbon_content', 'ash_content', 'sio2_content'),
        'blast_furnace_params': ('eta_co', 'slag_basicity', 'slag_enthalpy', 'wind_temperature', 'hot_blast_enthalpy'),
    }
    required = {'coal_params': ('carbon_content', 'hydrogen_content', 'ash_content'),
                'coke_params': ('carbon_content', 'ash_content'), 'blast_furnace_params': ()}
    fractions = {'carbon_content', 'hydrogen_content', 'ash_content', 'sio2_content', 'eta_co'}
    for group, names in fields.items():
        values = data.get(group, {})
        if not isinstance(values, dict):
            raise ValueError(f'{group}必须为对象')
        values = dict(values)
        for field in required[group]:
            if field not in values:
                raise ValueError(f'缺少参数: {group}.{field}')
        for field in names:
            if field not in values or (field == 'hot_blast_enthalpy' and values[field] is None):
                continue
            value = values[field]
            try:
                if isinstance(value, bool) or not isinstance(value, (str, int, float)):
                    raise ValueError
                value = float(value)
                if not math.isfinite(value) or value < 0 or (field in fractions and value > 1):
                    raise ValueError
                if field in {'carbon_content', 'slag_basicity'} and value == 0:
                    raise ValueError
            except (ValueError, TypeError, OverflowError):
                raise ValueError(f'{group}.{field}必须为有效范围内的有限数值') from None
            values[field] = value
        result[group] = values
    return result
