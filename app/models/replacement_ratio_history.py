#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""置换比历史模型。"""

import json

from app.extensions import db


class ReplacementRatioHistory(db.Model):
    """置换比结果历史表。"""

    __tablename__ = "replacement_ratio_history"

    id = db.Column(db.Integer, primary_key=True)
    calculation_type = db.Column(db.String(20), nullable=False)
    calculation_mode = db.Column(db.String(20), nullable=False)
    ratio_value = db.Column(db.Float, nullable=False)
    parameter_summary = db.Column(db.Text, nullable=False)
    request_payload = db.Column(db.Text)
    result_payload = db.Column(db.Text)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.current_timestamp(),
    )

    @staticmethod
    def _loads_json(raw_value, fallback):
        if not raw_value:
            return fallback

        try:
            return json.loads(raw_value)
        except (TypeError, ValueError):
            return fallback

    def to_summary_dict(self) -> dict:
        return {
            "id": self.id,
            "date": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "calculation_type": self.calculation_type,
            "calculation_mode": self.calculation_mode,
            "ratio_value": self.ratio_value,
            "parameter_summary": self.parameter_summary,
        }

    def to_detail_dict(self) -> dict:
        return {
            **self.to_summary_dict(),
            "request_payload": self._loads_json(self.request_payload, {}),
            "result_payload": self._loads_json(self.result_payload, {}),
        }
