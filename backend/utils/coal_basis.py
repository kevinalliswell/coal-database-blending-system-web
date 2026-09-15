"""Declared assay bases and input consistency checks; no basis conversion."""

BASIS_FIELDS = ('analysis_basis', 'calorific_basis', 'price_basis')
METADATA_FIELDS = (*BASIS_FIELDS, 'calorific_type')
BASES = ('unknown', 'ad', 'ar', 'd')
# Input quality-control allowance in percentage points, not method precision
# or proof that a laboratory measurement is accurate.
CLOSURE_TOLERANCE = 0.5


def basis_metadata(data):
    return {field: 'unknown' if data.get(field) is None or data.get(field) == '' else data[field]
            for field in METADATA_FIELDS}


def validate_assay_basis(data):
    errors = []
    metadata = basis_metadata(data)
    for field, value in metadata.items():
        allowed = ('unknown', 'gr', 'net') if field == 'calorific_type' else BASES
        if not isinstance(value, str) or value not in allowed:
            errors.append(f'{field}不支持该基准/类型；允许值: {", ".join(allowed)}')
    if errors:
        return errors
    basis = metadata['analysis_basis']
    if basis == 'unknown':
        return errors
    moisture = 0.0
    if basis in ('ad', 'ar'):
        canonical, alias = ('air_dry_moisture', 'mad') if basis == 'ad' else ('total_moisture', 'moisture')
        moisture = data.get(canonical, data.get(alias))
        if moisture is None or moisture == '':
            return [f'{basis}基准需提供{canonical}以检查工业分析闭合']
        moisture = float(moisture)
    total = sum(float(data[field]) for field in ('ash_content', 'volatile_matter', 'fixed_carbon')) + moisture
    if abs(total - 100) > CLOSURE_TOLERANCE + 1e-9:
        errors.append(f'工业分析不闭合：{basis}基准灰分+挥发分+固定碳+水分={total:.4f}%，需为100%±{CLOSURE_TOLERANCE}%（输入质控容差）')
    return errors
