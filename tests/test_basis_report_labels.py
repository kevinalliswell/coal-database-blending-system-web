from openpyxl import Workbook

from backend.utils.excel_utils import create_unified_a4_report


def report_text(validation):
    result = {
        'coal_names': ['A', 'B'], 'optimal_ratios': [0.5, 0.5],
        'total_price': 700, 'total_heat': 6500, 'total_ash': 10,
        'total_volatile': 20, 'total_fixed_carbon': 68, 'total_sulfur': 0.5,
        'constraints_satisfied': True, 'is_feasible': True,
        'data_validation': validation,
    }
    wb = Workbook()
    create_unified_a4_report(wb, {'result': result})
    return '\n'.join(str(cell.value) for row in wb.active.iter_rows() for cell in row if cell.value is not None)


def test_screening_report_cannot_describe_unconfirmed_data_as_production_recommendation():
    text = report_text({'status': 'unverified', 'ratio_basis': 'unknown',
                        'warnings': ['煤A的热值基准未知', '煤B的价格基准未知']})
    assert '仅用于筛选' in text
    assert '基准未确认' in text
    assert '煤A的热值基准未知' in text
    assert '煤B的价格基准未知' in text
    assert '推荐用于喷煤配煤' not in text
    assert '可直接用于喷煤工艺评估' not in text


def test_verified_report_identifies_the_check_scope_without_claiming_plant_validation():
    text = report_text({'status': 'verified', 'ratio_basis': 'ad', 'warnings': []})
    assert '基准检查通过' in text
    assert 'ad' in text
    assert '不代表现场工艺验证' in text


def test_legacy_report_does_not_invent_verified_basis():
    text = report_text(None)
    assert '基准验证未记录' in text
    assert '基准检查通过' not in text
