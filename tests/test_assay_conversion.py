"""Conservation examples and feature-specific admission for raw assay records."""
import copy
import math

import pytest

from app.services.assay_conversion import evaluate_assay, validate_raw_assay


def metric(value, basis='d', unit='%', **metadata):
    return dict(value=value, unit=unit, basis=basis, **metadata)


def assay():
    # A/V/FC close on dry matter; the two water values are deliberately different.
    return {
        'ash_content': metric(10), 'volatile_matter': metric(20),
        'fixed_carbon': metric(70), 'total_sulfur': metric(0.5),
        'total_moisture': metric(10, 'ar'),
        'air_dry_moisture': metric(2, 'ad'),
        'calorific_value': metric(32, unit='MJ/kg', heat_type='gr_v'),
        'price': metric(900, 'ar', 'CNY/t'),
        'carbon_content': metric(78),
        'hydrogen_content': metric(4, hydrogen_includes_moisture=False),
        'sio2_content': metric(48, 'ash'),
    }


def codes(section):
    return {(issue['field'], issue['code']) for issue in section['issues']}


def test_partial_storage_preserves_unknown_metadata_without_numeric_defaults():
    raw = {'ash_content': {'value': 8}, 'price': None,
           'fixed_carbon': {'value': None}}
    saved = validate_raw_assay(raw)
    assert saved == {'ash_content': metric(8, 'unknown', 'unknown')}
    assert raw['ash_content'] == {'value': 8}
    result = evaluate_assay(saved, {})
    assert not result['blending']['eligible']
    assert not result['theory']['eligible']
    assert ('ash_content', 'unknown_unit') in codes(result['blending'])


@pytest.mark.parametrize('value', [True, '10', float('nan'), float('inf'), -1, 101])
def test_invalid_percentage_cannot_be_stored(value):
    with pytest.raises(ValueError):
        validate_raw_assay({'ash_content': metric(value)})


@pytest.mark.parametrize('raw', [[], {'typo_ash': metric(1)},
    {'total_moisture': metric(100, 'ar')},
    {'total_moisture': metric(4, 'ad')},
    {'ash_content': metric(0, 'daf')},
    {'sio2_content': metric(50, 'd')},
    {'price': metric(1000, 'daf', 'CNY/t')},
    {'calorific_value': metric(32, unit='MWh', heat_type='gr_v')},
    {'hydrogen_content': metric(4, hydrogen_includes_moisture='false')},
    {'ash_content': dict(metric(1), typo=True)}])
def test_malformed_or_meaningless_raw_metadata_is_rejected(raw):
    with pytest.raises(ValueError):
        validate_raw_assay(raw)


def test_default_ar_net_volume_price_and_theory_values_are_independent():
    raw = assay()
    before = copy.deepcopy(raw)
    result = evaluate_assay(raw, {})
    blend, theory = result['blending'], result['theory']
    assert blend['eligible'], blend['issues']
    assert blend['values'] == pytest.approx({
        'ash_content': 9, 'volatile_matter': 18, 'fixed_carbon': 63,
        'total_sulfur': .45, 'calorific_value': 27828.4 / 4.1868,
        'price': 900,
    })
    assert theory['eligible'], theory['issues']
    assert theory['values'] == pytest.approx({
        'carbon_content': 78, 'hydrogen_content': 4,
        'ash_content': 10, 'sio2_content': 48,
    })
    assert raw == before
    assert any('206' in line and 'GB/T 213-2008' in line for line in blend['trace'])


def test_per_metric_ad_ar_d_daf_and_standard_fc_difference():
    raw = assay()
    raw['ash_content'] = metric(9.8, 'ad')
    raw['volatile_matter'] = metric(100 * 20 / 90, 'daf')
    raw['total_sulfur'] = metric(.45, 'ar')
    raw.pop('fixed_carbon')
    result = evaluate_assay(raw, {})['blending']
    assert result['eligible'], result['issues']
    assert result['values']['fixed_carbon'] == pytest.approx(63)
    assert result['values']['volatile_matter'] == pytest.approx(18)
    assert any('差减' in line for line in result['trace'])
    assert 'fixed_carbon' not in raw


def test_missing_mt_blocks_ar_closure_without_back_calculating_water():
    raw = assay()
    for field, value in [('ash_content', 9), ('volatile_matter', 18),
                         ('fixed_carbon', 63), ('total_sulfur', .45)]:
        raw[field] = metric(value, 'ar')
    raw['calorific_value'] = metric(27828.4, 'ar', 'kJ/kg', heat_type='net_v')
    raw.pop('total_moisture')
    result = evaluate_assay(raw, {})['blending']
    assert not result['eligible']
    assert ('total_moisture', 'missing') in codes(result)
    assert 'total_moisture' not in raw


def test_all_dry_gross_inputs_need_no_water_or_hydrogen_for_blending():
    raw = assay()
    raw['price'] = metric(1000, unit='CNY/t')
    for field in ('total_moisture', 'air_dry_moisture', 'hydrogen_content'):
        raw.pop(field)
    result = evaluate_assay(raw, {'ratio_basis': 'd', 'heat_type': 'gr_v'})
    assert result['blending']['eligible'], result['blending']['issues']
    assert result['blending']['values']['calorific_value'] == pytest.approx(32000 / 4.1868)
    assert not result['theory']['eligible']


@pytest.mark.parametrize('source_basis,source_heat', [
    ('ar', 27828.4), ('ad', 30506.48), ('d', 31176),
    ('daf', 31176 / .9),
])
@pytest.mark.parametrize('target_basis,expected', [('ar', 27828.4), ('d', 31176)])
def test_net_volume_basis_conversion_does_not_require_hydrogen(source_basis, source_heat, target_basis, expected):
    raw = assay()
    raw.pop('hydrogen_content')
    raw['calorific_value'] = metric(source_heat, source_basis, 'kJ/kg', heat_type='net_v')
    result = evaluate_assay(raw, {'ratio_basis': target_basis})['blending']
    assert result['eligible'], result['issues']
    assert result['values']['calorific_value'] == pytest.approx(expected / 4.1868)


@pytest.mark.parametrize('source_basis,value', [('ar', 27828.4), ('ad', 30506.48),
                                             ('d', 31176), ('daf', 31176 / .9)])
def test_net_to_gross_reverses_water_and_hydrogen_corrections(source_basis, value):
    raw = assay()
    raw['calorific_value'] = metric(value, source_basis, 'kJ/kg', heat_type='net_v')
    result = evaluate_assay(raw, {'ratio_basis': 'd', 'heat_type': 'gr_v'})['blending']
    assert result['eligible'], result['issues']
    assert result['values']['calorific_value'] == pytest.approx(32000 / 4.1868)


@pytest.mark.parametrize('basis,value', [('ar', 28800), ('ad', 31360),
                                      ('d', 32000), ('daf', 32000 / .9)])
def test_gross_normalization_from_each_supported_basis(basis, value):
    raw = assay()
    raw['calorific_value'] = metric(value / 4.1868, basis, 'kcal/kg', heat_type='gr_v')
    result = evaluate_assay(raw, {})['blending']
    assert result['eligible'], result['issues']
    assert result['values']['calorific_value'] == pytest.approx(27828.4 / 4.1868)


@pytest.mark.parametrize('includes,value', [(False, 3.92), (True, 3.92 + .1119 * 2)])
def test_hydrogen_definition_excludes_water_exactly_once(includes, value):
    raw = assay()
    raw['hydrogen_content'] = metric(value, 'ad', hydrogen_includes_moisture=includes)
    result = evaluate_assay(raw, {})
    assert result['theory']['values']['hydrogen_content'] == pytest.approx(4)
    assert result['blending']['values']['calorific_value'] == pytest.approx(27828.4 / 4.1868)


def test_unknown_hydrogen_definition_blocks_only_features_that_use_hydrogen():
    raw = assay()
    raw['hydrogen_content'] = metric(3.92, 'ad')
    result = evaluate_assay(raw, {})
    assert ('hydrogen_content', 'unknown_hydrogen_definition') in codes(result['blending'])
    raw['calorific_value'] = metric(27828.4, 'ar', 'kJ/kg', heat_type='net_v')
    result = evaluate_assay(raw, {})
    assert result['blending']['eligible']
    assert not result['theory']['eligible']


@pytest.mark.parametrize('heat_type', ['unknown', 'net_p'])
def test_unknown_or_constant_pressure_heat_stores_but_blocks_only_heat_use(heat_type):
    raw = assay()
    raw['calorific_value']['heat_type'] = heat_type
    validate_raw_assay(raw)
    result = evaluate_assay(raw, {})
    assert ('calorific_value', 'unsupported_heat_type') in codes(result['blending'])
    assert result['theory']['eligible']


def test_inconsistent_full_proximate_analysis_is_storable_but_cannot_blend():
    raw = assay()
    raw['fixed_carbon']['value'] = 67
    validate_raw_assay(raw)
    result = evaluate_assay(raw, {})['blending']
    assert ('fixed_carbon', 'proximate_closure') in codes(result)
    assert not result['eligible']
    assert raw['fixed_carbon']['value'] == 67


def test_invalid_derived_fixed_carbon_is_not_clipped_to_zero():
    raw = assay()
    raw['volatile_matter']['value'] = 95
    raw.pop('fixed_carbon')
    result = evaluate_assay(raw, {})['blending']
    assert not result['eligible']
    assert ('fixed_carbon', 'invalid_derived_value') in codes(result)
    assert 'fixed_carbon' not in result['values']


def test_daf_conversion_requires_ash_and_does_not_treat_ash_as_zero():
    raw = assay()
    raw['volatile_matter'] = metric(25, 'daf')
    raw.pop('ash_content')
    result = evaluate_assay(raw, {})['blending']
    assert not result['eligible']
    assert ('ash_content', 'missing') in codes(result)


def test_theory_depends_on_elemental_carbon_not_fixed_carbon_price_or_heat():
    raw = {key: assay()[key] for key in ('carbon_content', 'hydrogen_content', 'ash_content', 'sio2_content')}
    result = evaluate_assay(raw, {})
    assert result['theory']['eligible'], result['theory']['issues']
    assert not result['blending']['eligible']
    raw['fixed_carbon'] = metric(78)
    raw.pop('carbon_content')
    assert ('carbon_content', 'missing') in codes(evaluate_assay(raw, {})['theory'])


def test_impossible_elemental_totals_cannot_enter_theory():
    raw = assay()
    raw['carbon_content']['value'] = 99
    result = evaluate_assay(raw, {})['theory']
    assert not result['eligible']
    assert ('carbon_content', 'elemental_closure') in codes(result)


def test_wet_mass_heat_and_price_blending_conserve_dry_mass_and_heat():
    first, second = assay(), assay()
    second['total_moisture']['value'] = 20
    second['price']['value'] = 800
    first_values = evaluate_assay(first, {})['blending']['values']
    second_values = evaluate_assay(second, {})['blending']['values']
    # Equal dry masses require different wet masses, proportional to 1/(1-M).
    wet_weights = [(.5 / .9) / (.5 / .9 + .5 / .8), (.5 / .8) / (.5 / .9 + .5 / .8)]
    blend_moisture = wet_weights[0] * 10 + wet_weights[1] * 20
    expected_net = 31176 * (1 - blend_moisture / 100) - 23 * blend_moisture
    actual_net = sum(w * v['calorific_value'] * 4.1868 for w, v in zip(wet_weights, [first_values, second_values]))
    assert actual_net == pytest.approx(expected_net)
    assert sum(w * v['price'] for w, v in zip(wet_weights, [first_values, second_values])) / (1 - blend_moisture / 100) == pytest.approx(1000)


@pytest.mark.parametrize('settings', [{'ratio_basis': 'unknown'}, {'ratio_basis': 'ad'},
                                    {'heat_type': 'net_p'}, {'heat_unit': 'Btu/lb'}])
def test_unsupported_settings_are_not_silently_replaced(settings):
    with pytest.raises(ValueError):
        evaluate_assay(assay(), settings)


def test_finite_input_overflow_is_reported_without_emitting_infinite_results():
    raw = assay()
    raw['price'] = metric(1e308, 'ar', 'CNY/t')
    raw['total_moisture']['value'] = 99
    result = evaluate_assay(raw, {'ratio_basis': 'd'})['blending']
    assert not result['eligible']
    assert all(math.isfinite(value) for value in result['values'].values())


@pytest.mark.parametrize('field', ['basis', 'unit'])
def test_false_metadata_is_not_treated_as_unknown(field):
    raw = {'ash_content': dict(metric(8), **{field: False})}
    with pytest.raises(ValueError):
        validate_raw_assay(raw)


def test_water_conversion_cannot_create_more_than_100_percent_sulfur():
    raw = assay()
    raw['total_sulfur'] = metric(95, 'ar')
    result = evaluate_assay(raw, {})['blending']
    assert not result['eligible']
    assert ('total_sulfur', 'invalid_derived_value') in codes(result)
    assert 'total_sulfur' not in result['values']


def test_hydrogen_less_than_hydrogen_in_water_is_not_clipped():
    raw = assay()
    raw['hydrogen_content'] = metric(.01, 'ad', hydrogen_includes_moisture=True)
    result = evaluate_assay(raw, {})
    assert not result['theory']['eligible']
    assert 'hydrogen_content' not in result['theory']['values']


def test_quality_tolerance_never_rescales_supplied_fixed_carbon():
    raw = assay()
    raw['fixed_carbon']['value'] = 69.7
    result = evaluate_assay(raw, {})['blending']
    assert result['eligible'], result['issues']
    assert result['values']['fixed_carbon'] == pytest.approx(69.7 * .9)


def test_independent_coal_assay_theory_normalizes_ar_and_daf_elements():
    raw = assay()
    raw['carbon_content'] = metric(70.2, 'ar')
    raw['hydrogen_content'] = metric(4 / .9, 'daf')
    result = evaluate_assay(raw, {})['theory']
    assert result['eligible'], result['issues']
    assert result['values']['carbon_content'] == pytest.approx(78)
    assert result['values']['hydrogen_content'] == pytest.approx(4)
