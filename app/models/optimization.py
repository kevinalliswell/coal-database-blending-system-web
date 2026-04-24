#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""优化历史模型。"""

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
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.current_timestamp(),
    )
