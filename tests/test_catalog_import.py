import io
from datetime import datetime, timedelta

import pytest

from test_catalog_v2 import catalog_app  # noqa: F401
from app.extensions import db


def preview(text, **kwargs):
    from app.services.catalog_import import preview_import
    return preview_import(text=text, user_id=7, settings={}, **kwargs)


def test_ambiguous_columns_need_confirmation_but_partial_records_are_valid(catalog_app):
    data = '煤种名称,煤种类型,批次编号,灰分\n样煤,烟煤,B001,12.5\n'
    unresolved = preview(data)
    assert not unresolved['can_commit'] and not unresolved['preview_token']
    confirmed = preview(data, mapping={'灰分': 'ash_content.value'}, confirmed_headers=['灰分'])
    assert confirmed['can_commit']
    assert confirmed['rows'][0]['raw']['ash_content']['value'] == 12.5
    assert confirmed['rows'][0]['raw']['ash_content']['basis'] == 'unknown'
    assert not confirmed['rows'][0]['eligibility']['blending']['eligible']


def test_preview_commit_is_bound_to_user_and_one_use(catalog_app):
    from app.services.catalog_import import commit_import
    from app.models.catalog import AssayRevision
    response = preview('coal_name,type,batch_code\n样煤,烟煤,B001\n')
    token = response['preview_token']
    with pytest.raises(ValueError):
        commit_import(token, user_id=8)
    result = commit_import(token, user_id=7)
    db.session.commit()
    assert result['created_revisions'] == 1
    assert AssayRevision.query.count() == 1
    with pytest.raises(ValueError):
        commit_import(token, user_id=7)
    assert AssayRevision.query.count() == 1


def test_import_always_appends_revision_and_detects_stale_preview(catalog_app):
    from app.services.catalog_import import commit_import
    from app.models.catalog import AssayRevision
    from app.services.catalog_service import CatalogConflict
    text = 'coal_name,type,batch_code\n样煤,烟煤,B001\n'
    commit_import(preview(text)['preview_token'], user_id=7)
    db.session.commit()
    earlier = preview(text)
    later = preview(text)
    commit_import(later['preview_token'], user_id=7)
    db.session.commit()
    with pytest.raises(CatalogConflict):
        commit_import(earlier['preview_token'], user_id=7)
    db.session.rollback()
    assert [r.revision for r in AssayRevision.query.order_by(AssayRevision.id)] == [1, 2]


def test_expired_preview_does_not_write_any_rows(catalog_app):
    from app.services.catalog_import import commit_import
    from app.models.catalog import ImportPreview, AssayRevision
    token = preview('coal_name,type,batch_code\n样煤,烟煤,B001\n')['preview_token']
    ImportPreview.query.one().expires_at = datetime.utcnow() - timedelta(seconds=1)
    db.session.commit()
    with pytest.raises(ValueError, match='过期'):
        commit_import(token, user_id=7)
    assert AssayRevision.query.count() == 0


def test_bad_row_blocks_whole_preview(catalog_app):
    data = 'coal_name,type,batch_code,ash_content.value,ash_content.unit,ash_content.basis\nA,烟煤,1,10,%,d\nB,烟煤,2,NaN,%,d\n'
    response = preview(data)
    assert not response['can_commit']
    assert response['rows'][1]['issues']
    assert response['preview_token'] is None


def test_tab_paste_and_xlsx_preserve_raw_metadata(catalog_app):
    from openpyxl import Workbook
    from app.services.catalog_import import preview_import
    header = ['coal_name', 'type', 'batch_code', 'calorific_value.value', 'calorific_value.unit', 'calorific_value.basis', 'calorific_value.heat_type']
    values = ['样煤', '烟煤', '2026-01', 24.3, 'MJ/kg', 'ar', 'net_p']
    pasted = preview('\t'.join(header) + '\n' + '\t'.join(map(str, values)))
    book = Workbook()
    book.active.append(header)
    book.active.append(values)
    output = io.BytesIO()
    book.save(output)
    imported = preview_import(file_bytes=output.getvalue(), filename='化验.xlsx', user_id=7, settings={})
    assert pasted['can_commit'] and imported['can_commit']
    assert pasted['rows'][0]['raw'] == imported['rows'][0]['raw']


def test_export_roundtrip_keeps_all_revisions_and_full_raw(catalog_app):
    from app.services.catalog_import import commit_import, export_catalog, preview_import
    from app.models.catalog import AssayRevision
    data = ('coal_name,type,batch_code,hydrogen_content.value,hydrogen_content.unit,hydrogen_content.basis,hydrogen_content.hydrogen_includes_moisture\n'
            '样煤,烟煤,B,4.2,%,ad,true\n样煤,烟煤,B,4.4,%,ad,false\n')
    commit_import(preview(data)['preview_token'], user_id=7)
    db.session.commit()
    expected = [r.raw for r in AssayRevision.query.order_by(AssayRevision.id)]
    content, mime, filename = export_catalog('xlsx', include_archived=True)
    result = preview_import(file_bytes=content, filename=filename, user_id=7, settings={})
    assert result['can_commit'], result
    assert [row['raw'] for row in result['rows']] == expected
