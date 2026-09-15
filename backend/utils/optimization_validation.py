"""Validate and normalize the public optimization request before building genes."""
import math


def _object(value, label):
    if not isinstance(value, dict):
        raise ValueError(f'{label}必须是对象')
    return value


def _number(value, label, minimum=0, maximum=None, integer=False):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError(f'{label}必须为有限数值')
    try:
        number = float(value)
    except (ValueError, OverflowError):
        raise ValueError(f'{label}必须为有限数值') from None
    if not math.isfinite(number):
        raise ValueError(f'{label}必须为有限数值')
    if integer and not number.is_integer():
        raise ValueError(f'{label}必须为整数')
    if number < minimum or (maximum is not None and number > maximum):
        raise ValueError(f'{label}超出允许范围')
    return int(number) if integer else number


def _coal_id(value):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError('煤种ID必须是正整数')
    if isinstance(value, str) and (not value.isascii() or not value.isdecimal()):
        raise ValueError('煤种ID必须是正整数')
    value = int(value)
    if value <= 0 or value > 2**63 - 1:
        raise ValueError('煤种ID必须是有效正整数')
    return value


def normalize_optimization_request(data):
    """Return a new canonical request; never silently duplicate or truncate IDs."""
    _object(data, '请求体')
    supplied_ids = data.get('selected_coal_ids')
    if not isinstance(supplied_ids, list) or len(supplied_ids) < 2:
        raise ValueError('请至少选择两种煤进行混配，煤种ID须为数组')
    coal_ids = [_coal_id(value) for value in supplied_ids]
    if len(set(coal_ids)) != len(coal_ids):
        raise ValueError('煤种ID不能重复，请每种煤只选择一次')

    target = data.get('optimization_target', '喷煤性价比最优')
    if not isinstance(target, str) or target not in {'喷煤性价比最优', '最低成本', '最高性价比', '多目标Pareto最优'}:
        raise ValueError('不支持的优化目标，请使用多目标Pareto最优')
    constraints = dict(_object(data.get('constraints', {}), '约束条件'))
    ranges = [('heat_min', 'heat_max', 6000, 7800), ('ash_min', 'ash_max', 0, 20),
              ('volatile_min', 'volatile_max', 8, 40), ('fixed_carbon_min', 'fixed_carbon_max', 50, 85),
              ('sulfur_min', 'sulfur_max', 0, 1.2), ('price_min', 'price_max', 0, 1500)]
    for lower, upper, default_lower, default_upper in ranges:
        constraints[lower] = _number(constraints.get(lower, default_lower), lower)
        constraints[upper] = _number(constraints.get(upper, default_upper), upper)
        if constraints[lower] > constraints[upper]:
            raise ValueError(f'{lower}不能大于{upper}')
    if 'heat_target' in constraints:
        # Legacy metadata only: this is not an objective in the current NSGA-II.
        constraints['heat_target'] = _number(constraints['heat_target'], '热值目标')

    supplied_ratios = _object(constraints.get('ratio_constraints', {}), '配比约束')
    ratios = {}
    for key, value in supplied_ratios.items():
        coal_id = _coal_id(key)
        if coal_id not in coal_ids:
            raise ValueError(f'配比约束包含未选中的煤种: {coal_id}')
        if str(coal_id) in ratios:
            raise ValueError(f'煤种{coal_id}的配比约束重复')
        value = _object(value, f'煤种{coal_id}配比约束')
        lower = _number(value.get('min', 0), f'煤种{coal_id}配比下限', maximum=100)
        upper = _number(value.get('max', 100), f'煤种{coal_id}配比上限', maximum=100)
        if lower > upper:
            raise ValueError(f'煤种{coal_id}的配比下限不能大于上限')
        ratios[str(coal_id)] = {'min': lower, 'max': upper}
    for coal_id in coal_ids:
        ratios.setdefault(str(coal_id), {'min': 0.0, 'max': 100.0})
    if sum(item['min'] for item in ratios.values()) > 100 + 1e-8:
        raise ValueError('所选煤种配比下限总和不能超过100%')
    if sum(item['max'] for item in ratios.values()) < 100 - 1e-8:
        raise ValueError('所选煤种配比上限总和不能低于100%')
    constraints['ratio_constraints'] = ratios

    ga = dict(_object(data.get('ga_params', {}), '算法参数'))
    integer_ranges = {'population_size': (1, 2000), 'max_generations': (1, 10000),
                      'tournament_size': (2, 2000), 'early_stopping_patience': (1, 10000),
                      'parallel_workers': (1, 16), 'random_seed': (0, 2**32-1),
                      'pareto_solution_limit': (1, 2000)}
    real_ranges = {'mutation_rate': (0, 1), 'crossover_rate': (0, 1), 'elite_ratio': (0, 1),
                   'constraint_penalty_factor': (0, None), 'diversity_factor': (0, 1),
                   'convergence_threshold': (0, None)}
    for rules, integer in [(integer_ranges, True), (real_ranges, False)]:
        for key, (lower, upper) in rules.items():
            if key in ga:
                ga[key] = _number(ga[key], key, lower, upper, integer)
    if ga.get('tournament_size', 0) > ga.get('population_size', 500):
        raise ValueError('锦标赛大小不能大于种群大小')
    for key in ['adaptive_mutation', 'parallel_computing']:
        if key not in ga:
            continue
        if isinstance(ga[key], str):
            text = ga[key].lower()
            if text in {'true', '1', 'yes', 'on', 'false', '0', 'no', 'off'}:
                ga[key] = text in {'true', '1', 'yes', 'on'}
        if not isinstance(ga[key], bool):
            raise ValueError(f'{key}必须为布尔值')

    return {**data, 'selected_coal_ids': coal_ids, 'optimization_target': target,
            'constraints': constraints, 'ga_params': ga}
