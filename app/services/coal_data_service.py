#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""煤种数据 SQLite 服务层。"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd
from flask import current_app
from sqlalchemy import inspect, or_

from app.config import Config
from app.extensions import db
from app.models import Coal
from app.utils.file_utils import safe_read_csv
from app.utils.validation import validate_coal_data


REQUIRED_FIELDS = (
    "name",
    "type",
    "price",
    "calorific_value",
    "ash_content",
    "volatile_matter",
    "fixed_carbon",
    "total_sulfur",
)

OPTIONAL_FLOAT_FIELDS = (
    "total_moisture",
    "air_dry_moisture",
    "hgi",
    "burnout_rate",
    "carbon_content",
    "hydrogen_content",
    "nitrogen_content",
)

CSV_COLUMN_ALIASES = {
    "id": ("序号", "id"),
    "name": ("煤种名称", "name"),
    "type": ("煤种类型", "type"),
    "supplier": ("供应商/产地", "供应商", "产地", "supplier"),
    "price": ("价格(元/吨)", "价格", "price"),
    "calorific_value": ("热值(kcal/kg)", "热值", "calorific_value"),
    "ash_content": ("灰分(%)", "灰分", "ash_content"),
    "volatile_matter": ("挥发分(%)", "挥发分", "volatile_matter"),
    "fixed_carbon": ("固定碳(%)", "固定碳", "fixed_carbon"),
    "total_sulfur": ("全硫(%)", "全硫", "total_sulfur"),
    "total_moisture": ("全水分(%)", "水分（%）", "水分(%)", "moisture", "total_moisture"),
    "air_dry_moisture": ("空干基水分(%)", "空干基水分%)", "mad", "air_dry_moisture"),
    "hgi": ("可磨性HGI", "HGI", "hgi"),
    "burnout_rate": ("燃尽率(%)", "燃尽率", "burnout_rate"),
    "carbon_content": ("含碳量C(%)", "含碳量", "carbon_content"),
    "hydrogen_content": ("含氢量H(%)", "含氢量", "hydrogen_content"),
    "nitrogen_content": ("含氮量N(%)", "含氮量", "nitrogen_content"),
}


@dataclass(frozen=True)
class ImportSummary:
    """导入结果摘要。"""

    created_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    errors: tuple[str, ...] = ()

    @property
    def affected_count(self) -> int:
        return self.created_count + self.updated_count


def ensure_coal_data_initialized() -> None:
    """确保 SQLite 表存在，并在煤种表为空时从默认 CSV 初始化。"""
    app = current_app._get_current_object()
    if getattr(app, "_coal_data_initialized", False) and _coal_table_exists():
        return

    db.create_all()
    if Coal.query.count() == 0:
        seed_path = Path(Config.COAL_DATA_PATH)
        if seed_path.exists():
            seed_from_csv(seed_path)

    app._coal_data_initialized = True


def _coal_table_exists() -> bool:
    """检查当前数据库连接中是否存在煤种表。"""
    return inspect(db.engine).has_table(Coal.__tablename__)


def seed_from_csv(csv_path: str | Path) -> ImportSummary:
    """从 CSV 种子文件初始化煤种表，保留 CSV 中的序号。"""
    df = safe_read_csv(str(csv_path))
    return import_dataframe(df, preserve_ids=True, update_existing=False)


def list_coals(
    page: int = 1,
    page_size: int = 10,
    search: str = "",
    coal_type: str = "",
) -> dict:
    """分页查询煤种。page_size <= 0 时返回全部数据。"""
    ensure_coal_data_initialized()

    page = max(int(page or 1), 1)
    page_size = int(10 if page_size is None else page_size)

    query = Coal.query
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Coal.name.ilike(pattern),
                Coal.type.ilike(pattern),
                Coal.supplier.ilike(pattern),
            )
        )
    if coal_type:
        query = query.filter(Coal.type == coal_type.strip())

    query = query.order_by(Coal.id.asc())
    total = query.count()

    if page_size > 0:
        items = query.offset((page - 1) * page_size).limit(page_size).all()
        total_pages = (total + page_size - 1) // page_size if total else 0
    else:
        items = query.all()
        total_pages = 1 if total else 0

    return {
        "data": [coal_to_api_dict(coal) for coal in items],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        },
    }


def get_coal(coal_id: int) -> Coal | None:
    ensure_coal_data_initialized()
    return db.session.get(Coal, int(coal_id))


def get_coals_by_ids(coal_ids: Iterable[int]) -> list[Coal]:
    """按传入 ID 顺序返回煤种列表。"""
    ensure_coal_data_initialized()
    normalized_ids = [int(coal_id) for coal_id in coal_ids]
    if not normalized_ids:
        return []

    coals = Coal.query.filter(Coal.id.in_(normalized_ids)).all()
    coal_by_id = {coal.id: coal for coal in coals}
    return [coal_by_id[coal_id] for coal_id in normalized_ids if coal_id in coal_by_id]


def get_coal_types() -> list[str]:
    ensure_coal_data_initialized()
    rows = db.session.query(Coal.type).distinct().order_by(Coal.type.asc()).all()
    return [row[0] for row in rows if row[0]]


def create_coal(data: dict) -> Coal:
    ensure_coal_data_initialized()
    payload = normalize_coal_payload(data)
    coal = Coal(**payload)
    db.session.add(coal)
    db.session.commit()
    return coal


def update_coal(coal_id: int, data: dict) -> Coal | None:
    ensure_coal_data_initialized()
    coal = db.session.get(Coal, int(coal_id))
    if coal is None:
        return None

    merged = coal_to_api_dict(coal)
    merged.update(data)
    for alias, canonical in (("moisture", "total_moisture"), ("mad", "air_dry_moisture")):
        if alias in data and canonical not in data:
            merged[canonical] = data[alias]
    payload = normalize_coal_payload(merged)
    for field, value in payload.items():
        setattr(coal, field, value)

    db.session.commit()
    return coal


def delete_coal(coal_id: int) -> bool:
    ensure_coal_data_initialized()
    coal = db.session.get(Coal, int(coal_id))
    if coal is None:
        return False

    db.session.delete(coal)
    db.session.commit()
    return True


def delete_coals(coal_ids: Iterable[int]) -> int:
    ensure_coal_data_initialized()
    normalized_ids = [int(coal_id) for coal_id in coal_ids]
    if not normalized_ids:
        return 0

    coals = Coal.query.filter(Coal.id.in_(normalized_ids)).all()
    for coal in coals:
        db.session.delete(coal)
    db.session.commit()
    return len(coals)


def import_dataframe(
    df: pd.DataFrame,
    *,
    preserve_ids: bool = False,
    update_existing: bool = True,
) -> ImportSummary:
    """将上传/种子 DataFrame 导入 SQLite。"""
    created_count = 0
    updated_count = 0
    skipped_count = 0
    errors: list[str] = []

    for display_index, (_, row) in enumerate(df.iterrows(), start=1):
        try:
            data = dataframe_row_to_payload(row)
            if not data.get("name"):
                skipped_count += 1
                errors.append(f"第{display_index}行: 煤种名称为空")
                continue

            existing = Coal.query.filter_by(name=data["name"]).first()
            if existing and not update_existing:
                skipped_count += 1
                continue

            if existing:
                for field, value in data.items():
                    if field != "id":
                        setattr(existing, field, value)
                updated_count += 1
                continue

            if not preserve_ids:
                data.pop("id", None)
            elif data.get("id") is None:
                data.pop("id", None)

            db.session.add(Coal(**data))
            created_count += 1
        except Exception as exc:
            skipped_count += 1
            errors.append(f"第{display_index}行: {exc}")

    db.session.commit()
    return ImportSummary(
        created_count=created_count,
        updated_count=updated_count,
        skipped_count=skipped_count,
        errors=tuple(errors),
    )


def dataframe_row_to_payload(row: pd.Series) -> dict:
    """将 CSV/Excel 行转换为 ORM 字段。"""
    raw = {
        key: _read_alias(row, aliases)
        for key, aliases in CSV_COLUMN_ALIASES.items()
    }

    data = normalize_coal_payload(raw)
    data["id"] = _optional_int(raw.get("id"))
    return data


def normalize_coal_payload(data: dict) -> dict:
    """将 API 入参归一化为 Coal ORM 字段。"""
    valid, errors = validate_coal_data(data)
    if not valid:
        raise ValueError("; ".join(errors))
    normalized = {
        "name": _clean_string(data.get("name")),
        "type": _clean_string(data.get("type")),
        "supplier": _clean_string(data.get("supplier")),
        "price": _required_float(data.get("price"), "价格"),
        "calorific_value": _required_float(data.get("calorific_value"), "热值"),
        "ash_content": _required_float(data.get("ash_content"), "灰分"),
        "volatile_matter": _required_float(data.get("volatile_matter"), "挥发分"),
        "fixed_carbon": _required_float(data.get("fixed_carbon"), "固定碳"),
        "total_sulfur": _required_float(data.get("total_sulfur"), "全硫"),
    }

    optional_values = {
        "total_moisture": data.get("total_moisture", data.get("moisture")),
        "air_dry_moisture": data.get("air_dry_moisture", data.get("mad")),
        "hgi": data.get("hgi"),
        "burnout_rate": data.get("burnout_rate"),
        "carbon_content": data.get("carbon_content"),
        "hydrogen_content": data.get("hydrogen_content"),
        "nitrogen_content": data.get("nitrogen_content"),
    }
    for field, value in optional_values.items():
        normalized[field] = _optional_float(value)

    if not normalized["name"]:
        raise ValueError("煤种名称不能为空")
    if not normalized["type"]:
        raise ValueError("煤种类型不能为空")

    return normalized


def coal_to_api_dict(coal: Coal) -> dict:
    """将 Coal ORM 对象转换为前端 API 字典。"""
    payload = coal.to_dict()
    payload["moisture"] = coal.total_moisture
    payload["mad"] = coal.air_dry_moisture
    return payload


def coal_to_algorithm_dict(coal: Coal) -> dict:
    """将 Coal ORM 对象转换为混煤算法输入。"""
    return {
        "name": coal.name,
        "price": float(coal.price),
        "calorific_value": float(coal.calorific_value),
        "ash_content": float(coal.ash_content),
        "volatile_matter": float(coal.volatile_matter),
        "fixed_carbon": float(coal.fixed_carbon),
        "total_sulfur": float(coal.total_sulfur),
    }


def coals_to_export_dataframe(coals: Iterable[Coal]) -> pd.DataFrame:
    """将煤种列表转换为 Excel 导出 DataFrame。"""
    rows = []
    for coal in coals:
        rows.append(
            {
                "序号": coal.id,
                "煤种名称": coal.name,
                "煤种类型": coal.type,
                "供应商/产地": coal.supplier or "",
                "价格(元/吨)": coal.price,
                "热值(kcal/kg)": coal.calorific_value,
                "灰分(%)": coal.ash_content,
                "挥发分(%)": coal.volatile_matter,
                "固定碳(%)": coal.fixed_carbon,
                "全硫(%)": coal.total_sulfur,
                "全水分(%)": coal.total_moisture,
                "空干基水分(%)": coal.air_dry_moisture,
                "可磨性HGI": coal.hgi,
                "燃尽率(%)": coal.burnout_rate,
                "含碳量C(%)": coal.carbon_content,
                "含氢量H(%)": coal.hydrogen_content,
                "含氮量N(%)": coal.nitrogen_content,
            }
        )
    return pd.DataFrame(rows)


def _read_alias(row: pd.Series, aliases: tuple[str, ...]):
    for alias in aliases:
        if alias in row:
            return row.get(alias)
    return None


def _clean_string(value) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _required_float(value, label: str) -> float:
    parsed = _optional_float(value)
    if parsed is None:
        raise ValueError(f"{label}不能为空")
    return parsed


def _optional_float(value) -> float | None:
    if value is None or pd.isna(value) or str(value).strip() == "":
        return None
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("数值必须为有限值")
    return parsed


def _optional_int(value) -> int | None:
    if value is None or pd.isna(value) or str(value).strip() == "":
        return None
    return int(float(value))
