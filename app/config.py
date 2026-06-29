#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Flask 应用配置模块。"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()

BASE_DIR_PATH = Path(__file__).resolve().parent.parent
BASE_DIR = BASE_DIR_PATH
DATA_PATH = BASE_DIR_PATH / "data"
DEFAULT_DB_PATH = DATA_PATH / "coal_system.db"


def _build_default_database_uri() -> str:
    """生成默认的 SQLite 数据库连接串。"""
    return f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"


class Config:
    """项目基础配置。"""

    APP_NAME = "coal-database-blending-system-web"
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")

    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "5000"))

    DATA_STORAGE_MODE = os.getenv("DATA_STORAGE_MODE", "sqlite").lower()

    BASE_DIR = str(BASE_DIR_PATH)
    DATA_DIR = str(DATA_PATH)
    UPLOAD_FOLDER = str(DATA_PATH / "uploads")
    COAL_DATA_PATH = str(DATA_PATH / "test_coal_datas.csv")
    DATABASE_PATH = str(DEFAULT_DB_PATH)
    STATIC_IMAGES_DIR = str(BASE_DIR_PATH / "static" / "images")

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    ALLOWED_EXTENSIONS = {"csv", "xlsx", "xls"}

    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", _build_default_database_uri())
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JSON_SORT_KEYS = False
    LOG_LEVEL = logging.INFO

    @classmethod
    def init_app(cls, app) -> None:
        """初始化应用级目录和日志。"""
        for path in (cls.DATA_DIR, cls.UPLOAD_FOLDER, cls.STATIC_IMAGES_DIR):
            os.makedirs(path, exist_ok=True)

        logging.basicConfig(level=cls.LOG_LEVEL)
        app.logger.setLevel(cls.LOG_LEVEL)
        app.logger.info("应用初始化完成，数据模式: %s", cls.DATA_STORAGE_MODE)

    @classmethod
    def is_database_mode(cls) -> bool:
        """判断当前是否启用数据库模式。"""
        return cls.DATA_STORAGE_MODE in {"database", "sqlite"}


class DevelopmentConfig(Config):
    """开发环境配置。"""

    DEBUG = True


class ProductionConfig(Config):
    """生产环境配置。"""

    DEBUG = False


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


def get_config(config_name: str | None = None):
    """根据名称返回配置类。"""
    resolved_name = config_name or os.getenv("FLASK_CONFIG", "default")
    return config.get(resolved_name, config["default"])
