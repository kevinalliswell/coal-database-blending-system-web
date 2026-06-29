#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Flask 应用工厂入口。"""

from __future__ import annotations

from flask import Flask

from app.__version__ import __version__  # noqa: F401
from app.config import BASE_DIR, get_config
from app.extensions import cors, db, migrate


def create_app(config_name: str | None = None) -> Flask:
    """创建并初始化 Flask 应用实例。"""
    config_class = get_config(config_name)

    app = Flask(
        __name__,
        static_folder=str(BASE_DIR / "static"),
        template_folder=str(BASE_DIR / "templates"),
    )
    app.config.from_object(config_class)
    config_class.init_app(app)

    # 统一关闭中文 JSON 的 ASCII 转义，便于接口直接返回中文。
    app.json.ensure_ascii = False

    _init_extensions(app)

    # 导入模型以便 Flask-Migrate 能够发现元数据。
    from app import models  # noqa: F401
    from app.routes import register_blueprints, register_error_handlers

    register_blueprints(app)
    register_error_handlers(app)

    return app


def _init_extensions(app: Flask) -> None:
    """初始化所有扩展。"""
    db.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})
