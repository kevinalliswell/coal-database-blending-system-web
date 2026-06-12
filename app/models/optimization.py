#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""优化历史模型。"""

import json

from app.extensions import db


class OptimizationHistory(db.Model):
    """优化结果历史表，对应历史项目中的 `optimization_history`。"""

    __tablename__ = "optimization_history"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.String(20), nullable=False, index=True)
    coal_names = db.Column(db.Text, nullable=False)
    optimal_ratios = db.Column(db.Text, nullable=False)
    constraints = db.Column(db.Text, nullable=False)
    total_price = db.Column(db.Float)
    total_heat = db.Column(db.Float)
    total_ash = db.Column(db.Float)
    total_volatile = db.Column(db.Float)
    total_fixed_carbon = db.Column(db.Float)
    total_sulfur = db.Column(db.Float)
    performance_price_ratio = db.Column(db.Float)
    iterations = db.Column(db.Integer)
    time_taken = db.Column(db.Float)
    fitness_value = db.Column(db.Float)
    constraints_satisfied = db.Column(db.Boolean)
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
            parsed = json.loads(raw_value)
            return fallback if parsed is None else parsed
        except (TypeError, ValueError):
            return fallback

    def to_summary_dict(self) -> dict:
        coal_names = self._loads_json(self.coal_names, [])
        optimal_ratios = self._loads_json(self.optimal_ratios, [])
        ratio_items = []

        for index, coal_name in enumerate(coal_names):
            ratio_value = optimal_ratios[index] if index < len(optimal_ratios) else 0
            ratio_items.append(
                {
                    "coal_name": coal_name,
                    "ratio": ratio_value,
                    "ratio_percent": ratio_value * 100,
                }
            )

        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "date": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else self.timestamp,
            "coal_names": coal_names,
            "optimal_ratios": optimal_ratios,
            "ratio_items": ratio_items,
            "total_price": self.total_price,
            "total_heat": self.total_heat,
            "total_ash": self.total_ash,
            "total_volatile": self.total_volatile,
            "total_fixed_carbon": self.total_fixed_carbon,
            "total_sulfur": self.total_sulfur,
            "performance_price_ratio": self.performance_price_ratio,
            "iterations": self.iterations,
            "time_taken": self.time_taken,
            "fitness_value": self.fitness_value,
            "constraints_satisfied": bool(self.constraints_satisfied),
        }

    def to_detail_dict(self) -> dict:
        return {
            **self.to_summary_dict(),
            "constraints": self._loads_json(self.constraints, {}),
            "request_payload": self._loads_json(self.request_payload, {}),
            "result_payload": self._loads_json(self.result_payload, {}),
        }
