import csv

import pytest

from app import create_app
from app.config import Config
from app.extensions import db
from app.models import Coal


CSV_HEADERS = [
    "序号",
    "煤种名称",
    "煤种类型",
    "供应商/产地",
    "价格(元/吨)",
    "热值(kcal/kg)",
    "灰分(%)",
    "挥发分(%)",
    "固定碳(%)",
    "全硫(%)",
    "全水分(%)",
    "空干基水分%)",
]

CSV_ROWS = [
    [1, "经济煤", "烟煤", "测试", 500.0, 6000.0, 10.0, 20.0, 65.0, 0.5, 8.0, 1.0],
    [2, "高热值煤", "烟煤", "测试", 700.0, 6400.0, 9.0, 19.0, 68.0, 0.4, 8.0, 1.0],
]


@pytest.fixture
def sqlite_client(tmp_path, monkeypatch):
    db_path = tmp_path / "coal_storage.db"
    csv_path = tmp_path / "seed_coals.csv"

    with csv_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(CSV_HEADERS)
        writer.writerows(CSV_ROWS)

    app = create_app()
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{db_path.as_posix()}",
    )
    monkeypatch.setattr(Config, "COAL_DATA_PATH", str(csv_path))

    with app.app_context():
        db.drop_all()
        db.create_all()

    yield app, app.test_client(), csv_path

    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_coals_are_seeded_from_csv_into_sqlite(sqlite_client):
    app, client, _ = sqlite_client

    response = client.get("/api/coals?page_size=0")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["status"] == "success"
    assert [coal["id"] for coal in payload["data"]] == [1, 2]
    assert payload["data"][0]["name"] == "经济煤"
    assert payload["data"][0]["mad"] == 1.0

    with app.app_context():
        assert Coal.query.count() == 2

    health_response = client.get("/health")
    assert health_response.get_json()["storage_mode"] == "sqlite"


def test_coal_crud_updates_sqlite_without_rewriting_csv(sqlite_client):
    app, client, csv_path = sqlite_client
    original_csv = csv_path.read_text(encoding="utf-8")

    create_response = client.post(
        "/api/coals",
        json={
            "name": "新增测试煤",
            "type": "烟煤",
            "supplier": "测试",
            "price": 620.0,
            "calorific_value": 6200.0,
            "ash_content": 10.0,
            "volatile_matter": 20.0,
            "fixed_carbon": 65.0,
            "total_sulfur": 0.6,
            "moisture": 8.5,
            "mad": 1.2,
        },
    )
    create_payload = create_response.get_json()

    assert create_response.status_code == 200
    assert create_payload["status"] == "success"
    new_id = create_payload["coal_id"]

    update_response = client.put(
        f"/api/coals/{new_id}",
        json={
            "name": "新增测试煤",
            "type": "烟煤",
            "supplier": "测试",
            "price": 630.0,
            "calorific_value": 6250.0,
            "ash_content": 10.0,
            "volatile_matter": 20.0,
            "fixed_carbon": 65.0,
            "total_sulfur": 0.6,
            "moisture": 8.5,
            "mad": 1.2,
        },
    )
    assert update_response.status_code == 200

    detail_response = client.get(f"/api/coals/{new_id}")
    assert detail_response.get_json()["data"]["price"] == 630.0

    delete_response = client.delete(f"/api/coals/{new_id}")
    assert delete_response.status_code == 200

    with app.app_context():
        assert Coal.query.filter_by(name="新增测试煤").first() is None

    assert csv_path.read_text(encoding="utf-8") == original_csv
