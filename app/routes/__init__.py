#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""统一注册页面蓝图和 API 蓝图。"""

from app.routes.coal_management import coal_bp
from app.routes.errors import register_error_handlers
from app.routes.optimization import optimization_bp
from app.routes.pages import page_bp
from app.routes.replacement_ratio import replacement_ratio_bp
from app.routes.reports import reports_bp


def register_blueprints(app) -> None:
    """注册所有业务蓝图。"""
    from app.routes.catalog import catalog_bp
    app.register_blueprint(catalog_bp, url_prefix="/api")
    app.register_blueprint(page_bp)
    app.register_blueprint(coal_bp, url_prefix="/api")
    app.register_blueprint(optimization_bp, url_prefix="/api")
    app.register_blueprint(replacement_ratio_bp, url_prefix="/api")
    app.register_blueprint(reports_bp, url_prefix="/api")


__all__ = ["register_blueprints", "register_error_handlers"]
