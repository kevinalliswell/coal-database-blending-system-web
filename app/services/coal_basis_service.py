"""Gate physical input consistency before running the mathematical optimizer."""

from backend.utils.coal_basis import BASES, BASIS_FIELDS, basis_metadata
from backend.utils.validation import validate_coal_data


def validate_blending_basis(coals, calculation_mode='verified', ratio_basis='unknown'):
    if calculation_mode not in ('verified', 'screening'):
        raise ValueError('calculation_mode必须为verified或screening')
    if not isinstance(ratio_basis, str) or ratio_basis not in BASES:
        raise ValueError('ratio_basis必须为unknown、ad、ar或d；不支持daf')

    warnings = []
    known_bases = set()
    heat_types = set()
    for coal in coals:
        data = coal.to_dict()
        valid, errors = validate_coal_data(data)
        if not valid:
            raise ValueError(f'{coal.name}: {"; ".join(errors)}')
        metadata = basis_metadata(data)
        unknown = [field for field, value in metadata.items() if value == 'unknown']
        if unknown:
            warnings.append(f'{coal.name}尚未确认: {", ".join(unknown)}')
        known_bases.update(metadata[field] for field in BASIS_FIELDS if metadata[field] != 'unknown')
        if metadata['calorific_type'] != 'unknown':
            heat_types.add(metadata['calorific_type'])

    if ratio_basis != 'unknown':
        known_bases.add(ratio_basis)
    if len(known_bases) > 1:
        raise ValueError('已声明的工业分析、热值、计价与配比基准不一致；请先核实统一基准，本版本不自动换算')
    if len(heat_types) > 1:
        raise ValueError('煤种热值类型不一致，不能混用高位gr和低位net热值')

    if calculation_mode == 'verified':
        if ratio_basis == 'unknown':
            warnings.append('正式计算需明确ratio_basis为ad、ar或d')
        if warnings:
            raise ValueError('基准未确认，不能进行正式计算；可显式选择screening试算。' + '; '.join(warnings))
        return {'status': 'verified', 'ratio_basis': ratio_basis,
                'warnings': [], 'scope': 'input_consistency_only'}

    return {'status': 'unverified', 'ratio_basis': ratio_basis,
            'warnings': ['筛选试算：配比与指标未完成正式基准校验，不能作为生产投料依据。', *warnings],
            'scope': 'screening_only'}
