# -*- coding: utf-8 -*-

"""历史路由注册模块。"""

from .coal_management import coal_bp
from .optimization import optimization_bp
from .replacement_ratio import replacement_ratio_bp
from .reports import reports_bp


def register_blueprints(app):
    """注册所有蓝图到 Flask 应用。"""
    app.register_blueprint(coal_bp, url_prefix="/api")
    app.register_blueprint(optimization_bp, url_prefix="/api")
    app.register_blueprint(replacement_ratio_bp, url_prefix="/api")
    app.register_blueprint(reports_bp, url_prefix="/api")
