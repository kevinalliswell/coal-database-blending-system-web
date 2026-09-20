"""Pure, traceable assay normalization; no estimates or persistence side effects.

See docs/ASSAY_CONVERSION.md for units, equations, references and scope. Raw
records may be incomplete. Only evaluate_assay determines feature eligibility.
"""
import math


KJ_PER_KCAL = 4.1868
# Application input QC allowance on the common dry basis, not test precision.
CLOSURE_TOLERANCE = 0.5
STANDARD = 'GB/T 213-2008（恒容，kJ/kg；H/M 为百分数）'
BASIS_SOURCE = 'GB/T 35985-2018 / 质量守恒基准换算'
SOLID_BASES = {'unknown', 'ar', 'ad', 'd', 'daf'}
PERCENT_FIELDS = {
    'ash_content', 'volatile_matter', 'fixed_carbon', 'total_sulfur',
    'total_moisture', 'air_dry_moisture', 'carbon_content',
    'hydrogen_content', 'nitrogen_content', 'sio2_content', 'burnout_rate',
}
METRICS = PERCENT_FIELDS | {'price', 'calorific_value', 'hgi'}
ALLOWED_BASES = {
    'ash_content': {'unknown', 'ar', 'ad', 'd'},
    'total_moisture': {'unknown', 'ar'},
    'air_dry_moisture': {'unknown', 'ad'},
    'price': {'unknown', 'ar', 'd'},
    'sio2_content': {'unknown', 'ash'},
    'hgi': {'unknown'}, 'burnout_rate': {'unknown'},
}
UNITS = {
    'calorific_value': {'unknown', 'MJ/kg', 'kJ/kg', 'kcal/kg'},
    'price': {'unknown', 'CNY/t'}, 'hgi': {'unknown', 'index'},
}
LABELS = {
    'ash_content': '灰分', 'volatile_matter': '挥发分',
    'fixed_carbon': '固定碳', 'total_sulfur': '全硫',
    'calorific_value': '热值', 'price': '价格',
    'total_moisture': '全水分 Mt', 'air_dry_moisture': '分析样水分 Mad',
    'carbon_content': '元素碳 C', 'hydrogen_content': '元素氢 H',
    'nitrogen_content': '元素氮 N', 'sio2_content': '灰中 SiO₂',
}


def validate_raw_assay(raw):
    """Return a fresh raw dictionary; reject invalid values, never fill assays.

    Missing metadata becomes the explicit non-computable ``unknown`` state.
    Null metrics/values are empty fields and omitted from the returned record.
    Coherent-looking but incomplete/inconsistent chemistry may still be archived;
    complete functional validation happens separately in evaluate_assay.
    """
    if not isinstance(raw, dict):
        raise ValueError('raw 化验数据必须是对象')
    unknown = set(raw) - METRICS
    if unknown:
        raise ValueError(f'不支持的化验指标: {", ".join(sorted(map(str, unknown)))}')
    result = {}
    for field, item in raw.items():
        if item is None:
            continue
        if not isinstance(item, dict):
            raise ValueError(f'{field} 必须为指标对象')
        allowed = {'value', 'unit', 'basis'}
        if field == 'calorific_value':
            allowed.add('heat_type')
        if field == 'hydrogen_content':
            allowed.add('hydrogen_includes_moisture')
        if set(item) - allowed:
            raise ValueError(f'{field} 含不支持的属性')
        value = item.get('value')
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f'{field}.value 必须为有限数值，不能是布尔值或字符串')
        try:
            value = float(value)
        except (OverflowError, ValueError):
            raise ValueError(f'{field}.value 必须为有限数值') from None
        if not math.isfinite(value) or value < 0:
            raise ValueError(f'{field}.value 必须为非负有限数值')
        if field in PERCENT_FIELDS and value > 100:
            raise ValueError(f'{field} 百分数必须在 0–100 之间')
        if field in {'total_moisture', 'air_dry_moisture'} and value >= 100:
            raise ValueError(f'{field} 必须小于 100%，煤样须含干物质')
        basis = item.get('basis')
        unit = item.get('unit')
        basis = 'unknown' if basis is None or basis == '' else basis
        unit = 'unknown' if unit is None or unit == '' else unit
        if not isinstance(basis, str) or basis not in ALLOWED_BASES.get(field, SOLID_BASES):
            raise ValueError(f'{field} 不支持基准 {basis!r}')
        if not isinstance(unit, str) or unit not in UNITS.get(field, {'unknown', '%'}):
            raise ValueError(f'{field} 不支持单位 {unit!r}')
        normalized = {'value': value, 'unit': unit, 'basis': basis}
        if field == 'calorific_value':
            heat_type = item.get('heat_type')
            heat_type = 'unknown' if heat_type is None or heat_type == '' else heat_type
            if not isinstance(heat_type, str) or heat_type not in {'unknown', 'gr_v', 'net_v', 'net_p'}:
                raise ValueError('calorific_value.heat_type 不支持该热值定义')
            normalized['heat_type'] = heat_type
        if field == 'hydrogen_content':
            includes = item.get('hydrogen_includes_moisture')
            if includes is not None and not isinstance(includes, bool):
                raise ValueError('hydrogen_includes_moisture 必须为布尔值或 null')
            normalized['hydrogen_includes_moisture'] = includes
        result[field] = normalized
    return result


class _Conversion:
    """One function's dependency graph, with independently collected issues."""

    def __init__(self, raw):
        self.raw = raw
        self.issues = []
        self.trace = []
        self.cache = {}

    def issue(self, field, code, message):
        if not any(i['field'] == field and i['code'] == code for i in self.issues):
            self.issues.append({'field': field, 'code': code, 'message': message})

    def require(self, field):
        item = self.raw.get(field)
        if item is None:
            self.issue(field, 'missing', f'缺少{LABELS.get(field, field)}；不能使用默认数值替代')
            return None
        if item['unit'] == 'unknown':
            self.issue(field, 'unknown_unit', f'{LABELS.get(field, field)}单位待确认')
            return None
        if item['basis'] == 'unknown':
            self.issue(field, 'unknown_basis', f'{LABELS.get(field, field)}原始基准待确认')
            return None
        return item

    def finite(self, field, value):
        if not math.isfinite(value) or value < 0 or (field in PERCENT_FIELDS and value > 100):
            self.issue(field, 'invalid_derived_value', f'{LABELS.get(field, field)}换算/派生结果无效；请核对原始化验值和依赖')
            return None
        return value

    def moisture(self, basis):
        if basis == 'd' or basis == 'daf':
            return 0.0
        field = 'total_moisture' if basis == 'ar' else 'air_dry_moisture'
        item = self.require(field)
        if item is None:
            return None
        return item['value']

    def dry(self, field):
        if field in self.cache:
            return self.cache[field]
        value = self._dry(field)
        self.cache[field] = value
        return value

    def _dry(self, field):
        item = self.require(field)
        if item is None:
            return None
        basis, value = item['basis'], item['value']
        if field == 'calorific_value':
            if item['heat_type'] not in {'gr_v', 'net_v'}:
                self.issue(field, 'unsupported_heat_type', '仅支持明确的恒容高位 gr_v 或恒容低位 net_v；恒压或定义不明的热值只能存档')
                return None
            factor = {'MJ/kg': 1000.0, 'kJ/kg': 1.0, 'kcal/kg': KJ_PER_KCAL}[item['unit']]
            value *= factor
            self.trace.append(f'热值单位归一：{item["value"]:g} {item["unit"]} × {factor:g} = {value:g} kJ/kg')
        moisture = self.moisture(basis)
        if moisture is None:
            return None
        if field == 'hydrogen_content' and basis in {'ad', 'ar'}:
            includes = item['hydrogen_includes_moisture']
            if includes is None:
                self.issue(field, 'unknown_hydrogen_definition', '湿基氢必须明确是否包含水中氢；不能猜测或重复扣除')
                return None
            if includes:
                value -= 0.1119 * moisture
                self.trace.append(f'H_{basis} 扣水中氢：H_reported − 0.1119 × M = {value:g}%（SGS / ISO 1170 氢定义）')
                if self.finite(field, value) is None:
                    return None
        if field == 'calorific_value' and item['heat_type'] == 'net_v' and moisture:
            value += 23.0 * moisture
            self.trace.append(f'低位同类换基：Qnet,v,d = (Qnet,v,{basis} + 23 × M)/(1 − M/100)；无需氢，{STANDARD}')
        if basis == 'daf':
            ash = self.dry('ash_content')
            if ash is None:
                return None
            if ash >= 100:
                self.issue(field, 'invalid_ash_free_mass', '干基灰分须小于 100%，否则 daf 无可定义的无灰干物质')
                return None
            value *= 1 - ash / 100
            self.trace.append(f'{field}_d = {field}_daf × (1 − A_d/100) = {value:g}；{BASIS_SOURCE}')
        elif basis in {'ar', 'ad'}:
            value /= 1 - moisture / 100
            self.trace.append(f'{field} 归一干基：扣除 {basis} 水分 {moisture:g}%，结果 {value:g}；{BASIS_SOURCE}')
        else:
            self.trace.append(f'{field} 原值已是 d 基准：{value:g}')
        return self.finite(field, value)

    def target(self, field, dry_value, basis, heat_type=None):
        if dry_value is None:
            return None
        moisture = self.moisture(basis)
        if moisture is None:
            return None
        value = dry_value * (1 - moisture / 100)
        if heat_type == 'net_v':
            value -= 23.0 * moisture
        if self.finite(field, value) is None:
            return None
        self.trace.append(f'{field} 投影到 {basis}：干基值 × (1 − M/100)'
                          + (' − 23 × M' if heat_type == 'net_v' else '')
                          + f' = {value:g}'
                          + (f'；{STANDARD}' if heat_type else '；质量守恒'))
        return value

    def heat(self, basis, heat_type):
        value = self.dry('calorific_value')
        if value is None:
            return None
        source_type = self.raw['calorific_value']['heat_type']
        if source_type != heat_type:
            hydrogen = self.dry('hydrogen_content')
            if hydrogen is None:
                return None
            sign = -1 if heat_type == 'net_v' else 1
            value += sign * 206.0 * hydrogen
            self.trace.append(f'{source_type},d → {heat_type},d：Q {"−" if sign < 0 else "+"} 206 × H_d = {value:g}；{STANDARD}')
            if self.finite('calorific_value', value) is None:
                return None
        value = self.target('calorific_value', value, basis, heat_type)
        if value is None:
            return None
        if value <= 0:
            self.issue('calorific_value', 'invalid_derived_value', '参与混煤计算的热值必须大于零')
            return None
        self.trace.append(f'算法热值：{value:g} kJ/kg ÷ 4.1868 = {value / KJ_PER_KCAL:g} kcal/kg')
        return value / KJ_PER_KCAL

    def result(self, values):
        return {'eligible': not self.issues, 'issues': self.issues,
                'values': values, 'trace': self.trace}


def _blending(raw, basis, heat_type):
    context = _Conversion(raw)
    dry_values = {field: context.dry(field) for field in ('ash_content', 'volatile_matter')}
    if 'fixed_carbon' in raw:
        dry_values['fixed_carbon'] = context.dry('fixed_carbon')
    elif all(value is not None for value in dry_values.values()):
        fixed_carbon = 100 - dry_values['ash_content'] - dry_values['volatile_matter']
        dry_values['fixed_carbon'] = context.finite('fixed_carbon', fixed_carbon)
        if dry_values['fixed_carbon'] is not None:
            context.trace.append(f'固定碳标准差减派生：FC_d = 100 − A_d − V_d = {fixed_carbon:g}%（工业分析定义，非元素碳；不减全硫）')
    else:
        dry_values['fixed_carbon'] = None
        context.issue('fixed_carbon', 'missing_dependency', '固定碳未提供，且灰分/挥发分缺失或无法换基，不能差减派生')
    if all(value is not None for value in dry_values.values()):
        closure = sum(dry_values.values())
        if abs(closure - 100) > CLOSURE_TOLERANCE + 1e-9:
            context.issue('fixed_carbon', 'proximate_closure',
                          f'工业分析不闭合：干基 A+V+FC={closure:g}%，要求 100±{CLOSURE_TOLERANCE} 个百分点（输入质控容差，非标准精密度）')
        else:
            context.trace.append(f'工业分析干基闭合检查：A_d + V_d + FC_d = {closure:g}%，容差 ±{CLOSURE_TOLERANCE} 个百分点；未缩放原始值')
    dry_values['total_sulfur'] = context.dry('total_sulfur')
    dry_values['price'] = context.dry('price')
    values = {}
    for field, value in dry_values.items():
        converted = context.target(field, value, basis)
        if converted is not None:
            values[field] = converted
    heat = context.heat(basis, heat_type)
    if heat is not None:
        values['calorific_value'] = heat
    return context.result(values)


def _theory(raw):
    context = _Conversion(raw)
    values = {}
    for field in ('carbon_content', 'hydrogen_content', 'ash_content'):
        value = context.dry(field)
        if value is not None:
            values[field] = value
    silica = context.require('sio2_content')
    if silica is not None:
        values['sio2_content'] = silica['value']
        context.trace.append(f'灰中 SiO₂ = {silica["value"]:g}%（灰质量基准；混煤时须按灰质量加权）')
    if all(field in values for field in ('carbon_content', 'hydrogen_content', 'ash_content')):
        total = sum(values[field] for field in ('carbon_content', 'hydrogen_content', 'ash_content'))
        if total > 100 + CLOSURE_TOLERANCE:
            context.issue('carbon_content', 'elemental_closure', '干基元素 C+H+灰分超过 100% 加输入质控容差；不能进入理论模型')
    context.trace.append('理论输入为干基元素含量和灰基 SiO₂ 的百分数；调用置换比模型前由路由除以 100，固定碳不替代元素碳')
    return context.result(values)


def evaluate_assay(raw, settings):
    """Evaluate independent blending/theory dependencies without changing raw.

    Blending values: common ar/d percentages, CNY per corresponding tonne,
    kcal/kg of the selected constant-volume heat definition. Theory values:
    dry C/H/A percentages and ash-basis SiO2 percentage. Furnace/coke/process
    inputs are validated by their calculation routes, not invented here.
    """
    raw = validate_raw_assay(raw)
    if not isinstance(settings, dict):
        raise ValueError('settings 必须为对象')
    basis = settings.get('ratio_basis', 'ar')
    heat_type = settings.get('heat_type', 'net_v')
    heat_unit = settings.get('heat_unit', 'MJ/kg')
    if basis not in ('ar', 'd'):
        raise ValueError('计算质量基准只支持 ar 或 d')
    if heat_type not in ('gr_v', 'net_v'):
        raise ValueError('计算热值只支持恒容 gr_v 或 net_v')
    if heat_unit not in ('MJ/kg', 'kcal/kg'):
        raise ValueError('显示热值单位只支持 MJ/kg 或 kcal/kg')
    return {'blending': _blending(raw, basis, heat_type), 'theory': _theory(raw)}
