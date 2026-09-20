#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""煤种数据模型。"""

from app.extensions import db


class Coal(db.Model):
    """煤种基础信息表，对应历史项目中的 `coal_data`。"""

    __tablename__ = "coal_data"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True, index=True)
    type = db.Column(db.String(50), nullable=False, index=True)
    # Legacy assay columns are retained for lossless migration; new records live
    # in AssayRevision. A catalog master does not require a completed assay.
    price = db.Column(db.Float)
    calorific_value = db.Column(db.Float)
    ash_content = db.Column(db.Float)
    volatile_matter = db.Column(db.Float)
    fixed_carbon = db.Column(db.Float)
    total_sulfur = db.Column(db.Float)
    archived = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    analysis_basis = db.Column(db.String(16), nullable=False, default="unknown", server_default="unknown")
    calorific_basis = db.Column(db.String(16), nullable=False, default="unknown", server_default="unknown")
    calorific_type = db.Column(db.String(16), nullable=False, default="unknown", server_default="unknown")
    price_basis = db.Column(db.String(16), nullable=False, default="unknown", server_default="unknown")
    total_moisture = db.Column(db.Float)
    air_dry_moisture = db.Column(db.Float)
    supplier = db.Column(db.String(100))
    hgi = db.Column(db.Float)
    burnout_rate = db.Column(db.Float)
    carbon_content = db.Column(db.Float)
    hydrogen_content = db.Column(db.Float)
    nitrogen_content = db.Column(db.Float)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.current_timestamp(),
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
    )

    def to_dict(self) -> dict:
        """将 ORM 对象转换为接口可用字典。"""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "archived": self.archived,
            "price": self.price,
            "calorific_value": self.calorific_value,
            "ash_content": self.ash_content,
            "volatile_matter": self.volatile_matter,
            "fixed_carbon": self.fixed_carbon,
            "total_sulfur": self.total_sulfur,
            "analysis_basis": self.analysis_basis or "unknown",
            "calorific_basis": self.calorific_basis or "unknown",
            "calorific_type": self.calorific_type or "unknown",
            "price_basis": self.price_basis or "unknown",
            "total_moisture": self.total_moisture,
            "air_dry_moisture": self.air_dry_moisture,
            "moisture": self.total_moisture,
            "mad": self.air_dry_moisture,
            "supplier": self.supplier,
            "hgi": self.hgi,
            "burnout_rate": self.burnout_rate,
            "carbon_content": self.carbon_content,
            "hydrogen_content": self.hydrogen_content,
            "nitrogen_content": self.nitrogen_content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
