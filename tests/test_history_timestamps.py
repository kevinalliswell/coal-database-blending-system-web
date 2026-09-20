from datetime import datetime, timedelta, timezone

import pytest
from flask import Flask

from app.extensions import db
from app.models import OptimizationHistory, ReplacementRatioHistory


@pytest.fixture
def history_app(tmp_path):
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{tmp_path / "history.db"}'
    db.init_app(app)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()


@pytest.fixture(params=['optimization', 'replacement'])
def history(request):
    if request.param == 'optimization':
        return OptimizationHistory(timestamp='2026-09-20T18:00:00', coal_names='[]', optimal_ratios='[]', constraints='{}')
    return ReplacementRatioHistory(calculation_type='actual', calculation_mode='actual', ratio_value=1, parameter_summary='{}')


def test_sqlite_default_history_date_declares_utc(history_app, history):
    before = datetime.now(timezone.utc).replace(microsecond=0)
    db.session.add(history)
    db.session.commit()
    serialized = history.to_summary_dict()['date']
    assert serialized.endswith('Z')
    actual = datetime.fromisoformat(serialized)
    assert actual.utcoffset() == timedelta(0)
    assert before <= actual <= datetime.now(timezone.utc)


def test_explicit_offset_is_preserved(history_app, history):
    history.created_at = datetime(2026, 9, 20, 18, 0, tzinfo=timezone(timedelta(hours=8)))
    assert history.to_summary_dict()['date'] == '2026-09-20T18:00:00+08:00'


def test_unknown_mysql_timezone_is_not_invented(history_app, history, monkeypatch):
    # Serialize only: this models an existing MySQL value whose zone was never recorded.
    monkeypatch.setattr(db.engine.dialect, 'name', 'mysql')
    history.created_at = datetime(2026, 9, 20, 18, 0)
    assert history.to_summary_dict()['date'] == '2026-09-20 18:00:00'
